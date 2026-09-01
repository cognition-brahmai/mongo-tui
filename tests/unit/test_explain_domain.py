"""Tests for explain-plan normalization and evidence-based warnings."""

from __future__ import annotations

from mongrove.domain.explain import normalize_aggregation_explain, normalize_find_explain
from mongrove.domain.pipeline import parse_pipeline
from mongrove.domain.query import FindQuery


def _query(*, limit: int | None = None) -> FindQuery:
    return FindQuery(
        filter={"status": "active"},
        projection=None,
        sort=[],
        collation=None,
        skip=0,
        limit=limit,
        max_time_ms=60_000,
    )


def test_classic_and_sbe_explains_produce_compact_plan_fragments() -> None:
    classic = {
        "queryPlanner": {
            "winningPlan": {
                "stage": "FETCH",
                "inputStage": {"stage": "IXSCAN", "indexName": "status_1"},
            },
            "rejectedPlans": [{"stage": "COLLSCAN"}],
        }
    }
    sbe = {
        "queryPlanner": {
            "winningPlan": {
                "queryPlan": {
                    "stage": "SORT",
                    "inputStage": {"stage": "COLLSCAN"},
                },
                "slotBasedPlan": {"stages": "ignored internal text"},
            },
            "rejectedPlans": [],
        }
    }

    classic_result = normalize_find_explain(classic, _query(), 5)
    sbe_result = normalize_find_explain(sbe, _query(limit=10), 6)

    assert classic_result.fragments[0].stages == ("FETCH", "IXSCAN")
    assert classic_result.fragments[0].index_names == ("status_1",)
    assert any(warning.code == "rejected-plans" for warning in classic_result.warnings)
    assert any(warning.code == "unbounded-find" for warning in classic_result.warnings)
    assert sbe_result.fragments[0].stages == ("SORT", "COLLSCAN")
    assert {warning.code for warning in sbe_result.warnings} >= {
        "collection-scan",
        "in-memory-sort",
    }


def test_aggregation_cursor_and_unknown_shapes_remain_honest() -> None:
    pipeline = parse_pipeline('[{"$match":{"status":"active"}}]')
    raw = {
        "stages": [
            {
                "$cursor": {
                    "queryPlanner": {
                        "winningPlan": {"stage": "IXSCAN", "indexName": "status_1"},
                        "rejectedPlans": [],
                    }
                }
            }
        ],
        "optimizedPipeline": True,
    }

    result = normalize_aggregation_explain(raw, pipeline, 7)
    unknown = normalize_aggregation_explain({"ok": 1}, pipeline, 1)

    assert result.fragments[0].root_stage == "IXSCAN"
    assert any(warning.code == "optimized-pipeline" for warning in result.warnings)
    assert unknown.fragments == ()
    assert any(warning.code == "unrecognized-shape" for warning in unknown.warnings)
