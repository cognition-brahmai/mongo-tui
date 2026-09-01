"""Explicit confirmation modal for collection index mutations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static, TextArea

from mongrove.services.bson_codec import to_canonical_extended_json
from mongrove.ui.commands import CommandAction


@dataclass(frozen=True, slots=True)
class IndexConfirmationResult:
    """A user-approved index action with any typed target acknowledgement."""

    acknowledgement: str | None


class IndexConfirmationScreen(ModalScreen[IndexConfirmationResult | None]):
    """Show an immutable index action preview before gateway dispatch."""

    AUTO_FOCUS = "#confirm-index-action"
    BINDINGS = [
        Binding("ctrl+enter", "confirm", "Confirm", show=True),
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def __init__(
        self,
        *,
        title: str,
        connection_indicator: str,
        preview: dict[str, Any],
        required_phrase: str | None,
        destructive: bool,
    ) -> None:
        super().__init__()
        self.confirmation_title = title
        self.connection_indicator = connection_indicator
        self.preview = preview
        self.required_phrase = required_phrase
        self.destructive = destructive

    def compose(self) -> ComposeResult:
        with Vertical(id="index-confirmation-dialog"):
            yield Label(self.confirmation_title, classes="dialog-title")
            yield Static(self.connection_indicator, id="index-confirmation-target")
            yield Static("Review the exact index action:", id="index-confirmation-help")
            yield TextArea(
                to_canonical_extended_json(self.preview),
                id="index-confirmation-preview",
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
                yield Input(placeholder=self.required_phrase, id="index-acknowledgement")
            yield Static("", id="index-confirmation-status")
            with Horizontal(id="index-confirmation-actions"):
                yield Button("Cancel", id="cancel-index-action")
                yield Button(
                    "Confirm",
                    id="confirm-index-action",
                    variant="error" if self.destructive else "primary",
                    disabled=bool(self.required_phrase),
                )

    def on_mount(self) -> None:
        if self.required_phrase:
            self.query_one("#index-acknowledgement", Input).focus()

    def get_command_actions(self) -> tuple[CommandAction, ...]:
        return (
            CommandAction("Confirm index action", "Dispatch the reviewed index mutation", self.action_confirm),
            CommandAction("Cancel index action", "Do not dispatch the reviewed index mutation", self.action_cancel),
        )

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "index-acknowledgement":
            self.query_one("#confirm-index-action", Button).disabled = not self._acknowledged()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "confirm-index-action":
            self.action_confirm()
        elif event.button.id == "cancel-index-action":
            self.action_cancel()

    def action_confirm(self) -> None:
        if self.required_phrase and not self._acknowledged():
            self._set_status("The acknowledgement phrase must match exactly.", error=True)
            return
        acknowledgement = (
            self.query_one("#index-acknowledgement", Input).value
            if self.required_phrase
            else None
        )
        self.dismiss(IndexConfirmationResult(acknowledgement))

    def action_cancel(self) -> None:
        self.dismiss(None)

    def _acknowledged(self) -> bool:
        return self.query_one("#index-acknowledgement", Input).value == self.required_phrase

    def _set_status(self, message: str, *, error: bool = False) -> None:
        status = self.query_one("#index-confirmation-status", Static)
        status.update(message)
        status.set_class(error, "error")
