"""Tests for safe find-query parsing and paging."""

from __future__ import annotations

import pytest
from bson import ObjectId

from mongrove.domain.query import QueryFormState, QueryValidationError, parse_find_query


def test_parse_find_query_accepts_extended_json_and_options() -> None:
    query = parse_find_query(
        QueryFormState(
            filter_text='{"_id": {"$oid": "65ba0aa00000000000000001"}}',
            projection_text='{"name": 1, "status": 1}',
            sort_text='{"createdAt": -1, "_id": 1}',
            collation_text='{"locale": "en", "strength": 2}',
            skip_text="10",
            limit_text="50",
            max_time_ms_text="5000",
        )
    )

    assert query.filter["_id"] == ObjectId("65ba0aa00000000000000001")
    assert query.projection == {"name": 1, "status": 1}
    assert query.sort == [("createdAt", -1), ("_id", 1)]
    assert query.collation == {"locale": "en", "strength": 2}
    assert query.skip == 10
    assert query.limit == 50
    assert query.max_time_ms == 5000


def test_parse_find_query_rejects_invalid_sort_direction() -> None:
    with pytest.raises(QueryValidationError, match="must be 1 or -1"):
        parse_find_query(QueryFormState(sort_text='{"name": 0}'))


def test_parse_find_query_rejects_non_document_filter() -> None:
    with pytest.raises(QueryValidationError, match="Filter must be a JSON document"):
        parse_find_query(QueryFormState(filter_text="[]"))


def test_page_request_fetches_one_extra_document() -> None:
    query = parse_find_query(QueryFormState())

    assert query.page_request(page=0, page_size=25) == (0, 26)
    assert query.page_request(page=2, page_size=25) == (50, 26)


def test_page_request_respects_total_limit() -> None:
    query = parse_find_query(QueryFormState(skip_text="5", limit_text="30"))

    assert query.page_request(page=0, page_size=25) == (5, 26)
    assert query.page_request(page=1, page_size=25) == (30, 5)
    assert query.page_request(page=2, page_size=25) == (55, 0)


def test_zero_limit_uses_mongodb_unbounded_limit_convention() -> None:
    query = parse_find_query(QueryFormState(limit_text="0"))

    assert query.limit is None
    assert query.page_request(page=1, page_size=25) == (25, 26)
