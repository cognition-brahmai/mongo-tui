"""Full-screen read-only document inspector."""

from __future__ import annotations

from typing import Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label

from mongotui.services.bson_codec import to_extended_json
from mongotui.ui.widgets.document_viewer import DocumentJsonViewer


class DocumentScreen(ModalScreen[None]):
    """Render one full BSON document without losing type fidelity."""

    BINDINGS = [
        Binding("escape", "close", "Close", show=False),
        Binding("c", "copy", "Copy JSON", show=True),
    ]

    def __init__(self, document: dict[str, Any], namespace: str) -> None:
        super().__init__()
        self.document = document
        self.namespace = namespace

    def compose(self) -> ComposeResult:
        with Vertical(id="document-dialog"):
            yield Label(f"DOCUMENT: {self.namespace}", classes="dialog-title")
            yield DocumentJsonViewer(self.document, id="full-document-json")
            with Horizontal(id="document-actions"):
                yield Button("Copy JSON", id="copy-document")
                yield Button("Close", id="close-document", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "copy-document":
            self.action_copy()
        elif event.button.id == "close-document":
            self.action_close()

    def action_copy(self) -> None:
        self.app.copy_to_clipboard(to_extended_json(self.document))
        self.notify("Copy requested through the terminal clipboard protocol.")

    def action_close(self) -> None:
        self.dismiss(None)
