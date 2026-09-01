"""Tests for BSON-preserving EJSON editor helpers."""

from __future__ import annotations

import pytest
from bson import Binary, Decimal128, ObjectId
from bson.int64 import Int64

from mongrove.services.bson_codec import (
    EjsonValidationError,
    bson_values_equal,
    parse_ejson_document,
    to_canonical_extended_json,
)


def test_canonical_ejson_round_trips_editor_values_without_coercion() -> None:
    document = {
        "_id": ObjectId("65ba0aa00000000000000001"),
        "counter": Int64(9_007_199_254_740_993),
        "price": Decimal128("12.50"),
        "payload": Binary(b"abc", subtype=0x80),
        "nested": {"enabled": True},
    }

    text = to_canonical_extended_json(document)
    parsed = parse_ejson_document(text, "Document")

    assert "$numberLong" in text
    assert isinstance(parsed["_id"], ObjectId)
    assert isinstance(parsed["counter"], Int64)
    assert isinstance(parsed["price"], Decimal128)
    assert isinstance(parsed["payload"], Binary)
    assert bson_values_equal(document, parsed)


@pytest.mark.parametrize("value", ["", "[]", "true", "{not json}"])
def test_editor_parser_rejects_invalid_or_non_document_ejson(value: str) -> None:
    with pytest.raises(EjsonValidationError):
        parse_ejson_document(value, "Document")
