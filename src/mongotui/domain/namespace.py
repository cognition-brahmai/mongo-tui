"""Models used by namespace navigation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CollectionInfo:
    """A collection or view returned by a MongoDB database."""

    database: str
    name: str
    kind: str = "collection"

    @property
    def namespace(self) -> str:
        return f"{self.database}.{self.name}"


@dataclass(frozen=True, slots=True)
class NamespaceTreeItem:
    """Data attached to a Textual Tree node."""

    kind: str
    database: str
    collection: str | None = None
    collection_kind: str = "collection"
