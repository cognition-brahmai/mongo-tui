"""Textual integration tests for the first read-only workflow."""

from __future__ import annotations

import pytest
from textual.widgets import DataTable, Input, Tree

from mongrove.domain.connection import ConnectionProfile
from mongrove.services.profile_store import ProfileStore
from mongrove.ui.app import MongroveApp
from mongrove.ui.screens.browser import BrowserScreen
from mongrove.ui.screens.connection import ConnectionScreen
from mongrove.ui.widgets.document_table import DocumentTable
from mongrove.ui.widgets.document_viewer import DocumentJsonViewer

from tests.conftest import FakeGateway


async def _settle(pilot) -> None:
    """Yield enough event-loop turns for a fast thread worker to report back."""

    for _ in range(4):
        await pilot.pause()


@pytest.mark.asyncio
async def test_connect_then_open_collection_and_query_documents(tmp_path) -> None:
    gateway = FakeGateway()
    app = MongroveApp(
        gateway=gateway,
        profile_store=ProfileStore(tmp_path / "connections.json"),
    )

    async with app.run_test(size=(140, 42)) as pilot:
        assert isinstance(app.screen, ConnectionScreen)
        app.screen.query_one("#uri-input", Input).value = "mongodb://localhost:27017"
        await pilot.press("ctrl+enter")
        await _settle(pilot)

        assert isinstance(app.screen, BrowserScreen)
        browser = app.screen
        tree = browser.query_one("#namespace-tree", Tree)
        assert [str(node.label) for node in tree.root.children] == ["admin", "app"]

        app_node = tree.root.children[1]
        app_node.expand()
        await _settle(pilot)
        collection_node = app_node.children[0]
        tree.select_node(collection_node)
        await _settle(pilot)

        table = browser.query_one("#documents-table", DataTable)
        assert table.row_count == 2
        assert gateway.queries[-1][0:2] == ("app", "customers")
        assert "Alice" in str(table.get_row_at(0))


@pytest.mark.asyncio
async def test_query_options_validate_before_returning_to_browser(tmp_path) -> None:
    app = MongroveApp(
        gateway=FakeGateway(),
        profile_store=ProfileStore(tmp_path / "connections.json"),
    )

    async with app.run_test(size=(140, 42)) as pilot:
        connection = app.screen
        connection.query_one("#uri-input", Input).value = "mongodb://localhost:27017"
        await pilot.press("ctrl+enter")
        await _settle(pilot)

        browser = app.screen
        assert isinstance(browser, BrowserScreen)
        browser.action_open_query_options()
        await _settle(pilot)

        options = app.screen
        options.query_one("#sort-input", Input).value = '{"name": 1}'
        await pilot.press("ctrl+enter")
        await _settle(pilot)

        assert app.screen is browser
        assert browser._query_state.sort_text == '{"name": 1}'


@pytest.mark.asyncio
async def test_empty_document_table_ignores_header_clicks(tmp_path) -> None:
    app = MongroveApp(
        gateway=FakeGateway(),
        profile_store=ProfileStore(tmp_path / "connections.json"),
    )

    async with app.run_test(size=(140, 42)) as pilot:
        connection = app.screen
        connection.query_one("#uri-input", Input).value = "mongodb://localhost:27017"
        await pilot.press("ctrl+enter")
        await _settle(pilot)

        browser = app.screen
        assert isinstance(browser, BrowserScreen)
        table = browser.query_one("#documents-table", DocumentTable)
        assert table.ordered_columns == []

        await pilot.click("#documents-table", offset=(3, 1))
        await pilot.pause()

        assert app.screen is browser
        assert table.ordered_columns == []


@pytest.mark.asyncio
async def test_populated_document_table_accepts_header_clicks(tmp_path) -> None:
    gateway = FakeGateway()
    app = MongroveApp(
        gateway=gateway,
        profile_store=ProfileStore(tmp_path / "connections.json"),
    )

    async with app.run_test(size=(140, 42)) as pilot:
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

        await pilot.click("#documents-table", offset=(3, 1))
        await _settle(pilot)

        assert gateway.queries[-1][2].sort == [("_id", 1)]


@pytest.mark.asyncio
async def test_document_inspector_scrolls_with_keyboard(tmp_path) -> None:
    gateway = FakeGateway()
    gateway.documents[0]["large_payload"] = {
        f"field_{index:03}": f"Value {index}" for index in range(100)
    }
    app = MongroveApp(
        gateway=gateway,
        profile_store=ProfileStore(tmp_path / "connections.json"),
    )

    async with app.run_test(size=(140, 42)) as pilot:
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

        viewer = browser.query_one("#document-inspector", DocumentJsonViewer)
        assert viewer.max_scroll_y > 0
        viewer.focus()
        await pilot.press("pagedown")
        await pilot.pause()
        assert viewer.scroll_y > 0


@pytest.mark.asyncio
async def test_production_alias_is_prominently_guarded_in_the_workspace(tmp_path) -> None:
    profiles = ProfileStore(tmp_path / "connections.json")
    profiles.save(
        ConnectionProfile(
            name="production-eu",
            uri="mongodb://db.internal:27017",
            environment="production",
        )
    )
    app = MongroveApp(
        gateway=FakeGateway(),
        profile_store=profiles,
        startup_profile="production-eu",
    )

    async with app.run_test(size=(140, 42)) as pilot:
        connection = app.screen
        assert isinstance(connection, ConnectionScreen)
        assert connection.query_one("#environment-input", Input).value == "production"
        await pilot.press("ctrl+enter")
        await _settle(pilot)

        assert isinstance(app.screen, BrowserScreen)
        assert app.read_only is True
        banner = app.screen.query_one("#connection-banner")
        assert "ALIAS production-eu" in str(banner.render())
        assert "ENV PRODUCTION" in str(banner.render())
        assert "PRODUCTION READ ONLY" in str(banner.render())
