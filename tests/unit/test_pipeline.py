"""Tests for aggregation pipeline parsing and write-stage detection."""

from __future__ import annotations

import pytest
from bson import ObjectId

from mongrove.domain.pipeline import PipelineValidationError, parse_pipeline


def test_pipeline_parses_ejson_stages_and_detects_write_stages() -> None:
    pipeline = parse_pipeline(
        '[{"$match":{"_id":{"$oid":"65ba0aa00000000000000001"}}},'
        '{"$group":{"_id":"$status","count":{"$sum":1}}}]'
    )

    assert isinstance(pipeline.stages[0]["$match"]["_id"], ObjectId)
    assert pipeline.has_write_stage is False
    assert pipeline.write_stages == ()

    writing = parse_pipeline('[{"$merge":"daily_summary"}]')
    assert writing.has_write_stage is True
    assert writing.write_stages == ("$merge",)


@pytest.mark.parametrize("text", ["", "{}", "[{}]", "[{\"match\":{}}]", "[{}, {}]"])
def test_pipeline_rejects_invalid_stage_shapes(text: str) -> None:
    with pytest.raises(PipelineValidationError):
        parse_pipeline(text)
