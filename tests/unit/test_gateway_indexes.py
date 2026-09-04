"""Tests for index metadata, usage, and policy-gated mutations."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from mongrove.domain.session import SessionPolicy
from mongrove.services.mongo_gateway import MongoGatewayError, PyMongoGateway


class _Cursor:
    def __init__(self, documents: list[dict[str, Any]]) -> None:
        self.documents = documents

    def __iter__(self):
        return iter(self.documents)

    def close(self) -> None:
        return None


class _Collection:
    def __init__(self) -> None:
        self.write_concern = SimpleNamespace(acknowledged=True)
        self.created: list[tuple[list[tuple[str, Any]], dict[str, Any]]] = []
        self.dropped: list[str] = []

    def list_indexes(self):
        return iter(
            [
                {"name": "_id_", "key": {"_id": 1}, "unique": True},
                {"name": "status_1", "key": {"status": 1}, "sparse": True},
            ]
        )

    def aggregate(self, pipeline, **kwargs):
        assert pipeline == [{"$indexStats": {}}]
        return _Cursor(
            [
                {"name": "_id_", "accesses": {"ops": 8, "since": "2026-01-01"}},
                {"name": "status_1", "accesses": {"ops": 2, "since": "2026-01-01"}},
            ]
        )

    def create_index(self, keys, **options):
        self.created.append((keys, options))
        return options.get("name", "generated")

    def drop_index(self, name: str) -> None:
        self.dropped.append(name)


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


def test_gateway_maps_index_metadata_usage_and_ordered_mutations() -> None:
    collection = _Collection()
    gateway = PyMongoGateway()
    gateway._client = _Client(collection)  # type: ignore[assignment]

    indexes = gateway.list_indexes("app", "customers")
    usage = gateway.index_usage("app", "customers")
    created = gateway.create_index(
        "app",
        "customers",
        [("status", 1), ("createdAt", -1)],
        {"name": "status_created", "unique": True},
        policy=SessionPolicy(),
    )
    gateway.drop_index("app", "customers", "status_created", policy=SessionPolicy())

    assert [index.name for index in indexes] == ["_id_", "status_1"]
    assert indexes[1].sparse is True
    assert usage.available is True
    assert usage.usages[0].operations == 8
    assert created == "status_created"
    assert collection.created == [
        ([("status", 1), ("createdAt", -1)], {"name": "status_created", "unique": True})
    ]
    assert collection.dropped == ["status_created"]


def test_gateway_blocks_index_mutations_when_session_is_read_only() -> None:
    collection = _Collection()
    gateway = PyMongoGateway()
    gateway._client = _Client(collection)  # type: ignore[assignment]

    with pytest.raises(MongoGatewayError, match="read-only"):
        gateway.create_index(
            "app",
            "customers",
            [("status", 1)],
            {},
            policy=SessionPolicy(requested_read_only=True),
        )
    assert collection.created == []
