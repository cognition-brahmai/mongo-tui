"""Local saved-profile storage that avoids persisting URI credentials."""

from __future__ import annotations

import json
from pathlib import Path

from platformdirs import user_config_path

from mongrove.domain.connection import ConnectionProfile
from mongrove.services.mongo_gateway import remove_uri_credentials


class ProfileStore:
    """Persist named connection endpoints as a compact JSON document."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or user_config_path("mongrove") / "connections.json"

    def load(self) -> list[ConnectionProfile]:
        """Load saved profiles, returning an empty list for a first launch."""

        if not self.path.exists():
            return []
        try:
            raw_profiles = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ProfileStoreError(f"Could not read saved connections: {error}") from error

        if not isinstance(raw_profiles, list):
            raise ProfileStoreError("Saved connections must contain a JSON list.")

        profiles: list[ConnectionProfile] = []
        for raw_profile in raw_profiles:
            if not isinstance(raw_profile, dict):
                continue
            name = raw_profile.get("name")
            uri = raw_profile.get("uri")
            if not isinstance(name, str) or not isinstance(uri, str):
                continue
            profiles.append(
                ConnectionProfile(
                    name=name,
                    uri=remove_uri_credentials(uri),
                    favorite=bool(raw_profile.get("favorite", False)),
                    default_database=_optional_string(raw_profile.get("default_database")),
                )
            )

        return sorted(
            profiles,
            key=lambda profile: (not profile.favorite, profile.name.casefold()),
        )

    def save(self, profile: ConnectionProfile) -> ConnectionProfile:
        """Insert or replace one profile by name without writing credentials."""

        clean_profile = ConnectionProfile(
            name=profile.name.strip(),
            uri=remove_uri_credentials(profile.uri),
            favorite=profile.favorite,
            default_database=profile.default_database,
        )
        if not clean_profile.name:
            raise ProfileStoreError("Connection name cannot be empty.")
        if not clean_profile.uri:
            raise ProfileStoreError("Connection URI cannot be empty.")

        profiles = self.load()
        replacement_index = next(
            (
                index
                for index, existing in enumerate(profiles)
                if existing.name.casefold() == clean_profile.name.casefold()
            ),
            None,
        )
        if replacement_index is None:
            profiles.append(clean_profile)
        else:
            profiles[replacement_index] = clean_profile

        profiles = sorted(
            profiles,
            key=lambda item: (not item.favorite, item.name.casefold()),
        )
        self._write(profiles)
        return clean_profile

    def delete(self, name: str) -> None:
        """Delete a profile by name; missing profiles are ignored."""

        profiles = [
            profile
            for profile in self.load()
            if profile.name.casefold() != name.casefold()
        ]
        self._write(profiles)

    def _write(self, profiles: list[ConnectionProfile]) -> None:
        payload = [
            {
                "name": profile.name,
                "uri": profile.uri,
                "favorite": profile.favorite,
                "default_database": profile.default_database,
            }
            for profile in profiles
        ]
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary_path = self.path.with_suffix(".tmp")
            temporary_path.write_text(
                json.dumps(payload, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            temporary_path.replace(self.path)
        except OSError as error:
            raise ProfileStoreError(f"Could not save connection profiles: {error}") from error


class ProfileStoreError(RuntimeError):
    """A user-facing local-profile persistence error."""


def _optional_string(value: object) -> str | None:
    if isinstance(value, str) and value:
        return value
    return None
