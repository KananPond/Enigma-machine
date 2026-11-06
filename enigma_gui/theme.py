"""Colours, fonts and small drawing helpers shared by the interface.

The look is meant to feel like a piece of equipment: graphite panels, brass
lettering, a warm lamp.  Everything is drawn with plain Tk primitives - no
images, no external toolkit - so the machine starts on any Windows box with
nothing installed.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont

# ------------------------------------------------------------------ palette
BG = "#08090c"
BG_HEADER = "#0d0f14"
PANEL = "#12151b"
PANEL_ALT = "#171b22"
PANEL_DEEP = "#0b0d11"
LINE = "#232833"
LINE_SOFT = "#1a1e26"
LINE_STRONG = "#333b48"

TEXT = "#e9ecf1"
TEXT_SOFT = "#b9c0cd"
MUTED = "#858e9e"
FAINT = "#5a6272"

BRASS = "#d3a955"
BRASS_DIM = "#8d7031"
AMBER = "#ffb85c"
AMBER_DIM = "#7a5622"
GLOW = "#3a2a12"

TEAL = "#58c8bf"
ROSE = "#e2685f"
GREEN = "#6fcf8f"

CABLE_COLORS = (
    "#e0b464", "#6fc7bd", "#e08a72", "#9db4e0", "#c894d8",
    "#8fce8a", "#e0c46a", "#7fb2d8", "#d69ab4", "#a9c47f",
)

#: Typeface for the machine lettering, in order of preference.
_MONO_CANDIDATES = ("Cascadia Mono", "Consolas", "DejaVu Sans Mono", "Courier New")
_UI_CANDIDATES = ("Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI", "TkDefaultFont")


def _pick(candidates: tuple[str, ...], fallback: str = "TkDefaultFont") -> str:
    try:
        available = set(tkfont.families())
    except tk.TclError:  # pragma: no cover - only before a root exists
        return fallback
    for name in candidates:
        if name in available:
            return name
    return fallback


class Fonts:
    """The handful of fonts the interface uses, resolved once."""

    def __init__(self) -> None:
        self.mono_family = _pick(_MONO_CANDIDATES)
        self.ui_family = _pick(_UI_CANDIDATES)

    def mono(self, size: int, weight: str = "normal") -> tuple[str, int, str]:
        return (self.mono_family, size, weight)

    def ui(self, size: int, weight: str = "normal") -> tuple[str, int, str]:
        return (self.ui_family, size, weight)

    # named styles -------------------------------------------------------
    @property
    def brand(self) -> tuple[str, int, str]:
        return self.mono(17, "bold")

    @property
    def title(self) -> tuple[str, int, str]:
        return self.ui(9, "bold")

    @property
    def body(self) -> tuple[str, int, str]:
        return self.ui(9)

    @property
    def small(self) -> tuple[str, int, str]:
        return self.ui(8)

    @property
    def tiny(self) -> tuple[str, int, str]:
        return self.ui(7)

    @property
    def letter(self) -> tuple[str, int, str]:
        return self.mono(20, "bold")

    @property
    def letter_big(self) -> tuple[str, int, str]:
        return self.mono(24, "bold")

    @property
    def keycap(self) -> tuple[str, int, str]:
        return self.mono(10, "bold")


# ------------------------------------------------------------------- shapes
def round_rect(
    canvas: tk.Canvas,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    radius: float = 10,
    **kwargs,
) -> int:
    """Draw a rounded rectangle and return its item id."""
    radius = max(0, min(radius, (x2 - x1) / 2, (y2 - y1) / 2))
    points = [
        x1 + radius, y1,
        x2 - radius, y1,
        x2, y1,
        x2, y1 + radius,
        x2, y2 - radius,
        x2, y2,
        x2 - radius, y2,
        x1 + radius, y2,
        x1, y2,
        x1, y2 - radius,
        x1, y1 + radius,
        x1, y1,
    ]
    return canvas.create_polygon(points, smooth=True, splinesteps=12, **kwargs)


def text(
    canvas: tk.Canvas,
    x: float,
    y: float,
    value: str,
    font,
    fill: str = TEXT,
    anchor: str = "center",
    **kwargs,
) -> int:
    return canvas.create_text(x, y, text=value, font=font, fill=fill, anchor=anchor, **kwargs)


def glow_text(
    canvas: tk.Canvas,
    x: float,
    y: float,
    value: str,
    font,
    fill: str = AMBER,
    halo: str = GLOW,
    anchor: str = "center",
) -> list[int]:
    """Text with a cheap halo: the same string drawn four times, faded."""
    ids: list[int] = []
    for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        ids.append(
            canvas.create_text(
                x + dx, y + dy, text=value, font=font, fill=halo, anchor=anchor
            )
        )
    ids.append(
        canvas.create_text(x, y, text=value, font=font, fill=fill, anchor=anchor)
    )
    return ids


def mix(color_a: str, color_b: str, ratio: float) -> str:
    """Blend two ``#rrggbb`` colours; *ratio* 0 gives *color_a*."""
    ratio = max(0.0, min(1.0, ratio))
    a = tuple(int(color_a[i : i + 2], 16) for i in (1, 3, 5))
    b = tuple(int(color_b[i : i + 2], 16) for i in (1, 3, 5))
    return "#%02x%02x%02x" % tuple(
        round(a[i] + (b[i] - a[i]) * ratio) for i in range(3)
    )


def alpha(color: str, ratio: float, over: str = BG) -> str:
    """Fake transparency by blending *color* into *over*."""
    return mix(over, color, ratio)
