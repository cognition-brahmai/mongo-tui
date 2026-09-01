"""Shared fake services for Mongrove tests."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from bson import ObjectId

from mongrove.domain.connection import ConnectionInfo
from mongrove.domain.explain import ExplainResult, normalize_aggregation_explain, normalize_find_explain
from mongrove.domain.index import IndexInfo, IndexUsage, IndexUsageReport
from mongrove.domain.namespace import CollectionInfo
from mongrove.domain.pipeline import AggregationPipeline
from mongrove.domain.query import FindQuery
from mongrove.domain.session import SessionPolicy
from mongrove.services.mongo_gateway import (
    DeleteDocumentResult,
    AggregationPage,
    DocumentsPage,
    FindStreamResult,
    InsertDocumentResult,
    MongoGatewayError,
    ReplaceDocumentResult,
)


class FakeGateway:
    """In-memory MongoDB gateway used by UI tests."""

    def __init__(self) -> None:
        self.connected_uri: str | None = None
        self.disconnect_calls = 0
        self.queries: list[tuple[str, str, FindQuery, int, int]] = []
        self.insert_calls: list[tuple[str, str, dict[str, Any]]] = []
        self.replace_calls: list[tuple[str, str, Any, dict[str, Any]]] = []
        self.delete_calls: list[tuple[str, str, Any]] = []
        self.stream_calls: list[tuple[str, str, FindQuery]] = []
        self.aggregation_calls: list[tuple[str, str, AggregationPipeline, int, int]] = []
        self.find_explain_calls: list[tuple[str, str, FindQuery, int]] = []
        self.aggregation_explain_calls: list[tuple[str, str, AggregationPipeline, int]] = []
        self.index_create_calls: list[tuple[str, str, list[tuple[str, Any]], dict[str, Any]]] = []
        self.index_drop_calls: list[tuple[str, str, str]] = []
        self.indexes: list[IndexInfo] = [
            IndexInfo(
                name="_id_",
                keys=(("_id", 1),),
                unique=True,
                sparse=False,
                hidden=False,
                raw={"name": "_id_", "key": {"_id": 1}, "unique": True},
            ),
            IndexInfo(
                name="status_1",
                keys=(("status", 1),),
                unique=False,
                sparse=False,
                hidden=False,
                raw={"name": "status_1", "key": {"status": 1}},
            ),
        ]
        self.documents: list[dict[str, Any]] = [
            {
                "_id": ObjectId("65ba0aa00000000000000001"),
                "name": "Alice",
                "status": "active",
                "profile": {"age": 34, "city": "London"},
            },
            {
                "_id": ObjectId("65ba0aa00000000000000002"),
                "name": "Robert",
                "status": "active",
                "profile": {"age": 28, "city": "Paris"},
            },
        ]

    def connect(self, uri: str, *, timeout_ms: int = 10_000) -> ConnectionInfo:
        self.connected_uri = uri
        return ConnectionInfo(
            display_uri="mongodb://localhost:27017",
            server_version="8.0.3",
            topology="Standalone",
            is_writable_primary=True,
        )

    def disconnect(self) -> None:
        self.disconnect_calls += 1
        self.connected_uri = None

    def list_databases(self) -> list[str]:
        return ["admin", "app"]

    def list_collections(self, database: str) -> list[CollectionInfo]:
        if database == "app":
            return [CollectionInfo(database="app", name="customers")]
        return []

    def fetch_documents(
        self,
        database: str,
        collection: str,
        query: FindQuery,
        *,
        page: int,
        page_size: int,
    ) -> DocumentsPage:
        self.queries.append((database, collection, query, page, page_size))
        skip, fetch_size = query.page_request(page, page_size)
        result = self.documents[skip : skip + fetch_size]
        has_more = len(result) > page_size
        return DocumentsPage(
            documents=result[:page_size],
            has_more=has_more,
            elapsed_ms=4,
            skip=skip,
        )

    def insert_document(
        self,
        database: str,
        collection: str,
        document: dict[str, Any],
        *,
        policy: SessionPolicy,
    ) -> InsertDocumentResult:
        self._assert_writes_allowed(policy)
        stored = deepcopy(document)
        stored.setdefault("_id", ObjectId())
        self.documents.append(stored)
        self.insert_calls.append((database, collection, deepcopy(document)))
        return InsertDocumentResult(inserted_id=stored["_id"])

    def replace_document(
        self,
        database: str,
        collection: str,
        original_id: Any,
        replacement: dict[str, Any],
        *,
        policy: SessionPolicy,
    ) -> ReplaceDocumentResult:
        self._assert_writes_allowed(policy)
        self.replace_calls.append((database, collection, original_id, deepcopy(replacement)))
        for index, document in enumerate(self.documents):
            if document.get("_id") == original_id:
                modified = int(document != replacement)
                self.documents[index] = deepcopy(replacement)
                return ReplaceDocumentResult(matched_count=1, modified_count=modified)
        return ReplaceDocumentResult(matched_count=0, modified_count=0)

    def delete_document(
        self,
        database: str,
        collection: str,
        original_id: Any,
        *,
        policy: SessionPolicy,
    ) -> DeleteDocumentResult:
        self._assert_writes_allowed(policy)
        self.delete_calls.append((database, collection, original_id))
        for index, document in enumerate(self.documents):
            if document.get("_id") == original_id:
                del self.documents[index]
                return DeleteDocumentResult(deleted_count=1)
        return DeleteDocumentResult(deleted_count=0)

    def stream_documents(
        self,
        database: str,
        collection: str,
        query: FindQuery,
        *,
        consume,
        is_cancelled,
        batch_size: int = 100,
    ) -> FindStreamResult:
        self.stream_calls.append((database, collection, query))
        documents_seen = 0
        documents = self.documents[query.skip :]
        if query.limit is not None:
            documents = documents[: query.limit]
        for document in documents:
            if is_cancelled():
                return FindStreamResult(documents_seen=documents_seen, cancelled=True)
            consume(deepcopy(document))
            documents_seen += 1
        return FindStreamResult(documents_seen=documents_seen, cancelled=is_cancelled())

    def aggregate_documents(
        self,
        database: str,
        collection: str,
        pipeline: AggregationPipeline,
        *,
        page_size: int = 100,
        max_time_ms: int = 60_000,
    ) -> AggregationPage:
        if pipeline.has_write_stage:
            raise MongoGatewayError("Aggregation write stages are unavailable in FakeGateway.")
        self.aggregation_calls.append(
            (database, collection, pipeline, page_size, max_time_ms)
        )
        documents = deepcopy(self.documents[: page_size + 1])
        has_more = len(documents) > page_size
        return AggregationPage(
            documents=documents[:page_size],
            has_more=has_more,
            elapsed_ms=4,
        )

    def explain_find(
        self,
        database: str,
        collection: str,
        query: FindQuery,
        *,
        max_time_ms: int = 5_000,
    ) -> ExplainResult:
        self.find_explain_calls.append((database, collection, query, max_time_ms))
        raw = {
            "queryPlanner": {
                "winningPlan": {
                    "stage": "FETCH",
                    "inputStage": {"stage": "IXSCAN", "indexName": "status_1"},
                },
                "rejectedPlans": [],
            }
        }
        return normalize_find_explain(raw, query, 3)

    def explain_aggregation(
        self,
        database: str,
        collection: str,
        pipeline: AggregationPipeline,
        *,
        max_time_ms: int = 5_000,
    ) -> ExplainResult:
        if pipeline.has_write_stage:
            raise MongoGatewayError("Aggregation write stages are unavailable in FakeGateway.")
        self.aggregation_explain_calls.append((database, collection, pipeline, max_time_ms))
        raw = {
            "stages": [
                {
                    "$cursor": {
                        "queryPlanner": {
                            "winningPlan": {"stage": "COLLSCAN"},
                            "rejectedPlans": [],
                        }
                    }
                }
            ]
        }
        return normalize_aggregation_explain(raw, pipeline, 4)

    def list_indexes(self, database: str, collection: str) -> list[IndexInfo]:
        return deepcopy(self.indexes)

    def index_usage(
        self,
        database: str,
        collection: str,
        *,
        max_time_ms: int = 5_000,
    ) -> IndexUsageReport:
        return IndexUsageReport(
            available=True,
            usages=(
                IndexUsage(name="_id_", operations=7, since="2026-09-01T00:00:00Z"),
                IndexUsage(name="status_1", operations=3, since="2026-09-01T00:00:00Z"),
            ),
        )

    def create_index(
        self,
        database: str,
        collection: str,
        keys: list[tuple[str, Any]],
        options: dict[str, Any],
        *,
        policy: SessionPolicy,
    ) -> str:
        self._assert_writes_allowed(policy)
        self.index_create_calls.append((database, collection, deepcopy(keys), deepcopy(options)))
        configured_name = options.get("name")
        name = (
            configured_name
            if isinstance(configured_name, str)
            else "_".join(f"{field}_{value}" for field, value in keys)
        )
        self.indexes.append(
            IndexInfo(
                name=name,
                keys=tuple(keys),
                unique=bool(options.get("unique", False)),
                sparse=bool(options.get("sparse", False)),
                hidden=bool(options.get("hidden", False)),
                raw={"name": name, "key": dict(keys), **deepcopy(options)},
            )
        )
        return name

    def drop_index(
        self,
        database: str,
        collection: str,
        name: str,
        *,
        policy: SessionPolicy,
    ) -> None:
        self._assert_writes_allowed(policy)
        self.index_drop_calls.append((database, collection, name))
        self.indexes = [index for index in self.indexes if index.name != name]

    @staticmethod
    def _assert_writes_allowed(policy: SessionPolicy) -> None:
        if policy.write_block_reason is not None:
            raise MongoGatewayError(policy.write_block_reason)
