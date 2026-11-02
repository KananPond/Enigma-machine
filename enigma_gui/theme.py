"""Colours, fonts and widget styling for the Enigma GUI."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

# ---------------------------------------------------------------- palette
BG = "#12161f"
PANEL = "#1b212c"
PANEL_HI = "#232b38"
PANEL_LINE = "#2e3746"

TEXT = "#e7ebf2"
TEXT_DIM = "#8b95a8"
TEXT_FAINT = "#5d6779"

AMBER = "#f2b134"
AMBER_SOFT = "#7a5a1c"
AMBER_DIM = "#3d3115"

CYAN = "#4cc9f0"
CYAN_DIM = "#22414f"
GREEN = "#57cc99"

KEY_BG = "#232b38"
KEY_ACTIVE = "#38445a"
KEY_BORDER = "#39435a"

PLUG_BG = "#1f2733"
PLUG_SELECT = "#4cc9f0"

RED = "#e05561"


def pick_font(family: str, size: int, weight: str = "normal") -> tuple[str, int, str]:
    """Return a font tuple, falling back to the default family."""
    return (family, size, weight)


class Fonts:
    """Font tuples used throughout the application."""

    TITLE = ("Consolas", 22, "bold")
    SUBTITLE = ("Consolas", 10)
    SECTION = ("Consolas", 10, "bold")
    LETTER = ("Consolas", 13, "bold")
    LETTER_BIG = ("Consolas", 22, "bold")
    LAMP = ("Consolas", 12, "bold")
    KEY = ("Consolas", 12, "bold")
    MONO = ("Consolas", 11)
    SMALL = ("Consolas", 9)
    STATUS = ("Consolas", 10)


def build_styles(root: tk.Misc) -> ttk.Style:
    """Create the ttk styles used by the application."""
    style = ttk.Style(root)
    style.theme_use("clam")

    style.configure(
        "Enigma.TCombobox",
        fieldbackground=PANEL_HI,
        background=PANEL_HI,
        foreground=TEXT,
        arrowcolor=TEXT,
        bordercolor=PANEL_LINE,
        lightcolor=PANEL_LINE,
        darkcolor=PANEL_LINE,
        padding=2,
    )
    style.map(
        "Enigma.TCombobox",
        fieldbackground=[("readonly", PANEL_HI)],
        foreground=[("readonly", TEXT)],
        selectbackground=[("readonly", PANEL_HI)],
        selectforeground=[("readonly", TEXT)],
    )
    style.configure(
        "Enigma.TEntry",
        fieldbackground=PANEL_HI,
        foreground=TEXT,
        insertcolor=AMBER,
        bordercolor=PANEL_LINE,
        lightcolor=PANEL_LINE,
        darkcolor=PANEL_LINE,
    )
    for name in ("Vertical.TScrollbar", "Horizontal.TScrollbar"):
        style.configure(
            name,
            troughcolor=PANEL,
            background=PANEL_HI,
            arrowcolor=TEXT_DIM,
            bordercolor=PANEL,
            lightcolor=PANEL_HI,
            darkcolor=PANEL_HI,
        )
    return style
