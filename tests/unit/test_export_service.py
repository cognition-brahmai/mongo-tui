"""Tests for atomic BSON-aware streaming exports."""

from __future__ import annotations

import csv
import json
from typing import Any

import pytest
from bson import ObjectId, json_util
from bson.int64 import Int64

from mongrove.domain.query import FindQuery
from mongrove.services.import_export import (
    ExportCancelled,
    ExportFormat,
    ExportRequest,
    export_find_query,
    parse_csv_columns,
)
from mongrove.services.mongo_gateway import FindStreamResult


class _StreamingGateway:
    def __init__(self, documents: list[dict[str, Any]]) -> None:
        self.documents = documents
        self.calls: list[tuple[str, str, FindQuery]] = []

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
        self.calls.append((database, collection, query))
        seen = 0
        documents = self.documents[query.skip :]
        if query.limit is not None:
            documents = documents[: query.limit]
        for document in documents:
            if is_cancelled():
                return FindStreamResult(documents_seen=seen, cancelled=True)
            consume(document)
            seen += 1
        return FindStreamResult(documents_seen=seen, cancelled=is_cancelled())


def _query(*, skip: int = 0, limit: int | None = None) -> FindQuery:
    return FindQuery(
        filter={"status": "active"},
        projection=None,
        sort=[("name", 1)],
        collation=None,
        skip=skip,
        limit=limit,
        max_time_ms=5_000,
    )


def test_json_and_canonical_ejson_exports_stream_the_full_query(tmp_path) -> None:
    documents = [
        {"_id": ObjectId("65ba0aa00000000000000001"), "count": Int64(7), "name": "Alice"},
        {"_id": ObjectId("65ba0aa00000000000000002"), "count": Int64(8), "name": "Robert"},
    ]
    gateway = _StreamingGateway(documents)
    json_destination = tmp_path / "customers.json"
    ejson_destination = tmp_path / "customers.ejson"

    json_result = export_find_query(
        gateway,
        "app",
        "customers",
        _query(),
        ExportRequest(json_destination, ExportFormat.JSON),
        is_cancelled=lambda: False,
    )
    ejson_result = export_find_query(
        gateway,
        "app",
        "customers",
        _query(),
        ExportRequest(ejson_destination, ExportFormat.EJSON),
        is_cancelled=lambda: False,
    )

    assert json_result.documents_written == 2
    assert ejson_result.documents_written == 2
    assert json.loads(json_destination.read_text(encoding="utf-8"))[0]["_id"]["$oid"]
    canonical = json_util.loads(ejson_destination.read_text(encoding="utf-8"))
    assert isinstance(canonical[0]["count"], Int64)
    assert gateway.calls[0] == ("app", "customers", _query())


def test_csv_uses_explicit_bson_safe_top_level_columns(tmp_path) -> None:
    gateway = _StreamingGateway(
        [{"name": "A, B", "nested": {"score": Int64(7)}, "empty": "", "null": None}]
    )
    destination = tmp_path / "customers.csv"

    result = export_find_query(
        gateway,
        "app",
        "customers",
        _query(),
        ExportRequest(
            destination,
            ExportFormat.CSV,
            csv_columns=("name", "nested", "empty", "null", "missing"),
        ),
        is_cancelled=lambda: False,
    )

    with destination.open("r", encoding="utf-8", newline="") as source:
        rows = list(csv.reader(source))
    assert result.documents_written == 1
    assert rows[0] == ["name", "nested", "empty", "null", "missing"]
    assert rows[1][0] == '"A, B"'
    assert "$numberLong" in rows[1][1]
    assert rows[1][2] == '""'
    assert rows[1][3] == "null"
    assert rows[1][4] == ""
    assert parse_csv_columns('["_id", "name"]') == ("_id", "name")


def test_cancelled_export_preserves_existing_destination_and_removes_stage(tmp_path) -> None:
    destination = tmp_path / "customers.ejson"
    destination.write_text("old export\n", encoding="utf-8")
    cancelled = {"value": False}

    class _CancellingGateway(_StreamingGateway):
        def stream_documents(self, *args, **kwargs) -> FindStreamResult:
            consume = kwargs["consume"]
            consume({"name": "staged"})
            cancelled["value"] = True
            return FindStreamResult(documents_seen=1, cancelled=True)

    gateway = _CancellingGateway([])
    with pytest.raises(ExportCancelled):
        export_find_query(
            gateway,
            "app",
            "customers",
            _query(),
            ExportRequest(destination, ExportFormat.EJSON),
            is_cancelled=lambda: cancelled["value"],
        )

    assert destination.read_text(encoding="utf-8") == "old export\n"
    assert list(tmp_path.glob("*.part")) == []
