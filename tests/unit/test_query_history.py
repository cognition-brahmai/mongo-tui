"""Tests for bounded local query history."""

from __future__ import annotations

import pytest

from mongrove.domain.query import QueryFormState
from mongrove.services.query_history import (
    QueryHistory,
    QueryHistoryStore,
    QueryHistoryStoreError,
    deserialize_query_form_state,
    serialize_query_form_state,
    target_id_for_uri,
)


def _state(number: int) -> QueryFormState:
    return QueryFormState(
        filter_text=f'{{"number": {number}, "name": "Miyuki"}}',
        projection_text='{"name": 1}',
        sort_text='{"number": -1}',
        collation_text='{"locale": "en"}',
        skip_text=str(number),
        limit_text="25",
        max_time_ms_text="3000",
    )


def test_query_form_serialization_round_trips_every_raw_field() -> None:
    state = QueryFormState(
        filter_text=' {"$comment": "cafe\u0301"} ',
        projection_text="",
        sort_text="  ",
        collation_text='{"locale":"fr"}',
        skip_text="0",
        limit_text="",
        max_time_ms_text="60000",
    )

    assert deserialize_query_form_state(serialize_query_form_state(state)) == state
    with pytest.raises(QueryHistoryStoreError, match="unsupported format"):
        deserialize_query_form_state('{"version":2,"state":{}}')


def test_history_deduplicates_runs_and_prunes_each_namespace(tmp_path) -> None:
    store = QueryHistoryStore(tmp_path / "history.sqlite3")
    target = "target-a"
    for number in range(31):
        store.record(target_id=target, database="app", collection="customers", state=_state(number))

    entries = store.list_entries(target_id=target, database="app", collection="customers")

    assert len(entries) == 30
    assert {entry.state.filter_text for entry in entries} == {
        _state(number).filter_text for number in range(1, 31)
    }

    store.record(target_id=target, database="app", collection="customers", state=_state(30))
    repeated = store.list_entries(target_id=target, database="app", collection="customers")

    assert len(repeated) == 30
    assert repeated[0].state == _state(30)
    assert repeated[0].run_count == 2


def test_history_scope_favorites_and_disabled_service_are_safe(tmp_path) -> None:
    path = tmp_path / "history.sqlite3"
    store = QueryHistoryStore(path)
    store.record(target_id="target-a", database="app", collection="customers", state=_state(1))
    store.record(target_id="target-b", database="app", collection="customers", state=_state(2))
    entry = store.list_entries(target_id="target-a", database="app", collection="customers")[0]

    store.set_favorite(entry.id, True)
    store.rename(entry.id, "Important customers")
    favorite = store.list_entries(target_id="target-a", database="app", collection="customers")[0]
    other_target = store.list_entries(target_id="target-b", database="app", collection="customers")

    assert favorite.favorite is True
    assert favorite.label == "Important customers"
    assert other_target[0].state == _state(2)

    disabled_path = tmp_path / "disabled.sqlite3"
    disabled = QueryHistory(QueryHistoryStore(disabled_path), enabled=False)
    disabled.record(target_id="target", database="app", collection="customers", state=_state(3))
    assert disabled_path.exists() is False
    assert disabled.list_entries(target_id="target", database="app", collection="customers") == []


def test_history_target_hash_never_persists_uri_credentials(tmp_path) -> None:
    secret_uri = "mongodb://reader:top-secret@db.internal:27017/app"
    target_id = target_id_for_uri(secret_uri)
    store = QueryHistoryStore(tmp_path / "history.sqlite3")
    store.record(target_id=target_id, database="app", collection="customers", state=_state(1))

    assert "top-secret" not in target_id
    assert "top-secret" not in store.path.read_text(encoding="utf-8", errors="ignore")
