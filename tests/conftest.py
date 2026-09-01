"""Shared fake services for Mongrove tests."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from bson import ObjectId

from mongrove.domain.connection import ConnectionInfo
from mongrove.domain.namespace import CollectionInfo
from mongrove.domain.query import FindQuery
from mongrove.domain.session import SessionPolicy
from mongrove.services.mongo_gateway import (
    DeleteDocumentResult,
    DocumentsPage,
    FindStreamResult,
    InsertDocumentResult,
    MongoGatewayError,
    ReplaceDocumentResult,
)


class FakeGateway:
    """In-memory MongoDB gateway used by UI tests."""

    def __init__(self) -> None:
        self.connected_uri: str | None = None
        self.disconnect_calls = 0
        self.queries: list[tuple[str, str, FindQuery, int, int]] = []
        self.insert_calls: list[tuple[str, str, dict[str, Any]]] = []
        self.replace_calls: list[tuple[str, str, Any, dict[str, Any]]] = []
        self.delete_calls: list[tuple[str, str, Any]] = []
        self.stream_calls: list[tuple[str, str, FindQuery]] = []
        self.documents: list[dict[str, Any]] = [
            {
                "_id": ObjectId("65ba0aa00000000000000001"),
                "name": "Alice",
                "status": "active",
                "profile": {"age": 34, "city": "London"},
            },
            {
                "_id": ObjectId("65ba0aa00000000000000002"),
                "name": "Robert",
                "status": "active",
                "profile": {"age": 28, "city": "Paris"},
            },
        ]

    def connect(self, uri: str, *, timeout_ms: int = 10_000) -> ConnectionInfo:
        self.connected_uri = uri
        return ConnectionInfo(
            display_uri="mongodb://localhost:27017",
            server_version="8.0.3",
            topology="Standalone",
            is_writable_primary=True,
        )

    def disconnect(self) -> None:
        self.disconnect_calls += 1
        self.connected_uri = None

    def list_databases(self) -> list[str]:
        return ["admin", "app"]

    def list_collections(self, database: str) -> list[CollectionInfo]:
        if database == "app":
            return [CollectionInfo(database="app", name="customers")]
        return []

    def fetch_documents(
        self,
        database: str,
        collection: str,
        query: FindQuery,
        *,
        page: int,
        page_size: int,
    ) -> DocumentsPage:
        self.queries.append((database, collection, query, page, page_size))
        skip, fetch_size = query.page_request(page, page_size)
        result = self.documents[skip : skip + fetch_size]
        has_more = len(result) > page_size
        return DocumentsPage(
            documents=result[:page_size],
            has_more=has_more,
            elapsed_ms=4,
            skip=skip,
        )

    def insert_document(
        self,
        database: str,
        collection: str,
        document: dict[str, Any],
        *,
        policy: SessionPolicy,
    ) -> InsertDocumentResult:
        self._assert_writes_allowed(policy)
        stored = deepcopy(document)
        stored.setdefault("_id", ObjectId())
        self.documents.append(stored)
        self.insert_calls.append((database, collection, deepcopy(document)))
        return InsertDocumentResult(inserted_id=stored["_id"])

    def replace_document(
        self,
        database: str,
        collection: str,
        original_id: Any,
        replacement: dict[str, Any],
        *,
        policy: SessionPolicy,
    ) -> ReplaceDocumentResult:
        self._assert_writes_allowed(policy)
        self.replace_calls.append((database, collection, original_id, deepcopy(replacement)))
        for index, document in enumerate(self.documents):
            if document.get("_id") == original_id:
                modified = int(document != replacement)
                self.documents[index] = deepcopy(replacement)
                return ReplaceDocumentResult(matched_count=1, modified_count=modified)
        return ReplaceDocumentResult(matched_count=0, modified_count=0)

    def delete_document(
        self,
        database: str,
        collection: str,
        original_id: Any,
        *,
        policy: SessionPolicy,
    ) -> DeleteDocumentResult:
        self._assert_writes_allowed(policy)
        self.delete_calls.append((database, collection, original_id))
        for index, document in enumerate(self.documents):
            if document.get("_id") == original_id:
                del self.documents[index]
                return DeleteDocumentResult(deleted_count=1)
        return DeleteDocumentResult(deleted_count=0)

    def stream_documents(
        self,
        database: str,
        collection: str,
        query: FindQuery,
        *,
        consume,
        is_cancelled,
        batch_size: int = 100,
    ) -> FindStreamResult:
        self.stream_calls.append((database, collection, query))
        documents_seen = 0
        documents = self.documents[query.skip :]
        if query.limit is not None:
            documents = documents[: query.limit]
        for document in documents:
            if is_cancelled():
                return FindStreamResult(documents_seen=documents_seen, cancelled=True)
            consume(deepcopy(document))
            documents_seen += 1
        return FindStreamResult(documents_seen=documents_seen, cancelled=is_cancelled())

    @staticmethod
    def _assert_writes_allowed(policy: SessionPolicy) -> None:
        if policy.write_block_reason is not None:
            raise MongoGatewayError(policy.write_block_reason)
