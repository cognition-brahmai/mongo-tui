"""Canonical EJSON editor for a single index definition."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static, TextArea

from mongrove.services.bson_codec import EjsonValidationError, parse_ejson_document
from mongrove.ui.commands import CommandAction


@dataclass(frozen=True, slots=True)
class IndexCreateDraft:
    """Parsed ordered keys and options awaiting explicit index confirmation."""

    keys: tuple[tuple[str, Any], ...]
    options: dict[str, Any]


class IndexEditorScreen(ModalScreen[IndexCreateDraft | None]):
    """Collect index keys and PyMongo create-index options without direct writes."""

    AUTO_FOCUS = "#index-keys"
    BINDINGS = [
        Binding("ctrl+enter", "continue", "Continue", show=True),
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def __init__(self, namespace: str) -> None:
        super().__init__()
        self.namespace = namespace

    def compose(self) -> ComposeResult:
        with Vertical(id="index-editor-dialog"):
            yield Label(f"CREATE INDEX: {self.namespace}", classes="dialog-title")
            yield Static(
                "Keys preserve their JSON order. Options are passed to create_index after confirmation.",
                id="index-editor-help",
            )
            yield Label("Index keys (JSON/EJSON document)", classes="field-label")
            yield TextArea(
                '{"field": 1}',
                id="index-keys",
                show_line_numbers=True,
                soft_wrap=False,
                tab_behavior="focus",
            )
            yield Label("Options (JSON/EJSON document)", classes="field-label")
            yield TextArea(
                "{}",
                id="index-options",
                show_line_numbers=True,
                soft_wrap=False,
                tab_behavior="focus",
            )
            yield Static("Review the definition, then continue to confirmation.", id="index-editor-status")
            with Horizontal(id="index-editor-actions"):
                yield Button("Cancel", id="cancel-index-editor")
                yield Button("Continue", id="continue-index-editor", variant="primary")

    def get_command_actions(self) -> tuple[CommandAction, ...]:
        return (
            CommandAction("Continue index editor", "Validate keys and options for confirmation", self.action_continue),
            CommandAction("Cancel index editor", "Discard the index definition", self.action_cancel),
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "continue-index-editor":
            self.action_continue()
        elif event.button.id == "cancel-index-editor":
            self.action_cancel()

    def action_continue(self) -> None:
        try:
            keys_document = parse_ejson_document(
                self.query_one("#index-keys", TextArea).text,
                "Index keys",
            )
            options = parse_ejson_document(
                self.query_one("#index-options", TextArea).text,
                "Index options",
            )
            keys = tuple(keys_document.items())
            if not keys or any(not name.strip() for name, _ in keys):
                raise EjsonValidationError("Index keys must contain non-empty field names.")
        except EjsonValidationError as error:
            status = self.query_one("#index-editor-status", Static)
            status.update(str(error))
            status.add_class("error")
            return
        self.dismiss(IndexCreateDraft(keys=keys, options=options))

    def action_cancel(self) -> None:
        self.dismiss(None)
