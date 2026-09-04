"""Textual workflows for confirmed single-document writes."""

from __future__ import annotations

import pytest
from bson import ObjectId
from bson.int64 import Int64
from textual.widgets import Button, Input, TextArea, Tree

from mongrove.services.profile_store import ProfileStore
from mongrove.ui.app import MongroveApp
from mongrove.ui.screens.browser import BrowserScreen
from mongrove.ui.screens.document_editor import DocumentEditorScreen
from mongrove.ui.screens.mutation_confirmation import MutationConfirmationScreen

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
async def test_insert_uses_canonical_ejson_then_explicit_confirmation(tmp_path) -> None:
    gateway = FakeGateway()
    app = MongroveApp(
        gateway=gateway,
        profile_store=ProfileStore(tmp_path / "connections.json"),
        no_history=True,
    )

    async with app.run_test(size=(140, 42)) as pilot:
        browser = await _open_customers(app, pilot)
        browser.action_insert_document()
        await pilot.pause()
        assert isinstance(app.screen, DocumentEditorScreen)
        editor = app.screen.query_one("#document-editor", TextArea)
        editor.text = (
            '{"_id":{"$oid":"65ba0aa00000000000000003"},'
            '"counter":{"$numberLong":"7"},"name":"Miyuki"}'
        )
        await pilot.press("ctrl+enter")
        await pilot.pause()

        assert isinstance(app.screen, MutationConfirmationScreen)
        assert gateway.insert_calls == []
        await pilot.press("ctrl+enter")
        await _settle(pilot)

        assert app.screen is browser
        assert gateway.insert_calls[0][0:2] == ("app", "customers")
        inserted = gateway.insert_calls[0][2]
        assert inserted["_id"] == ObjectId("65ba0aa00000000000000003")
        assert inserted["counter"] == Int64(7)


@pytest.mark.asyncio
async def test_replace_and_delete_use_only_the_selected_immutable_id(tmp_path) -> None:
    gateway = FakeGateway()
    app = MongroveApp(
        gateway=gateway,
        profile_store=ProfileStore(tmp_path / "connections.json"),
        no_history=True,
    )

    async with app.run_test(size=(140, 42)) as pilot:
        browser = await _open_customers(app, pilot)
        original_id = gateway.documents[0]["_id"]
        browser.action_replace_selected_document()
        await pilot.pause()
        assert isinstance(app.screen, DocumentEditorScreen)
        app.screen.query_one("#document-editor", TextArea).text = (
            '{"_id":{"$oid":"65ba0aa00000000000000001"},"name":"Updated"}'
        )
        await pilot.press("ctrl+enter")
        await pilot.pause()
        assert isinstance(app.screen, MutationConfirmationScreen)
        await pilot.press("ctrl+enter")
        await _settle(pilot)

        assert gateway.replace_calls[0][2] == original_id
        assert gateway.replace_calls[0][3]["_id"] == original_id
        browser.action_delete_selected_document()
        await pilot.pause()
        assert isinstance(app.screen, MutationConfirmationScreen)
        acknowledgement = app.screen.query_one("#mutation-acknowledgement", Input)
        acknowledgement.value = "DELETE app.customers"
        await pilot.press("ctrl+enter")
        await _settle(pilot)

        assert gateway.delete_calls[0] == ("app", "customers", original_id)


@pytest.mark.asyncio
async def test_replace_rejects_a_missing_or_changed_id_before_confirmation(tmp_path) -> None:
    gateway = FakeGateway()
    app = MongroveApp(
        gateway=gateway,
        profile_store=ProfileStore(tmp_path / "connections.json"),
        no_history=True,
    )

    async with app.run_test(size=(140, 42)) as pilot:
        browser = await _open_customers(app, pilot)
        browser.action_replace_selected_document()
        await pilot.pause()
        assert isinstance(app.screen, DocumentEditorScreen)
        app.screen.query_one("#document-editor", TextArea).text = '{"name":"No id"}'
        await pilot.press("ctrl+enter")
        await pilot.pause()

        assert isinstance(app.screen, DocumentEditorScreen)
        assert gateway.replace_calls == []


@pytest.mark.asyncio
async def test_production_writes_need_an_explicit_target_acknowledgement(tmp_path) -> None:
    gateway = FakeGateway()
    app = MongroveApp(
        gateway=gateway,
        profile_store=ProfileStore(tmp_path / "connections.json"),
        no_history=True,
        environment="production",
        allow_production_writes=True,
    )

    async with app.run_test(size=(140, 42)) as pilot:
        browser = await _open_customers(app, pilot)
        assert browser.query_one("#insert-document", Button).disabled is False
        browser.action_insert_document()
        await pilot.pause()
        assert isinstance(app.screen, DocumentEditorScreen)
        app.screen.query_one("#document-editor", TextArea).text = '{"name":"Reviewed"}'
        await pilot.press("ctrl+enter")
        await pilot.pause()
        assert isinstance(app.screen, MutationConfirmationScreen)

        acknowledgement = app.screen.query_one("#mutation-acknowledgement", Input)
        acknowledgement.value = "WRITE wrong.namespace"
        await pilot.press("ctrl+enter")
        await pilot.pause()
        assert isinstance(app.screen, MutationConfirmationScreen)
        assert gateway.insert_calls == []

        acknowledgement.value = "WRITE app.customers"
        await pilot.press("ctrl+enter")
        await _settle(pilot)
        assert gateway.insert_calls[0][2]["name"] == "Reviewed"


@pytest.mark.asyncio
async def test_read_only_mode_blocks_direct_document_mutation_actions(tmp_path) -> None:
    gateway = FakeGateway()
    app = MongroveApp(
        gateway=gateway,
        profile_store=ProfileStore(tmp_path / "connections.json"),
        no_history=True,
        read_only=True,
    )

    async with app.run_test(size=(140, 42)) as pilot:
        browser = await _open_customers(app, pilot)
        assert browser.query_one("#insert-document", Button).disabled is True
        browser.action_insert_document()
        await pilot.pause()
        assert app.screen is browser
        assert gateway.insert_calls == []
