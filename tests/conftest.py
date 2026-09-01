"""Shared fake services for Mongrove tests."""

from __future__ import annotations

from typing import Any

from bson import ObjectId

from mongrove.domain.connection import ConnectionInfo
from mongrove.domain.namespace import CollectionInfo
from mongrove.domain.query import FindQuery
from mongrove.services.mongo_gateway import DocumentsPage


class FakeGateway:
    """In-memory MongoDB gateway used by UI tests."""

    def __init__(self) -> None:
        self.connected_uri: str | None = None
        self.disconnect_calls = 0
        self.queries: list[tuple[str, str, FindQuery, int, int]] = []
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
