"""Tests for curated theme selection."""

from __future__ import annotations

import pytest

from mongrove.services.profile_store import ProfileStore
from mongrove.services.settings_store import SettingsStore
from mongrove.ui.app import MongroveApp
from mongrove.ui.themes import CURATED_THEME_NAMES, DEFAULT_THEME


def test_theme_names_are_unique_and_include_the_default() -> None:
    assert len(CURATED_THEME_NAMES) == len(set(CURATED_THEME_NAMES))
    assert DEFAULT_THEME in CURATED_THEME_NAMES


def test_app_uses_saved_theme_and_persists_selection(tmp_path) -> None:
    settings = SettingsStore(tmp_path / "settings.json")
    settings.save_theme("mongrove-ocean")
    app = MongroveApp(
        profile_store=ProfileStore(tmp_path / "connections.json"),
        settings_store=settings,
    )

    assert app.theme == "mongrove-ocean"

    app.select_theme("mongrove-paper")

    assert app.theme == "mongrove-paper"
    assert settings.load_theme() == "mongrove-paper"


def test_app_rejects_unknown_theme(tmp_path) -> None:
    app = MongroveApp(
        profile_store=ProfileStore(tmp_path / "connections.json"),
        settings_store=SettingsStore(tmp_path / "settings.json"),
    )

    with pytest.raises(ValueError, match="Unsupported Mongrove theme"):
        app.select_theme("not-a-theme")
