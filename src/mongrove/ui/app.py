"""The Mongrove Textual application shell."""

from __future__ import annotations

from pathlib import Path

from textual.app import App
from textual.binding import Binding

from mongrove.domain.connection import ConnectionInfo
from mongrove.services.mongo_gateway import MongoGateway, PyMongoGateway
from mongrove.services.profile_store import ProfileStore
from mongrove.services.settings_store import SettingsStore, SettingsStoreError
from mongrove.ui.themes import (
    CURATED_THEME_NAMES,
    CUSTOM_THEMES,
    DEFAULT_THEME,
    get_theme_option,
)


class MongroveApp(App[None]):
    """Own shared services and screen-level application state."""

    TITLE = "Mongrove"
    SUB_TITLE = "MongoDB terminal workspace"
    CSS_PATH = "styles/app.tcss"
    HORIZONTAL_BREAKPOINTS = [(0, "-narrow"), (100, "-wide")]
    BINDINGS = [
        Binding("ctrl+t", "choose_theme", "Theme", show=True, priority=True),
        Binding("ctrl+q", "quit", "Quit", show=True, priority=True),
    ]

    def __init__(
        self,
        *,
        gateway: MongoGateway | None = None,
        profile_store: ProfileStore | None = None,
        settings_store: SettingsStore | None = None,
        startup_uri: str | None = None,
        startup_profile: str | None = None,
        startup_database: str | None = None,
        startup_collection: str | None = None,
        read_only: bool = False,
        no_history: bool = False,
        config_dir: Path | None = None,
        theme_name: str | None = None,
    ) -> None:
        super().__init__()
        self.gateway = gateway or PyMongoGateway()
        self.profile_store = profile_store or ProfileStore(
            config_dir / "connections.json" if config_dir else None
        )
        self.settings_store = settings_store or SettingsStore(
            config_dir / "settings.json" if config_dir else None
        )
        for theme in CUSTOM_THEMES:
            self.register_theme(theme)
        self.theme = self._initial_theme(theme_name)
        self.startup_uri = startup_uri
        self.startup_profile = startup_profile
        self.startup_database = startup_database
        self.startup_collection = startup_collection
        self.read_only = read_only
        self.no_history = no_history
        self.connection_info: ConnectionInfo | None = None

    def on_mount(self) -> None:
        """Show the connection manager as the first visible screen."""

        from mongrove.ui.screens.connection import ConnectionScreen

        self.push_screen(ConnectionScreen())

    def action_choose_theme(self) -> None:
        """Open the curated theme picker from any application screen."""

        from mongrove.ui.screens.theme_picker import ThemePickerScreen

        self.push_screen(ThemePickerScreen(self.theme), self._theme_selected)

    def select_theme(self, name: str, *, persist: bool = True) -> None:
        """Apply a curated theme and optionally retain it for future sessions."""

        if name not in CURATED_THEME_NAMES:
            raise ValueError(f"Unsupported Mongrove theme: {name}")
        self.theme = name
        if persist:
            self.settings_store.save_theme(name)

    def _initial_theme(self, requested_theme: str | None) -> str:
        if requested_theme in CURATED_THEME_NAMES:
            return requested_theme
        try:
            saved_theme = self.settings_store.load_theme()
        except SettingsStoreError:
            return DEFAULT_THEME
        if saved_theme in CURATED_THEME_NAMES:
            return saved_theme
        return DEFAULT_THEME

    def _theme_selected(self, name: str | None) -> None:
        if name is None:
            return
        try:
            self.select_theme(name)
        except SettingsStoreError as error:
            self.notify(str(error), severity="error")
            return
        option = get_theme_option(name)
        label = option.label if option else name
        self.notify(f"Theme changed to {label}.")

    async def action_quit(self) -> None:
        """Close the driver client before restoring the terminal."""

        self.gateway.disconnect()
        self.exit()
