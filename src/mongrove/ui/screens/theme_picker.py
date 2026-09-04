"""Keyboard-first curated theme picker."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, OptionList, Static
from textual.widgets.option_list import Option

from mongrove.ui.themes import CURATED_THEME_OPTIONS, get_theme_option
from mongrove.ui.commands import CommandAction


class ThemePickerScreen(ModalScreen[str | None]):
    """Choose a supported theme with arrows/Enter or mouse clicks."""

    AUTO_FOCUS = "#theme-list"
    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def __init__(self, current_theme: str) -> None:
        super().__init__()
        self.current_theme = current_theme

    def compose(self) -> ComposeResult:
        current_option = get_theme_option(self.current_theme)
        current_label = current_option.label if current_option else self.current_theme
        options = [
            Option(
                _option_label(option.name, option.label, option.description, self.current_theme),
                id=option.name,
            )
            for option in CURATED_THEME_OPTIONS
        ]
        with Vertical(id="theme-picker-dialog"):
            yield Label("CHOOSE A THEME", classes="dialog-title")
            yield Static(f"Current theme: {current_label}", id="theme-current")
            yield OptionList(*options, id="theme-list")
            yield Static(
                "Use arrows and Enter, or click a theme. Your choice is saved locally.",
                id="theme-picker-help",
            )
            with Horizontal(id="theme-picker-actions"):
                yield Button("Cancel", id="cancel-theme")

    def on_mount(self) -> None:
        for index, option in enumerate(CURATED_THEME_OPTIONS):
            if option.name == self.current_theme:
                theme_list = self.query_one("#theme-list", OptionList)
                theme_list.highlighted = index
                theme_list.scroll_to_highlight()
                break

    def get_command_actions(self) -> tuple[CommandAction, ...]:
        """Allow palette users to leave the modal without a mouse."""

        return (CommandAction("Cancel theme picker", "Keep the current theme", self.action_cancel),)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option_list.id != "theme-list" or event.option.id is None:
            return
        self.dismiss(event.option.id)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel-theme":
            self.action_cancel()

    def action_cancel(self) -> None:
        self.dismiss(None)


def _option_label(name: str, label: str, description: str, current_theme: str) -> str:
    marker = "* " if name == current_theme else "  "
    return f"{marker}{label} - {description}"
