"""Pure, bounded BSON-aware field analysis for sampled MongoDB documents."""

from __future__ import annotations

import hashlib
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from bson import Binary, Decimal128, ObjectId, Timestamp
from bson.int64 import Int64

from mongrove.domain.schema import SchemaField, SchemaReport
from mongrove.services.bson_codec import to_canonical_extended_json


_MAX_VALUE_SIGNATURE_BYTES = 4_096
_MAX_EXAMPLE_CHARS = 1_000


@dataclass
class _FieldAccumulator:
    present_count: int = 0
    null_count: int = 0
    type_counts: Counter[str] = field(default_factory=Counter)
    values: set[str] = field(default_factory=set)
    distinct_capped: bool = False
    examples: list[str] = field(default_factory=list)


def analyze_schema(
    documents: list[dict[str, Any]],
    *,
    max_distinct_values: int = 1_000,
    max_examples: int = 3,
) -> SchemaReport:
    """Infer field observations without retaining unbounded values or documents."""

    if max_distinct_values < 1 or max_examples < 1:
        raise ValueError("Schema analysis limits must be at least one.")
    fields: dict[str, _FieldAccumulator] = {}
    for document in documents:
        seen_paths: set[str] = set()
        seen_types: set[tuple[str, str]] = set()
        seen_nulls: set[str] = set()
        _walk(
            document,
            "",
            fields,
            seen_paths,
            seen_types,
            seen_nulls,
            max_distinct_values,
            max_examples,
        )
    result = tuple(
        SchemaField(
            path=path,
            present_count=accumulator.present_count,
            null_count=accumulator.null_count,
            type_counts=tuple(sorted(accumulator.type_counts.items())),
            distinct_count=len(accumulator.values),
            distinct_capped=accumulator.distinct_capped,
            examples=tuple(accumulator.examples),
        )
        for path, accumulator in sorted(fields.items(), key=lambda item: item[0])
    )
    return SchemaReport(sampled_count=len(documents), fields=result)


def _walk(
    value: Any,
    path: str,
    fields: dict[str, _FieldAccumulator],
    seen_paths: set[str],
    seen_types: set[tuple[str, str]],
    seen_nulls: set[str],
    max_distinct_values: int,
    max_examples: int,
) -> None:
    if path:
        _observe(
            path,
            value,
            fields,
            seen_paths,
            seen_types,
            seen_nulls,
            max_distinct_values,
            max_examples,
        )
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else key
            _walk(
                child,
                child_path,
                fields,
                seen_paths,
                seen_types,
                seen_nulls,
                max_distinct_values,
                max_examples,
            )
    elif isinstance(value, list):
        for child in value:
            _walk(
                child,
                f"{path}[]",
                fields,
                seen_paths,
                seen_types,
                seen_nulls,
                max_distinct_values,
                max_examples,
            )


def _observe(
    path: str,
    value: Any,
    fields: dict[str, _FieldAccumulator],
    seen_paths: set[str],
    seen_types: set[tuple[str, str]],
    seen_nulls: set[str],
    max_distinct_values: int,
    max_examples: int,
) -> None:
    accumulator = fields.setdefault(path, _FieldAccumulator())
    if path not in seen_paths:
        accumulator.present_count += 1
        seen_paths.add(path)
    if value is None and path not in seen_nulls:
        accumulator.null_count += 1
        seen_nulls.add(path)
    type_name = _bson_type_name(value)
    if (path, type_name) not in seen_types:
        accumulator.type_counts[type_name] += 1
        seen_types.add((path, type_name))
    rendered = to_canonical_extended_json(value, indent=None)
    encoded = rendered.encode("utf-8")
    signature = (
        rendered
        if len(encoded) <= _MAX_VALUE_SIGNATURE_BYTES
        else f"sha256:{hashlib.sha256(encoded).hexdigest()}"
    )
    if signature not in accumulator.values:
        if len(accumulator.values) < max_distinct_values:
            accumulator.values.add(signature)
        else:
            accumulator.distinct_capped = True
    example = rendered if len(rendered) <= _MAX_EXAMPLE_CHARS else f"{rendered[:997]}..."
    if example not in accumulator.examples and len(accumulator.examples) < max_examples:
        accumulator.examples.append(example)


def _bson_type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, ObjectId):
        return "objectId"
    if isinstance(value, Int64):
        return "int64"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "double"
    if isinstance(value, Decimal128):
        return "decimal128"
    if isinstance(value, datetime):
        return "date"
    if isinstance(value, Timestamp):
        return "timestamp"
    if isinstance(value, Binary):
        return "binary"
    if isinstance(value, str):
        return "string"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    return type(value).__name__
