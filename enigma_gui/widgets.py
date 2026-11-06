"""The parts the machine is drawn from.

Everything here is a Tk canvas with its own hit testing, so the whole
interface can be painted flat and dark instead of looking like a dialog box.
Each widget takes plain data (the machine state dictionary, a trace, a
letter) and never talks to the rest of the program by itself.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont
from typing import Callable, Sequence

from .theme import (
    AMBER,
    BG,
    BRASS,
    CABLE_COLORS,
    FAINT,
    Fonts,
    LINE,
    LINE_SOFT,
    LINE_STRONG,
    MUTED,
    PANEL,
    PANEL_ALT,
    PANEL_DEEP,
    ROSE,
    TEXT,
    TEXT_SOFT,
    alpha,
    mix,
    round_rect,
    text,
)

#: The keyboard of the machine, as printed on the real keys.
KEY_ROWS: tuple[str, ...] = ("QWERTZUIO", "ASDFGHJK", "PYXCVBNML")


def _glow(canvas: tk.Canvas, x: float, y: float, value: str, font, fill: str,
          halo: str, tag: str = "") -> None:
    """Text with a cheap halo: the same string drawn four times, faded."""
    for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        canvas.create_text(x + dx, y + dy, text=value, font=font, fill=halo)
    canvas.create_text(x, y, text=value, font=font, fill=fill, tags=tag)


# ===================================================================== button
class Button(tk.Canvas):
    """A flat button that draws itself, with hover and press states."""

    KINDS = {
        "primary": (BRASS, "#1d1608"),
        "ghost": (None, TEXT_SOFT),
        "subtle": (PANEL_ALT, TEXT_SOFT),
        "danger": (None, ROSE),
    }

    def __init__(
        self,
        master,
        text_value: str,
        command: Callable[[], None] | None = None,
        kind: str = "ghost",
        fonts: Fonts | None = None,
        width: int | None = None,
        height: int = 30,
        font=None,
        radius: int = 7,
    ) -> None:
        self.fonts = fonts or Fonts()
        self.label = text_value
        self.command = command
        self.kind = kind
        self.radius = radius
        self._font = font or self.fonts.ui(9, "bold")
        self._enabled = True
        self._hover = False
        self._pressed = False
        self._height = height
        super().__init__(
            master,
            width=width or 80,
            height=height,
            bg=master["bg"],
            highlightthickness=0,
            bd=0,
            cursor="hand2",
        )
        if width is None:
            measured = tkfont.Font(root=self, font=self._font).measure(text_value)
            self._width = max(64, measured + 26)
            self.configure(width=self._width)
        else:
            self._width = width
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Configure>", self._on_configure)
        self._draw()

    def _on_configure(self, event) -> None:
        if event.width > 2 and event.width != self._width:
            self._width = event.width
            self._draw()

    # ------------------------------------------------------------------ api
    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled
        self.configure(cursor="hand2" if enabled else "arrow")
        self._draw()

    def set_text(self, value: str) -> None:
        self.label = value
        self._draw()

    def set_kind(self, kind: str) -> None:
        self.kind = kind
        self._draw()

    # --------------------------------------------------------------- events
    def _on_enter(self, _event=None) -> None:
        self._hover = True
        self._draw()

    def _on_leave(self, _event=None) -> None:
        self._hover = False
        self._pressed = False
        self._draw()

    def _on_press(self, _event=None) -> None:
        if not self._enabled:
            return
        self._pressed = True
        self._draw()

    def _on_release(self, _event=None) -> None:
        was_pressed = self._pressed
        self._pressed = False
        self._draw()
        if was_pressed and self._enabled and self.command is not None:
            self.command()

    # ---------------------------------------------------------------- paint
    def _draw(self) -> None:
        self.delete("all")
        background = self["bg"]
        filled, fg = self.KINDS.get(self.kind, self.KINDS["ghost"])

        if filled is None:
            fill = PANEL if not self._hover else PANEL_ALT
            outline = LINE if not self._hover else LINE_STRONG
        else:
            fill = filled if not self._pressed else mix(filled, "#000000", 0.12)
            outline = mix(filled, "#ffffff", 0.22)

        if not self._enabled:
            fill = mix(background, PANEL, 0.5)
            outline = LINE_SOFT
            fg = FAINT

        offset = 1 if self._pressed else 0
        round_rect(self, 1, 1 + offset, self._width - 1, self._height - 1 + offset,
                   self.radius, fill=fill, outline=outline)
        if self.kind == "primary" and self._enabled:
            round_rect(self, 4, 3 + offset, self._width - 4, 5 + offset, 2,
                       fill=mix(fill, "#ffffff", 0.4), outline="")
        text(self, self._width / 2, self._height / 2 + offset, self.label, self._font, fg)


# ================================================================== rotor deck
class RotorDeck(tk.Canvas):
    """Reflector plus three rotors, each with a window, a ring and a notch."""

    HEIGHT = 192

    def __init__(
        self,
        master,
        rotors: Sequence[str],
        reflectors: Sequence[str],
        on_rotor: Callable[[int, str], None],
        on_ring: Callable[[int, int], None],
        on_window: Callable[[int, int], None],
        on_reflector: Callable[[str], None],
        fonts: Fonts | None = None,
    ) -> None:
        self.fonts = fonts or Fonts()
        super().__init__(master, height=self.HEIGHT, bg=PANEL, highlightthickness=0, bd=0)
        self.rotor_names = list(rotors)
        self.reflector_names = list(reflectors)
        self.on_rotor = on_rotor
        self.on_ring = on_ring
        self.on_window = on_window
        self.on_reflector = on_reflector
        self.state: dict | None = None
        self._hits: list[tuple[float, float, float, float, Callable[[], None]]] = []
        self._menu: tk.Menu | None = None
        self.bind("<Configure>", lambda _event: self.redraw())
        self.bind("<Button-1>", self._on_click)

    # ---------------------------------------------------------------- state
    def update_state(self, state: dict, animate: bool = True) -> None:
        previous = None if self.state is None else self.state.get("positions")
        self.state = state
        self.redraw()
        if animate and previous and previous != state["positions"]:
            for slot in range(3):
                if previous[slot] != state["positions"][slot]:
                    self.itemconfigure(f"win{slot}", fill="#fff0d0")
                    self.after(
                        130,
                        lambda s=slot: self.itemconfigure(f"win{s}", fill="#ffd79a"),
                    )

    # ------------------------------------------------------------ hit tests
    def _hit(self, x1, y1, x2, y2, action: Callable[[], None]) -> None:
        self._hits.append((x1, y1, x2, y2, action))

    def _on_click(self, event) -> None:
        for x1, y1, x2, y2, action in reversed(self._hits):
            if x1 <= event.x <= x2 and y1 <= event.y <= y2:
                action()
                return

    # ---------------------------------------------------------------- paint
    def redraw(self) -> None:
        self.delete("all")
        self._hits.clear()
        if not self.state:
            return
        width = self.winfo_width()
        if width < 200:
            width = 900
        pad, gap, reflector_width = 10, 9, 108
        rotor_width = (width - pad * 2 - reflector_width - gap * 3) / 3
        top, height = 6, self.HEIGHT - 12

        self._draw_reflector(pad, top, reflector_width, height, width)
        x = pad + reflector_width + gap
        roles = ("左转子", "中转子", "右转子")
        for slot in range(3):
            self._draw_rotor(slot, roles[slot], x, top, rotor_width, height)
            x += rotor_width + gap

    def _card(self, x1, y1, x2, y2) -> None:
        round_rect(self, x1, y1, x2, y2, 11, fill=PANEL_ALT, outline=LINE)
        round_rect(self, x1 + 1, y1 + 1, x2 - 1, y1 + 4, 2,
                   fill=mix(PANEL_ALT, "#ffffff", 0.035), outline="")

    def _draw_reflector(self, x1, y1, width, height, canvas_width) -> None:
        self._card(x1, y1, x1 + width, y1 + height)
        text(self, x1 + 11, y1 + 15, "反射器 UKW", self.fonts.small, FAINT, anchor="w")
        value = self.state["reflector"]
        _glow(self, x1 + width / 2, y1 + 52, value, self.fonts.mono(20, "bold"),
              BRASS, alpha(BRASS, 0.13, PANEL_ALT))
        for index in range(3):
            round_rect(self, x1 + 14, y1 + 84 + index * 8, x1 + width - 14,
                       y1 + 88 + index * 8, 2,
                       fill=mix(PANEL_ALT, BRASS, 0.12 + index * 0.12), outline="")
        text(self, x1 + 11, y1 + height - 13, "无自连点 · 互逆", self.fonts.tiny,
             FAINT, anchor="w")
        self._hit(x1, y1 + 28, x1 + width, y1 + 80,
                  lambda: self._open_menu("reflector", self.reflector_names, value,
                                          x1, y1 + 70))

    def _draw_rotor(self, slot: int, role: str, x1, y1, width, height) -> None:
        self._card(x1, y1, x1 + width, y1 + height)
        text(self, x1 + 10, y1 + 15, role, self.fonts.small, FAINT, anchor="w")

        name = self.state["rotors"][slot]
        name_x1, name_x2 = x1 + width - 52, x1 + width - 8
        round_rect(self, name_x1, y1 + 6, name_x2, y1 + 24, 5,
                   fill=mix(PANEL_ALT, BRASS, 0.10), outline=mix(PANEL_ALT, BRASS, 0.35))
        text(self, (name_x1 + name_x2) / 2, y1 + 15, f"W{name}",
             self.fonts.mono(8, "bold"), BRASS)
        self._hit(name_x1, y1 + 6, name_x2, y1 + 24,
                  lambda: self._open_menu("rotor", self.rotor_names, name,
                                          name_x1, y1 + 26, slot=slot))

        # window -----------------------------------------------------------
        win_x1, win_x2 = x1 + 8, x1 + width - 8
        win_y1, win_y2 = y1 + 30, y1 + 88
        round_rect(self, win_x1, win_y1, win_x2, win_y2, 8, fill=PANEL_DEEP, outline=LINE_SOFT)
        round_rect(self, win_x1 + 1, win_y1 + 1, win_x2 - 1, win_y1 + 3, 1,
                   fill=mix(PANEL_DEEP, "#ffffff", 0.05), outline="")
        letter = self.state["positions"][slot]
        _glow(self, (win_x1 + win_x2) / 2 - 6, (win_y1 + win_y2) / 2, letter,
              self.fonts.mono(20, "bold"), "#ffd79a", alpha(AMBER, 0.18, PANEL_DEEP),
              tag=f"win{slot}")

        step_x2 = win_x2 - 5
        step_x1 = step_x2 - 17
        for index, (glyph, delta) in enumerate((("▲", 1), ("▼", -1))):
            sy1 = win_y1 + 6 + index * 23
            sy2 = sy1 + 19
            round_rect(self, step_x1, sy1, step_x2, sy2, 4,
                       fill=mix(PANEL_DEEP, "#ffffff", 0.045), outline=LINE_SOFT)
            text(self, (step_x1 + step_x2) / 2, (sy1 + sy2) / 2 + 1, glyph,
                 self.fonts.ui(6), MUTED)
            self._hit(step_x1, sy1, step_x2, sy2,
                      lambda s=slot, d=delta: self.on_window(s, d))

        # ring setting -----------------------------------------------------
        ring_y = y1 + height - 28
        text(self, x1 + 10, ring_y + 11, "环", self.fonts.small, FAINT, anchor="w")
        box_x1 = x1 + 24
        box_x2 = box_x1 + 58
        round_rect(self, box_x1, ring_y, box_x2, ring_y + 21, 5,
                   fill=PANEL_DEEP, outline=LINE_SOFT)
        text(self, (box_x1 + box_x2) / 2, ring_y + 11, self.state["rings"][slot],
             self.fonts.mono(10, "bold"), TEXT_SOFT)
        self._hit(box_x1, ring_y, box_x1 + 18, ring_y + 21,
                  lambda s=slot: self.on_ring(s, -1))
        self._hit(box_x2 - 18, ring_y, box_x2, ring_y + 21,
                  lambda s=slot: self.on_ring(s, 1))
        text(self, box_x1 + 9, ring_y + 11, "◀", self.fonts.ui(5), FAINT)
        text(self, box_x2 - 9, ring_y + 11, "▶", self.fonts.ui(5), FAINT)

        # notch ------------------------------------------------------------
        notch_on = bool(self.state["notches"][slot])
        nx = x1 + width - 56
        colour = AMBER if notch_on else "#2a2f38"
        self.create_oval(nx, ring_y + 7, nx + 7, ring_y + 14,
                         fill=colour, outline=mix(colour, "#ffffff", 0.25))
        text(self, nx + 12, ring_y + 11, "缺口", self.fonts.tiny,
             AMBER if notch_on else FAINT, anchor="w")

    # ----------------------------------------------------------------- menu
    def _open_menu(self, kind: str, options: Sequence[str], current: str,
                   x: int, y: int, slot: int | None = None) -> None:
        if self._menu is not None:
            try:
                self._menu.destroy()
            except tk.TclError:
                pass
        menu = tk.Menu(self, tearoff=0, bg=PANEL_ALT, fg=TEXT,
                       activebackground=mix(PANEL_ALT, BRASS, 0.3),
                       activeforeground="#ffffff", bd=0, relief="flat",
                       font=self.fonts.ui(9))
        for option in options:
            label = f"UKW {option}" if kind == "reflector" else f"Walze {option}"
            prefix = "●  " if option == current else "   "
            if kind == "reflector":
                action = lambda value=option: self.on_reflector(value)
            else:
                action = lambda value=option: self.on_rotor(slot, value)
            menu.add_command(label=prefix + label, command=action)
        self._menu = menu
        try:
            menu.tk_popup(self.winfo_rootx() + x, self.winfo_rooty() + y)
        finally:
            menu.grab_release()


# =================================================================== keyboard
class LetterBoard(tk.Canvas):
    """A lampboard or a keyboard: same layout, different furniture."""

    def __init__(
        self,
        master,
        kind: str,
        on_press: Callable[[str], None] | None = None,
        fonts: Fonts | None = None,
    ) -> None:
        self.fonts = fonts or Fonts()
        self.kind = kind
        self.on_press = on_press
        self.lit: str | None = None
        height = 112 if kind == "lamp" else 120
        super().__init__(master, height=height, bg=PANEL, highlightthickness=0, bd=0)
        self._height = height
        self._diameter = 29 if kind == "lamp" else 32
        self._centres: dict[str, tuple[float, float]] = {}
        self._flash: str | None = None
        self.bind("<Configure>", lambda _e: self.redraw())
        self.bind("<Button-1>", self._on_click)

    def _on_click(self, event) -> None:
        if self.kind != "key":
            return
        radius = self._diameter / 2
        for letter, (cx, cy) in self._centres.items():
            if (event.x - cx) ** 2 + (event.y - cy) ** 2 <= radius ** 2:
                self.press_flash(letter)
                if self.on_press is not None:
                    self.on_press(letter)
                return

    def redraw(self) -> None:
        self.delete("all")
        self._centres.clear()
        width = max(self.winfo_width(), 400)
        diameter = self._diameter
        gap, row_gap = 6, 6
        rows = len(KEY_ROWS)
        total_h = rows * diameter + (rows - 1) * row_gap
        top = (self._height - total_h) / 2 + 1
        widest = max(len(row) for row in KEY_ROWS)
        total_w = widest * diameter + (widest - 1) * gap
        left = (width - total_w) / 2
        round_rect(self, left - 12, top - 8, left + total_w + 12, top + total_h + 8, 9,
                   fill=mix(PANEL, "#000000", 0.22), outline=LINE_SOFT)

        for row_index, row in enumerate(KEY_ROWS):
            row_width = len(row) * diameter + (len(row) - 1) * gap
            x = (width - row_width) / 2
            y = top + row_index * (diameter + row_gap)
            for letter in row:
                cx, cy = x + diameter / 2, y + diameter / 2
                self._centres[letter] = (cx, cy)
                self._draw_key(letter, cx, cy, diameter)
                x += diameter + gap

    def _draw_key(self, letter: str, cx: float, cy: float, diameter: float) -> None:
        r = diameter / 2
        if self.kind == "lamp":
            on = self.lit == letter
            if on:
                for scale, colour in ((1.30, alpha(AMBER, 0.09, PANEL)),
                                      (1.15, alpha(AMBER, 0.20, PANEL))):
                    self.create_oval(cx - r * scale, cy - r * scale,
                                     cx + r * scale, cy + r * scale,
                                     fill=colour, outline="")
                self.create_oval(cx - r, cy - r, cx + r, cy + r,
                                 fill=AMBER, outline=mix(AMBER, "#ffffff", 0.55))
                text(self, cx, cy, letter, self.fonts.mono(9, "bold"), "#241703")
            else:
                self.create_oval(cx - r, cy - r, cx + r, cy + r,
                                 fill=mix(PANEL, "#000000", 0.55), outline=LINE)
                self.create_oval(cx - r + 4, cy - r + 4, cx + r - 4, cy + r - 4,
                                 fill="", outline=mix(PANEL, "#ffffff", 0.05))
                text(self, cx, cy, letter, self.fonts.mono(9, "bold"), MUTED)
        else:
            pressed = self._flash == letter
            offset = 1.5 if pressed else 0
            self.create_oval(cx - r, cy - r + 1.5, cx + r, cy + r + 1.5,
                             fill="#05070a", outline="")
            face = (mix(PANEL_ALT, "#ffffff", 0.035) if not pressed
                    else mix(PANEL_ALT, AMBER, 0.2))
            self.create_oval(cx - r, cy - r + offset, cx + r, cy + r + offset,
                             fill=face, outline=LINE_STRONG if not pressed else AMBER)
            self.create_oval(cx - r + 3, cy - r + 3 + offset, cx + r - 3,
                             cy - r * 0.15 + offset,
                             fill=mix(face, "#ffffff", 0.06), outline="")
            self.create_arc(cx - r + 1, cy - r + 1 + offset, cx + r - 1, cy + r - 1 + offset,
                            start=200, extent=140, style="arc",
                            outline=mix("#000000", face, 0.55))
            text(self, cx, cy + offset, letter, self.fonts.mono(9, "bold"),
                 TEXT_SOFT if not pressed else AMBER)

    def press_flash(self, letter: str) -> None:
        if self.kind != "key":
            return
        self._flash = letter
        self.redraw()
        self.after(110, self._clear_flash)

    def _clear_flash(self) -> None:
        self._flash = None
        self.redraw()

    def light(self, letter: str, hold: int = 900) -> None:
        self.lit = letter
        self.redraw()
        self.after(hold, self._clear_lamp)

    def _clear_lamp(self) -> None:
        self.lit = None
        self.redraw()


# ================================================================= plugboard
class Plugboard(tk.Canvas):
    """Twenty-six sockets in two rows, with cables drawn between them."""

    HEIGHT = 124

    def __init__(
        self,
        master,
        on_socket: Callable[[str], None],
        fonts: Fonts | None = None,
    ) -> None:
        self.fonts = fonts or Fonts()
        super().__init__(master, height=self.HEIGHT, bg=PANEL, highlightthickness=0, bd=0)
        self.on_socket = on_socket
        self.state: dict | None = None
        self.pending: str | None = None
        self._centres: dict[str, tuple[float, float]] = {}
        self._diameter = 31
        self.bind("<Configure>", lambda _e: self.redraw())
        self.bind("<Button-1>", self._on_click)

    def update_state(self, state: dict, pending: str | None = None) -> None:
        self.state = state
        self.pending = pending
        self.redraw()

    def _on_click(self, event) -> None:
        radius = self._diameter / 2
        for letter, (cx, cy) in self._centres.items():
            if (event.x - cx) ** 2 + (event.y - cy) ** 2 <= radius ** 2:
                self.on_socket(letter)
                return

    def redraw(self) -> None:
        self.delete("all")
        self._centres.clear()
        if not self.state:
            return
        width = max(self.winfo_width(), 420)
        diameter, gap, columns = self._diameter, 7, 13
        total_w = columns * diameter + (columns - 1) * gap
        left = (width - total_w) / 2
        round_rect(self, left - 14, 6, left + total_w + 14, self.HEIGHT - 6, 9,
                   fill=PANEL_DEEP, outline=LINE_SOFT)

        for index in range(26):
            letter = chr(ord("A") + index)
            row, column = divmod(index, columns)
            cx = left + column * (diameter + gap) + diameter / 2
            cy = 32 + row * (diameter + 14)
            self._centres[letter] = (cx, cy)

        pairs: dict[str, str] = {}
        for pair in self.state["plugboard"].split():
            pairs[pair[0]] = pair[1]
            pairs[pair[1]] = pair[0]
        self._draw_cables(pairs)

        for letter, (cx, cy) in self._centres.items():
            plugged = letter in pairs
            pending = self.pending == letter
            r = diameter / 2
            if pending:
                for scale in (1.26, 1.13):
                    self.create_oval(cx - r * scale, cy - r * scale,
                                     cx + r * scale, cy + r * scale,
                                     fill=alpha(AMBER, 0.13, PANEL_DEEP), outline="")
                fill, outline, fg = AMBER, mix(AMBER, "#ffffff", 0.5), "#241703"
            elif plugged:
                fill = mix(PANEL_DEEP, AMBER, 0.18)
                outline = mix(AMBER, "#000000", 0.45)
                fg = AMBER
            else:
                fill, outline, fg = PANEL_ALT, LINE_STRONG, TEXT_SOFT
            self.create_oval(cx - r, cy - r, cx + r, cy + r, fill=fill, outline=outline)
            if not (plugged or pending):
                self.create_oval(cx - 2.5, cy + r - 7, cx + 2.5, cy + r - 2.5,
                                 fill="#05070a", outline="")
            text(self, cx, cy - 1, letter, self.fonts.mono(9, "bold"), fg)

    def _draw_cables(self, pairs: dict[str, str]) -> None:
        seen: set[str] = set()
        index = 0
        for letter, partner in pairs.items():
            if letter in seen or partner in seen:
                continue
            seen.update({letter, partner})
            a = self._centres.get(letter)
            b = self._centres.get(partner)
            if not a or not b:
                continue
            colour = CABLE_COLORS[index % len(CABLE_COLORS)]
            index += 1
            sag = min(30, max(12, abs(a[0] - b[0]) * 0.10))
            points = [
                a[0], a[1] + 7,
                (a[0] + b[0]) / 2, max(a[1], b[1]) + sag,
                b[0], b[1] + 7,
            ]
            self.create_line(*points, smooth=True, width=4.5,
                             fill=alpha("#000000", 0.6, PANEL_DEEP))
            self.create_line(*points, smooth=True, width=2, fill=colour)


# ================================================================= trace bar
class TraceBar(tk.Canvas):
    """The path the current took, one chip per hop."""

    HEIGHT = 52

    def __init__(self, master, fonts: Fonts | None = None) -> None:
        self.fonts = fonts or Fonts()
        super().__init__(master, height=self.HEIGHT, bg=BG, highlightthickness=0, bd=0)
        self.entries: list[tuple[str, str]] = []
        self.note = "按一个键，看电流怎么走"
        self.bind("<Configure>", lambda _e: self.redraw())

    def show(self, trace: Sequence[dict], key: str = "", lamp: str = "") -> None:
        self.entries = [(step["stage"], step["letter"]) for step in trace]
        if key and lamp:
            self.note = f"{key} → {lamp}"
        self.redraw()

    def clear(self) -> None:
        self.entries = []
        self.note = "按一个键，看电流怎么走"
        self.redraw()

    def redraw(self) -> None:
        self.delete("all")
        width = max(self.winfo_width(), 600)
        text(self, 16, 17, "信号路径", self.fonts.ui(8, "bold"), TEXT_SOFT, anchor="w")
        text(self, 16, 35, self.note, self.fonts.small, FAINT, anchor="w")
        if not self.entries:
            return

        measure = tkfont.Font(root=self, font=self.fonts.small)
        x = 96
        y = self.HEIGHT / 2
        for position, (stage, letter) in enumerate(self.entries):
            last = position == len(self.entries) - 1
            chip_w = max(56, measure.measure(stage) + 42)
            if x + chip_w > width - 10:
                break
            fill = alpha(AMBER, 0.13, BG) if last else PANEL
            outline = mix(AMBER, BG, 0.45) if last else LINE
            round_rect(self, x, y - 12, x + chip_w, y + 12, 6, fill=fill, outline=outline)
            text(self, x + 9, y, stage, self.fonts.small, MUTED, anchor="w")
            text(self, x + chip_w - 10, y, letter, self.fonts.mono(9, "bold"),
                 AMBER if last else TEXT, anchor="e")
            x += chip_w + 5
            if not last:
                text(self, x, y - 1, "›", self.fonts.ui(9), FAINT, anchor="w")
                x += 11


# =============================================================== progress bar
class ProgressBar(tk.Canvas):
    def __init__(self, master, height: int = 5) -> None:
        super().__init__(master, height=height, bg=PANEL, highlightthickness=0, bd=0)
        self._value = 0.0
        self._height = height
        self.bind("<Configure>", lambda _e: self.redraw())

    def set(self, value: float) -> None:
        self._value = max(0.0, min(1.0, value))
        self.redraw()

    def redraw(self) -> None:
        self.delete("all")
        width = max(self.winfo_width(), 10)
        round_rect(self, 0, 1, width, self._height - 1, 2, fill=LINE, outline="")
        filled = width * self._value
        if filled > 3:
            round_rect(self, 0, 1, filled, self._height - 1, 2, fill=BRASS, outline="")


# ===================================================================== check
class Check(tk.Canvas):
    """A small check box with a label, drawn to match the dark panels."""

    def __init__(self, master, caption: str, variable: tk.BooleanVar,
                 fonts: Fonts | None = None, on_change: Callable[[], None] | None = None):
        self.fonts = fonts or Fonts()
        self.variable = variable
        self.caption = caption
        self.on_change = on_change
        width = tkfont.Font(font=self.fonts.small).measure(caption) + 26
        super().__init__(master, width=width, height=20, bg=master["bg"],
                         highlightthickness=0, bd=0, cursor="hand2")
        self.bind("<Button-1>", self._toggle)
        self._draw()

    def _toggle(self, _event=None) -> None:
        self.variable.set(not self.variable.get())
        self._draw()
        if self.on_change is not None:
            self.on_change()

    def _draw(self) -> None:
        self.delete("all")
        checked = self.variable.get()
        box = (2, 4, 15, 17)
        round_rect(self, box[0], box[1], box[2], box[3], 3,
                   fill=BRASS if checked else PANEL_DEEP,
                   outline=BRASS if checked else LINE_STRONG)
        if checked:
            self.create_line(5, 10.5, 8, 13.5, fill="#241a08", width=1.6)
            self.create_line(8, 13.5, 13, 7.5, fill="#241a08", width=1.6)
        text(self, 22, 10, self.caption, self.fonts.small,
             TEXT_SOFT if checked else MUTED, anchor="w")


# ================================================================ scroll area
class ScrollArea(tk.Frame):
    """A vertical scroller whose scrollbar only appears when it is needed."""

    def __init__(self, master, bg: str = PANEL) -> None:
        super().__init__(master, bg=bg)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0)
        self.bar = tk.Scrollbar(
            self, orient="vertical", command=self.canvas.yview, width=9, bd=0,
            relief="flat", troughcolor=bg, background=LINE,
            activebackground=BRASS, highlightthickness=0,
        )
        self.body = tk.Frame(self.canvas, bg=bg)
        self._window = self.canvas.create_window((0, 0), window=self.body, anchor="nw")
        self.canvas.configure(yscrollcommand=self._on_scroll)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.body.bind("<Configure>", lambda _e: self._update())
        self.canvas.bind("<Configure>", lambda _e: self._update())
        self._visible = False

    def _on_scroll(self, first: str, last: str) -> None:
        self.bar.set(first, last)
        needed = not (float(first) <= 0.0 and float(last) >= 1.0)
        if needed != self._visible:
            self._visible = needed
            if needed:
                self.bar.pack(side="right", fill="y")
            else:
                self.bar.pack_forget()

    def _update(self) -> None:
        self.canvas.itemconfigure(self._window, width=self.canvas.winfo_width())
        self.canvas.configure(scrollregion=self.canvas.bbox("all") or (0, 0, 0, 0))


# ===================================================================== panels
class Panel(tk.Frame):
    """A titled section: thin border, small caption, content below."""

    def __init__(self, master, title: str, subtitle: str = "", fonts: Fonts | None = None,
                 padding: int = 11) -> None:
        self.fonts = fonts or Fonts()
        super().__init__(master, bg=PANEL, highlightthickness=1,
                         highlightbackground=LINE, bd=0)
        if title:
            header = tk.Frame(self, bg=PANEL)
            header.pack(fill="x", padx=padding + 1, pady=(max(0, padding - 3), 5))
            tk.Label(header, text=title, bg=PANEL, fg=TEXT_SOFT,
                     font=self.fonts.ui(8, "bold")).pack(side="left")
            if subtitle:
                tk.Label(header, text=subtitle, bg=PANEL, fg=FAINT,
                         font=self.fonts.small).pack(side="left", padx=(8, 0))
        self.body = tk.Frame(self, bg=PANEL)
        self.body.pack(fill="both", expand=True, padx=padding, pady=(0 if title else 0, padding))
