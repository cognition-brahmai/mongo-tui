"""Textual workflow tests for active-query export."""

from __future__ import annotations

import json

import pytest
from textual.widgets import Input, Tree

from mongrove.services.profile_store import ProfileStore
from mongrove.ui.app import MongroveApp
from mongrove.ui.screens.browser import BrowserScreen
from mongrove.ui.screens.export import ExportScreen

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
async def test_read_only_export_snapshots_current_filter_and_streams_ejson(tmp_path) -> None:
    gateway = FakeGateway()
    app = MongroveApp(
        gateway=gateway,
        profile_store=ProfileStore(tmp_path / "connections.json"),
        no_history=True,
        read_only=True,
    )
    destination = tmp_path / "customers.ejson"

    async with app.run_test(size=(140, 42)) as pilot:
        browser = await _open_customers(app, pilot)
        browser.query_one("#filter-input", Input).value = '{"status":"active"}'
        browser.action_export_query()
        await pilot.pause()
        assert isinstance(app.screen, ExportScreen)
        export = app.screen
        export.query_one("#export-destination", Input).value = str(destination)
        await pilot.press("ctrl+enter")
        await _settle(pilot)

        assert destination.exists()
        assert gateway.stream_calls[-1][0:2] == ("app", "customers")
        assert gateway.stream_calls[-1][2].filter == {"status": "active"}
        assert gateway.insert_calls == []
        assert json.loads(destination.read_text(encoding="utf-8"))[0]["_id"]["$oid"]

        await pilot.press("ctrl+enter")
        await pilot.pause()
        assert app.screen is browser
