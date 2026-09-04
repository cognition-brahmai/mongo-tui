"""Tests for command-line parsing without opening the TUI."""

from __future__ import annotations

import pytest

from mongrove.cli import build_parser, resolve_startup_options


def test_cli_parses_startup_options() -> None:
    args = build_parser().parse_args(
        [
            "mongodb://localhost:27017",
            "--database",
            "app",
            "--collection",
            "customers",
            "--read-only",
            "--no-history",
            "--theme",
            "mongrove-ocean",
        ]
    )

    assert args.uri == "mongodb://localhost:27017"
    assert args.database == "app"
    assert args.collection == "customers"
    assert args.read_only is True
    assert args.no_history is True
    assert args.theme == "mongrove-ocean"


def test_cli_alias_and_explicit_values_override_environment() -> None:
    args = build_parser().parse_args(
        ["--alias", "staging", "--environment", "prod", "--read-only"]
    )

    options = resolve_startup_options(
        args,
        {
            "MONGROVE_URI": "mongodb://unexpected.internal:27017",
            "MONGROVE_PROFILE": "unexpected",
            "MONGROVE_ENVIRONMENT": "development",
            "MONGROVE_READ_ONLY": "false",
        },
    )

    assert options.uri is None
    assert options.profile == "staging"
    assert options.environment == "production"
    assert options.read_only is True


def test_environment_startup_options_are_strict_and_support_false_values() -> None:
    args = build_parser().parse_args([])

    options = resolve_startup_options(
        args,
        {
            "MONGROVE_URI": "mongodb://reader@db.internal:27017",
            "MONGROVE_READ_ONLY": "false",
            "MONGROVE_NO_HISTORY": "yes",
            "MONGROVE_ALLOW_PRODUCTION_WRITES": "1",
            "MONGROVE_ENVIRONMENT": "staging",
        },
    )

    assert options.uri == "mongodb://reader@db.internal:27017"
    assert options.profile is None
    assert options.read_only is False
    assert options.no_history is True
    assert options.allow_production_writes is True
    assert options.environment == "staging"

    with pytest.raises(ValueError, match="MONGROVE_READ_ONLY"):
        resolve_startup_options(args, {"MONGROVE_READ_ONLY": "sometimes"})
