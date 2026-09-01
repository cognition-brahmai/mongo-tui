"""Explicit human confirmation for a parsed single-document mutation."""

from __future__ import annotations

from dataclasses import dataclass

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static, TextArea

from mongrove.services.bson_codec import to_canonical_extended_json
from mongrove.ui.commands import CommandAction
from mongrove.ui.screens.document_editor import DocumentWriteDraft


@dataclass(frozen=True, slots=True)
class MutationConfirmationResult:
    """An approved draft plus any typed acknowledgement captured by the modal."""

    draft: DocumentWriteDraft
    acknowledgement: str | None


class MutationConfirmationScreen(ModalScreen[MutationConfirmationResult | None]):
    """Show the immutable write target and require a deliberate confirmation."""

    AUTO_FOCUS = "#confirm-mutation"
    BINDINGS = [
        Binding("ctrl+enter", "confirm", "Confirm", show=True),
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def __init__(
        self,
        draft: DocumentWriteDraft,
        *,
        connection_indicator: str,
        required_phrase: str | None,
    ) -> None:
        super().__init__()
        self.draft = draft
        self.connection_indicator = connection_indicator
        self.required_phrase = required_phrase

    def compose(self) -> ComposeResult:
        operation = self.draft.operation.upper()
        preview = (
            {"_id": self.draft.original_id}
            if self.draft.operation == "delete"
            else self.draft.document
        )
        with Vertical(id="mutation-confirmation-dialog"):
            yield Label(f"CONFIRM {operation}: {self.draft.namespace}", classes="dialog-title")
            yield Static(self.connection_indicator, id="mutation-target")
            yield Static("Review the exact BSON-aware mutation payload:", id="mutation-help")
            yield TextArea(
                to_canonical_extended_json(preview),
                id="mutation-preview",
                read_only=True,
                show_line_numbers=True,
                soft_wrap=False,
                tab_behavior="focus",
            )
            if self.required_phrase:
                yield Label(
                    f'Type "{self.required_phrase}" to enable confirmation.',
                    classes="field-label",
                )
                yield Input(placeholder=self.required_phrase, id="mutation-acknowledgement")
            else:
                yield Static(
                    "Select Confirm to dispatch this single-document mutation.",
                    id="mutation-confirmation-note",
                )
            yield Static("", id="mutation-status")
            with Horizontal(id="mutation-confirmation-actions"):
                yield Button("Cancel", id="cancel-mutation")
                yield Button(
                    "Confirm",
                    id="confirm-mutation",
                    variant="error" if self.draft.operation == "delete" else "primary",
                    disabled=bool(self.required_phrase),
                )

    def on_mount(self) -> None:
        if self.required_phrase:
            self.query_one("#mutation-acknowledgement", Input).focus()

    def get_command_actions(self) -> tuple[CommandAction, ...]:
        """Expose the same guarded decisions through the command palette."""

        return (
            CommandAction("Confirm mutation", "Dispatch the reviewed single-document write", self.action_confirm),
            CommandAction("Cancel mutation", "Do not dispatch the reviewed write", self.action_cancel),
        )

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id != "mutation-acknowledgement":
            return
        self.query_one("#confirm-mutation", Button).disabled = not self._acknowledged()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "confirm-mutation":
            self.action_confirm()
        elif event.button.id == "cancel-mutation":
            self.action_cancel()

    def action_confirm(self) -> None:
        if self.required_phrase and not self._acknowledged():
            self._set_status("The acknowledgement phrase must match exactly.", error=True)
            return
        acknowledgement = (
            self.query_one("#mutation-acknowledgement", Input).value
            if self.required_phrase
            else None
        )
        self.dismiss(MutationConfirmationResult(self.draft, acknowledgement))

    def action_cancel(self) -> None:
        self.dismiss(None)

    def _acknowledged(self) -> bool:
        return (
            self.query_one("#mutation-acknowledgement", Input).value
            == self.required_phrase
        )

    def _set_status(self, message: str, *, error: bool = False) -> None:
        status = self.query_one("#mutation-status", Static)
        status.update(message)
        status.set_class(error, "error")
