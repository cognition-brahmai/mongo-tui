"""Bounded BSON-aware schema-sampling report models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SchemaField:
    """Observed field facts from a finite document sample, never a full schema claim."""

    path: str
    present_count: int
    null_count: int
    type_counts: tuple[tuple[str, int], ...]
    distinct_count: int
    distinct_capped: bool
    examples: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SchemaReport:
    """A bounded analysis of sampled documents and their observed fields."""

    sampled_count: int
    fields: tuple[SchemaField, ...]
