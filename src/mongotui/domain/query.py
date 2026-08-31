"""Safe parsing and pagination rules for MongoDB find queries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from bson import json_util


class QueryValidationError(ValueError):
    """Raised when query editor text cannot become a safe find query."""


@dataclass(frozen=True, slots=True)
class QueryFormState:
    """Raw text maintained by the query bar and its options dialog."""

    filter_text: str = "{}"
    projection_text: str = ""
    sort_text: str = ""
    collation_text: str = ""
    skip_text: str = "0"
    limit_text: str = ""
    max_time_ms_text: str = "60000"


@dataclass(frozen=True, slots=True)
class FindQuery:
    """Validated MongoDB find options independent of UI widgets."""

    filter: dict[str, Any]
    projection: dict[str, Any] | None
    sort: list[tuple[str, int]]
    collation: dict[str, Any] | None
    skip: int
    limit: int | None
    max_time_ms: int

    def page_request(self, page: int, page_size: int) -> tuple[int, int]:
        """Return the safe cursor skip and fetch size for one result page.

        One extra document is fetched whenever possible so the UI can show a
        reliable next-page affordance without calling countDocuments().
        """

        if page < 0:
            raise ValueError("Page cannot be negative.")
        if page_size < 1:
            raise ValueError("Page size must be at least one.")

        page_offset = page * page_size
        cursor_skip = self.skip + page_offset
        if self.limit is None:
            return cursor_skip, page_size + 1

        remaining = self.limit - page_offset
        if remaining <= 0:
            return cursor_skip, 0
        return cursor_skip, min(page_size + 1, remaining)


def parse_find_query(state: QueryFormState) -> FindQuery:
    """Parse EJSON-compatible form inputs without executing arbitrary code."""

    filter_document = _parse_document(state.filter_text, "Filter", empty_value={})
    projection = _parse_optional_document(state.projection_text, "Projection")
    sort_document = _parse_optional_document(state.sort_text, "Sort")
    collation = _parse_optional_document(state.collation_text, "Collation")

    sort: list[tuple[str, int]] = []
    if sort_document is not None:
        for field, direction in sort_document.items():
            if isinstance(direction, bool) or direction not in (1, -1):
                raise QueryValidationError(
                    f'Sort direction for "{field}" must be 1 or -1.'
                )
            sort.append((field, int(direction)))

    skip = _parse_non_negative_int(state.skip_text, "Skip", default=0)
    limit = _parse_non_negative_int(state.limit_text, "Limit", default=None)
    max_time_ms = _parse_positive_int(
        state.max_time_ms_text,
        "Max Time MS",
        default=60_000,
    )

    if skip is None:
        raise AssertionError("Skip defaults to zero and cannot be None.")
    if limit == 0:
        # Match MongoDB's limit(0) convention while retaining bounded UI pages.
        limit = None

    return FindQuery(
        filter=filter_document,
        projection=projection,
        sort=sort,
        collation=collation,
        skip=skip,
        limit=limit,
        max_time_ms=max_time_ms,
    )


def _parse_optional_document(value: str, label: str) -> dict[str, Any] | None:
    if not value.strip():
        return None
    return _parse_document(value, label, empty_value={})


def _parse_document(
    value: str,
    label: str,
    *,
    empty_value: dict[str, Any],
) -> dict[str, Any]:
    if not value.strip():
        return empty_value

    try:
        parsed = json_util.loads(value)
    except Exception as error:  # json_util exposes multiple parser exceptions.
        raise QueryValidationError(f"{label} must be valid JSON or Extended JSON: {error}") from error

    if not isinstance(parsed, dict):
        raise QueryValidationError(f"{label} must be a JSON document.")
    return parsed


def _parse_non_negative_int(
    value: str,
    label: str,
    *,
    default: int | None,
) -> int | None:
    if not value.strip():
        return default
    try:
        parsed = int(value)
    except ValueError as error:
        raise QueryValidationError(f"{label} must be a whole number.") from error
    if parsed < 0:
        raise QueryValidationError(f"{label} cannot be negative.")
    return parsed


def _parse_positive_int(value: str, label: str, *, default: int) -> int:
    if not value.strip():
        return default
    try:
        parsed = int(value)
    except ValueError as error:
        raise QueryValidationError(f"{label} must be a whole number.") from error
    if parsed < 1:
        raise QueryValidationError(f"{label} must be at least 1.")
    return parsed
