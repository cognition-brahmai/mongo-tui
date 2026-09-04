"""Tests for bounded MongoDB $sample command construction."""

from __future__ import annotations

from typing import Any

from mongrove.services.mongo_gateway import PyMongoGateway


class _Cursor:
    def __init__(self) -> None:
        self.closed = False

    def __iter__(self):
        return iter([{"name": "Alice"}])

    def close(self) -> None:
        self.closed = True


class _Collection:
    def __init__(self) -> None:
        self.calls: list[tuple[list[dict[str, Any]], dict[str, Any]]] = []
        self.cursor = _Cursor()

    def aggregate(self, pipeline: list[dict[str, Any]], **kwargs: Any) -> _Cursor:
        self.calls.append((pipeline, kwargs))
        return self.cursor


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


def test_gateway_samples_after_active_filter_with_bounded_size() -> None:
    collection = _Collection()
    gateway = PyMongoGateway()
    gateway._client = _Client(collection)  # type: ignore[assignment]

    sample = gateway.sample_documents(
        "app",
        "customers",
        {"status": "active"},
        sample_size=250,
        max_time_ms=8_000,
    )

    assert sample.documents == [{"name": "Alice"}]
    assert collection.calls == [
        ([{"$match": {"status": "active"}}, {"$sample": {"size": 250}}], {"maxTimeMS": 8_000, "batchSize": 250})
    ]
    assert collection.cursor.closed is True
