"""Lossless EJSON editor for inserting or replacing one document."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, cast

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static, TextArea

from mongrove.services.bson_codec import (
    EjsonValidationError,
    bson_values_equal,
    parse_ejson_document,
    to_canonical_extended_json,
)
from mongrove.ui.commands import CommandAction


DocumentWriteOperation = Literal["insert", "replace", "delete"]
EditorOperation = Literal["insert", "replace"]


@dataclass(frozen=True, slots=True)
class DocumentWriteDraft:
    """A parsed, unconfirmed single-document mutation."""

    operation: DocumentWriteOperation
    namespace: str
    document: dict[str, Any] | None
    original_id: Any = None


class DocumentEditorScreen(ModalScreen[DocumentWriteDraft | None]):
    """Edit canonical EJSON before it is shown to the confirmation screen."""

    AUTO_FOCUS = "#document-editor"
    BINDINGS = [
        Binding("ctrl+enter", "continue", "Continue", show=True),
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def __init__(
        self,
        operation: EditorOperation,
        namespace: str,
        *,
        document: dict[str, Any] | None = None,
        original_id: Any = None,
    ) -> None:
        super().__init__()
        self.operation = operation
        self.namespace = namespace
        self.original_id = original_id
        self._initial_document = document if document is not None else {}

    def compose(self) -> ComposeResult:
        label = "INSERT DOCUMENT" if self.operation == "insert" else "REPLACE DOCUMENT"
        with Vertical(id="document-editor-dialog"):
            yield Label(f"{label}: {self.namespace}", classes="dialog-title")
            yield Static(
                "Canonical Extended JSON preserves BSON values while you edit.",
                id="document-editor-help",
            )
            yield TextArea(
                to_canonical_extended_json(self._initial_document),
                id="document-editor",
                show_line_numbers=True,
                soft_wrap=False,
                tab_behavior="focus",
            )
            yield Static("Review the document, then continue to confirmation.", id="editor-status")
            with Horizontal(id="document-editor-actions"):
                yield Button("Cancel", id="cancel-document-editor")
                yield Button("Continue", id="continue-document-editor", variant="primary")

    def get_command_actions(self) -> tuple[CommandAction, ...]:
        """Expose editing decisions through the active modal's palette."""

        return (
            CommandAction("Continue document edit", "Validate EJSON and review the mutation", self.action_continue),
            CommandAction("Cancel document edit", "Discard the current document draft", self.action_cancel),
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "continue-document-editor":
            self.action_continue()
        elif event.button.id == "cancel-document-editor":
            self.action_cancel()

    def action_continue(self) -> None:
        label = "Document" if self.operation == "insert" else "Replacement document"
        try:
            document = parse_ejson_document(
                self.query_one("#document-editor", TextArea).text,
                label,
            )
            if self.operation == "replace":
                self._validate_replacement_id(document)
        except EjsonValidationError as error:
            status = self.query_one("#editor-status", Static)
            status.update(str(error))
            status.add_class("error")
            return
        self.dismiss(
            DocumentWriteDraft(
                operation=cast(DocumentWriteOperation, self.operation),
                namespace=self.namespace,
                document=document,
                original_id=self.original_id,
            )
        )

    def action_cancel(self) -> None:
        self.dismiss(None)

    def _validate_replacement_id(self, document: dict[str, Any]) -> None:
        if "_id" not in document:
            raise EjsonValidationError("Replacement document must retain its _id field.")
        if not bson_values_equal(document["_id"], self.original_id):
            raise EjsonValidationError("The _id field is immutable and cannot be changed.")
