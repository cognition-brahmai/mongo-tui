"""Tests for policy-gated acknowledged document writes."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from bson import ObjectId

from mongrove.domain.session import SessionPolicy
from mongrove.services.mongo_gateway import MongoGatewayError, PyMongoGateway


class _Collection:
    def __init__(self, *, acknowledged: bool = True) -> None:
        self.write_concern = SimpleNamespace(acknowledged=acknowledged)
        self.calls: list[Any] = []

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
