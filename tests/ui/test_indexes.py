"""Textual index-management workflow tests."""

from __future__ import annotations

import pytest
from textual.widgets import Button, DataTable, Input, TextArea, Tree

from mongrove.services.profile_store import ProfileStore
from mongrove.ui.app import MongroveApp
from mongrove.ui.screens.browser import BrowserScreen
from mongrove.ui.screens.index_confirmation import IndexConfirmationScreen
from mongrove.ui.screens.index_editor import IndexEditorScreen
from mongrove.ui.screens.indexes import IndexScreen

from tests.conftest import FakeGateway


async def _settle(pilot) -> None:
    for _ in range(5):
        await pilot.pause()


async def _open_customers(app: MongroveApp, pilot) -> BrowserScreen:
    connection = app.screen
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
    return browser


@pytest.mark.asyncio
async def test_index_screen_lists_usage_and_creates_confirmed_index(tmp_path) -> None:
    gateway = FakeGateway()
    app = MongroveApp(
        gateway=gateway,
        profile_store=ProfileStore(tmp_path / "connections.json"),
        no_history=True,
    )

    async with app.run_test(size=(140, 42)) as pilot:
        browser = await _open_customers(app, pilot)
        browser.action_open_indexes()
        await _settle(pilot)
        assert isinstance(app.screen, IndexScreen)
        indexes = app.screen
        assert indexes.query_one("#indexes-table", DataTable).row_count == 2
        indexes.action_create()
        await pilot.pause()
        assert isinstance(app.screen, IndexEditorScreen)
        app.screen.query_one("#index-keys", TextArea).text = '{"region":1}'
        app.screen.query_one("#index-options", TextArea).text = '{"name":"region_1","unique":true}'
        await pilot.press("ctrl+enter")
        await pilot.pause()
        assert isinstance(app.screen, IndexConfirmationScreen)
        await pilot.press("ctrl+enter")
        await _settle(pilot)

        assert app.screen is indexes
        assert gateway.index_create_calls == [
            ("app", "customers", [("region", 1)], {"name": "region_1", "unique": True})
        ]


@pytest.mark.asyncio
async def test_index_drop_requires_typed_target_and_read_only_blocks_actions(tmp_path) -> None:
    gateway = FakeGateway()
    app = MongroveApp(
        gateway=gateway,
        profile_store=ProfileStore(tmp_path / "connections.json"),
        no_history=True,
    )

    async with app.run_test(size=(140, 42)) as pilot:
        browser = await _open_customers(app, pilot)
        browser.action_open_indexes()
        await _settle(pilot)
        assert isinstance(app.screen, IndexScreen)
        indexes = app.screen
        indexes.query_one("#indexes-table", DataTable).move_cursor(row=1)
        await pilot.pause()
        indexes.action_drop()
        await pilot.pause()
        assert isinstance(app.screen, IndexConfirmationScreen)
        app.screen.query_one("#index-acknowledgement", Input).value = "DROP status_1"
        await pilot.press("ctrl+enter")
        await _settle(pilot)

        assert gateway.index_drop_calls == [("app", "customers", "status_1")]

    read_only_app = MongroveApp(
        gateway=FakeGateway(),
        profile_store=ProfileStore(tmp_path / "read-only-connections.json"),
        no_history=True,
        read_only=True,
    )
    async with read_only_app.run_test(size=(140, 42)) as pilot:
        browser = await _open_customers(read_only_app, pilot)
        browser.action_open_indexes()
        await _settle(pilot)
        assert isinstance(read_only_app.screen, IndexScreen)
        indexes = read_only_app.screen
        assert indexes.query_one("#create-index", Button).disabled is True
        indexes.action_create()
        await pilot.pause()
        assert read_only_app.screen is indexes
