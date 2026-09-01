"""Thread-safe boundary between the Textual UI and PyMongo."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from time import perf_counter
from typing import Any, Protocol

from bson.errors import BSONError
from pymongo import MongoClient
from pymongo.collation import Collation
from pymongo.errors import PyMongoError

from mongrove.domain.connection import ConnectionInfo
from mongrove.domain.namespace import CollectionInfo
from mongrove.domain.query import FindQuery
from mongrove.domain.session import SessionPolicy


class MongoGatewayError(RuntimeError):
    """A safe, user-facing wrapper for driver errors."""


@dataclass(frozen=True, slots=True)
class DocumentsPage:
    """A bounded page of documents and the metadata needed by the UI."""

    documents: list[dict[str, Any]]
    has_more: bool
    elapsed_ms: int
    skip: int


@dataclass(frozen=True, slots=True)
class InsertDocumentResult:
    """Acknowledged result of inserting one document."""

    inserted_id: Any


@dataclass(frozen=True, slots=True)
class ReplaceDocumentResult:
    """Acknowledged result of replacing one selected document."""

    matched_count: int
    modified_count: int


@dataclass(frozen=True, slots=True)
class DeleteDocumentResult:
    """Acknowledged result of deleting one selected document."""

    deleted_count: int


@dataclass(frozen=True, slots=True)
class FindStreamResult:
    """Result metadata for a cursor consumed incrementally by a local sink."""

    documents_seen: int
    cancelled: bool


class MongoGateway(Protocol):
    """The synchronous API invoked from Textual worker threads."""

    def connect(self, uri: str, *, timeout_ms: int = 10_000) -> ConnectionInfo:
        """Connect and return basic deployment facts."""
        ...

    def disconnect(self) -> None:
        """Close the active client if one exists."""
        ...

    def list_databases(self) -> list[str]:
        """List databases accessible to the active client."""
        ...

    def list_collections(self, database: str) -> list[CollectionInfo]:
        """List collections and views within one database."""
        ...

    def fetch_documents(
        self,
        database: str,
        collection: str,
        query: FindQuery,
        *,
        page: int,
        page_size: int,
    ) -> DocumentsPage:
        """Fetch one bounded page of documents."""
        ...

    def insert_document(
        self,
        database: str,
        collection: str,
        document: dict[str, Any],
        *,
        policy: SessionPolicy,
    ) -> InsertDocumentResult:
        """Insert one document under the supplied session write policy."""
        ...

    def replace_document(
        self,
        database: str,
        collection: str,
        original_id: Any,
        replacement: dict[str, Any],
        *,
        policy: SessionPolicy,
    ) -> ReplaceDocumentResult:
        """Replace one document selected by its immutable _id."""
        ...

    def delete_document(
        self,
        database: str,
        collection: str,
        original_id: Any,
        *,
        policy: SessionPolicy,
    ) -> DeleteDocumentResult:
        """Delete one document selected by its immutable _id."""
        ...

    def stream_documents(
        self,
        database: str,
        collection: str,
        query: FindQuery,
        *,
        consume: Callable[[dict[str, Any]], None],
        is_cancelled: Callable[[], bool],
        batch_size: int = 100,
    ) -> FindStreamResult:
        """Stream every document matching a find query without materializing it."""
        ...


class PyMongoGateway:
    """PyMongo implementation used by the production application.

    All public methods are synchronous by design. Textual invokes them from
    workers, keeping the terminal interface responsive while preserving the
    familiar PyMongo client API.
    """

    def __init__(self) -> None:
        self._client: MongoClient[dict[str, Any]] | None = None

    def connect(self, uri: str, *, timeout_ms: int = 10_000) -> ConnectionInfo:
        candidate: MongoClient[dict[str, Any]] | None = None
        try:
            candidate = MongoClient(
                uri,
                serverSelectionTimeoutMS=timeout_ms,
                connectTimeoutMS=timeout_ms,
                socketTimeoutMS=timeout_ms,
            appname="Mongrove",
            )
            candidate.admin.command("ping")
            server_info = candidate.server_info()
            hello = candidate.admin.command("hello")
        except (PyMongoError, TypeError, ValueError) as error:
            if candidate is not None:
                candidate.close()
            raise MongoGatewayError(_driver_error_message(error)) from error

        self.disconnect()
        self._client = candidate
        topology = _topology_from_hello(hello)
        return ConnectionInfo(
            display_uri=redact_connection_uri(uri),
            server_version=server_info.get("version"),
            topology=topology,
            is_writable_primary=bool(hello.get("isWritablePrimary")),
        )

    def disconnect(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    def list_databases(self) -> list[str]:
        client = self._require_client()
        try:
            return sorted(client.list_database_names(), key=str.casefold)
        except PyMongoError as error:
            raise MongoGatewayError(_driver_error_message(error)) from error

    def list_collections(self, database: str) -> list[CollectionInfo]:
        client = self._require_client()
        try:
            raw_collections = client[database].list_collections()
            collections = [
                CollectionInfo(
                    database=database,
                    name=entry["name"],
                    kind=entry.get("type", "collection"),
                )
                for entry in raw_collections
            ]
            return sorted(collections, key=lambda item: item.name.casefold())
        except PyMongoError as error:
            raise MongoGatewayError(_driver_error_message(error)) from error

    def fetch_documents(
        self,
        database: str,
        collection: str,
        query: FindQuery,
        *,
        page: int,
        page_size: int,
    ) -> DocumentsPage:
        client = self._require_client()
        cursor_skip, fetch_size = query.page_request(page, page_size)
        if fetch_size == 0:
            return DocumentsPage([], False, 0, cursor_skip)

        collection_ref = client[database][collection]
        kwargs: dict[str, Any] = {
            "skip": cursor_skip,
            "limit": fetch_size,
            "max_time_ms": query.max_time_ms,
        }
        if query.projection is not None:
            kwargs["projection"] = query.projection
        if query.collation is not None:
            kwargs["collation"] = Collation(**query.collation)

        started = perf_counter()
        try:
            cursor = collection_ref.find(query.filter, **kwargs)
            if query.sort:
                cursor = cursor.sort(query.sort)
            documents = list(cursor)
        except (PyMongoError, ValueError, TypeError) as error:
            raise MongoGatewayError(_driver_error_message(error)) from error
        elapsed_ms = max(round((perf_counter() - started) * 1_000), 0)

        has_more = len(documents) > page_size
        if has_more:
            documents = documents[:page_size]
        return DocumentsPage(documents, has_more, elapsed_ms, cursor_skip)

    def insert_document(
        self,
        database: str,
        collection: str,
        document: dict[str, Any],
        *,
        policy: SessionPolicy,
    ) -> InsertDocumentResult:
        """Insert one document with an acknowledged write concern."""

        collection_ref = self._write_collection(database, collection, policy)
        try:
            result = collection_ref.insert_one(dict(document))
        except (PyMongoError, BSONError, TypeError, ValueError) as error:
            raise MongoGatewayError(_driver_error_message(error)) from error
        return InsertDocumentResult(inserted_id=result.inserted_id)

    def replace_document(
        self,
        database: str,
        collection: str,
        original_id: Any,
        replacement: dict[str, Any],
        *,
        policy: SessionPolicy,
    ) -> ReplaceDocumentResult:
        """Replace exactly one document using its original immutable _id."""

        collection_ref = self._write_collection(database, collection, policy)
        try:
            result = collection_ref.replace_one(
                {"_id": original_id},
                dict(replacement),
                upsert=False,
            )
        except (PyMongoError, BSONError, TypeError, ValueError) as error:
            raise MongoGatewayError(_driver_error_message(error)) from error
        return ReplaceDocumentResult(
            matched_count=result.matched_count,
            modified_count=result.modified_count,
        )

    def delete_document(
        self,
        database: str,
        collection: str,
        original_id: Any,
        *,
        policy: SessionPolicy,
    ) -> DeleteDocumentResult:
        """Delete exactly one document using its original immutable _id."""

        collection_ref = self._write_collection(database, collection, policy)
        try:
            result = collection_ref.delete_one({"_id": original_id})
        except (PyMongoError, BSONError, TypeError, ValueError) as error:
            raise MongoGatewayError(_driver_error_message(error)) from error
        return DeleteDocumentResult(deleted_count=result.deleted_count)

    def stream_documents(
        self,
        database: str,
        collection: str,
        query: FindQuery,
        *,
        consume: Callable[[dict[str, Any]], None],
        is_cancelled: Callable[[], bool],
        batch_size: int = 100,
    ) -> FindStreamResult:
        """Consume a cursor incrementally while honoring the complete find query."""

        if batch_size < 1:
            raise ValueError("Stream batch size must be at least one.")
        if is_cancelled():
            return FindStreamResult(documents_seen=0, cancelled=True)

        collection_ref = self._require_client()[database][collection]
        kwargs: dict[str, Any] = {
            "skip": query.skip,
            "max_time_ms": query.max_time_ms,
        }
        if query.limit is not None:
            kwargs["limit"] = query.limit
        if query.projection is not None:
            kwargs["projection"] = query.projection
        if query.collation is not None:
            kwargs["collation"] = Collation(**query.collation)

        cursor: Any = None
        documents_seen = 0
        try:
            cursor = collection_ref.find(query.filter, **kwargs)
            if query.sort:
                cursor = cursor.sort(query.sort)
            cursor = cursor.batch_size(batch_size)
            for document in cursor:
                if is_cancelled():
                    return FindStreamResult(documents_seen=documents_seen, cancelled=True)
                consume(document)
                documents_seen += 1
        except (PyMongoError, BSONError, TypeError, ValueError) as error:
            raise MongoGatewayError(_driver_error_message(error)) from error
        finally:
            if cursor is not None:
                try:
                    cursor.close()
                except PyMongoError:
                    pass
        return FindStreamResult(documents_seen=documents_seen, cancelled=is_cancelled())

    def _require_client(self) -> MongoClient[dict[str, Any]]:
        if self._client is None:
            raise MongoGatewayError("No active MongoDB connection.")
        return self._client

    def _write_collection(
        self,
        database: str,
        collection: str,
        policy: SessionPolicy,
    ) -> Any:
        reason = policy.write_block_reason
        if reason is not None:
            raise MongoGatewayError(reason)
        collection_ref = self._require_client()[database][collection]
        if not collection_ref.write_concern.acknowledged:
            raise MongoGatewayError(
                "Mongrove requires acknowledged writes; unacknowledged w=0 writes are unsupported."
            )
        return collection_ref


_URI_CREDENTIALS = re.compile(r"(mongodb(?:\+srv)?://)([^@/]+)@", re.IGNORECASE)


def redact_connection_uri(uri: str) -> str:
    """Replace URI user information without modifying the target endpoint."""

    return _URI_CREDENTIALS.sub(r"\1***@", uri.strip(), count=1)


def remove_uri_credentials(uri: str) -> str:
    """Return a URI suitable for local profile storage without credentials."""

    return _URI_CREDENTIALS.sub(r"\1", uri.strip(), count=1)


def redact_sensitive_text(value: str) -> str:
    """Remove URI credentials when a driver error embeds a connection string."""

    return _URI_CREDENTIALS.sub(r"\1***@", value)


def _topology_from_hello(hello: dict[str, Any]) -> str:
    if hello.get("msg") == "isdbgrid":
        return "Sharded cluster"
    if hello.get("setName"):
        return "Replica set"
    return "Standalone"


def _driver_error_message(error: Exception) -> str:
    message = str(error).strip()
    if not message:
        return type(error).__name__
    return redact_sensitive_text(message)
