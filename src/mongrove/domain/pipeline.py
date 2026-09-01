"""Validated BSON-aware aggregation pipeline models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from bson import json_util


class PipelineValidationError(ValueError):
    """Raised when raw editor text cannot become a MongoDB pipeline."""


@dataclass(frozen=True, slots=True)
class AggregationPipeline:
    """Parsed pipeline plus a safety classification of its write stages."""

    stages: tuple[dict[str, Any], ...]
    write_stages: tuple[str, ...] = ()

    @property
    def has_write_stage(self) -> bool:
        return bool(self.write_stages)


def parse_pipeline(text: str) -> AggregationPipeline:
    """Parse a JSON/EJSON array of one-key aggregation stage documents."""

    if not text.strip():
        raise PipelineValidationError("Pipeline cannot be empty; use [] for no stages.")
    try:
        parsed = json_util.loads(text)
    except Exception as error:  # json_util exposes multiple parser exceptions.
        raise PipelineValidationError(
            f"Pipeline must be valid JSON or Extended JSON: {error}"
        ) from error
    if not isinstance(parsed, list):
        raise PipelineValidationError("Pipeline must be a JSON array of stage documents.")

    stages: list[dict[str, Any]] = []
    write_stages: list[str] = []
    for index, stage in enumerate(parsed, start=1):
        if not isinstance(stage, dict) or len(stage) != 1:
            raise PipelineValidationError(
                f"Stage {index} must be a JSON document with exactly one operator."
            )
        operator = next(iter(stage))
        if not isinstance(operator, str) or not operator.startswith("$"):
            raise PipelineValidationError(f"Stage {index} must start with a $ operator.")
        stages.append(stage)
        if operator in {"$out", "$merge"}:
            write_stages.append(operator)
    return AggregationPipeline(tuple(stages), tuple(write_stages))
