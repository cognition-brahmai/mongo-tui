"""BSON-safe display helpers used by Mongrove document widgets."""

from __future__ import annotations

from typing import Any

from bson import json_util


class EjsonValidationError(ValueError):
    """Raised when editor text is not a BSON-compatible EJSON document."""


def to_extended_json(value: Any, *, indent: int | None = 2) -> str:
    """Render a value as Extended JSON while retaining BSON type information."""

    return json_util.dumps(
        value,
        indent=indent,
        json_options=json_util.RELAXED_JSON_OPTIONS,
    )


def to_canonical_extended_json(value: Any, *, indent: int | None = 2) -> str:
    """Render canonical EJSON for lossless document editing and comparison."""

    return json_util.dumps(
        value,
        indent=indent,
        json_options=json_util.CANONICAL_JSON_OPTIONS,
    )


def parse_ejson_document(text: str, label: str) -> dict[str, Any]:
    """Parse one non-empty JSON/EJSON document without evaluating code."""

    if not text.strip():
        raise EjsonValidationError(f"{label} cannot be empty.")
    try:
        parsed = json_util.loads(text)
    except Exception as error:  # json_util exposes multiple parser exceptions.
        raise EjsonValidationError(
            f"{label} must be valid JSON or Extended JSON: {error}"
        ) from error
    if not isinstance(parsed, dict):
        raise EjsonValidationError(f"{label} must be a JSON document.")
    return parsed


def bson_values_equal(left: Any, right: Any) -> bool:
    """Compare BSON values through canonical EJSON rather than Python coercions."""

    return to_canonical_extended_json(left, indent=None) == to_canonical_extended_json(
        right,
        indent=None,
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
