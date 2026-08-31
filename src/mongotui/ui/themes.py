"""Curated Textual themes for MongoTUI."""

from __future__ import annotations

from dataclasses import dataclass

from textual.theme import Theme


@dataclass(frozen=True, slots=True)
class ThemeOption:
    """A user-facing theme entry in the curated picker."""

    name: str
    label: str
    description: str


CUSTOM_THEMES = (
    Theme(
        name="mongotui-night",
        primary="#00ED64",
        secondary="#1EB980",
        warning="#FFD166",
        error="#FF6B6B",
        success="#00ED64",
        accent="#5EF2A6",
        foreground="#E7FFF0",
        background="#07110C",
        surface="#0D1912",
        panel="#12251A",
        boost="#1A3827",
        dark=True,
    ),
    Theme(
        name="mongotui-forest",
        primary="#6EE7B7",
        secondary="#2F855A",
        warning="#F6AD55",
        error="#FC8181",
        success="#68D391",
        accent="#9AE6B4",
        foreground="#E8FFF1",
        background="#07120D",
        surface="#0D1B14",
        panel="#14261B",
        boost="#1C3526",
        dark=True,
    ),
    Theme(
        name="mongotui-ocean",
        primary="#4FD1C5",
        secondary="#2B6CB0",
        warning="#F6C177",
        error="#F87171",
        success="#5EEAD4",
        accent="#7DD3FC",
        foreground="#E8F3FF",
        background="#08111F",
        surface="#0F1C2E",
        panel="#142841",
        boost="#1E3A5F",
        dark=True,
    ),
    Theme(
        name="mongotui-paper",
        primary="#00684A",
        secondary="#157A5A",
        warning="#A15C00",
        error="#B42318",
        success="#00684A",
        accent="#005E9C",
        foreground="#1D2A24",
        background="#F7F7F2",
        surface="#FFFFFF",
        panel="#E7EEE8",
        boost="#D5E4D8",
        dark=False,
        text_alpha=1.0,
    ),
)

CURATED_THEME_OPTIONS = (
    ThemeOption(
        "mongotui-night",
        "Mongo Night",
        "Deep charcoal with MongoDB green accents.",
    ),
    ThemeOption(
        "mongotui-forest",
        "Emerald Forest",
        "Low-glare green for long server sessions.",
    ),
    ThemeOption(
        "mongotui-ocean",
        "Midnight Ocean",
        "Navy foundation with cyan focus states.",
    ),
    ThemeOption(
        "mongotui-paper",
        "Mongo Paper",
        "Warm light mode with high-contrast text.",
    ),
    ThemeOption(
        "dracula",
        "Dracula",
        "Popular purple dark theme from Textual.",
    ),
    ThemeOption(
        "nord",
        "Nord",
        "Cool arctic dark palette from Textual.",
    ),
    ThemeOption(
        "solarized-dark",
        "Solarized Dark",
        "Low-contrast dark palette for reduced eye strain.",
    ),
    ThemeOption(
        "solarized-light",
        "Solarized Light",
        "Light Solarized palette for bright environments.",
    ),
    ThemeOption(
        "gruvbox",
        "Gruvbox",
        "Warm retro dark palette from Textual.",
    ),
    ThemeOption(
        "ansi-dark",
        "ANSI Dark",
        "16-color fallback for limited terminal emulators.",
    ),
    ThemeOption(
        "ansi-light",
        "ANSI Light",
        "16-color light fallback for limited terminal emulators.",
    ),
)

DEFAULT_THEME = "mongotui-night"
CURATED_THEME_NAMES = tuple(option.name for option in CURATED_THEME_OPTIONS)
THEME_OPTIONS_BY_NAME = {option.name: option for option in CURATED_THEME_OPTIONS}


def get_theme_option(name: str) -> ThemeOption | None:
    """Return display metadata for a supported theme name."""

    return THEME_OPTIONS_BY_NAME.get(name)
