"""Command-line entry point for Mongrove."""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from mongrove import __version__
from mongrove.domain.session import normalize_environment
from mongrove.ui.app import MongroveApp
from mongrove.ui.themes import CURATED_THEME_NAMES


@dataclass(frozen=True, slots=True)
class StartupOptions:
    """Resolved startup settings after applying CLI-over-environment precedence."""

    uri: str | None
    profile: str | None
    database: str | None
    collection: str | None
    read_only: bool
    no_history: bool
    config_dir: Path | None
    theme: str | None
    environment: str | None
    allow_production_writes: bool


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser without starting a terminal UI."""

    parser = argparse.ArgumentParser(
        prog="mongrove",
        description="A keyboard-first MongoDB workspace for the terminal.",
    )
    parser.add_argument(
        "uri",
        nargs="?",
        help="MongoDB connection URI. Avoid passwords here when possible.",
    )
    parser.add_argument(
        "--profile",
        "--alias",
        dest="profile",
        help="Saved connection alias to preselect.",
    )
    parser.add_argument("--database", help="Database to open after connecting.")
    parser.add_argument("--collection", help="Collection to open after connecting.")
    parser.add_argument(
        "--read-only",
        action="store_true",
        default=None,
        help="Hide write controls. MongoDB roles remain the security boundary.",
    )
    parser.add_argument(
        "--no-history",
        action="store_true",
        default=None,
        help="Disable local query history for this session.",
    )
    parser.add_argument(
        "--config-dir",
        type=Path,
        help="Override the directory containing local Mongrove configuration.",
    )
    parser.add_argument(
        "--theme",
        choices=CURATED_THEME_NAMES,
        metavar="THEME",
        help="Use a curated theme for this launch.",
    )
    parser.add_argument(
        "--environment",
        type=_parse_environment,
        metavar="ENV",
        help="Label this direct connection as development, staging, or production.",
    )
    parser.add_argument(
        "--allow-production-writes",
        action="store_true",
        default=None,
        help="Allow writes for a production target; each mutation still confirms explicitly.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Parse arguments and run the interactive application."""

    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        options = resolve_startup_options(args)
    except ValueError as error:
        parser.error(str(error))
    app = MongroveApp(
        startup_uri=options.uri,
        startup_profile=options.profile,
        startup_database=options.database,
        startup_collection=options.collection,
        read_only=options.read_only,
        no_history=options.no_history,
        config_dir=options.config_dir,
        theme_name=options.theme,
        environment=options.environment,
        allow_production_writes=options.allow_production_writes,
    )
    app.run()
    return 0


def resolve_startup_options(
    args: argparse.Namespace,
    environ: Mapping[str, str] | None = None,
) -> StartupOptions:
    """Resolve startup values with explicit command-line values taking priority.

    A direct URI or alias supplied on the command line takes precedence over all
    environment connection selectors. This prevents a shell's stale URI from
    silently changing an explicitly requested target.
    """

    environment = os.environ if environ is None else environ
    if args.uri:
        uri = args.uri
        profile = None
    elif args.profile:
        uri = None
        profile = args.profile
    else:
        uri = _environment_value(environment, "MONGROVE_URI")
        profile = None if uri else _environment_value(environment, "MONGROVE_PROFILE")

    resolved_environment = (
        args.environment
        if args.environment is not None
        else normalize_environment(_environment_value(environment, "MONGROVE_ENVIRONMENT"))
    )
    theme = args.theme or _environment_value(environment, "MONGROVE_THEME")
    if theme is not None and theme not in CURATED_THEME_NAMES:
        choices = ", ".join(CURATED_THEME_NAMES)
        raise ValueError(f"MONGROVE_THEME must be one of: {choices}.")

    config_dir = args.config_dir
    if config_dir is None:
        config_dir_value = _environment_value(environment, "MONGROVE_CONFIG_DIR")
        config_dir = Path(config_dir_value) if config_dir_value else None

    return StartupOptions(
        uri=uri,
        profile=profile,
        database=args.database or _environment_value(environment, "MONGROVE_DATABASE"),
        collection=args.collection or _environment_value(environment, "MONGROVE_COLLECTION"),
        read_only=_resolve_boolean_option(
            args.read_only,
            environment,
            "MONGROVE_READ_ONLY",
        ),
        no_history=_resolve_boolean_option(
            args.no_history,
            environment,
            "MONGROVE_NO_HISTORY",
        ),
        config_dir=config_dir,
        theme=theme,
        environment=resolved_environment,
        allow_production_writes=_resolve_boolean_option(
            args.allow_production_writes,
            environment,
            "MONGROVE_ALLOW_PRODUCTION_WRITES",
        ),
    )


def _parse_environment(value: str) -> str:
    try:
        parsed = normalize_environment(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from error
    if parsed is None:
        raise argparse.ArgumentTypeError("Environment cannot be empty.")
    return parsed


def _environment_value(environment: Mapping[str, str], name: str) -> str | None:
    value = environment.get(name)
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _resolve_boolean_option(
    command_line_value: bool | None,
    environment: Mapping[str, str],
    name: str,
) -> bool:
    if command_line_value is not None:
        return command_line_value
    value = _environment_value(environment, name)
    if value is None:
        return False
    normalized = value.casefold()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be true or false.")
