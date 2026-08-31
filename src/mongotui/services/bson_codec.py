"""BSON-safe display helpers used by document widgets."""

from __future__ import annotations

from typing import Any

from bson import json_util


def to_extended_json(value: Any, *, indent: int | None = 2) -> str:
    """Render a value as Extended JSON while retaining BSON type information."""

    return json_util.dumps(
        value,
        indent=indent,
        json_options=json_util.RELAXED_JSON_OPTIONS,
    )


def format_cell(value: Any, *, width: int = 48) -> str:
    """Render a compact, single-line BSON value for a document table."""

    if value is None:
        rendered = "null"
    elif isinstance(value, bool):
        rendered = "true" if value else "false"
    elif isinstance(value, str):
        rendered = value
    else:
        rendered = to_extended_json(value, indent=None)

    rendered = " ".join(rendered.split())
    if len(rendered) <= width:
        return rendered
    return f"{rendered[: max(width - 3, 0)]}..."
