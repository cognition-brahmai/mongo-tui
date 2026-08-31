"""Tests for non-secret local settings."""

from __future__ import annotations

from mongotui.services.settings_store import SettingsStore


def test_settings_store_persists_theme_without_connection_data(tmp_path) -> None:
    path = tmp_path / "settings.json"
    store = SettingsStore(path)

    store.save_theme("mongotui-ocean")

    assert store.load_theme() == "mongotui-ocean"
    assert path.read_text(encoding="utf-8") == '{\n  "theme": "mongotui-ocean"\n}\n'
