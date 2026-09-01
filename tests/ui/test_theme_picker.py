"""Textual integration tests for the keyboard theme picker."""

from __future__ import annotations

import pytest
from textual.widgets import OptionList

from mongrove.services.profile_store import ProfileStore
from mongrove.services.settings_store import SettingsStore
from mongrove.ui.app import MongroveApp
from mongrove.ui.screens.connection import ConnectionScreen
from mongrove.ui.screens.theme_picker import ThemePickerScreen

from tests.conftest import FakeGateway


@pytest.mark.asyncio
async def test_theme_picker_switches_and_persists_theme(tmp_path) -> None:
    settings = SettingsStore(tmp_path / "settings.json")
    app = MongroveApp(
        gateway=FakeGateway(),
        profile_store=ProfileStore(tmp_path / "connections.json"),
        settings_store=settings,
    )

    async with app.run_test(size=(120, 38)) as pilot:
        assert app.theme == "mongrove-night"
        await pilot.press("ctrl+t")
        await pilot.pause()

        assert isinstance(app.screen, ThemePickerScreen)
        theme_list = app.screen.query_one("#theme-list", OptionList)
        assert theme_list.highlighted == 0

        await pilot.press("down", "enter")
        await pilot.pause()

        assert isinstance(app.screen, ConnectionScreen)
        assert app.theme == "mongrove-forest"
        assert settings.load_theme() == "mongrove-forest"
