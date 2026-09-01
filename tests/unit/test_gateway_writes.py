"""Tests for policy-gated acknowledged document writes."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from bson import ObjectId

from mongrove.domain.query import FindQuery
from mongrove.domain.pipeline import parse_pipeline
from mongrove.domain.session import SessionPolicy
from mongrove.services.mongo_gateway import MongoGatewayError, PyMongoGateway


class _Collection:
    def __init__(self, *, acknowledged: bool = True) -> None:
        self.write_concern = SimpleNamespace(acknowledged=acknowledged)
        self.calls: list[Any] = []
        self.documents: list[dict[str, Any]] = []
        self.last_cursor: _Cursor | None = None

    def find(self, filter_document: dict[str, Any], **kwargs: Any) -> "_Cursor":
        self.calls.append(("find", filter_document, kwargs))
        self.last_cursor = _Cursor(self.documents)
        return self.last_cursor

    def aggregate(self, pipeline: list[dict[str, Any]], **kwargs: Any) -> "_Cursor":
        self.calls.append(("aggregate", pipeline, kwargs))
        self.last_cursor = _Cursor(self.documents)
        return self.last_cursor

    def insert_one(self, document: dict[str, Any]) -> SimpleNamespace:
        self.calls.append(("insert", document))
        return SimpleNamespace(inserted_id=document.get("_id", "generated"))

    def replace_one(
        self,
        selector: dict[str, Any],
        replacement: dict[str, Any],
        *,
        upsert: bool,
    ) -> SimpleNamespace:
        self.calls.append(("replace", selector, replacement, upsert))
        return SimpleNamespace(matched_count=1, modified_count=1)

    def delete_one(self, selector: dict[str, Any]) -> SimpleNamespace:
        self.calls.append(("delete", selector))
        return SimpleNamespace(deleted_count=1)


class _Cursor:
    def __init__(self, documents: list[dict[str, Any]]) -> None:
        self.documents = documents
        self.sort_fields: list[tuple[str, int]] | None = None
        self.batch_size_value: int | None = None
        self.closed = False

    def sort(self, fields: list[tuple[str, int]]) -> "_Cursor":
        self.sort_fields = fields
        return self

    def batch_size(self, value: int) -> "_Cursor":
        self.batch_size_value = value
        return self

    def __iter__(self):
        return iter(self.documents)

    def close(self) -> None:
        self.closed = True


class _Database:
    def __init__(self, collection: _Collection) -> None:
        self.collection = collection

    def __getitem__(self, name: str) -> _Collection:
        assert name == "customers"
        return self.collection


class _Client:
    def __init__(self, collection: _Collection) -> None:
        self.database = _Database(collection)

    def __getitem__(self, name: str) -> _Database:
        assert name == "app"
        return self.database


def test_gateway_dispatches_single_document_writes_with_immutable_selectors() -> None:
    collection = _Collection()
    gateway = PyMongoGateway()
    gateway._client = _Client(collection)  # type: ignore[assignment]
    identifier = ObjectId("65ba0aa00000000000000001")
    policy = SessionPolicy()

    inserted = gateway.insert_document("app", "customers", {"name": "Iris"}, policy=policy)
    replaced = gateway.replace_document(
        "app",
        "customers",
        identifier,
        {"_id": identifier, "name": "Iris Updated"},
        policy=policy,
    )
    deleted = gateway.delete_document("app", "customers", identifier, policy=policy)

    assert inserted.inserted_id == "generated"
    assert replaced.matched_count == 1
    assert replaced.modified_count == 1
    assert deleted.deleted_count == 1
    assert collection.calls == [
        ("insert", {"name": "Iris"}),
        ("replace", {"_id": identifier}, {"_id": identifier, "name": "Iris Updated"}, False),
        ("delete", {"_id": identifier}),
    ]


def test_gateway_rejects_blocked_and_unacknowledged_writes() -> None:
    gateway = PyMongoGateway()
    gateway._client = _Client(_Collection())  # type: ignore[assignment]

    with pytest.raises(MongoGatewayError, match="read-only"):
        gateway.insert_document(
            "app",
            "customers",
            {"name": "Iris"},
            policy=SessionPolicy(requested_read_only=True),
        )

    gateway._client = _Client(_Collection(acknowledged=False))  # type: ignore[assignment]
    with pytest.raises(MongoGatewayError, match="acknowledged writes"):
        gateway.delete_document("app", "customers", "id", policy=SessionPolicy())


def test_gateway_streams_the_full_find_query_and_closes_its_cursor() -> None:
    collection = _Collection()
    collection.documents = [{"name": "Alice"}, {"name": "Robert"}]
    gateway = PyMongoGateway()
    gateway._client = _Client(collection)  # type: ignore[assignment]
    query = FindQuery(
        filter={"status": "active"},
        projection={"name": 1},
        sort=[("name", 1)],
        collation={"locale": "en"},
        skip=4,
        limit=20,
        max_time_ms=7_000,
    )
    consumed: list[dict[str, Any]] = []

    result = gateway.stream_documents(
        "app",
        "customers",
        query,
        consume=consumed.append,
        is_cancelled=lambda: False,
        batch_size=50,
    )

    assert result.documents_seen == 2
    assert result.cancelled is False
    assert consumed == collection.documents
    assert collection.calls[0][0:2] == ("find", {"status": "active"})
    assert collection.calls[0][2]["skip"] == 4
    assert collection.calls[0][2]["limit"] == 20
    assert collection.calls[0][2]["max_time_ms"] == 7_000
    assert collection.calls[0][2]["projection"] == {"name": 1}
    assert collection.last_cursor is not None
    assert collection.last_cursor.sort_fields == [("name", 1)]
    assert collection.last_cursor.batch_size_value == 50
    assert collection.last_cursor.closed is True


def test_gateway_aggregation_appends_only_a_bounded_preview_limit() -> None:
    collection = _Collection()
    collection.documents = [{"name": "Alice"}, {"name": "Robert"}]
    gateway = PyMongoGateway()
    gateway._client = _Client(collection)  # type: ignore[assignment]
    pipeline = parse_pipeline('[{"$match":{"status":"active"}}]')

    page = gateway.aggregate_documents("app", "customers", pipeline, page_size=1, max_time_ms=8_000)

    assert page.documents == [{"name": "Alice"}]
    assert page.has_more is True
    assert collection.calls[0][0] == "aggregate"
    assert collection.calls[0][1] == [
        {"$match": {"status": "active"}},
        {"$limit": 2},
    ]
    assert collection.calls[0][2] == {"maxTimeMS": 8_000, "batchSize": 2}
    assert collection.last_cursor is not None
    assert collection.last_cursor.closed is True
