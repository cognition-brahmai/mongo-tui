"""Session safety policy and connection-environment helpers."""

from __future__ import annotations

from dataclasses import dataclass


_ENVIRONMENT_ALIASES = {
    "dev": "development",
    "development": "development",
    "stage": "staging",
    "staging": "staging",
    "prod": "production",
    "production": "production",
}


def normalize_environment(value: str | None) -> str | None:
    """Return a canonical environment label or reject an unsafe unknown value."""

    if value is None or not value.strip():
        return None
    normalized = _ENVIRONMENT_ALIASES.get(value.strip().casefold())
    if normalized is None:
        choices = ", ".join(("development", "staging", "production"))
        raise ValueError(f"Environment must be one of: {choices}.")
    return normalized


@dataclass(frozen=True, slots=True)
class SessionPolicy:
    """Local safeguards for one Mongrove session.

    MongoDB authorization remains the server-side security boundary. This policy
    makes the operator's target and intended safety mode explicit in the UI and
    gives mutation workflows one central decision point.
    """

    environment: str | None = None
    requested_read_only: bool = False
    allow_production_writes: bool = False
    no_history: bool = False

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def writes_blocked(self) -> bool:
        """Whether local policy must reject all mutation requests."""

        return self.requested_read_only or (
            self.is_production and not self.allow_production_writes
        )

    @property
    def history_enabled(self) -> bool:
        return not self.no_history

    @property
    def environment_label(self) -> str:
        return (self.environment or "unlabeled").upper()

    @property
    def write_mode_label(self) -> str:
        if self.requested_read_only:
            return "READ ONLY"
        if self.is_production and not self.allow_production_writes:
            return "PRODUCTION READ ONLY"
        if self.is_production:
            return "PRODUCTION CONFIRMATIONS"
        return "CONFIRM WRITES"

    @property
    def production_confirmation_required(self) -> bool:
        """Whether a permitted mutation needs the production acknowledgment."""

        return self.is_production and not self.writes_blocked
