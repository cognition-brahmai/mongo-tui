"""Tests for Mongrove command-palette action registration."""

from __future__ import annotations

import pytest
from textual.command import CommandPalette
from textual.widgets import Input, Tree

from mongrove.services.profile_store import ProfileStore
from mongrove.ui.app import MongroveApp
from mongrove.ui.screens.browser import BrowserScreen
from mongrove.ui.screens.connection import ConnectionScreen

from tests.conftest import FakeGateway


async def _settle(pilot) -> None:
    for _ in range(4):
        await pilot.pause()


def _command_titles(app: MongroveApp, screen) -> set[str]:
    return {command.title for command in app.get_system_commands(screen)}


@pytest.mark.asyncio
async def test_command_palette_registers_global_and_contextual_actions(tmp_path) -> None:
    app = MongroveApp(
        gateway=FakeGateway(),
        profile_store=ProfileStore(tmp_path / "connections.json"),
        no_history=True,
    )

    async with app.run_test(size=(140, 42)) as pilot:
        assert isinstance(app.screen, ConnectionScreen)
        connection_commands = _command_titles(app, app.screen)
        assert "Choose Mongrove theme" in connection_commands
        assert "Connect to MongoDB" in connection_commands
        assert "Save connection alias" in connection_commands

        await pilot.press("ctrl+p")
        await pilot.pause()
        assert isinstance(app.screen, CommandPalette)
        await pilot.press("escape")
        await pilot.pause()

        connection = app.screen
        assert isinstance(connection, ConnectionScreen)
        connection.query_one("#uri-input", Input).value = "mongodb://localhost:27017"
        await pilot.press("ctrl+enter")
        await _settle(pilot)

        browser = app.screen
        assert isinstance(browser, BrowserScreen)
        tree = browser.query_one("#namespace-tree", Tree)
        app_node = tree.root.children[1]
        app_node.expand()
        await _settle(pilot)
        tree.select_node(app_node.children[0])
        await _settle(pilot)

        browser_commands = _command_titles(app, browser)
        assert "Run query" in browser_commands
        assert "Open query options" in browser_commands
        assert "Open aggregation editor" in browser_commands
        assert "Explain active query" in browser_commands
        assert "Manage indexes" in browser_commands
        assert "Sample collection schema" in browser_commands
        assert "Open query history" not in browser_commands
        assert "Export active query" in browser_commands
        assert "Open selected document" in browser_commands
        assert "Disconnect from MongoDB" in browser_commands
