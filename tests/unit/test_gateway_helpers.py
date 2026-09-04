"""Tests for non-network MongoDB gateway helpers."""

from __future__ import annotations

import pytest

from mongrove.services.mongo_gateway import (
    MongoGatewayError,
    PyMongoGateway,
    redact_connection_uri,
    redact_sensitive_text,
    remove_uri_credentials,
)


def test_uri_helpers_redact_and_remove_credentials() -> None:
    uri = "mongodb://reader:secret@db.internal:27017/app?replicaSet=rs0"

    assert redact_connection_uri(uri) == "mongodb://***@db.internal:27017/app?replicaSet=rs0"
    assert remove_uri_credentials(uri) == "mongodb://db.internal:27017/app?replicaSet=rs0"
    assert redact_sensitive_text(f"Could not connect to {uri}") == (
        "Could not connect to mongodb://***@db.internal:27017/app?replicaSet=rs0"
    )


def test_invalid_uri_becomes_a_gateway_error() -> None:
    with pytest.raises(MongoGatewayError):
        PyMongoGateway().connect("mongodb://")
