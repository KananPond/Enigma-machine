"""Reusable widgets for the Enigma desktop application."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Iterable

from . import theme

KEYBOARD_ROWS = ("QWERTYUIOP", "ASDFGHJKL", "ZXCVBNM")
ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


class LampField(tk.Frame):
    """The 26 lamps of the Enigma lamp field."""

    def __init__(self, master: tk.Misc, **kwargs) -> None:
        super().__init__(master, bg=theme.PANEL, **kwargs)
        self._lamps: dict[str, tk.Label] = {}
        self._lit: str | None = None

        for row_index, row in enumerate(KEYBOARD_ROWS):
            for key_index, letter in enumerate(row):
                lamp = tk.Label(
                    self,
                    text=letter,
                    bg=theme.PANEL_HI,
                    fg=theme.TEXT_FAINT,
                    font=theme.Fonts.LAMP,
                    width=2,
                    height=1,
                    relief="flat",
                    bd=0,
                )
                lamp.grid(
                    row=row_index,
                    column=2 * key_index + row_index,
                    padx=2,
                    pady=2,
                    sticky="nsew",
                )
                self._lamps[letter] = lamp

        for column in range(20):
            self.grid_columnconfigure(column, weight=1)

    def light(self, letter: str) -> None:
        """Light the lamp of *letter* and switch off all others."""
        self.clear()
        lamp = self._lamps.get(letter)
        if lamp is not None:
            lamp.configure(bg=theme.AMBER, fg=theme.BG)
            self._lit = letter

    def clear(self) -> None:
        for lamp in self._lamps.values():
            lamp.configure(bg=theme.PANEL_HI, fg=theme.TEXT_FAINT)
        self._lit = None


class Keyboard(tk.Frame):
    """The 26 keys of the Enigma keyboard."""

    def __init__(
        self,
        master: tk.Misc,
        on_press: Callable[[str], None],
        **kwargs,
    ) -> None:
        super().__init__(master, bg=theme.PANEL, **kwargs)
        self._on_press = on_press
        self._keys: dict[str, tk.Button] = {}

        for row_index, row in enumerate(KEYBOARD_ROWS):
            for key_index, letter in enumerate(row):
                key = tk.Button(
                    self,
                    text=letter,
                    command=lambda l=letter: self._on_press(l),
                    bg=theme.KEY_BG,
                    fg=theme.TEXT,
                    activebackground=theme.KEY_ACTIVE,
                    activeforeground=theme.AMBER,
                    font=theme.Fonts.KEY,
                    relief="flat",
                    bd=0,
                    highlightthickness=1,
                    highlightbackground=theme.KEY_BORDER,
                    highlightcolor=theme.AMBER,
                    cursor="hand2",
                    width=3,
                )
                key.grid(
                    row=row_index,
                    column=2 * key_index + row_index,
                    padx=2,
                    pady=2,
                    sticky="nsew",
                )
                self._keys[letter] = key

        for column in range(20):
            self.grid_columnconfigure(column, weight=1)


class RotorControl(tk.Frame):
    """Settings for one rotor: type, ring setting, position and notch lamp."""

    def __init__(
        self,
        master: tk.Misc,
        title: str,
        on_rotor_change: Callable[[str], None],
        on_ring_change: Callable[[int], None],
        on_position_change: Callable[[int], None],
        **kwargs,
    ) -> None:
        super().__init__(master, bg=theme.PANEL, **kwargs)
        self._on_rotor_change = on_rotor_change
        self._on_ring_change = on_ring_change
        self._on_position_change = on_position_change

        tk.Label(
            self,
            text=title,
            bg=theme.PANEL,
            fg=theme.TEXT_DIM,
            font=theme.Fonts.SECTION,
        ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 4))

        self.rotor_box = ttk.Combobox(
            self,
            values=["I", "II", "III", "IV", "V", "VI", "VII", "VIII"],
            state="readonly",
            width=6,
            font=theme.Fonts.MONO,
            style="Enigma.TCombobox",
        )
        self.rotor_box.grid(row=1, column=0, columnspan=3, sticky="ew")
        self.rotor_box.bind("<<ComboboxSelected>>", self._rotor_selected)

        # ring setting
        tk.Label(
            self, text="Ring", bg=theme.PANEL, fg=theme.TEXT_FAINT, font=theme.Fonts.SMALL
        ).grid(row=2, column=0, sticky="w", pady=(6, 0))
        self.ring_label = tk.Label(
            self,
            text="A",
            bg=theme.PANEL_HI,
            fg=theme.CYAN,
            font=theme.Fonts.LETTER,
            width=3,
        )
        self.ring_label.grid(row=3, column=0, sticky="ew", padx=(0, 4))
        self._spinner(self.ring_label, self._on_ring_change, row=3, column=1)

        # position
        tk.Label(
            self, text="Position", bg=theme.PANEL, fg=theme.TEXT_FAINT, font=theme.Fonts.SMALL
        ).grid(row=4, column=0, sticky="w", pady=(6, 0))
        self.position_label = tk.Label(
            self,
            text="A",
            bg=theme.PANEL_HI,
            fg=theme.AMBER,
            font=theme.Fonts.LETTER_BIG,
            width=3,
        )
        self.position_label.grid(row=5, column=0, sticky="ew", padx=(0, 4))
        self._spinner(self.position_label, self._on_position_change, row=5, column=1)

        # turnover notch indicator
        self.notch_lamp = tk.Label(
            self,
            text="NOTCH",
            bg=theme.PANEL,
            fg=theme.TEXT_FAINT,
            font=theme.Fonts.SMALL,
            anchor="e",
        )
        self.notch_lamp.grid(row=6, column=0, columnspan=3, sticky="e", pady=(4, 0))

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(2, weight=1)

    # ------------------------------------------------------------- helpers
    def _spinner(
        self, target: tk.Label, callback: Callable[[int], None], row: int, column: int
    ) -> None:
        """Build the little ▲/▼ buttons that step a value by one."""
        frame = tk.Frame(self, bg=theme.PANEL)
        frame.grid(row=row, column=column, sticky="w")
        tk.Button(
            frame,
            text="▲",
            command=lambda: callback(1),
            bg=theme.KEY_BG,
            fg=theme.TEXT_DIM,
            activebackground=theme.KEY_ACTIVE,
            activeforeground=theme.AMBER,
            relief="flat",
            bd=0,
            width=2,
            cursor="hand2",
            font=("Consolas", 7),
        ).pack(side="left", fill="x", expand=True)
        tk.Button(
            frame,
            text="▼",
            command=lambda: callback(-1),
            bg=theme.KEY_BG,
            fg=theme.TEXT_DIM,
            activebackground=theme.KEY_ACTIVE,
            activeforeground=theme.AMBER,
            relief="flat",
            bd=0,
            width=2,
            cursor="hand2",
            font=("Consolas", 7),
        ).pack(side="left", fill="x", expand=True)

    def _rotor_selected(self, _event=None) -> None:
        self._on_rotor_change(self.rotor_box.get())

    # ----------------------------------------------------------------- API
    def set_rotor(self, name: str) -> None:
        self.rotor_box.set(name)

    def set_ring(self, letter: str) -> None:
        self.ring_label.configure(text=letter)

    def set_position(self, letter: str) -> None:
        self.position_label.configure(text=letter)

    def set_notch_active(self, active: bool) -> None:
        self.notch_lamp.configure(
            bg=theme.AMBER if active else theme.PANEL,
            fg=theme.BG if active else theme.TEXT_FAINT,
        )


class PlugboardWidget(tk.Frame):
    """The Steckerbrett: click two letters to plug a cable between them."""

    def __init__(
        self,
        master: tk.Misc,
        on_change: Callable[[], None],
        **kwargs,
    ) -> None:
        super().__init__(master, bg=theme.PANEL, **kwargs)
        self._on_change = on_change
        self._buttons: dict[str, tk.Button] = {}
        self._pending: str | None = None

        grid = tk.Frame(self, bg=theme.PANEL)
        grid.pack(side="left", anchor="n")
        for index, letter in enumerate(ALPHABET):
            row, column = divmod(index, 5)
            button = tk.Button(
                grid,
                text=letter,
                command=lambda l=letter: self._click(l),
                bg=theme.PLUG_BG,
                fg=theme.TEXT_DIM,
                activebackground=theme.PLUG_SELECT,
                activeforeground=theme.BG,
                relief="flat",
                bd=0,
                width=2,
                font=theme.Fonts.SMALL,
                cursor="hand2",
            )
            button.grid(row=row, column=column, padx=1, pady=1)
            self._buttons[letter] = button

        tk.Label(
            self,
            text=(
                "Click a letter, then a second one,\n"
                "to run a cable between them.\n"
                "Click a plugged letter again to\n"
                "remove its cable.\n\n"
                "At most ten cables, no letter twice."
            ),
            bg=theme.PANEL,
            fg=theme.TEXT_FAINT,
            font=theme.Fonts.SMALL,
            justify="left",
            anchor="nw",
        ).pack(side="left", padx=(16, 0), pady=4)

    def _click(self, letter: str) -> None:
        if self._pending is None:
            self._pending = letter
        elif self._pending == letter:
            self._pending = None
        else:
            self._on_change(letter, self._pending)
            self._pending = None
        self._refresh_pending()

    def _refresh_pending(self) -> None:
        for letter, button in self._buttons.items():
            if self._pending == letter:
                button.configure(bg=theme.PLUG_SELECT, fg=theme.BG)

    def set_plugged(self, plugged: Iterable[str]) -> None:
        """Mark the given letters as plugged in."""
        plugged = set(plugged)
        for letter, button in self._buttons.items():
            if letter in plugged:
                button.configure(bg=theme.CYAN_DIM, fg=theme.CYAN)
            elif letter != self._pending:
                button.configure(bg=theme.PLUG_BG, fg=theme.TEXT_DIM)

    def clear_pending(self) -> None:
        self._pending = None
        self._refresh_pending()


class SignalTrace(tk.Frame):
    """Shows the path the current takes through the machine."""

    def __init__(self, master: tk.Misc, **kwargs) -> None:
        super().__init__(master, bg=theme.PANEL, **kwargs)
        self._label = tk.Label(
            self,
            text="—",
            bg=theme.PANEL_HI,
            fg=theme.TEXT_DIM,
            font=theme.Fonts.MONO,
            anchor="w",
            justify="left",
            wraplength=320,
            padx=8,
            pady=6,
        )
        self._label.pack(fill="x")

    def show(self, steps: Iterable[tuple[str, str]]) -> None:
        parts = []
        for stage, letter in steps:
            parts.append(f"{letter}")
            parts.append(f"[{stage}]")
        self._label.configure(text="  ".join(parts) if parts else "—")
