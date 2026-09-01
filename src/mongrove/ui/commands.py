"""Small, screen-owned command-palette action contract."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class CommandAction:
    """One discoverable Mongrove operation for Textual's command palette."""

    title: str
    help: str
    callback: Callable[[], Any]
    discover: bool = True
