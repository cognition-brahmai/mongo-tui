"""Tests for explicit session safety policy."""

from __future__ import annotations

import pytest

from mongrove.domain.session import SessionPolicy, normalize_environment


def test_production_is_read_only_without_an_explicit_write_override() -> None:
    policy = SessionPolicy(environment="production")

    assert policy.writes_blocked is True
    assert policy.write_mode_label == "PRODUCTION READ ONLY"
    assert policy.production_confirmation_required is False


def test_explicit_production_write_override_still_requires_confirmation() -> None:
    policy = SessionPolicy(environment="production", allow_production_writes=True)

    assert policy.writes_blocked is False
    assert policy.write_mode_label == "PRODUCTION CONFIRMATIONS"
    assert policy.production_confirmation_required is True


def test_environment_normalization_rejects_unknown_labels() -> None:
    assert normalize_environment("prod") == "production"
    assert normalize_environment(" ") is None
    with pytest.raises(ValueError, match="Environment must be one of"):
        normalize_environment("customer-a")
