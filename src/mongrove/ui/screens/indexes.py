"""Collection index inventory, usage inspection, and confirmed mutations."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Label, Static

from mongrove.domain.index import IndexInfo, IndexUsageReport
from mongrove.domain.session import SessionPolicy
from mongrove.services.mongo_gateway import MongoGatewayError
from mongrove.ui.commands import CommandAction
from mongrove.ui.screens.index_confirmation import (
    IndexConfirmationResult,
    IndexConfirmationScreen,
)
from mongrove.ui.screens.index_editor import IndexCreateDraft, IndexEditorScreen
from mongrove.ui.widgets.document_viewer import DocumentJsonViewer

if TYPE_CHECKING:
    from mongrove.ui.app import MongroveApp


class IndexScreen(ModalScreen[None]):
    """Manage one collection's indexes without hiding unavailable usage data."""

    BINDINGS = [
        Binding("r", "refresh", "Refresh", show=True),
        Binding("escape", "close", "Close", show=False),
    ]

    def __init__(self, database: str, collection: str, *, writable_collection: bool) -> None:
        super().__init__()
        self._database = database
        self._collection = collection
        self._writable_collection = writable_collection
        self._indexes: list[IndexInfo] = []
        self._usage = IndexUsageReport(available=False, message="Usage has not been loaded.")
        self._request_id = 0
        self._mutation_in_flight = False

    @property
    def mongrove_app(self) -> MongroveApp:
        return cast("MongroveApp", self.app)

    @property
    def namespace(self) -> str:
        return f"{self._database}.{self._collection}"

    def compose(self) -> ComposeResult:
        with Vertical(id="indexes-dialog"):
            yield Label(f"INDEXES: {self.namespace}", classes="dialog-title")
            yield Static(
                "Usage comes from node-local $indexStats and resets after server restart. "
                "Unavailable usage is never displayed as zero.",
                id="indexes-help",
            )
            yield DataTable(
                id="indexes-table",
                cursor_type="row",
                zebra_stripes=True,
                show_row_labels=False,
            )
            yield Static("Loading indexes...", id="indexes-status")
            yield Label("INDEX SPECIFICATION", classes="field-label")
            yield DocumentJsonViewer(id="index-inspector")
            with Horizontal(id="indexes-actions"):
                yield Button("Refresh", id="refresh-indexes", variant="primary")
                yield Button("Create Index", id="create-index", disabled=True)
                yield Button("Drop Selected", id="drop-index", variant="error", disabled=True)
                yield Button("Close", id="close-indexes")

    def on_mount(self) -> None:
        table = self.query_one("#indexes-table", DataTable)
        table.add_column("Name", width=28)
        table.add_column("Keys", width=32)
        table.add_column("Flags", width=20)
        table.add_column("Usage ops", width=14)
        table.add_column("Usage since", width=24)
        self._update_controls()
        self.action_refresh()

    def get_command_actions(self) -> tuple[CommandAction, ...]:
        commands = [
            CommandAction("Refresh indexes", "Reload index definitions and usage data", self.action_refresh),
            CommandAction("Close indexes", "Return to the collection workspace", self.action_close),
        ]
        if self._write_block_reason() is None:
            commands.append(
                CommandAction("Create index", "Create an index through EJSON review and confirmation", self.action_create)
            )
            if self._selected_index() is not None:
                commands.append(
                    CommandAction("Drop selected index", "Drop the selected named index after typed confirmation", self.action_drop)
                )
        return tuple(commands)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        actions = {
            "refresh-indexes": self.action_refresh,
            "create-index": self.action_create,
            "drop-index": self.action_drop,
            "close-indexes": self.action_close,
        }
        button_id = event.button.id
        if button_id is not None and button_id in actions:
            actions[button_id]()

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if event.data_table.id != "indexes-table":
            return
        index = self._selected_index()
        if index is not None:
            self.query_one("#index-inspector", DocumentJsonViewer).show_document(index.raw)
        self._update_controls()

    def action_refresh(self) -> None:
        if self._mutation_in_flight:
            return
        self._request_id += 1
        request_id = self._request_id
        self._set_status("Loading index definitions and usage data...")
        self._load_indexes(request_id)

    def action_create(self) -> None:
        if not self._ensure_writes_allowed():
            return
        self.app.push_screen(IndexEditorScreen(self.namespace), self._index_editor_closed)

    def action_drop(self) -> None:
        if not self._ensure_writes_allowed():
            return
        index = self._selected_index()
        if index is None:
            self._set_status("Select an index before dropping it.", error=True)
            return
        self._show_drop_confirmation(index)

    def action_close(self) -> None:
        if self._mutation_in_flight:
            self._set_status("Wait for the index mutation to finish before closing.")
            return
        self.dismiss(None)

    @work(thread=True, exclusive=True, group="indexes-read", exit_on_error=False)
    def _load_indexes(self, request_id: int) -> None:
        try:
            indexes = self.mongrove_app.gateway.list_indexes(self._database, self._collection)
            usage = self.mongrove_app.gateway.index_usage(self._database, self._collection)
        except MongoGatewayError as error:
            self.app.call_from_thread(self._load_failed, request_id, str(error))
            return
        self.app.call_from_thread(self._indexes_loaded, request_id, indexes, usage)

    @work(thread=True, exclusive=True, group="indexes-write", exit_on_error=False)
    def _create_index(self, draft: IndexCreateDraft, policy: SessionPolicy) -> None:
        try:
            name = self.mongrove_app.gateway.create_index(
                self._database,
                self._collection,
                list(draft.keys),
                draft.options,
                policy=policy,
            )
        except MongoGatewayError as error:
            self.app.call_from_thread(self._mutation_failed, str(error))
            return
        self.app.call_from_thread(self._mutation_succeeded, f'Created index "{name}".')

    @work(thread=True, exclusive=True, group="indexes-write", exit_on_error=False)
    def _drop_index(self, name: str, policy: SessionPolicy) -> None:
        try:
            self.mongrove_app.gateway.drop_index(
                self._database,
                self._collection,
                name,
                policy=policy,
            )
        except MongoGatewayError as error:
            self.app.call_from_thread(self._mutation_failed, str(error))
            return
        self.app.call_from_thread(self._mutation_succeeded, f'Dropped index "{name}".')

    def _indexes_loaded(
        self,
        request_id: int,
        indexes: list[IndexInfo],
        usage: IndexUsageReport,
    ) -> None:
        if request_id != self._request_id:
            return
        self._indexes = indexes
        self._usage = usage
        table = self.query_one("#indexes-table", DataTable)
        table.clear()
        usage_by_name = {entry.name: entry for entry in usage.usages}
        for index in indexes:
            index_usage = usage_by_name.get(index.name)
            table.add_row(
                index.name,
                ", ".join(f"{field}: {value}" for field, value in index.keys),
                _index_flags(index),
                str(index_usage.operations) if index_usage and index_usage.operations is not None else "-",
                index_usage.since if index_usage and index_usage.since else "-",
                key=index.name,
            )
        if indexes:
            table.move_cursor(row=0)
            self.query_one("#index-inspector", DocumentJsonViewer).show_document(indexes[0].raw)
        else:
            self.query_one("#index-inspector", DocumentJsonViewer).show_message("No visible indexes.")
        usage_status = "Usage available." if usage.available else (usage.message or "Usage unavailable.")
        self._set_status(f"{len(indexes)} indexes. {usage_status}")
        self._update_controls()

    def _load_failed(self, request_id: int, message: str) -> None:
        if request_id == self._request_id:
            self._set_status(f"Could not load indexes: {message}", error=True)

    def _index_editor_closed(self, draft: IndexCreateDraft | None) -> None:
        if draft is not None:
            self._show_create_confirmation(draft)

    def _show_create_confirmation(self, draft: IndexCreateDraft) -> None:
        if not self._ensure_writes_allowed():
            return
        preview = {"createIndexes": self._collection, "key": dict(draft.keys), "options": draft.options}
        self.app.push_screen(
            IndexConfirmationScreen(
                title=f"CONFIRM CREATE INDEX: {self.namespace}",
                connection_indicator=self.mongrove_app.connection_indicator(),
                preview=preview,
                required_phrase=self._confirmation_phrase(None),
                destructive=False,
            ),
            lambda result: self._create_confirmation_closed(draft, result),
        )

    def _show_drop_confirmation(self, index: IndexInfo) -> None:
        self.app.push_screen(
            IndexConfirmationScreen(
                title=f"CONFIRM DROP INDEX: {self.namespace}",
                connection_indicator=self.mongrove_app.connection_indicator(),
                preview={"dropIndex": index.name, "key": dict(index.keys)},
                required_phrase=self._confirmation_phrase(index.name),
                destructive=True,
            ),
            lambda result: self._drop_confirmation_closed(index.name, result),
        )

    def _create_confirmation_closed(
        self,
        draft: IndexCreateDraft,
        result: IndexConfirmationResult | None,
    ) -> None:
        if result is None or not self._ensure_writes_allowed():
            return
        required = self._confirmation_phrase(None)
        if required is not None and result.acknowledgement != required:
            self._set_status("The required acknowledgement was not accepted.", error=True)
            return
        self._start_mutation()
        self._create_index(draft, self.mongrove_app.session_policy)

    def _drop_confirmation_closed(
        self,
        name: str,
        result: IndexConfirmationResult | None,
    ) -> None:
        if result is None or not self._ensure_writes_allowed():
            return
        required = self._confirmation_phrase(name)
        if required is not None and result.acknowledgement != required:
            self._set_status("The required acknowledgement was not accepted.", error=True)
            return
        self._start_mutation()
        self._drop_index(name, self.mongrove_app.session_policy)

    def _start_mutation(self) -> None:
        self._mutation_in_flight = True
        self._update_controls()
        self._set_status("Running index mutation...")

    def _mutation_succeeded(self, message: str) -> None:
        self._mutation_in_flight = False
        self.notify(message)
        self._update_controls()
        self.action_refresh()

    def _mutation_failed(self, message: str) -> None:
        self._mutation_in_flight = False
        self._update_controls()
        self._set_status(f"Index mutation failed: {message}", error=True)

    def _write_block_reason(self) -> str | None:
        if not self._writable_collection:
            return "MongoDB views do not support collection index mutations."
        if self._mutation_in_flight:
            return "Another index mutation is already in progress."
        return self.mongrove_app.session_policy.write_block_reason

    def _ensure_writes_allowed(self) -> bool:
        reason = self._write_block_reason()
        if reason is None:
            return True
        self._set_status(reason, error=True)
        return False

    def _confirmation_phrase(self, dropped_index_name: str | None) -> str | None:
        if self.mongrove_app.session_policy.production_confirmation_required:
            return f"WRITE {self.namespace}"
        if dropped_index_name is not None:
            return f"DROP {dropped_index_name}"
        return None

    def _selected_index(self) -> IndexInfo | None:
        table = self.query_one("#indexes-table", DataTable)
        if 0 <= table.cursor_row < len(self._indexes):
            return self._indexes[table.cursor_row]
        return None

    def _update_controls(self) -> None:
        reason = self._write_block_reason()
        self.query_one("#create-index", Button).disabled = reason is not None
        self.query_one("#drop-index", Button).disabled = reason is not None or self._selected_index() is None

    def _set_status(self, message: str, *, error: bool = False) -> None:
        status = self.query_one("#indexes-status", Static)
        status.update(message)
        status.set_class(error, "error")


def _index_flags(index: IndexInfo) -> str:
    flags = []
    if index.unique:
        flags.append("unique")
    if index.sparse:
        flags.append("sparse")
    if index.hidden:
        flags.append("hidden")
    return ", ".join(flags) or "-"
