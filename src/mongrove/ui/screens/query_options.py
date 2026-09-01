"""Modal editor for find-query options."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static

from mongrove.domain.query import QueryFormState, QueryValidationError, parse_find_query
from mongrove.ui.commands import CommandAction


class QueryOptionsScreen(ModalScreen[QueryFormState | None]):
    """Edit and validate non-filter find options before running a query."""

    AUTO_FOCUS = "#projection-input"
    BINDINGS = [
        Binding("ctrl+enter", "apply", "Apply", show=True),
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def __init__(self, state: QueryFormState) -> None:
        super().__init__()
        self.state = state

    def compose(self) -> ComposeResult:
        with Vertical(id="query-options-dialog"):
            yield Label("QUERY OPTIONS", classes="dialog-title")
            yield Label("Projection (JSON/EJSON document)", classes="field-label")
            yield Input(self.state.projection_text, id="projection-input")
            yield Label("Sort (for example: {\"createdAt\": -1})", classes="field-label")
            yield Input(self.state.sort_text, id="sort-input")
            yield Label("Collation (JSON/EJSON document)", classes="field-label")
            yield Input(self.state.collation_text, id="collation-input")
            with Horizontal(classes="integer-options"):
                with Vertical():
                    yield Label("Skip", classes="field-label")
                    yield Input(self.state.skip_text, id="skip-input")
                with Vertical():
                    yield Label("Limit", classes="field-label")
                    yield Input(self.state.limit_text, id="limit-input")
                with Vertical():
                    yield Label("Max Time MS", classes="field-label")
                    yield Input(self.state.max_time_ms_text, id="max-time-input")
            yield Static("Leave Limit empty to page through all matching documents.", id="options-status")
            with Horizontal(id="query-options-actions"):
                yield Button("Cancel", id="cancel-options")
                yield Button("Apply", id="apply-options", variant="primary")

    def get_command_actions(self) -> tuple[CommandAction, ...]:
        """Expose query editing actions from the modal palette context."""

        return (
            CommandAction("Apply query options", "Validate and return the edited options", self.action_apply),
            CommandAction("Cancel query options", "Discard option edits", self.action_cancel),
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "apply-options":
            self.action_apply()
        elif event.button.id == "cancel-options":
            self.action_cancel()

    def action_apply(self) -> None:
        candidate = QueryFormState(
            filter_text=self.state.filter_text,
            projection_text=self.query_one("#projection-input", Input).value,
            sort_text=self.query_one("#sort-input", Input).value,
            collation_text=self.query_one("#collation-input", Input).value,
            skip_text=self.query_one("#skip-input", Input).value,
            limit_text=self.query_one("#limit-input", Input).value,
            max_time_ms_text=self.query_one("#max-time-input", Input).value,
        )
        try:
            parse_find_query(candidate)
        except QueryValidationError as error:
            status = self.query_one("#options-status", Static)
            status.update(str(error))
            status.add_class("error")
            return
        self.dismiss(candidate)

    def action_cancel(self) -> None:
        self.dismiss(None)
