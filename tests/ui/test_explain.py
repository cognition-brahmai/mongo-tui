"""Textual workflows for planner-only explain views."""

from __future__ import annotations

import pytest
from textual.widgets import DataTable, Input, TextArea, Tree

from mongrove.services.profile_store import ProfileStore
from mongrove.ui.app import MongroveApp
from mongrove.ui.screens.aggregation import AggregationScreen
from mongrove.ui.screens.browser import BrowserScreen
from mongrove.ui.screens.explain import ExplainScreen

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
async def test_find_explain_snapshots_unsaved_filter_and_renders_plan(tmp_path) -> None:
    gateway = FakeGateway()
    app = MongroveApp(
        gateway=gateway,
        profile_store=ProfileStore(tmp_path / "connections.json"),
        no_history=True,
    )

    async with app.run_test(size=(140, 42)) as pilot:
        browser = await _open_customers(app, pilot)
        browser.query_one("#filter-input", Input).value = '{"status":"active"}'
        browser.action_explain_query()
        await _settle(pilot)

        assert isinstance(app.screen, ExplainScreen)
        assert gateway.find_explain_calls[-1][2].filter == {"status": "active"}
        assert app.screen.query_one("#explain-table", DataTable).row_count == 1


@pytest.mark.asyncio
async def test_aggregation_explain_rejects_write_stages_before_dispatch(tmp_path) -> None:
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
        app.screen.action_explain()
        await pilot.pause()

        assert app.screen.__class__ is AggregationScreen
        assert gateway.aggregation_explain_calls == []
