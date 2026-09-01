"""Connection-facing domain models for Mongrove."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ConnectionProfile:
    """A locally saved connection endpoint without secret credentials."""

    name: str
    uri: str
    favorite: bool = False
    default_database: str | None = None


@dataclass(frozen=True, slots=True)
class ConnectionInfo:
    """Connection facts collected after a successful server ping."""

    display_uri: str
    server_version: str | None = None
    topology: str | None = None
    is_writable_primary: bool | None = None
