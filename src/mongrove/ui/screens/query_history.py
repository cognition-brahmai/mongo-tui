"""Keyboard-first local query-history browser."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, cast

from rich.text import Text
from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Input, Label, Static

from mongrove.domain.query import QueryFormState
from mongrove.services.query_history import QueryHistoryEntry, QueryHistoryStoreError

if TYPE_CHECKING:
    from mongrove.ui.app import MongroveApp


class QueryHistoryScreen(ModalScreen[QueryFormState | None]):
    """Search, restore, favorite, and prune saved queries for one namespace."""

    AUTO_FOCUS = "#history-search"
    BINDINGS = [
        Binding("ctrl+enter", "load", "Load", show=True),
        Binding("ctrl+f", "toggle_favorite", "Favorite", show=True),
        Binding("ctrl+d", "delete", "Delete", show=True),
        Binding("ctrl+c", "copy_filter", "Copy filter", show=True),
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def __init__(
        self,
        entries: list[QueryHistoryEntry],
        *,
        target_id: str,
        database: str,
        collection: str,
    ) -> None:
        super().__init__()
        self._entries = entries
        self._visible_entries: list[QueryHistoryEntry] = []
        self._target_id = target_id
        self._database = database
        self._collection = collection

    @property
    def mongrove_app(self) -> MongroveApp:
        return cast("MongroveApp", self.app)

    @property
    def namespace(self) -> str:
        return f"{self._database}.{self._collection}"

    def compose(self) -> ComposeResult:
        with Vertical(id="query-history-dialog"):
            yield Label(f"QUERY HISTORY: {self.namespace}", classes="dialog-title")
            yield Input(placeholder="Search saved filters and names", id="history-search")
            yield DataTable(
                id="history-table",
                cursor_type="row",
                zebra_stripes=True,
                show_row_labels=False,
            )
            yield Static(
                "History stores raw query text locally. Use --no-history for sensitive sessions.",
                id="history-status",
            )
            yield Label("Optional query name", classes="field-label")
            yield Input(placeholder="For example: active customers", id="history-name")
            with Horizontal(id="query-history-actions"):
                yield Button("Load", id="load-history", variant="primary")
                yield Button("Favorite", id="favorite-history")
                yield Button("Save Name", id="name-history")
                yield Button("Copy Filter", id="copy-history")
                yield Button("Delete", id="delete-history", variant="error")
                yield Button("Cancel", id="cancel-history")

    def on_mount(self) -> None:
        table = self.query_one("#history-table", DataTable)
        table.add_column("Query", width=28)
        table.add_column("Filter", width=34)
        table.add_column("Options", width=24)
        table.add_column("Last used", width=18)
        self._render_entries()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "history-search":
            self._render_entries()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        actions = {
            "load-history": self.action_load,
            "favorite-history": self.action_toggle_favorite,
            "name-history": self.action_save_name,
            "copy-history": self.action_copy_filter,
            "delete-history": self.action_delete,
            "cancel-history": self.action_cancel,
        }
        button_id = event.button.id
        if button_id is None:
            return
        action = actions.get(button_id)
        if action is not None:
            action()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.data_table.id == "history-table":
            self.action_load()

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if event.data_table.id != "history-table":
            return
        entry = self._selected_entry()
        if entry is not None:
            self.query_one("#history-name", Input).value = entry.label or ""

    def action_load(self) -> None:
        entry = self._selected_entry()
        if entry is None:
            self._set_status("Select a saved query first.", error=True)
            return
        self.dismiss(entry.state)

    def action_toggle_favorite(self) -> None:
        entry = self._selected_entry()
        if entry is None:
            self._set_status("Select a saved query first.", error=True)
            return
        self._mutate_entry(entry.id, "favorite", not entry.favorite)

    def action_save_name(self) -> None:
        entry = self._selected_entry()
        if entry is None:
            self._set_status("Select a saved query first.", error=True)
            return
        label = self.query_one("#history-name", Input).value
        self._mutate_entry(entry.id, "rename", label)

    def action_copy_filter(self) -> None:
        entry = self._selected_entry()
        if entry is None:
            self._set_status("Select a saved query first.", error=True)
            return
        self.app.copy_to_clipboard(entry.state.filter_text)
        self._set_status("Filter copy requested through the terminal clipboard protocol.")

    def action_delete(self) -> None:
        entry = self._selected_entry()
        if entry is None:
            self._set_status("Select a saved query first.", error=True)
            return
        self._mutate_entry(entry.id, "delete", None)

    def action_cancel(self) -> None:
        self.dismiss(None)

    @work(thread=True, group="history-mutation", exit_on_error=False)
    def _mutate_entry(self, entry_id: int, action: str, value: bool | str | None) -> None:
        try:
            if action == "favorite":
                self.mongrove_app.query_history.set_favorite(entry_id, bool(value))
            elif action == "rename":
                self.mongrove_app.query_history.rename(
                    entry_id, value if isinstance(value, str) else None
                )
            elif action == "delete":
                self.mongrove_app.query_history.delete(entry_id)
            else:
                raise AssertionError(f"Unsupported history action: {action}")
            entries = self.mongrove_app.query_history.list_entries(
                target_id=self._target_id,
                database=self._database,
                collection=self._collection,
            )
        except QueryHistoryStoreError as error:
            self.app.call_from_thread(self._history_error, str(error))
            return
        self.app.call_from_thread(self._history_refreshed, entries)

    def _history_refreshed(self, entries: list[QueryHistoryEntry]) -> None:
        self._entries = entries
        self._render_entries()
        self._set_status("History updated.")

    def _history_error(self, message: str) -> None:
        self._set_status(message, error=True)

    def _render_entries(self) -> None:
        table = self.query_one("#history-table", DataTable)
        search = self.query_one("#history-search", Input).value.casefold().strip()
        self._visible_entries = [
            entry
            for entry in self._entries
            if not search or search in _entry_search_text(entry)
        ]
        table.clear()
        for entry in self._visible_entries:
            title = entry.label or _filter_preview(entry.state.filter_text)
            marker = "* " if entry.favorite else ""
            table.add_row(
                _cell(marker + title),
                _cell(_filter_preview(entry.state.filter_text)),
                _cell(_options_summary(entry.state)),
                _cell(_last_used_summary(entry)),
                key=str(entry.id),
            )
        if self._visible_entries:
            table.move_cursor(row=0)
            self.query_one("#history-name", Input).value = self._visible_entries[0].label or ""
            count = len(self._visible_entries)
            label = "saved query" if count == 1 else "saved queries"
            self._set_status(f"{count} {label} in this namespace.")
        else:
            self.query_one("#history-name", Input).value = ""
            self._set_status("No saved queries match this namespace.")

    def _selected_entry(self) -> QueryHistoryEntry | None:
        table = self.query_one("#history-table", DataTable)
        if 0 <= table.cursor_row < len(self._visible_entries):
            return self._visible_entries[table.cursor_row]
        return None

    def _set_status(self, message: str, *, error: bool = False) -> None:
        status = self.query_one("#history-status", Static)
        status.update(message)
        status.set_class(error, "error")


def _cell(value: str) -> Text:
    return Text(value.replace("\n", " "))


def _filter_preview(value: str, *, maximum: int = 48) -> str:
    compact = " ".join(value.split()) or "{}"
    return compact if len(compact) <= maximum else f"{compact[: maximum - 3]}..."


def _options_summary(state: QueryFormState) -> str:
    parts: list[str] = []
    if state.projection_text.strip():
        parts.append("projection")
    if state.sort_text.strip():
        parts.append("sort")
    if state.collation_text.strip():
        parts.append("collation")
    if state.skip_text.strip() not in {"", "0"}:
        parts.append(f"skip {state.skip_text.strip()}")
    if state.limit_text.strip():
        parts.append(f"limit {state.limit_text.strip()}")
    return ", ".join(parts) or "filter only"


def _last_used_summary(entry: QueryHistoryEntry) -> str:
    timestamp = datetime.fromtimestamp(entry.last_used_at_ms / 1_000).strftime("%Y-%m-%d %H:%M")
    suffix = "run" if entry.run_count == 1 else "runs"
    return f"{timestamp} | {entry.run_count} {suffix}"


def _entry_search_text(entry: QueryHistoryEntry) -> str:
    return " ".join(
        (
            entry.label or "",
            entry.state.filter_text,
            entry.state.projection_text,
            entry.state.sort_text,
            entry.state.collation_text,
        )
    ).casefold()
