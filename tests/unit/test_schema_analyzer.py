"""Tests for bounded BSON-aware schema inference."""

from __future__ import annotations

from bson import ObjectId
from bson.int64 import Int64

from mongrove.services.schema_analyzer import analyze_schema


def test_schema_analysis_reports_presence_nulls_types_and_bounded_cardinality() -> None:
    documents = [
        {
            "_id": ObjectId("65ba0aa00000000000000001"),
            "name": "Alice",
            "age": Int64(34),
            "profile": {"city": "London"},
            "tags": ["paid", "beta"],
            "optional": None,
        },
        {
            "_id": ObjectId("65ba0aa00000000000000002"),
            "name": "Robert",
            "age": 28,
            "profile": {"city": "Paris"},
            "tags": ["paid"],
        },
    ]

    report = analyze_schema(documents, max_distinct_values=1)
    fields = {field.path: field for field in report.fields}

    assert report.sampled_count == 2
    assert fields["name"].present_count == 2
    assert fields["name"].distinct_count == 1
    assert fields["name"].distinct_capped is True
    assert dict(fields["age"].type_counts) == {"int": 1, "int64": 1}
    assert fields["optional"].present_count == 1
    assert fields["optional"].null_count == 1
    assert fields["profile.city"].present_count == 2
    assert dict(fields["tags"].type_counts) == {"array": 2}
    assert dict(fields["tags[]"].type_counts) == {"string": 2}


def test_schema_analysis_truncates_large_examples_without_losing_cardinality_signal() -> None:
    report = analyze_schema([{"payload": "x" * 5_000}, {"payload": "y" * 5_000}])
    payload = {field.path: field for field in report.fields}["payload"]

    assert payload.distinct_count == 2
    assert all(len(example) <= 1_000 for example in payload.examples)
