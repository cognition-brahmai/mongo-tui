"""Bounded, local query-history persistence."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, fields
from pathlib import Path
from time import time_ns
from typing import Iterator

from platformdirs import user_data_path

from mongrove.domain.query import QueryFormState
from mongrove.services.mongo_gateway import remove_uri_credentials


_STATE_FIELDS = tuple(field.name for field in fields(QueryFormState))


@dataclass(frozen=True, slots=True)
class QueryHistoryEntry:
    """One restorable query form scoped to a credential-free connection target."""

    id: int
    target_id: str
    database: str
    collection: str
    state: QueryFormState
    created_at_ms: int
    last_used_at_ms: int
    run_count: int
    favorite: bool = False
    label: str | None = None

    @property
    def namespace(self) -> str:
        return f"{self.database}.{self.collection}"


class QueryHistoryStore:
    """SQLite persistence with per-namespace and total non-favorite retention."""

    MAX_ENTRIES_PER_NAMESPACE = 30
    MAX_ENTRIES_TOTAL = 1_000
    MAX_STATE_BYTES = 64 * 1_024

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or user_data_path("mongrove") / "history.sqlite3"

    def record(
        self,
        *,
        target_id: str,
        database: str,
        collection: str,
        state: QueryFormState,
    ) -> None:
        """Record a successful explicit query, refreshing an identical entry."""

        try:
            payload = serialize_query_form_state(state)
        except TypeError as error:
            raise QueryHistoryStoreError("Query history can only store text form fields.") from error
        if len(payload.encode("utf-8")) > self.MAX_STATE_BYTES:
            raise QueryHistoryStoreError(
                "Query is too large to retain in local history (maximum 64 KiB)."
            )
        state_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        now_ms = time_ns() // 1_000_000
        try:
            with self._connection() as connection:
                connection.execute(
                    """
                    INSERT INTO query_history (
                        target_id, database_name, collection_name, state_hash,
                        state_json, created_at_ms, last_used_at_ms, run_count
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 1)
                    ON CONFLICT(target_id, database_name, collection_name, state_hash)
                    DO UPDATE SET
                        state_json = excluded.state_json,
                        last_used_at_ms = excluded.last_used_at_ms,
                        run_count = query_history.run_count + 1
                    """,
                    (
                        target_id,
                        database,
                        collection,
                        state_hash,
                        payload,
                        now_ms,
                        now_ms,
                    ),
                )
                self._prune_namespace(connection, target_id, database, collection)
                self._prune_total(connection)
        except (OSError, sqlite3.Error) as error:
            raise QueryHistoryStoreError(f"Could not save query history: {error}") from error

    def list_entries(
        self,
        *,
        target_id: str,
        database: str,
        collection: str,
    ) -> list[QueryHistoryEntry]:
        """Return newest saved entries for one target namespace."""

        try:
            with self._connection() as connection:
                rows = connection.execute(
                    """
                    SELECT
                        id, target_id, database_name, collection_name, state_json,
                        created_at_ms, last_used_at_ms, run_count, is_favorite, label
                    FROM query_history
                    WHERE target_id = ? AND database_name = ? AND collection_name = ?
                    ORDER BY is_favorite DESC, last_used_at_ms DESC, id DESC
                    """,
                    (target_id, database, collection),
                ).fetchall()
        except (OSError, sqlite3.Error) as error:
            raise QueryHistoryStoreError(f"Could not load query history: {error}") from error

        entries: list[QueryHistoryEntry] = []
        for row in rows:
            try:
                state = deserialize_query_form_state(row[4])
            except QueryHistoryStoreError:
                continue
            entries.append(
                QueryHistoryEntry(
                    id=int(row[0]),
                    target_id=str(row[1]),
                    database=str(row[2]),
                    collection=str(row[3]),
                    state=state,
                    created_at_ms=int(row[5]),
                    last_used_at_ms=int(row[6]),
                    run_count=int(row[7]),
                    favorite=bool(row[8]),
                    label=str(row[9]) if isinstance(row[9], str) and row[9] else None,
                )
            )
        return entries

    def set_favorite(self, entry_id: int, favorite: bool) -> None:
        """Set one entry's favorite state without changing its query text."""

        self._update_entry(
            "UPDATE query_history SET is_favorite = ? WHERE id = ?",
            (int(favorite), entry_id),
        )

    def rename(self, entry_id: int, label: str | None) -> None:
        """Assign an optional local label to one history entry."""

        cleaned = label.strip() if label else None
        self._update_entry(
            "UPDATE query_history SET label = ? WHERE id = ?",
            (cleaned or None, entry_id),
        )

    def delete(self, entry_id: int) -> None:
        """Remove one history entry; an absent ID is harmless."""

        try:
            with self._connection() as connection:
                connection.execute("DELETE FROM query_history WHERE id = ?", (entry_id,))
        except (OSError, sqlite3.Error) as error:
            raise QueryHistoryStoreError(f"Could not delete query history: {error}") from error

    def _update_entry(self, statement: str, parameters: tuple[object, ...]) -> None:
        try:
            with self._connection() as connection:
                connection.execute(statement, parameters)
        except (OSError, sqlite3.Error) as error:
            raise QueryHistoryStoreError(f"Could not update query history: {error}") from error

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=5)
        try:
            connection.execute("PRAGMA busy_timeout = 5000")
            self._initialize(connection)
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _initialize(connection: sqlite3.Connection) -> None:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS query_history (
                id INTEGER PRIMARY KEY,
                target_id TEXT NOT NULL,
                database_name TEXT NOT NULL,
                collection_name TEXT NOT NULL,
                state_hash TEXT NOT NULL,
                state_json TEXT NOT NULL,
                created_at_ms INTEGER NOT NULL,
                last_used_at_ms INTEGER NOT NULL,
                run_count INTEGER NOT NULL DEFAULT 1 CHECK (run_count >= 1),
                is_favorite INTEGER NOT NULL DEFAULT 0,
                label TEXT,
                UNIQUE (target_id, database_name, collection_name, state_hash)
            );
            CREATE INDEX IF NOT EXISTS query_history_scope_recent_idx
            ON query_history (
                target_id, database_name, collection_name, last_used_at_ms DESC, id DESC
            );
            CREATE INDEX IF NOT EXISTS query_history_recent_idx
            ON query_history (last_used_at_ms DESC, id DESC);
            """
        )

    def _prune_namespace(
        self,
        connection: sqlite3.Connection,
        target_id: str,
        database: str,
        collection: str,
    ) -> None:
        connection.execute(
            """
            DELETE FROM query_history
            WHERE target_id = ?
              AND database_name = ?
              AND collection_name = ?
              AND is_favorite = 0
              AND id NOT IN (
                  SELECT id FROM query_history
                  WHERE target_id = ?
                    AND database_name = ?
                    AND collection_name = ?
                    AND is_favorite = 0
                  ORDER BY last_used_at_ms DESC, id DESC
                  LIMIT ?
              )
            """,
            (
                target_id,
                database,
                collection,
                target_id,
                database,
                collection,
                self.MAX_ENTRIES_PER_NAMESPACE,
            ),
        )

    def _prune_total(self, connection: sqlite3.Connection) -> None:
        connection.execute(
            """
            DELETE FROM query_history
            WHERE is_favorite = 0
              AND id NOT IN (
                  SELECT id FROM query_history
                  WHERE is_favorite = 0
                  ORDER BY last_used_at_ms DESC, id DESC
                  LIMIT ?
              )
            """,
            (self.MAX_ENTRIES_TOTAL,),
        )


class QueryHistory:
    """Session-facing history boundary that enforces the no-history policy."""

    def __init__(self, store: QueryHistoryStore, *, enabled: bool) -> None:
        self._store = store
        self.enabled = enabled

    def record(
        self,
        *,
        target_id: str,
        database: str,
        collection: str,
        state: QueryFormState,
    ) -> None:
        if self.enabled:
            self._store.record(
                target_id=target_id,
                database=database,
                collection=collection,
                state=state,
            )

    def list_entries(
        self,
        *,
        target_id: str,
        database: str,
        collection: str,
    ) -> list[QueryHistoryEntry]:
        if not self.enabled:
            return []
        return self._store.list_entries(
            target_id=target_id,
            database=database,
            collection=collection,
        )

    def set_favorite(self, entry_id: int, favorite: bool) -> None:
        if self.enabled:
            self._store.set_favorite(entry_id, favorite)

    def rename(self, entry_id: int, label: str | None) -> None:
        if self.enabled:
            self._store.rename(entry_id, label)

    def delete(self, entry_id: int) -> None:
        if self.enabled:
            self._store.delete(entry_id)


class QueryHistoryStoreError(RuntimeError):
    """A user-facing local query-history persistence error."""


def target_id_for_uri(uri: str) -> str:
    """Hash the credential-free target identity instead of persisting its URI."""

    safe_uri = remove_uri_credentials(uri)
    return hashlib.sha256(safe_uri.encode("utf-8")).hexdigest()


def serialize_query_form_state(state: QueryFormState) -> str:
    """Serialize all raw form fields without coercing BSON/EJSON query strings."""

    values = {name: getattr(state, name) for name in _STATE_FIELDS}
    if not all(isinstance(value, str) for value in values.values()):
        raise TypeError("Query form state must contain strings.")
    return json.dumps(
        {"version": 1, "state": values},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def deserialize_query_form_state(payload: str) -> QueryFormState:
    """Deserialize one versioned raw query form safely."""

    try:
        decoded = json.loads(payload)
    except (TypeError, json.JSONDecodeError) as error:
        raise QueryHistoryStoreError("Stored query history is invalid.") from error
    state = decoded.get("state") if isinstance(decoded, dict) else None
    if (
        not isinstance(decoded, dict)
        or decoded.get("version") != 1
        or not isinstance(state, dict)
        or set(state) != set(_STATE_FIELDS)
        or not all(isinstance(state[name], str) for name in _STATE_FIELDS)
    ):
        raise QueryHistoryStoreError("Stored query history has an unsupported format.")
    return QueryFormState(**{name: state[name] for name in _STATE_FIELDS})
