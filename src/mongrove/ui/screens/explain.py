"""Planner-only MongoDB explain modal with normalized and raw views."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, cast

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Label, Static

from mongrove.domain.explain import ExplainResult
from mongrove.domain.pipeline import AggregationPipeline
from mongrove.domain.query import FindQuery
from mongrove.services.bson_codec import to_canonical_extended_json
from mongrove.services.mongo_gateway import MongoGatewayError
from mongrove.ui.commands import CommandAction
from mongrove.ui.widgets.document_viewer import DocumentJsonViewer

if TYPE_CHECKING:
    from mongrove.ui.app import MongroveApp


ExplainOperation = Literal["find", "aggregation"]


class ExplainScreen(ModalScreen[None]):
    """Run bounded planner-only explain commands without persisting their output."""

    BINDINGS = [
        Binding("r", "refresh", "Refresh", show=True),
        Binding("ctrl+c", "copy_raw", "Copy raw", show=True),
        Binding("escape", "close", "Close", show=False),
    ]

    def __init__(
        self,
        operation: ExplainOperation,
        database: str,
        collection: str,
        payload: FindQuery | AggregationPipeline,
    ) -> None:
        super().__init__()
        self._operation = operation
        self._database = database
        self._collection = collection
        self._payload = payload
        self._request_id = 0
        self._result: ExplainResult | None = None

    @property
    def mongrove_app(self) -> MongroveApp:
        return cast("MongroveApp", self.app)

    @property
    def namespace(self) -> str:
        return f"{self._database}.{self._collection}"

    def compose(self) -> ComposeResult:
        with Vertical(id="explain-dialog"):
            yield Label(
                f"EXPLAIN {self._operation.upper()}: {self.namespace}",
                classes="dialog-title",
            )
            yield Static(
                "Planner only | max 5,000 ms | execution statistics are not collected | "
                "diagnostic output may differ from normal cached execution.",
                id="explain-help",
            )
            yield Static("Loading planner output...", id="explain-warnings")
            yield DataTable(
                id="explain-table",
                cursor_type="row",
                zebra_stripes=True,
                show_row_labels=False,
            )
            yield Label("RAW EJSON", classes="field-label")
            yield DocumentJsonViewer(id="explain-raw")
            with Horizontal(id="explain-actions"):
                yield Button("Refresh", id="refresh-explain", variant="primary")
                yield Button("Copy Raw EJSON", id="copy-explain")
                yield Button("Close", id="close-explain")

    def on_mount(self) -> None:
        table = self.query_one("#explain-table", DataTable)
        table.add_column("Scope", width=28)
        table.add_column("Root", width=14)
        table.add_column("Stages", width=28)
        table.add_column("Indexes", width=28)
        table.add_column("Rejected", width=10)
        self.action_refresh()

    def get_command_actions(self) -> tuple[CommandAction, ...]:
        """Expose planner actions from the modal command-palette context."""

        return (
            CommandAction("Refresh explain", "Run a new bounded planner-only explain", self.action_refresh),
            CommandAction("Copy raw explain EJSON", "Copy the latest unpersisted raw response", self.action_copy_raw),
            CommandAction("Close explain", "Return to the workspace", self.action_close),
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "refresh-explain":
            self.action_refresh()
        elif event.button.id == "copy-explain":
            self.action_copy_raw()
        elif event.button.id == "close-explain":
            self.action_close()

    def action_refresh(self) -> None:
        self._request_id += 1
        request_id = self._request_id
        self.query_one("#explain-warnings", Static).update("Loading planner output...")
        self._load_explain(request_id)

    def action_copy_raw(self) -> None:
        if self._result is None:
            self.notify("No explain response is available to copy.", severity="warning")
            return
        self.app.copy_to_clipboard(to_canonical_extended_json(self._result.raw))
        self.notify("Raw explain copy requested through the terminal clipboard protocol.")

    def action_close(self) -> None:
        self._request_id += 1
        self.dismiss(None)

    @work(thread=True, exclusive=True, group="explain", exit_on_error=False)
    def _load_explain(self, request_id: int) -> None:
        try:
            if self._operation == "find":
                if not isinstance(self._payload, FindQuery):
                    raise AssertionError("Find explain requires a FindQuery payload.")
                result = self.mongrove_app.gateway.explain_find(
                    self._database,
                    self._collection,
                    self._payload,
                )
            else:
                if not isinstance(self._payload, AggregationPipeline):
                    raise AssertionError("Aggregation explain requires a pipeline payload.")
                result = self.mongrove_app.gateway.explain_aggregation(
                    self._database,
                    self._collection,
                    self._payload,
                )
        except MongoGatewayError as error:
            self.app.call_from_thread(self._explain_failed, request_id, str(error))
            return
        self.app.call_from_thread(self._explain_completed, request_id, result)

    def _explain_completed(self, request_id: int, result: ExplainResult) -> None:
        if request_id != self._request_id:
            return
        self._result = result
        self._render_fragments(result)
        self.query_one("#explain-raw", DocumentJsonViewer).show_document(result.raw)
        observations = " | ".join(warning.message for warning in result.warnings)
        self.query_one("#explain-warnings", Static).update(
            f"Planner response in {result.elapsed_ms} ms. {observations}"
        )

    def _explain_failed(self, request_id: int, message: str) -> None:
        if request_id == self._request_id:
            warning = self.query_one("#explain-warnings", Static)
            warning.update(f"Explain failed: {message}")
            warning.add_class("error")

    def _render_fragments(self, result: ExplainResult) -> None:
        table = self.query_one("#explain-table", DataTable)
        table.clear()
        if not result.fragments:
            table.add_row("Raw only", "-", "-", "-", "-")
            return
        for fragment in result.fragments:
            table.add_row(
                fragment.path,
                fragment.root_stage or "-",
                " > ".join(fragment.stages) or "-",
                ", ".join(fragment.index_names) or "-",
                str(fragment.rejected_plan_count)
                if fragment.rejected_plan_count is not None
                else "-",
            )
