"""A Mongrove document table hardened for empty and loading states."""

from __future__ import annotations

from textual import events
from textual.widgets import DataTable


class DocumentTable(DataTable):
    """Avoid Textual's empty-header click edge case during asynchronous loads."""

    async def on_event(self, event: events.Event) -> None:
        """Stop header clicks that cannot resolve to a rendered column.

        Textual 8.2.8 can emit a header click for an empty DataTable while a
        collection is loading. Its registered click handler then indexes an
        empty ``ordered_columns`` list. Intercepting at the event boundary is
        necessary because the registered base handler runs before an override
        of its private click method.
        """

        if isinstance(event, events.Click):
            columns = self.ordered_columns
            meta = event.style.meta
            if isinstance(meta, dict) and meta.get("row") == -1:
                column_index = meta.get("column")
                if not isinstance(column_index, int) or not 0 <= column_index < len(columns):
                    event.stop()
                    return

        await super().on_event(event)
