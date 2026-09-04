"""MongoDB index metadata models independent of PyMongo result objects."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class IndexInfo:
    """One server-reported collection index and its complete raw specification."""

    name: str
    keys: tuple[tuple[str, Any], ...]
    unique: bool
    sparse: bool
    hidden: bool
    raw: dict[str, Any]


@dataclass(frozen=True, slots=True)
class IndexUsage:
    """Best-effort node-local $indexStats usage data for one index."""

    name: str
    operations: int | None
    since: str | None


@dataclass(frozen=True, slots=True)
class IndexUsageReport:
    """Usage availability is explicit so absent privileges never look like zero."""

    available: bool
    usages: tuple[IndexUsage, ...] = ()
    message: str | None = None
