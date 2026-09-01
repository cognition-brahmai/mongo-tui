"""Tests for command-line parsing without opening the TUI."""

from __future__ import annotations

from mongrove.cli import build_parser


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
