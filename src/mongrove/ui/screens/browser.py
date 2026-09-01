"""Read-only database, collection, query, and document browser screen."""

from __future__ import annotations

import json
from dataclasses import replace
from typing import TYPE_CHECKING, Any, cast

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, DataTable, Footer, Header, Input, Label, Static, Tree

from mongrove.domain.namespace import CollectionInfo, NamespaceTreeItem
from mongrove.domain.query import FindQuery, QueryFormState, QueryValidationError, parse_find_query
from mongrove.services.bson_codec import format_cell
from mongrove.services.mongo_gateway import DocumentsPage, MongoGatewayError
from mongrove.services.query_history import QueryHistoryEntry, QueryHistoryStoreError
from mongrove.ui.screens.document import DocumentScreen
from mongrove.ui.screens.query_history import QueryHistoryScreen
from mongrove.ui.screens.query_options import QueryOptionsScreen
from mongrove.ui.widgets.document_table import DocumentTable
from mongrove.ui.widgets.document_viewer import DocumentJsonViewer

if TYPE_CHECKING:
    from mongrove.ui.app import MongroveApp


class BrowserScreen(Screen[None]):
    """Browse namespaces and execute bounded read-only find queries."""

    BINDINGS = [
        Binding("f5", "refresh", "Refresh", show=True),
        Binding("o", "open_query_options", "Query options", show=True),
        Binding("ctrl+r", "open_query_history", "Query history", show=True),
        Binding("[", "previous_page", "Previous page", show=True),
        Binding("]", "next_page", "Next page", show=True),
        Binding("ctrl+d", "disconnect", "Disconnect", show=True),
    ]
    PAGE_SIZE = 25

    def __init__(self) -> None:
        super().__init__()
        self._database_nodes: dict[str, Any] = {}
        self._loaded_databases: set[str] = set()
        self._loading_databases: set[str] = set()
        self._active_database: str | None = None
        self._active_collection: str | None = None
        self._collection_kind = "collection"
        self._query_state = QueryFormState()
        self._current_page = 0
        self._has_more = False
        self._documents: list[dict[str, Any]] = []
        self._selected_document_index: int | None = None
        self._request_id = 0
        self._sort_field: str | None = None
        self._sort_direction = 1
        self._history_request_id = 0
        self._record_history_requests: dict[int, QueryFormState] = {}

    @property
    def mongrove_app(self) -> MongroveApp:
        return cast("MongroveApp", self.app)

    @property
    def namespace(self) -> str | None:
        if self._active_database and self._active_collection:
            return f"{self._active_database}.{self._active_collection}"
        return None

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("Connecting workspace...", id="connection-banner")
        with Horizontal(id="browser-layout"):
            with Vertical(id="namespace-pane"):
                yield Label("NAMESPACES", classes="pane-title")
                yield Tree("Databases", id="namespace-tree")
            with Vertical(id="collection-pane"):
                yield Static("Select a collection from the namespace tree.", id="collection-title")
                with Horizontal(id="query-row"):
                    yield Input(
                        self._query_state.filter_text,
                        placeholder="Filter JSON or Extended JSON, for example: {\"status\": \"active\"}",
                        id="filter-input",
                    )
                    yield Button("Run", id="run-query", variant="primary")
                    yield Button("Options", id="query-options")
                    yield Button("History", id="query-history")
                yield Static("Select a collection to query.", id="query-status")
                with Horizontal(id="result-layout"):
                    yield DocumentTable(
                        id="documents-table",
                        cursor_type="row",
                        zebra_stripes=True,
                        show_row_labels=False,
                    )
                    with Vertical(id="inspector-pane"):
                        yield Static(
                            "JSON VIEWER | Tab to focus | arrows/PgUp/PgDn scroll",
                            id="inspector-hint",
                        )
                        yield DocumentJsonViewer(id="document-inspector")
                with Horizontal(id="pager"):
                    yield Button("Previous", id="previous-page", compact=True, disabled=True)
                    yield Button("Next", id="next-page", compact=True, disabled=True)
        yield Footer()

    def on_mount(self) -> None:
        tree = self.query_one("#namespace-tree", Tree)
        tree.show_root = False
        tree.root.expand()
        connection_info = self.mongrove_app.connection_info
        if connection_info is not None:
            server_version = connection_info.server_version or "unknown version"
            topology = connection_info.topology or "unknown topology"
            self.query_one("#connection-banner", Static).update(
                f"{connection_info.display_uri} | MongoDB {server_version} | {topology} | "
                f"{self.mongrove_app.connection_indicator()}"
            )
        self._load_databases()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        actions = {
            "run-query": self.action_run_query,
            "query-options": self.action_open_query_options,
            "query-history": self.action_open_query_history,
            "previous-page": self.action_previous_page,
            "next-page": self.action_next_page,
        }
        button_id = event.button.id
        if button_id is None:
            return
        action = actions.get(button_id)
        if action is not None:
            action()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "filter-input":
            self.action_run_query()

    def on_tree_node_expanded(self, event: Tree.NodeExpanded) -> None:
        data = event.node.data
        if isinstance(data, NamespaceTreeItem) and data.kind == "database":
            self._request_collections(data.database)

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        data = event.node.data
        if not isinstance(data, NamespaceTreeItem):
            return
        if data.kind == "database":
            self.query_one("#collection-title", Static).update(
                f"Database: {data.database}. Press Space to expand collections."
            )
            return
        if data.kind == "collection" and data.collection is not None:
            self._active_database = data.database
            self._active_collection = data.collection
            self._collection_kind = data.collection_kind
            self._current_page = 0
            self._set_collection_title()
            self._run_query(record_history=False)

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if event.data_table.id != "documents-table":
            return
        if 0 <= event.cursor_row < len(self._documents):
            self._selected_document_index = event.cursor_row
            self._render_document_inspector(self._documents[event.cursor_row])

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.data_table.id != "documents-table":
            return
        if not 0 <= event.cursor_row < len(self._documents):
            return
        namespace = self.namespace
        if namespace is None:
            return
        self.app.push_screen(DocumentScreen(self._documents[event.cursor_row], namespace))

    def on_data_table_header_selected(self, event: DataTable.HeaderSelected) -> None:
        if event.data_table.id != "documents-table":
            return
        fields = _document_columns(self._documents)
        if not 0 <= event.column_index < len(fields):
            return
        field = fields[event.column_index]
        if self._sort_field == field:
            self._sort_direction *= -1
        else:
            self._sort_field = field
            self._sort_direction = 1
        self._query_state = replace(
            self._query_state,
            sort_text=json.dumps({field: self._sort_direction}),
        )
        self._set_query_status(f"Sorting by {field}: {self._sort_direction}. Running query...")
        self.action_run_query()

    def action_refresh(self) -> None:
        self._load_databases()
        if self.namespace is not None:
            self.action_run_query()

    def action_run_query(self) -> None:
        self._run_query(record_history=True)

    def _run_query(self, *, record_history: bool) -> None:
        if self.namespace is None:
            self._set_query_status("Select a collection before running a query.", error=True)
            return

        self._query_state = replace(
            self._query_state,
            filter_text=self.query_one("#filter-input", Input).value,
        )
        try:
            query = parse_find_query(self._query_state)
        except QueryValidationError as error:
            self._set_query_status(str(error), error=True)
            self.query_one("#filter-input", Input).focus()
            return

        self._current_page = 0
        self._start_document_load(
            query,
            self._current_page,
            record_history=record_history,
        )

    def action_previous_page(self) -> None:
        if self._current_page <= 0 or self.namespace is None:
            return
        try:
            query = parse_find_query(self._query_state)
        except QueryValidationError as error:
            self._set_query_status(str(error), error=True)
            return
        self._start_document_load(query, self._current_page - 1)

    def action_next_page(self) -> None:
        if not self._has_more or self.namespace is None:
            return
        try:
            query = parse_find_query(self._query_state)
        except QueryValidationError as error:
            self._set_query_status(str(error), error=True)
            return
        self._start_document_load(query, self._current_page + 1)

    def action_open_query_options(self) -> None:
        self._query_state = replace(
            self._query_state,
            filter_text=self.query_one("#filter-input", Input).value,
        )
        self.app.push_screen(QueryOptionsScreen(self._query_state), self._query_options_closed)

    def action_open_query_history(self) -> None:
        if self.namespace is None or self._active_database is None or self._active_collection is None:
            self._set_query_status("Select a collection before opening query history.", error=True)
            return
        if not self.mongrove_app.query_history.enabled:
            self._set_query_status("Local query history is disabled for this session.")
            return
        target_id = self.mongrove_app.history_target_id
        if target_id is None:
            self._set_query_status("Connect before opening query history.", error=True)
            return
        self._history_request_id += 1
        request_id = self._history_request_id
        self._set_query_status("Loading local query history...")
        self._load_query_history(
            request_id,
            target_id,
            self._active_database,
            self._active_collection,
        )

    def action_disconnect(self) -> None:
        self.mongrove_app.gateway.disconnect()
        self.mongrove_app.connection_info = None
        self.mongrove_app.set_connection_context(alias=None, environment=None)
        self.app.pop_screen()

    @work(thread=True, exclusive=True, group="databases", exit_on_error=False)
    def _load_databases(self) -> None:
        try:
            databases = self.mongrove_app.gateway.list_databases()
        except MongoGatewayError as error:
            self.app.call_from_thread(self._namespace_error, str(error))
            return
        self.app.call_from_thread(self._render_databases, databases)

    @work(thread=True, exclusive=True, group="collections", exit_on_error=False)
    def _load_collections(self, database: str) -> None:
        try:
            collections = self.mongrove_app.gateway.list_collections(database)
        except MongoGatewayError as error:
            self.app.call_from_thread(self._collection_error, database, str(error))
            return
        self.app.call_from_thread(self._render_collections, database, collections)

    @work(thread=True, exclusive=True, group="documents", exit_on_error=False)
    def _load_documents(
        self,
        request_id: int,
        database: str,
        collection: str,
        query: Any,
        page: int,
    ) -> None:
        try:
            result = self.mongrove_app.gateway.fetch_documents(
                database,
                collection,
                query,
                page=page,
                page_size=self.PAGE_SIZE,
            )
        except MongoGatewayError as error:
            self.app.call_from_thread(self._document_error, request_id, str(error))
            return
        self.app.call_from_thread(self._render_documents, request_id, page, result)

    @work(thread=True, exclusive=True, group="history-read", exit_on_error=False)
    def _load_query_history(
        self,
        request_id: int,
        target_id: str,
        database: str,
        collection: str,
    ) -> None:
        try:
            entries = self.mongrove_app.query_history.list_entries(
                target_id=target_id,
                database=database,
                collection=collection,
            )
        except QueryHistoryStoreError as error:
            self.app.call_from_thread(self._history_load_error, request_id, str(error))
            return
        self.app.call_from_thread(
            self._history_loaded,
            request_id,
            entries,
            target_id,
            database,
            collection,
        )

    def _render_databases(self, databases: list[str]) -> None:
        tree = self.query_one("#namespace-tree", Tree)
        tree.root.remove_children()
        self._database_nodes.clear()
        self._loaded_databases.clear()
        self._loading_databases.clear()

        for database in databases:
            node = tree.root.add(
                database,
                data=NamespaceTreeItem(kind="database", database=database),
                allow_expand=True,
            )
            self._database_nodes[database] = node

        if not databases:
            self._set_query_status("The connected user cannot see any databases.")
            return

        startup_database = self.mongrove_app.startup_database
        if startup_database and startup_database in self._database_nodes:
            self._request_collections(startup_database)
        else:
            self._set_query_status("Choose a database, then press Space to expand its collections.")

    def _render_collections(self, database: str, collections: list[CollectionInfo]) -> None:
        self._loading_databases.discard(database)
        node = self._database_nodes.get(database)
        if node is None:
            return
        node.remove_children()
        for collection in collections:
            suffix = " [view]" if collection.kind == "view" else ""
            node.add_leaf(
                f"{collection.name}{suffix}",
                data=NamespaceTreeItem(
                    kind="collection",
                    database=collection.database,
                    collection=collection.name,
                    collection_kind=collection.kind,
                ),
            )
        self._loaded_databases.add(database)

        if not collections:
            self._set_query_status(f"{database} has no visible collections.")
            return

        startup_database = self.mongrove_app.startup_database
        startup_collection = self.mongrove_app.startup_collection
        if database == startup_database and startup_collection:
            for collection in collections:
                if collection.name == startup_collection:
                    self._active_database = database
                    self._active_collection = collection.name
                    self._collection_kind = collection.kind
                    self._set_collection_title()
                    self._run_query(record_history=False)
                    break

    def _start_document_load(
        self,
        query: FindQuery,
        page: int,
        *,
        record_history: bool = False,
    ) -> None:
        if self._active_database is None or self._active_collection is None:
            return
        self._request_id += 1
        request_id = self._request_id
        if record_history:
            self._record_history_requests[request_id] = self._query_state
        self._set_query_status("Running query...")
        self._set_pager_disabled(previous=page <= 0, next_page=True)
        self._load_documents(
            request_id,
            self._active_database,
            self._active_collection,
            query,
            page,
        )

    def _request_collections(self, database: str) -> None:
        """Mark a namespace request on the UI thread before starting its worker."""

        if database in self._loaded_databases or database in self._loading_databases:
            return
        self._loading_databases.add(database)
        self._load_collections(database)

    def _render_documents(self, request_id: int, page: int, result: DocumentsPage) -> None:
        if request_id != self._request_id:
            self._record_history_requests.pop(request_id, None)
            return
        self._current_page = page
        self._documents = result.documents
        self._has_more = result.has_more
        self._selected_document_index = 0 if result.documents else None
        self._render_document_table(result.documents)
        if result.documents:
            self._render_document_inspector(result.documents[0])
        else:
            self.query_one("#document-inspector", DocumentJsonViewer).show_message(
                "No documents matched this query."
            )

        self._set_pager_disabled(previous=page <= 0, next_page=not result.has_more)
        self._set_query_status(
            f"{len(result.documents)} shown | page {page + 1} | {result.elapsed_ms} ms | skip {result.skip}"
        )
        state = self._record_history_requests.pop(request_id, None)
        if state is not None:
            target_id = self.mongrove_app.history_target_id
            if (
                target_id is not None
                and self._active_database is not None
                and self._active_collection is not None
            ):
                self._record_query_history(
                    target_id,
                    self._active_database,
                    self._active_collection,
                    state,
                )

    def _render_document_table(self, documents: list[dict[str, Any]]) -> None:
        table = self.query_one("#documents-table", DataTable)
        table.clear(columns=True)
        fields = _document_columns(documents)
        if not fields:
            table.add_columns("Result")
            table.add_row("No documents matched the query.")
            return

        table.add_columns(*fields)
        for index, document in enumerate(documents):
            cells = [
                format_cell(document[field]) if field in document else "(missing)"
                for field in fields
            ]
            table.add_row(*cells, key=str(index))

    def _render_document_inspector(self, document: dict[str, Any]) -> None:
        self.query_one("#document-inspector", DocumentJsonViewer).show_document(document)

    def _set_collection_title(self) -> None:
        namespace = self.namespace
        if namespace is None:
            return
        kind_label = "VIEW" if self._collection_kind == "view" else "COLLECTION"
        self.query_one("#collection-title", Static).update(f"{kind_label}: {namespace}")

    def _set_pager_disabled(self, *, previous: bool, next_page: bool) -> None:
        self.query_one("#previous-page", Button).disabled = previous
        self.query_one("#next-page", Button).disabled = next_page

    def _set_query_status(self, message: str, *, error: bool = False) -> None:
        status = self.query_one("#query-status", Static)
        status.update(message)
        status.set_class(error, "error")

    def _namespace_error(self, message: str) -> None:
        self._set_query_status(f"Could not load databases: {message}", error=True)

    def _collection_error(self, database: str, message: str) -> None:
        self._loading_databases.discard(database)
        self._set_query_status(f"Could not load {database} collections: {message}", error=True)

    def _document_error(self, request_id: int, message: str) -> None:
        self._record_history_requests.pop(request_id, None)
        if request_id != self._request_id:
            return
        self._set_query_status(f"Query failed: {message}", error=True)
        self._set_pager_disabled(previous=self._current_page <= 0, next_page=not self._has_more)

    def _query_options_closed(self, state: QueryFormState | None) -> None:
        if state is None:
            return
        self._query_state = state
        self.query_one("#filter-input", Input).value = state.filter_text
        self._set_query_status("Query options updated. Press F5 or Run to execute.")

    @work(thread=True, group="history-write", exit_on_error=False)
    def _record_query_history(
        self,
        target_id: str,
        database: str,
        collection: str,
        state: QueryFormState,
    ) -> None:
        if not self.mongrove_app.query_history.enabled:
            return
        try:
            self.mongrove_app.query_history.record(
                target_id=target_id,
                database=database,
                collection=collection,
                state=state,
            )
        except QueryHistoryStoreError as error:
            self.app.call_from_thread(self._history_record_error, str(error))

    def _history_loaded(
        self,
        request_id: int,
        entries: list[QueryHistoryEntry],
        target_id: str,
        database: str,
        collection: str,
    ) -> None:
        if request_id != self._history_request_id:
            return
        self.app.push_screen(
            QueryHistoryScreen(
                entries,
                target_id=target_id,
                database=database,
                collection=collection,
            ),
            self._query_history_closed,
        )

    def _history_load_error(self, request_id: int, message: str) -> None:
        if request_id == self._history_request_id:
            self._set_query_status(message, error=True)

    def _history_record_error(self, message: str) -> None:
        self.notify(message, severity="warning")

    def _query_history_closed(self, state: QueryFormState | None) -> None:
        if state is None:
            return
        try:
            parse_find_query(state)
        except QueryValidationError as error:
            self._set_query_status(f"Stored query is invalid: {error}", error=True)
            return
        self._query_state = state
        self._sort_field = None
        self._sort_direction = 1
        self.query_one("#filter-input", Input).value = state.filter_text
        self._set_query_status("Historical query loaded. Press F5 or Run to execute.")


def _document_columns(documents: list[dict[str, Any]], *, maximum: int = 8) -> list[str]:
    """Derive stable top-level columns without scanning an unbounded result set."""

    fields: list[str] = []
    if any("_id" in document for document in documents):
        fields.append("_id")
    for document in documents:
        for field in document:
            if field not in fields:
                fields.append(field)
            if len(fields) >= maximum:
                return fields
    return fields
