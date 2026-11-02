"""可复用的界面控件（中文界面）。"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Iterable

from . import theme

KEYBOARD_ROWS = ("QWERTYUIOP", "ASDFGHJKL", "ZXCVBNM")
ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


class LampField(tk.Frame):
    """恩尼格码的 26 个灯泡。"""

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
                    padx=3,
                    pady=3,
                    sticky="nsew",
                )
                self._lamps[letter] = lamp

        for column in range(20):
            self.grid_columnconfigure(column, weight=1)

    def light(self, letter: str) -> None:
        """点亮 *letter* 对应的灯泡，并熄灭其它灯泡。"""
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
    """恩尼格码的 26 个按键。"""

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
                    pady=4,
                )
                key.grid(
                    row=row_index,
                    column=2 * key_index + row_index,
                    padx=3,
                    pady=3,
                    sticky="nsew",
                )
                self._keys[letter] = key

        for column in range(20):
            self.grid_columnconfigure(column, weight=1)


class LetterEntry(tk.Entry):
    """只接受一个字母的输入框，用于环设定与窗口位置。"""

    def __init__(
        self,
        master: tk.Misc,
        color: str,
        font,
        on_commit: Callable[[str], None],
        **kwargs,
    ) -> None:
        super().__init__(
            master,
            width=3,
            font=font,
            justify="center",
            bg=theme.PANEL_HI,
            fg=color,
            insertbackground=color,
            relief="flat",
            bd=0,
            highlightthickness=1,
            highlightbackground=theme.PANEL_LINE,
            highlightcolor=color,
            **kwargs,
        )
        self._on_commit = on_commit
        self._current = "A"
        self.bind("<Return>", self._commit)
        self.bind("<FocusOut>", self._commit)
        self.bind("<KeyRelease>", self._uppercase)

    def _uppercase(self, _event=None) -> None:
        text = self.get().upper()
        if text != self.get():
            self.delete(0, "end")
            self.insert(0, text)

    def _commit(self, _event=None) -> None:
        text = self.get().strip().upper()
        if len(text) == 1 and text in ALPHABET:
            self._current = text
            self._on_commit(text)
        else:
            self.set(self._current)

    def set(self, letter: str) -> None:
        """设置当前显示的字母（不会触发回调）。"""
        self._current = letter
        self.delete(0, "end")
        self.insert(0, letter)


class RotorControl(tk.Frame):
    """单个转子的设置：型号、环设定、窗口位置与缺口指示。"""

    def __init__(
        self,
        master: tk.Misc,
        title: str,
        on_rotor_change: Callable[[str], None],
        on_ring_change: Callable[[int], None],
        on_position_change: Callable[[int], None],
        on_ring_set: Callable[[str], None] | None = None,
        on_position_set: Callable[[str], None] | None = None,
        **kwargs,
    ) -> None:
        super().__init__(master, bg=theme.PANEL, **kwargs)
        self._on_rotor_change = on_rotor_change
        self._on_ring_change = on_ring_change
        self._on_position_change = on_position_change
        self._on_ring_set = on_ring_set or (lambda letter: None)
        self._on_position_set = on_position_set or (lambda letter: None)

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
        self.rotor_box.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(0, 4))
        self.rotor_box.bind("<<ComboboxSelected>>", self._rotor_selected)

        # 环设定
        tk.Label(
            self, text="环设定", bg=theme.PANEL, fg=theme.TEXT_FAINT,
            font=theme.Fonts.SMALL,
        ).grid(row=2, column=0, sticky="w", pady=(6, 0))
        self.ring_entry = LetterEntry(
            self, theme.CYAN, theme.Fonts.LETTER, self._on_ring_set
        )
        self.ring_entry.grid(row=3, column=0, sticky="ew", padx=(0, 6), pady=(2, 0))
        self._spinner(self._on_ring_change, row=3, column=1)

        # 窗口位置
        tk.Label(
            self, text="窗口位置", bg=theme.PANEL, fg=theme.TEXT_FAINT,
            font=theme.Fonts.SMALL,
        ).grid(row=4, column=0, sticky="w", pady=(6, 0))
        self.position_entry = LetterEntry(
            self, theme.AMBER, theme.Fonts.LETTER_BIG, self._on_position_set
        )
        self.position_entry.grid(row=5, column=0, sticky="ew", padx=(0, 6), pady=(2, 0))
        self._spinner(self._on_position_change, row=5, column=1)

        # 缺口指示
        self.notch_lamp = tk.Label(
            self,
            text="缺口",
            bg=theme.PANEL,
            fg=theme.TEXT_FAINT,
            font=theme.Fonts.SMALL,
            anchor="e",
        )
        self.notch_lamp.grid(row=6, column=0, columnspan=3, sticky="e", pady=(6, 0))

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(2, weight=1)

    # ------------------------------------------------------------- helpers
    def _spinner(self, callback: Callable[[int], None], row: int, column: int) -> None:
        """构建上下微调按钮。"""
        frame = tk.Frame(self, bg=theme.PANEL)
        frame.grid(row=row, column=column, sticky="w")
        tk.Button(
            frame,
            text="▲",
            command=lambda: callback(1),
            bg=theme.KEY_BG,
            fg=theme.TEXT_DIM,
            activebackground=theme.AMBER,
            activeforeground=theme.BG,
            relief="flat",
            bd=0,
            width=3,
            cursor="hand2",
            font=("Consolas", 9),
            pady=2,
        ).pack(side="left", fill="x", expand=True, padx=(0, 2))
        tk.Button(
            frame,
            text="▼",
            command=lambda: callback(-1),
            bg=theme.KEY_BG,
            fg=theme.TEXT_DIM,
            activebackground=theme.AMBER,
            activeforeground=theme.BG,
            relief="flat",
            bd=0,
            width=3,
            cursor="hand2",
            font=("Consolas", 9),
            pady=2,
        ).pack(side="left", fill="x", expand=True)

    def _rotor_selected(self, _event=None) -> None:
        self._on_rotor_change(self.rotor_box.get())

    # ----------------------------------------------------------------- API
    def set_rotor(self, name: str) -> None:
        self.rotor_box.set(name)

    def set_ring(self, letter: str) -> None:
        self.ring_entry.set(letter)

    def set_position(self, letter: str) -> None:
        self.position_entry.set(letter)

    def set_notch_active(self, active: bool) -> None:
        self.notch_lamp.configure(
            bg=theme.AMBER if active else theme.PANEL,
            fg=theme.BG if active else theme.TEXT_FAINT,
        )


class PlugboardWidget(tk.Frame):
    """接线板：点击两个字母即接一根电缆。"""

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
            button.grid(row=row, column=column, padx=2, pady=2)
            self._buttons[letter] = button

        tk.Label(
            self,
            text=(
                "点击一个字母，再点另一个，\n"
                "即可接上一根电缆。\n"
                "再次点击已接线的字母可拔掉。\n\n"
                "最多 10 根，同一字母只能用一次。"
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
        """把已接线的字母标记出来。"""
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
    """显示电流在机器内部的走向。"""

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
            wraplength=640,
            padx=10,
            pady=8,
        )
        self._label.pack(fill="x")

    def show(self, steps: Iterable[tuple[str, str]]) -> None:
        parts = []
        for stage, letter in steps:
            parts.append(f"{letter}")
            parts.append(f"[{stage}]")
        self._label.configure(text="  ".join(parts) if parts else "—")
