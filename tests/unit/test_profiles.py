"""Tests for profile persistence and credential stripping."""

from __future__ import annotations

from mongrove.domain.connection import ConnectionProfile
from mongrove.services.profile_store import ProfileStore


def test_profile_store_never_writes_uri_credentials(tmp_path) -> None:
    path = tmp_path / "connections.json"
    store = ProfileStore(path)

    saved = store.save(
        ConnectionProfile(
            name="Production",
            uri="mongodb://reader:top-secret@db.internal:27017/admin",
            favorite=True,
        )
    )

    assert saved.uri == "mongodb://db.internal:27017/admin"
    assert "top-secret" not in path.read_text(encoding="utf-8")
    assert store.load() == [saved]


def test_profile_store_replaces_matching_names_case_insensitively(tmp_path) -> None:
    store = ProfileStore(tmp_path / "connections.json")
    store.save(ConnectionProfile(name="Production", uri="mongodb://one.internal:27017"))
    store.save(ConnectionProfile(name="production", uri="mongodb://two.internal:27017"))

    profiles = store.load()

    assert len(profiles) == 1
    assert profiles[0].name == "production"
    assert profiles[0].uri == "mongodb://two.internal:27017"
