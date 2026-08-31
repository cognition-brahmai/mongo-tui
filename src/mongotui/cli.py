"""Command-line entry point for MongoTUI."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from mongotui import __version__
from mongotui.ui.app import MongoTUIApp
from mongotui.ui.themes import CURATED_THEME_NAMES


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser without starting a terminal UI."""

    parser = argparse.ArgumentParser(
        prog="mongotui",
        description="A keyboard-first terminal user interface for MongoDB.",
    )
    parser.add_argument(
        "uri",
        nargs="?",
        help="MongoDB connection URI. Avoid passwords here when possible.",
    )
    parser.add_argument("--profile", help="Saved profile name to preselect.")
    parser.add_argument("--database", help="Database to open after connecting.")
    parser.add_argument("--collection", help="Collection to open after connecting.")
    parser.add_argument(
        "--read-only",
        action="store_true",
        help="Hide write controls. MongoDB roles remain the security boundary.",
    )
    parser.add_argument(
        "--no-history",
        action="store_true",
        help="Disable local query history for this session.",
    )
    parser.add_argument(
        "--config-dir",
        type=Path,
        help="Override the directory containing local MongoTUI configuration.",
    )
    parser.add_argument(
        "--theme",
        choices=CURATED_THEME_NAMES,
        metavar="THEME",
        help="Use a curated theme for this launch.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Parse arguments and run the interactive application."""

    args = build_parser().parse_args(argv)
    app = MongoTUIApp(
        startup_uri=args.uri,
        startup_profile=args.profile,
        startup_database=args.database,
        startup_collection=args.collection,
        read_only=args.read_only,
        no_history=args.no_history,
        config_dir=args.config_dir,
        theme_name=args.theme,
    )
    app.run()
    return 0
