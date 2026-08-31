"""Small non-secret application settings store."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from platformdirs import user_config_path


class SettingsStore:
    """Persist user interface preferences separately from connection profiles."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or user_config_path("mongotui") / "settings.json"

    def load_theme(self) -> str | None:
        """Return the saved theme name, if one has been selected."""

        value = self._load().get("theme")
        return value if isinstance(value, str) and value else None

    def save_theme(self, theme_name: str) -> None:
        """Persist one curated theme name without touching connection data."""

        settings = self._load()
        settings["theme"] = theme_name
        self._write(settings)

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise SettingsStoreError(f"Could not read MongoTUI settings: {error}") from error
        if not isinstance(value, dict):
            raise SettingsStoreError("MongoTUI settings must contain a JSON object.")
        return value

    def _write(self, settings: dict[str, Any]) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary_path = self.path.with_suffix(".tmp")
            temporary_path.write_text(
                json.dumps(settings, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            temporary_path.replace(self.path)
        except OSError as error:
            raise SettingsStoreError(f"Could not save MongoTUI settings: {error}") from error


class SettingsStoreError(RuntimeError):
    """A user-facing settings persistence error."""
