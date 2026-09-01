"""Best-effort normalization of version-variable MongoDB explain responses."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

from mongrove.domain.pipeline import AggregationPipeline
from mongrove.domain.query import FindQuery


@dataclass(frozen=True, slots=True)
class ExplainFragment:
    """One independently normalized planner fragment within an explain response."""

    path: str
    root_stage: str | None
    stages: tuple[str, ...]
    index_names: tuple[str, ...]
    rejected_plan_count: int | None
    optimized_pipeline: bool = False


@dataclass(frozen=True, slots=True)
class ExplainWarning:
    """Evidence-based planner observation, never an automatic tuning claim."""

    code: str
    severity: Literal["info", "warning"]
    message: str


@dataclass(frozen=True, slots=True)
class ExplainResult:
    """Planner-only explain response with raw BSON-compatible fallback data."""

    operation: Literal["find", "aggregation"]
    elapsed_ms: int
    fragments: tuple[ExplainFragment, ...]
    warnings: tuple[ExplainWarning, ...]
    raw: dict[str, Any]


def normalize_find_explain(raw: dict[str, Any], query: FindQuery, elapsed_ms: int) -> ExplainResult:
    """Normalize a planner-only find explain and retain the raw server response."""

    result = _normalize("find", raw, elapsed_ms)
    warnings = list(result.warnings)
    if query.limit is None:
        warnings.append(
            ExplainWarning(
                code="unbounded-find",
                severity="info",
                message="The logical find query has no limit.",
            )
        )
    return ExplainResult(
        operation=result.operation,
        elapsed_ms=result.elapsed_ms,
        fragments=result.fragments,
        warnings=tuple(warnings),
        raw=result.raw,
    )


def normalize_aggregation_explain(
    raw: dict[str, Any],
    pipeline: AggregationPipeline,
    elapsed_ms: int,
) -> ExplainResult:
    """Normalize a planner-only aggregation explain and retain raw response data."""

    return _normalize("aggregation", raw, elapsed_ms)


def _normalize(
    operation: Literal["find", "aggregation"],
    raw: dict[str, Any],
    elapsed_ms: int,
) -> ExplainResult:
    planners, truncated = _planner_nodes(raw)
    fragments = tuple(_fragment(path, planner, raw) for path, planner in planners)
    warnings: list[ExplainWarning] = []
    stages = {stage for fragment in fragments for stage in fragment.stages}
    if "COLLSCAN" in stages:
        warnings.append(
            ExplainWarning("collection-scan", "warning", "Observed COLLSCAN in the winning plan.")
        )
    if "SORT" in stages:
        warnings.append(
            ExplainWarning("in-memory-sort", "warning", "Observed SORT in the winning plan.")
        )
    if "SHARD_MERGE" in stages:
        warnings.append(
            ExplainWarning("shard-merge", "info", "Observed SHARD_MERGE in the winning plan.")
        )
    rejected = sum(fragment.rejected_plan_count or 0 for fragment in fragments)
    if rejected:
        warnings.append(
            ExplainWarning(
                "rejected-plans",
                "info",
                f"Observed {rejected} rejected planner candidate(s).",
            )
        )
    if any(fragment.optimized_pipeline for fragment in fragments):
        warnings.append(
            ExplainWarning(
                "optimized-pipeline",
                "info",
                "Server reported an optimized aggregation pipeline.",
            )
        )
    if not fragments:
        warnings.append(
            ExplainWarning(
                "unrecognized-shape",
                "info",
                "Plan shape was not normalized; inspect Raw EJSON for server-specific details.",
            )
        )
    if truncated:
        warnings.append(
            ExplainWarning(
                "normalization-truncated",
                "info",
                "Plan normalization reached its safety bound; inspect Raw EJSON for remaining details.",
            )
        )
    return ExplainResult(
        operation=operation,
        elapsed_ms=elapsed_ms,
        fragments=fragments,
        warnings=tuple(warnings),
        raw=raw,
    )


def _planner_nodes(raw: Mapping[str, Any]) -> tuple[list[tuple[str, Mapping[str, Any]]], bool]:
    nodes: list[tuple[str, Mapping[str, Any]]] = []
    truncated = False
    visited = 0

    def walk(value: Any, path: str, depth: int) -> None:
        nonlocal truncated, visited
        if depth > 24 or visited >= 1_000 or len(nodes) >= 32:
            truncated = True
            return
        visited += 1
        if isinstance(value, Mapping):
            planner = value.get("queryPlanner")
            if isinstance(planner, Mapping):
                nodes.append((f"{path}.queryPlanner" if path else "queryPlanner", planner))
            for key, child in value.items():
                if key == "queryPlanner":
                    continue
                walk(child, f"{path}.{key}" if path else str(key), depth + 1)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, f"{path}[{index}]", depth + 1)

    walk(raw, "", 0)
    return nodes, truncated


def _fragment(path: str, planner: Mapping[str, Any], raw: Mapping[str, Any]) -> ExplainFragment:
    winning = planner.get("winningPlan")
    if not isinstance(winning, Mapping):
        winning = {}
    query_plan = winning.get("queryPlan")
    root = query_plan if isinstance(query_plan, Mapping) else winning
    stages, indexes = _plan_details(root)
    rejected = planner.get("rejectedPlans")
    return ExplainFragment(
        path=path,
        root_stage=stages[0] if stages else None,
        stages=tuple(stages),
        index_names=tuple(indexes),
        rejected_plan_count=len(rejected) if isinstance(rejected, list) else None,
        optimized_pipeline=bool(planner.get("optimizedPipeline") or raw.get("optimizedPipeline")),
    )


def _plan_details(root: Mapping[str, Any]) -> tuple[list[str], list[str]]:
    stages: list[str] = []
    indexes: list[str] = []
    children = ("inputStage", "inputStages", "thenStage", "elseStage", "innerStage", "outerStage")

    def walk(node: Any, depth: int) -> None:
        if depth > 24 or not isinstance(node, Mapping):
            return
        stage = node.get("stage")
        if isinstance(stage, str):
            stages.append(stage)
        index_name = node.get("indexName")
        if isinstance(index_name, str) and index_name not in indexes:
            indexes.append(index_name)
        for key in children:
            child = node.get(key)
            if isinstance(child, list):
                for item in child:
                    walk(item, depth + 1)
            else:
                walk(child, depth + 1)

    walk(root, 0)
    return stages, indexes
