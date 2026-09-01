"""The Mongrove Textual application shell."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path
from typing import cast

from textual.app import App, SystemCommand
from textual.binding import Binding
from textual.screen import Screen

from mongrove.domain.connection import ConnectionInfo
from mongrove.domain.session import SessionPolicy, normalize_environment
from mongrove.services.mongo_gateway import MongoGateway, PyMongoGateway
from mongrove.services.profile_store import ProfileStore
from mongrove.services.query_history import QueryHistory, QueryHistoryStore, target_id_for_uri
from mongrove.services.settings_store import SettingsStore, SettingsStoreError
from mongrove.ui.themes import (
    CURATED_THEME_NAMES,
    CUSTOM_THEMES,
    DEFAULT_THEME,
    get_theme_option,
)
from mongrove.ui.commands import CommandAction


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
        history_store: QueryHistoryStore | None = None,
        startup_uri: str | None = None,
        startup_profile: str | None = None,
        startup_database: str | None = None,
        startup_collection: str | None = None,
        read_only: bool = False,
        no_history: bool = False,
        config_dir: Path | None = None,
        theme_name: str | None = None,
        environment: str | None = None,
        allow_production_writes: bool = False,
    ) -> None:
        super().__init__()
        self.gateway = gateway or PyMongoGateway()
        self.profile_store = profile_store or ProfileStore(
            config_dir / "connections.json" if config_dir else None
        )
        self.settings_store = settings_store or SettingsStore(
            config_dir / "settings.json" if config_dir else None
        )
        self.query_history = QueryHistory(
            history_store
            or QueryHistoryStore(config_dir / "history.sqlite3" if config_dir else None),
            enabled=not no_history,
        )
        for theme in CUSTOM_THEMES:
            self.register_theme(theme)
        self.theme = self._initial_theme(theme_name)
        self.startup_uri = startup_uri
        self.startup_profile = startup_profile
        self.startup_database = startup_database
        self.startup_collection = startup_collection
        self._configured_environment = normalize_environment(environment)
        self._requested_read_only = read_only
        self._allow_production_writes = allow_production_writes
        self._no_history = no_history
        self.connection_alias: str | None = None
        self.session_policy = SessionPolicy(
            environment=self._configured_environment,
            requested_read_only=read_only,
            allow_production_writes=allow_production_writes,
            no_history=no_history,
        )
        self.connection_info: ConnectionInfo | None = None
        self.export_in_progress = False

    @property
    def read_only(self) -> bool:
        """Whether the current session policy prohibits all mutations."""

        return self.session_policy.writes_blocked

    @property
    def no_history(self) -> bool:
        """Whether local query persistence is disabled for this session."""

        return self.session_policy.no_history

    def set_connection_context(
        self,
        *,
        alias: str | None,
        environment: str | None,
    ) -> None:
        """Apply the selected target label before opening a collection workspace."""

        self.connection_alias = alias.strip() if alias and alias.strip() else None
        effective_environment = normalize_environment(environment)
        if effective_environment is None:
            effective_environment = self._configured_environment
        self.session_policy = SessionPolicy(
            environment=effective_environment,
            requested_read_only=self._requested_read_only,
            allow_production_writes=self._allow_production_writes,
            no_history=self._no_history,
        )

    def connection_indicator(self) -> str:
        """Return an unambiguous, credential-free target indicator for the UI."""

        labels = [f"ENV {self.session_policy.environment_label}"]
        if self.connection_alias:
            labels.insert(0, f"ALIAS {self.connection_alias}")
        labels.append(self.session_policy.write_mode_label)
        return " | ".join(labels)

    @property
    def history_target_id(self) -> str | None:
        """Return the credential-free target ID used to scope local history."""

        if self.connection_info is None:
            return None
        return target_id_for_uri(self.connection_info.display_uri)

    def on_mount(self) -> None:
        """Show the connection manager as the first visible screen."""

        from mongrove.ui.screens.connection import ConnectionScreen

        self.push_screen(ConnectionScreen())

    def get_system_commands(self, screen: Screen) -> Iterable[SystemCommand]:
        """Expose global and active-screen operations through Ctrl+P."""

        yield from super().get_system_commands(screen)
        yield SystemCommand(
            "Choose Mongrove theme",
            "Open the curated Mongrove theme picker",
            self.action_choose_theme,
        )
        actions = getattr(screen, "get_command_actions", None)
        if not callable(actions):
            return
        action_provider = cast(Callable[[], Iterable[CommandAction]], actions)
        for action in action_provider():
            if not isinstance(action, CommandAction):
                continue
            yield SystemCommand(
                action.title,
                action.help,
                action.callback,
                discover=action.discover,
            )

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

        if self.export_in_progress:
            self.notify("Wait for export cleanup to finish before quitting.", severity="warning")
            return
        self.gateway.disconnect()
        self.exit()
