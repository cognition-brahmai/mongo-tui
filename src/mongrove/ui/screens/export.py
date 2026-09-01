"""Keyboard-first streaming export modal for the active find query."""

from __future__ import annotations

import json
from pathlib import Path
from threading import Event
from typing import TYPE_CHECKING, cast

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static

from mongrove.domain.query import FindQuery
from mongrove.services.import_export import (
    ExportCancelled,
    ExportError,
    ExportFormat,
    ExportProgress,
    ExportRequest,
    ExportResult,
    export_find_query,
    parse_csv_columns,
    parse_export_format,
)
from mongrove.services.mongo_gateway import MongoGatewayError
from mongrove.ui.commands import CommandAction

if TYPE_CHECKING:
    from mongrove.ui.app import MongroveApp


class ExportScreen(ModalScreen[ExportResult | None]):
    """Collect a destination, stream output, and preserve existing local files."""

    AUTO_FOCUS = "#export-format"
    BINDINGS = [
        Binding("ctrl+enter", "start", "Start export", show=True),
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def __init__(
        self,
        *,
        database: str,
        collection: str,
        query: FindQuery,
        csv_columns: list[str],
        connection_indicator: str,
    ) -> None:
        super().__init__()
        self._database = database
        self._collection = collection
        self._query = query
        self._csv_columns = csv_columns
        self._connection_indicator = connection_indicator
        self._cancel_event = Event()
        self._exporting = False
        self._completed_result: ExportResult | None = None

    @property
    def mongrove_app(self) -> MongroveApp:
        return cast("MongroveApp", self.app)

    @property
    def namespace(self) -> str:
        return f"{self._database}.{self._collection}"

    def compose(self) -> ComposeResult:
        with Vertical(id="export-dialog"):
            yield Label(f"EXPORT QUERY: {self.namespace}", classes="dialog-title")
            yield Static(self._connection_indicator, id="export-target")
            yield Static(_query_summary(self._query), id="export-query-summary")
            yield Static(
                "Exports every match after this query's Skip/Limit, not just the visible page. "
                "Exports are not backups or point-in-time snapshots.",
                id="export-warning",
            )
            yield Label("Format: json, ejson, or csv", classes="field-label")
            yield Input("ejson", id="export-format")
            yield Label("Destination file", classes="field-label")
            yield Input(placeholder="/secure/exports/customers.ejson", id="export-destination")
            yield Label("CSV columns (JSON array; used only for csv)", classes="field-label")
            yield Input(json.dumps(self._csv_columns), id="export-csv-columns")
            yield Label("Overwrite acknowledgement (type OVERWRITE only if file exists)", classes="field-label")
            yield Input(placeholder="OVERWRITE", id="export-overwrite")
            yield Static("Choose a destination and start a streaming export.", id="export-status")
            with Horizontal(id="export-actions"):
                yield Button("Start Export", id="start-export", variant="primary")
                yield Button("Cancel", id="cancel-export")

    def get_command_actions(self) -> tuple[CommandAction, ...]:
        """Expose start/cancel through the active modal command palette."""

        return (
            CommandAction("Start export", "Validate and stream the active query", self.action_start),
            CommandAction("Cancel export", "Cancel before completion or request worker cancellation", self.action_cancel),
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "start-export":
            self.action_start()
        elif event.button.id == "cancel-export":
            self.action_cancel()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "export-destination" and not self._exporting:
            self.query_one("#export-overwrite", Input).value = ""

    def action_start(self) -> None:
        if self._completed_result is not None:
            self.dismiss(self._completed_result)
            return
        if self._exporting:
            return
        try:
            request = self._request_from_inputs()
        except ExportError as error:
            self._set_status(str(error), error=True)
            return
        if request.destination.exists() and self.query_one("#export-overwrite", Input).value != "OVERWRITE":
            self._set_status(
                "Destination exists. Type OVERWRITE exactly before replacing it.",
                error=True,
            )
            self.query_one("#export-overwrite", Input).focus()
            return
        self._exporting = True
        self._cancel_event.clear()
        self.mongrove_app.export_in_progress = True
        self._set_controls(disabled=True)
        self._set_status("Starting streaming export...")
        self._run_export(request)

    def action_cancel(self) -> None:
        if self._exporting:
            self._cancel_event.set()
            self.query_one("#cancel-export", Button).disabled = True
            self._set_status("Cancellation requested; waiting for cursor and file cleanup...")
            return
        self.dismiss(None)

    @work(thread=True, exclusive=True, group="export", exit_on_error=False)
    def _run_export(self, request: ExportRequest) -> None:
        try:
            result = export_find_query(
                self.mongrove_app.gateway,
                self._database,
                self._collection,
                self._query,
                request,
                is_cancelled=self._cancel_event.is_set,
                on_progress=lambda progress: self.app.call_from_thread(
                    self._export_progress,
                    progress,
                ),
            )
        except ExportCancelled as error:
            self.app.call_from_thread(self._export_cancelled, str(error))
            return
        except (ExportError, MongoGatewayError) as error:
            self.app.call_from_thread(self._export_failed, str(error))
            return
        self.app.call_from_thread(self._export_completed, result)

    def _export_progress(self, progress: ExportProgress) -> None:
        if not self._exporting:
            return
        self._set_status(
            f"Writing {progress.documents_written:,} documents | "
            f"{_format_bytes(progress.bytes_written)} | {progress.elapsed_ms / 1_000:.1f}s"
        )

    def _export_completed(self, result: ExportResult) -> None:
        self._exporting = False
        self.mongrove_app.export_in_progress = False
        self._completed_result = result
        self._set_status(
            f"Exported {result.documents_written:,} documents to {result.destination} | "
            f"{_format_bytes(result.bytes_written)} | {result.elapsed_ms / 1_000:.1f}s"
        )
        self.query_one("#start-export", Button).label = "Close"
        self.query_one("#start-export", Button).disabled = False
        self.query_one("#cancel-export", Button).disabled = True

    def _export_cancelled(self, message: str) -> None:
        self._exporting = False
        self.mongrove_app.export_in_progress = False
        self._set_controls(disabled=False)
        self._set_status(message)

    def _export_failed(self, message: str) -> None:
        self._exporting = False
        self.mongrove_app.export_in_progress = False
        self._set_controls(disabled=False)
        self._set_status(f"Export failed: {message}", error=True)

    def _request_from_inputs(self) -> ExportRequest:
        destination_text = self.query_one("#export-destination", Input).value.strip()
        if not destination_text:
            raise ExportError("Choose a destination file path.")
        export_format = parse_export_format(self.query_one("#export-format", Input).value)
        columns = (
            parse_csv_columns(self.query_one("#export-csv-columns", Input).value)
            if export_format is ExportFormat.CSV
            else ()
        )
        return ExportRequest(
            destination=Path(destination_text).expanduser(),
            format=export_format,
            csv_columns=columns,
        )

    def _set_controls(self, *, disabled: bool) -> None:
        for selector in (
            "#export-format",
            "#export-destination",
            "#export-csv-columns",
            "#export-overwrite",
            "#start-export",
        ):
            self.query_one(selector).disabled = disabled
        self.query_one("#cancel-export", Button).disabled = False

    def _set_status(self, message: str, *, error: bool = False) -> None:
        status = self.query_one("#export-status", Static)
        status.update(message)
        status.set_class(error, "error")


def _query_summary(query: FindQuery) -> str:
    projection = "yes" if query.projection is not None else "no"
    sort = ", ".join(f"{field}:{direction}" for field, direction in query.sort) or "none"
    limit = str(query.limit) if query.limit is not None else "unbounded"
    return (
        f"Filter: {json.dumps(query.filter, default=str)} | projection: {projection} | "
        f"sort: {sort} | skip: {query.skip} | limit: {limit} | maxTimeMS: {query.max_time_ms}"
    )


def _format_bytes(value: int) -> str:
    if value < 1_024:
        return f"{value} B"
    if value < 1_024 * 1_024:
        return f"{value / 1_024:.1f} KiB"
    return f"{value / (1_024 * 1_024):.1f} MiB"
