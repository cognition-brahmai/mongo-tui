"""Textual workflow tests for schema sampling."""

from __future__ import annotations

import pytest
from textual.widgets import DataTable, Input, Tree

from mongrove.services.profile_store import ProfileStore
from mongrove.ui.app import MongroveApp
from mongrove.ui.screens.browser import BrowserScreen
from mongrove.ui.screens.schema import SchemaScreen

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
async def test_schema_sampler_uses_active_filter_and_renders_observed_fields(tmp_path) -> None:
    gateway = FakeGateway()
    app = MongroveApp(
        gateway=gateway,
        profile_store=ProfileStore(tmp_path / "connections.json"),
        no_history=True,
    )

    async with app.run_test(size=(140, 42)) as pilot:
        browser = await _open_customers(app, pilot)
        browser.query_one("#filter-input", Input).value = '{"status":"active"}'
        browser.action_open_schema()
        await pilot.pause()
        assert isinstance(app.screen, SchemaScreen)
        await pilot.press("ctrl+enter")
        await _settle(pilot)

        assert gateway.schema_sample_calls[-1][0:2] == ("app", "customers")
        assert gateway.schema_sample_calls[-1][2] == {"status": "active"}
        assert app.screen.query_one("#schema-table", DataTable).row_count > 0
