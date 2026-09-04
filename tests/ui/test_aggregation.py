"""Textual workflow tests for the raw aggregation editor."""

from __future__ import annotations

import pytest
from textual.widgets import DataTable, Input, TextArea, Tree

from mongrove.services.profile_store import ProfileStore
from mongrove.ui.app import MongroveApp
from mongrove.ui.screens.aggregation import AggregationScreen
from mongrove.ui.screens.browser import BrowserScreen

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
async def test_raw_aggregation_editor_runs_a_bounded_preview(tmp_path) -> None:
    gateway = FakeGateway()
    app = MongroveApp(
        gateway=gateway,
        profile_store=ProfileStore(tmp_path / "connections.json"),
        no_history=True,
    )

    async with app.run_test(size=(140, 42)) as pilot:
        browser = await _open_customers(app, pilot)
        browser.action_open_aggregation()
        await pilot.pause()
        assert isinstance(app.screen, AggregationScreen)
        editor = app.screen.query_one("#pipeline-editor", TextArea)
        editor.text = '[{"$match":{"status":"active"}}]'
        await pilot.press("ctrl+enter")
        await _settle(pilot)

        assert gateway.aggregation_calls[-1][0:2] == ("app", "customers")
        assert gateway.aggregation_calls[-1][2].stages == ({"$match": {"status": "active"}},)
        assert app.screen.query_one("#aggregation-table", DataTable).row_count == 2


@pytest.mark.asyncio
async def test_aggregation_editor_blocks_write_stages_before_gateway_dispatch(tmp_path) -> None:
    gateway = FakeGateway()
    app = MongroveApp(
        gateway=gateway,
        profile_store=ProfileStore(tmp_path / "connections.json"),
        no_history=True,
    )

    async with app.run_test(size=(140, 42)) as pilot:
        browser = await _open_customers(app, pilot)
        browser.action_open_aggregation()
        await pilot.pause()
        assert isinstance(app.screen, AggregationScreen)
        app.screen.query_one("#pipeline-editor", TextArea).text = '[{"$out":"summary"}]'
        await pilot.press("ctrl+enter")
        await pilot.pause()

        assert gateway.aggregation_calls == []
