"""Connection manager screen."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, DataTable, Footer, Header, Input, Label, Static

from mongotui.domain.connection import ConnectionInfo, ConnectionProfile
from mongotui.services.mongo_gateway import MongoGatewayError, remove_uri_credentials
from mongotui.services.profile_store import ProfileStoreError
from mongotui.ui.screens.browser import BrowserScreen

if TYPE_CHECKING:
    from mongotui.ui.app import MongoTUIApp


class ConnectionScreen(Screen[None]):
    """Connect to MongoDB and select a locally saved endpoint."""

    AUTO_FOCUS = "#uri-input"
    BINDINGS = [
        Binding("ctrl+enter", "connect", "Connect", show=True),
        Binding("ctrl+s", "save_profile", "Save profile", show=True),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._profiles: list[ConnectionProfile] = []

    @property
    def mongo_app(self) -> MongoTUIApp:
        return cast("MongoTUIApp", self.app)

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="connection-layout"):
            with Vertical(id="saved-profiles-pane"):
                yield Label("SAVED CONNECTIONS", classes="pane-title")
                yield DataTable(
                    id="profiles-table",
                    cursor_type="row",
                    zebra_stripes=True,
                    show_row_labels=False,
                )
                yield Static(
                    "Profiles retain endpoints, never URI passwords.",
                    id="profile-help",
                )
            with Vertical(id="connection-form"):
                yield Label("CONNECT TO MONGODB", classes="pane-title")
                yield Label("Connection name", classes="field-label")
                yield Input(placeholder="Production EU", id="connection-name")
                yield Label("MongoDB URI", classes="field-label")
                yield Input(
                    placeholder="mongodb://localhost:27017",
                    id="uri-input",
                )
                yield Static(
                    "Use an environment variable or prompt for sensitive credentials when possible.",
                    id="credential-note",
                )
                with Horizontal(id="connection-actions"):
                    yield Button("Test and Connect", id="connect-button", variant="primary")
                    yield Button("Save Profile", id="save-profile-button")
                yield Static("Enter a MongoDB URI to begin.", id="connection-status")
        yield Footer()

    def on_mount(self) -> None:
        self._render_profiles()
        startup_uri = self.mongo_app.startup_uri
        if startup_uri:
            self.query_one("#uri-input", Input).value = startup_uri
            self.call_after_refresh(self.action_connect)
            return

        startup_profile = self.mongo_app.startup_profile
        if startup_profile:
            self._select_profile_by_name(startup_profile)

    def on_screen_resume(self) -> None:
        if self.mongo_app.connection_info is None:
            self._set_status("Disconnected. Select a profile or enter a URI.")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "connect-button":
            self.action_connect()
        elif event.button.id == "save-profile-button":
            self.action_save_profile()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.data_table.id != "profiles-table":
            return
        if not 0 <= event.cursor_row < len(self._profiles):
            return
        profile = self._profiles[event.cursor_row]
        self.query_one("#connection-name", Input).value = profile.name
        self.query_one("#uri-input", Input).value = profile.uri
        self._set_status(f'Loaded profile "{profile.name}". Credentials are requested separately.')

    def action_connect(self) -> None:
        uri = self.query_one("#uri-input", Input).value.strip()
        if not uri:
            self._set_status("Enter a MongoDB URI before connecting.", error=True)
            self.query_one("#uri-input", Input).focus()
            return
        self._set_connection_controls(disabled=True)
        self._set_status("Connecting and running a server ping...")
        self._connect(uri)

    def action_save_profile(self) -> None:
        uri = self.query_one("#uri-input", Input).value.strip()
        name = self.query_one("#connection-name", Input).value.strip()
        if not uri:
            self._set_status("Enter a MongoDB URI before saving a profile.", error=True)
            return
        if not name:
            name = _profile_name_from_uri(uri)
            self.query_one("#connection-name", Input).value = name

        try:
            self.mongo_app.profile_store.save(ConnectionProfile(name=name, uri=uri))
        except ProfileStoreError as error:
            self._set_status(str(error), error=True)
            return

        self._render_profiles()
        self._set_status("Profile saved without URI credentials.")

    @work(thread=True, exclusive=True, group="connection", exit_on_error=False)
    def _connect(self, uri: str) -> None:
        try:
            connection_info = self.mongo_app.gateway.connect(uri)
        except MongoGatewayError as error:
            self.app.call_from_thread(self._connection_failed, str(error))
            return
        self.app.call_from_thread(self._connection_succeeded, connection_info)

    def _connection_failed(self, message: str) -> None:
        self._set_connection_controls(disabled=False)
        self._set_status(f"Connection failed: {message}", error=True)

    def _connection_succeeded(self, connection_info: ConnectionInfo) -> None:
        self._set_connection_controls(disabled=False)
        self.mongo_app.connection_info = connection_info
        self._set_status("Connected. Loading namespaces...")
        self.mongo_app.push_screen(BrowserScreen())

    def _render_profiles(self) -> None:
        table = self.query_one("#profiles-table", DataTable)
        try:
            self._profiles = self.mongo_app.profile_store.load()
        except ProfileStoreError as error:
            self._profiles = []
            self._set_status(str(error), error=True)

        table.clear(columns=True)
        table.add_columns("Name", "Endpoint")
        if not self._profiles:
            table.add_row("No saved profiles", "Save an endpoint to see it here.")
            return
        for profile in self._profiles:
            name = f"* {profile.name}" if profile.favorite else profile.name
            table.add_row(name, profile.uri, key=profile.name)

    def _select_profile_by_name(self, name: str) -> None:
        for index, profile in enumerate(self._profiles):
            if profile.name.casefold() == name.casefold():
                self.query_one("#connection-name", Input).value = profile.name
                self.query_one("#uri-input", Input).value = profile.uri
                self._set_status(f'Loaded profile "{profile.name}".')
                self.query_one("#profiles-table", DataTable).move_cursor(row=index)
                return
        self._set_status(f'No saved profile named "{name}" was found.', error=True)

    def _set_connection_controls(self, *, disabled: bool) -> None:
        self.query_one("#connect-button", Button).disabled = disabled
        self.query_one("#save-profile-button", Button).disabled = disabled

    def _set_status(self, message: str, *, error: bool = False) -> None:
        status = self.query_one("#connection-status", Static)
        status.update(message)
        status.set_class(error, "error")


def _profile_name_from_uri(uri: str) -> str:
    endpoint = remove_uri_credentials(uri)
    without_scheme = endpoint.split("://", maxsplit=1)[-1]
    return without_scheme.split("/", maxsplit=1)[0] or "MongoDB connection"
