"""Focusable, scrollable BSON document rendering."""

from __future__ import annotations

from typing import Any

from rich.syntax import Syntax
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.widgets import Static

from mongrove.services.bson_codec import to_extended_json


class DocumentJsonViewer(VerticalScroll):
    """Render one document in a keyboard and mouse scrollable viewport."""

    BINDINGS = [
        Binding("up", "scroll_up", "JSON up", show=True),
        Binding("down", "scroll_down", "JSON down", show=True),
        Binding("pageup", "page_up", "JSON page up", show=True),
        Binding("pagedown", "page_down", "JSON page down", show=True),
        Binding("home", "scroll_home", "JSON top", show=True),
        Binding("end", "scroll_end", "JSON bottom", show=True),
    ]

    def __init__(
        self,
        document: dict[str, Any] | None = None,
        *,
        empty_message: str = "Select a document to inspect it.",
        id: str | None = None,
    ) -> None:
        super().__init__(id=id)
        self._document = document
        self._empty_message = empty_message

    def compose(self) -> ComposeResult:
        if self._document is None:
            yield Static(self._empty_message)
        else:
            yield Static(_document_syntax(self._document))

    def show_document(self, document: dict[str, Any]) -> None:
        """Replace content and return the viewport to the beginning."""

        self._document = document
        self.query_one(Static).update(_document_syntax(document))
        self._scroll_to_top_after_layout()

    def show_message(self, message: str) -> None:
        """Replace the current document with a plain informational message."""

        self._document = None
        self.query_one(Static).update(message)
        self._scroll_to_top_after_layout()

    def _scroll_to_top_after_layout(self) -> None:
        # Content height changes after Static refreshes, so reset after layout.
        self.call_after_refresh(
            lambda: self.scroll_home(animate=False, immediate=True)
        )


def _document_syntax(document: dict[str, Any]) -> Syntax:
    return Syntax(
        to_extended_json(document),
        "json",
        theme="monokai",
        word_wrap=True,
    )
