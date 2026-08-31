"""Thread-safe boundary between the Textual UI and PyMongo."""

from __future__ import annotations

import re
from dataclasses import dataclass
from time import perf_counter
from typing import Any, Protocol

from pymongo import MongoClient
from pymongo.collation import Collation
from pymongo.errors import PyMongoError

from mongotui.domain.connection import ConnectionInfo
from mongotui.domain.namespace import CollectionInfo
from mongotui.domain.query import FindQuery


class MongoGatewayError(RuntimeError):
    """A safe, user-facing wrapper for driver errors."""


@dataclass(frozen=True, slots=True)
class DocumentsPage:
    """A bounded page of documents and the metadata needed by the UI."""

    documents: list[dict[str, Any]]
    has_more: bool
    elapsed_ms: int
    skip: int


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
                appname="MongoTUI",
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

    def _require_client(self) -> MongoClient[dict[str, Any]]:
        if self._client is None:
            raise MongoGatewayError("No active MongoDB connection.")
        return self._client


_URI_CREDENTIALS = re.compile(r"^(mongodb(?:\+srv)?://)([^@/]+)@", re.IGNORECASE)


def redact_connection_uri(uri: str) -> str:
    """Replace URI user information without modifying the target endpoint."""

    return _URI_CREDENTIALS.sub(r"\1***@", uri.strip(), count=1)


def remove_uri_credentials(uri: str) -> str:
    """Return a URI suitable for local profile storage without credentials."""

    return _URI_CREDENTIALS.sub(r"\1", uri.strip(), count=1)


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
    return message
