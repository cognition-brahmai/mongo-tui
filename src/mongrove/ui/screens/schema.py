"""Bounded BSON-aware schema sampler for one filtered collection."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Input, Label, Static

from mongrove.domain.schema import SchemaField, SchemaReport
from mongrove.services.bson_codec import to_extended_json
from mongrove.services.mongo_gateway import MongoGatewayError, SchemaSample
from mongrove.services.schema_analyzer import analyze_schema
from mongrove.ui.commands import CommandAction

if TYPE_CHECKING:
    from mongrove.ui.app import MongroveApp


class SchemaScreen(ModalScreen[None]):
    """Sample documents after a filter and display observed field distributions."""

    BINDINGS = [
        Binding("ctrl+enter", "sample", "Run sample", show=True),
        Binding("escape", "close", "Close", show=False),
    ]

    def __init__(self, database: str, collection: str, filter_document: dict[str, Any]) -> None:
        super().__init__()
        self._database = database
        self._collection = collection
        self._filter_document = filter_document
        self._fields: list[SchemaField] = []
        self._request_id = 0

    @property
    def mongrove_app(self) -> MongroveApp:
        return cast("MongroveApp", self.app)

    @property
    def namespace(self) -> str:
        return f"{self._database}.{self._collection}"

    def compose(self) -> ComposeResult:
        with Vertical(id="schema-dialog"):
            yield Label(f"SCHEMA SAMPLE: {self.namespace}", classes="dialog-title")
            yield Static(
                "Observed sample only; it is not a complete schema or validator. "
                f"Active filter: {to_extended_json(self._filter_document, indent=None)}",
                id="schema-help",
            )
            with Horizontal(id="schema-controls"):
                yield Label("Random sample size", classes="field-label")
                yield Input("100", id="schema-sample-size")
                yield Button("Run Sample", id="run-schema", variant="primary")
                yield Button("Close", id="close-schema")
            yield Static("Choose a bounded sample size, then run analysis.", id="schema-status")
            yield DataTable(
                id="schema-table",
                cursor_type="row",
                zebra_stripes=True,
                show_row_labels=False,
            )
            yield Static("Select a field to inspect canonical EJSON examples.", id="schema-examples")

    def on_mount(self) -> None:
        table = self.query_one("#schema-table", DataTable)
        table.add_column("Path", width=32)
        table.add_column("Presence", width=16)
        table.add_column("Null", width=14)
        table.add_column("BSON types", width=30)
        table.add_column("Cardinality", width=14)

    def get_command_actions(self) -> tuple[CommandAction, ...]:
        return (
            CommandAction("Run schema sample", "Sample documents after the active filter", self.action_sample),
            CommandAction("Close schema sample", "Return to collection results", self.action_close),
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "run-schema":
            self.action_sample()
        elif event.button.id == "close-schema":
            self.action_close()

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if event.data_table.id != "schema-table":
            return
        if 0 <= event.cursor_row < len(self._fields):
            field = self._fields[event.cursor_row]
            examples = " | ".join(field.examples) or "No examples captured."
            self.query_one("#schema-examples", Static).update(
                f"{field.path}: {examples}"
            )

    def action_sample(self) -> None:
        raw_size = self.query_one("#schema-sample-size", Input).value.strip()
        try:
            sample_size = int(raw_size)
        except ValueError:
            self._set_status("Sample size must be a whole number.", error=True)
            return
        if not 1 <= sample_size <= 10_000:
            self._set_status("Sample size must be between 1 and 10000.", error=True)
            return
        self._request_id += 1
        request_id = self._request_id
        self._set_status("Sampling and analyzing documents...")
        self._sample_documents(request_id, sample_size)

    def action_close(self) -> None:
        self._request_id += 1
        self.dismiss(None)

    @work(thread=True, exclusive=True, group="schema", exit_on_error=False)
    def _sample_documents(self, request_id: int, sample_size: int) -> None:
        try:
            sample = self.mongrove_app.gateway.sample_documents(
                self._database,
                self._collection,
                self._filter_document,
                sample_size=sample_size,
            )
            report = analyze_schema(sample.documents)
        except MongoGatewayError as error:
            self.app.call_from_thread(self._sample_failed, request_id, str(error))
            return
        self.app.call_from_thread(self._sample_completed, request_id, sample, report)

    def _sample_completed(
        self,
        request_id: int,
        sample: SchemaSample,
        report: SchemaReport,
    ) -> None:
        if request_id != self._request_id:
            return
        self._fields = list(report.fields)
        table = self.query_one("#schema-table", DataTable)
        table.clear()
        for field in self._fields:
            table.add_row(
                field.path,
                _ratio(field.present_count, report.sampled_count),
                _ratio(field.null_count, report.sampled_count),
                ", ".join(f"{name}:{count}" for name, count in field.type_counts),
                f"{field.distinct_count}{'+' if field.distinct_capped else ''}",
                key=field.path,
            )
        if self._fields:
            table.move_cursor(row=0)
            field = self._fields[0]
            self.query_one("#schema-examples", Static).update(
                f"{field.path}: {' | '.join(field.examples)}"
            )
        else:
            self.query_one("#schema-examples", Static).update("No fields were observed in this sample.")
        self._set_status(
            f"{report.sampled_count} sampled documents | {len(report.fields)} observed fields | {sample.elapsed_ms} ms"
        )

    def _sample_failed(self, request_id: int, message: str) -> None:
        if request_id == self._request_id:
            self._set_status(f"Schema sample failed: {message}", error=True)

    def _set_status(self, message: str, *, error: bool = False) -> None:
        status = self.query_one("#schema-status", Static)
        status.update(message)
        status.set_class(error, "error")


def _ratio(value: int, total: int) -> str:
    if total <= 0:
        return "-"
    return f"{value}/{total} ({value / total:.0%})"
