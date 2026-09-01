"""Raw BSON-aware aggregation pipeline editor with bounded previews."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Label, Static, TextArea

from mongrove.domain.pipeline import AggregationPipeline, PipelineValidationError, parse_pipeline
from mongrove.services.bson_codec import format_cell
from mongrove.services.mongo_gateway import AggregationPage, MongoGatewayError
from mongrove.ui.commands import CommandAction
from mongrove.ui.widgets.document_table import DocumentTable
from mongrove.ui.widgets.document_viewer import DocumentJsonViewer

if TYPE_CHECKING:
    from mongrove.ui.app import MongroveApp


class AggregationScreen(ModalScreen[None]):
    """Edit raw JSON/EJSON pipeline stages and inspect a safe preview."""

    AUTO_FOCUS = "#pipeline-editor"
    BINDINGS = [
        Binding("ctrl+enter", "run", "Run preview", show=True),
        Binding("escape", "close", "Close", show=False),
    ]
    PAGE_SIZE = 100

    def __init__(self, database: str, collection: str) -> None:
        super().__init__()
        self._database = database
        self._collection = collection
        self._documents: list[dict[str, Any]] = []
        self._request_id = 0

    @property
    def mongrove_app(self) -> MongroveApp:
        return cast("MongroveApp", self.app)

    @property
    def namespace(self) -> str:
        return f"{self._database}.{self._collection}"

    def compose(self) -> ComposeResult:
        with Vertical(id="aggregation-dialog"):
            yield Label(f"AGGREGATION PIPELINE: {self.namespace}", classes="dialog-title")
            yield Static(
                "Raw JSON/EJSON pipeline. Previews are capped at 100 documents; "
                "$out and $merge are blocked until their confirmed write flow exists.",
                id="aggregation-help",
            )
            yield TextArea(
                "[]",
                id="pipeline-editor",
                show_line_numbers=True,
                soft_wrap=False,
                tab_behavior="focus",
            )
            with Horizontal(id="aggregation-actions"):
                yield Button("Run Preview", id="run-aggregation", variant="primary")
                yield Button("Copy Pipeline", id="copy-pipeline")
                yield Button("Close", id="close-aggregation")
            yield Static("Enter a pipeline and run a preview.", id="aggregation-status")
            with Horizontal(id="aggregation-results"):
                yield DocumentTable(
                    id="aggregation-table",
                    cursor_type="row",
                    zebra_stripes=True,
                    show_row_labels=False,
                )
                yield DocumentJsonViewer(id="aggregation-inspector")

    def get_command_actions(self) -> tuple[CommandAction, ...]:
        """Expose pipeline operations in the contextual command palette."""

        return (
            CommandAction("Run aggregation preview", "Validate and run the raw pipeline", self.action_run),
            CommandAction("Copy aggregation pipeline", "Copy raw JSON/EJSON pipeline text", self.action_copy_pipeline),
            CommandAction("Close aggregation editor", "Return to collection results", self.action_close),
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "run-aggregation":
            self.action_run()
        elif event.button.id == "copy-pipeline":
            self.action_copy_pipeline()
        elif event.button.id == "close-aggregation":
            self.action_close()

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if event.data_table.id != "aggregation-table":
            return
        if 0 <= event.cursor_row < len(self._documents):
            self.query_one("#aggregation-inspector", DocumentJsonViewer).show_document(
                self._documents[event.cursor_row]
            )

    def action_run(self) -> None:
        try:
            pipeline = parse_pipeline(self.query_one("#pipeline-editor", TextArea).text)
        except PipelineValidationError as error:
            self._set_status(str(error), error=True)
            return
        if pipeline.has_write_stage:
            stages = ", ".join(pipeline.write_stages)
            self._set_status(
                f"{stages} writes are blocked here; use a confirmed write workflow.",
                error=True,
            )
            return
        self._request_id += 1
        request_id = self._request_id
        self._set_status("Running bounded aggregation preview...")
        self._run_pipeline(request_id, pipeline)

    def action_copy_pipeline(self) -> None:
        self.app.copy_to_clipboard(self.query_one("#pipeline-editor", TextArea).text)
        self.notify("Pipeline copy requested through the terminal clipboard protocol.")

    def action_close(self) -> None:
        self.dismiss(None)

    @work(thread=True, exclusive=True, group="aggregation", exit_on_error=False)
    def _run_pipeline(self, request_id: int, pipeline: AggregationPipeline) -> None:
        try:
            result = self.mongrove_app.gateway.aggregate_documents(
                self._database,
                self._collection,
                pipeline,
                page_size=self.PAGE_SIZE,
            )
        except MongoGatewayError as error:
            self.app.call_from_thread(self._pipeline_failed, request_id, str(error))
            return
        self.app.call_from_thread(self._pipeline_completed, request_id, result)

    def _pipeline_completed(self, request_id: int, result: AggregationPage) -> None:
        if request_id != self._request_id:
            return
        self._documents = result.documents
        self._render_documents(result.documents)
        suffix = "+" if result.has_more else ""
        self._set_status(
            f"{len(result.documents)}{suffix} documents | {result.elapsed_ms} ms | preview limit {self.PAGE_SIZE}"
        )

    def _pipeline_failed(self, request_id: int, message: str) -> None:
        if request_id == self._request_id:
            self._set_status(f"Aggregation failed: {message}", error=True)

    def _render_documents(self, documents: list[dict[str, Any]]) -> None:
        table = self.query_one("#aggregation-table", DataTable)
        table.clear(columns=True)
        fields = _document_columns(documents)
        if not fields:
            table.add_columns("Result")
            table.add_row("No documents were returned by this pipeline.")
            self.query_one("#aggregation-inspector", DocumentJsonViewer).show_message(
                "No documents were returned by this pipeline."
            )
            return
        table.add_columns(*fields)
        for index, document in enumerate(documents):
            table.add_row(
                *[
                    format_cell(document[field]) if field in document else "(missing)"
                    for field in fields
                ],
                key=str(index),
            )
        self.query_one("#aggregation-inspector", DocumentJsonViewer).show_document(documents[0])

    def _set_status(self, message: str, *, error: bool = False) -> None:
        status = self.query_one("#aggregation-status", Static)
        status.update(message)
        status.set_class(error, "error")


def _document_columns(documents: list[dict[str, Any]], *, maximum: int = 8) -> list[str]:
    fields: list[str] = []
    if any("_id" in document for document in documents):
        fields.append("_id")
    for document in documents:
        for field in document:
            if field not in fields:
                fields.append(field)
            if len(fields) >= maximum:
                return fields
    return fields
