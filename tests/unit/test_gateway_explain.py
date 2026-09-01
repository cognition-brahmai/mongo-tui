"""Tests for explicit planner-only explain command construction."""

from __future__ import annotations

from typing import Any

import pytest

from mongrove.domain.pipeline import parse_pipeline
from mongrove.domain.query import FindQuery
from mongrove.services.mongo_gateway import MongoGatewayError, PyMongoGateway


class _Collection:
    def __init__(self) -> None:
        self.read_preference = "secondary-preferred"


class _Database:
    def __init__(self, collection: _Collection) -> None:
        self.collection = collection
        self.commands: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    def __getitem__(self, name: str) -> _Collection:
        assert name == "customers"
        return self.collection

    def command(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        self.commands.append((args, kwargs))
        return {"queryPlanner": {"winningPlan": {"stage": "IXSCAN"}, "rejectedPlans": []}}


class _Client:
    def __init__(self) -> None:
        self.database = _Database(_Collection())

    def __getitem__(self, name: str) -> _Database:
        assert name == "app"
        return self.database


def _query() -> FindQuery:
    return FindQuery(
        filter={"status": "active"},
        projection={"name": 1},
        sort=[("createdAt", -1), ("_id", 1)],
        collation={"locale": "en"},
        skip=4,
        limit=20,
        max_time_ms=9_000,
    )


def test_gateway_builds_logical_find_explain_command_without_page_limit() -> None:
    client = _Client()
    gateway = PyMongoGateway()
    gateway._client = client  # type: ignore[assignment]

    result = gateway.explain_find("app", "customers", _query(), max_time_ms=5_000)

    args, kwargs = client.database.commands[0]
    command = args[1]
    assert args[0] == "explain"
    assert command["find"] == "customers"
    assert command["filter"] == {"status": "active"}
    assert command["projection"] == {"name": 1}
    assert list(command["sort"].items()) == [("createdAt", -1), ("_id", 1)]
    assert command["collation"] == {"locale": "en"}
    assert command["skip"] == 4
    assert command["limit"] == 20
    assert command["maxTimeMS"] == 5_000
    assert kwargs["verbosity"] == "queryPlanner"
    assert kwargs["read_preference"] == "secondary-preferred"
    assert result.fragments[0].root_stage == "IXSCAN"


def test_gateway_explains_original_pipeline_and_rejects_write_stages() -> None:
    client = _Client()
    gateway = PyMongoGateway()
    gateway._client = client  # type: ignore[assignment]
    pipeline = parse_pipeline('[{"$match":{"status":"active"}}]')

    gateway.explain_aggregation("app", "customers", pipeline)
    command = client.database.commands[0][0][1]
    assert command["pipeline"] == [{"$match": {"status": "active"}}]
    assert "$limit" not in command["pipeline"][-1]
    assert command["cursor"] == {}

    with pytest.raises(MongoGatewayError, match="write stages"):
        gateway.explain_aggregation("app", "customers", parse_pipeline('[{"$out":"summary"}]'))
    assert len(client.database.commands) == 1
