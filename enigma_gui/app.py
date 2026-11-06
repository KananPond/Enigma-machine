"""The Enigma machine as a native desktop window.

Everything is drawn with Tk - no browser, no web view, no external toolkit -
so the program starts on a plain Windows installation with nothing but
Python and (for the attacks) numpy.
"""

from __future__ import annotations

import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox
from typing import Any, Callable

from enigma import autosolve, samples
from enigma.data import ALPHABET, REFLECTORS, ROTORS
from enigma.decode import decode
from enigma.english import DEFAULT_MODEL
from enigma.keys import REFLECTOR_NAMES, ROTOR_NAMES, Key, KeyError_
from enigma.machine import EnigmaMachine
from enigma.message import split_messages
from enigma.plugboard import Plugboard
from enigma.preparation import prepare_text

from .theme import (
    AMBER,
    BG,
    BG_HEADER,
    BRASS,
    FAINT,
    GREEN,
    LINE,
    LINE_SOFT,
    MUTED,
    PANEL,
    PANEL_ALT,
    PANEL_DEEP,
    ROSE,
    TEAL,
    TEXT,
    TEXT_SOFT,
    Fonts,
    alpha,
    mix,
    round_rect,
)
from .widgets import (
    Button,
    Check,
    LetterBoard,
    Panel,
    Plugboard as PlugboardView,
    ProgressBar,
    RotorDeck,
    ScrollArea,
    TraceBar,
)

APP_TITLE = "ENIGMA · M3"

#: Cribs operators actually used, offered as one-click fill-ins.
CRIB_PRESETS = (
    "ATTACK AT DAWN",
    "WEATHER REPORT",
    "CONVOY SIGHTED",
    "OBERKOMMANDO",
    "NOTHING TO REPORT",
    "KEINE BESONDEREN",
)


def groups(value: str, size: int = 5) -> str:
    """Split a run of letters into groups, the way a signal sheet looked."""
    letters = "".join(char for char in value.upper() if char in ALPHABET)
    return " ".join(letters[index : index + size] for index in range(0, len(letters), size))


# ---------------------------------------------------------------------- jobs
class Job:
    """A long running search, followed by the window while it works."""

    def __init__(self) -> None:
        self.cancel = threading.Event()
        self.progress = 0.0
        self.message = "准备中…"
        self.started = time.time()
        self.done = False
        self.result: Any = None
        self.error: str = ""


class EnigmaApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.fonts = Fonts()
        self.title(APP_TITLE)
        self.configure(bg=BG)
        self.geometry("1460x920")
        self.minsize(1180, 700)

        self.key = Key()
        self.machine: EnigmaMachine = self.key.machine()
        self.pending_socket: str | None = None
        self.lamp_timer: str | None = None
        self.job: Job | None = None
        self.break_result: autosolve.AutoResult | None = None
        self.decode_result: Any = None
        self.last_output = ""

        self._build_styles()
        self._build_header()
        self._build_body()
        self._build_footer()
        self._bind_keys()
        self.refresh(animate=False)
        self.after(300, self._focus_hint)

    # ================================================================= setup
    def _build_styles(self) -> None:
        self.option_add("*Menu.background", PANEL_ALT)
        self.option_add("*Menu.foreground", TEXT)
        self.option_add("*Menu.activeBackground", mix(PANEL_ALT, BRASS, 0.3))
        self.option_add("*Menu.activeForeground", "#ffffff")
        self.option_add("*Menu.font", self.fonts.ui(9))

    # ---------------------------------------------------------------- header
    def _build_header(self) -> None:
        header = tk.Frame(self, bg=BG_HEADER, height=60)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        brand = tk.Canvas(header, width=250, height=60, bg=BG_HEADER, highlightthickness=0)
        brand.pack(side="left", padx=(18, 0))
        self._draw_mark(brand, 28, 30)
        brand.create_text(54, 22, text="ENIGMA", font=self.fonts.mono(15, "bold"),
                          fill=BRASS, anchor="w")
        brand.create_text(55, 40, text="M3 · 恩尼格码密码机", font=self.fonts.ui(7),
                          fill=FAINT, anchor="w")

        actions = tk.Frame(header, bg=BG_HEADER)
        actions.pack(side="right", padx=16)
        for label, command in (
            ("密钥卡", self.open_keycard),
            ("示例", self.open_samples),
            ("使用说明", self.open_help),
        ):
            Button(actions, label, command, kind="ghost", fonts=self.fonts,
                   height=28, width=74).pack(side="left", padx=3)

        self.readout = tk.Canvas(header, width=560, height=60, bg=BG_HEADER,
                                 highlightthickness=0)
        self.readout.pack(side="right", padx=(0, 6))

    def _draw_mark(self, canvas: tk.Canvas, cx: int, cy: int) -> None:
        canvas.create_oval(cx - 15, cy - 15, cx + 15, cy + 15, outline=alpha(BRASS, 0.5, BG_HEADER), width=1)
        canvas.create_oval(cx - 10, cy - 10, cx + 10, cy + 10, outline=alpha(BRASS, 0.3, BG_HEADER), width=1)
        for dx, dy in ((0, -18), (0, 18), (-18, 0), (18, 0), (-13, -13), (13, 13), (13, -13), (-13, 13)):
            canvas.create_line(cx + dx * 0.62, cy + dy * 0.62, cx + dx * 0.86, cy + dy * 0.86,
                               fill=alpha(BRASS, 0.55, BG_HEADER))
        canvas.create_oval(cx - 3.4, cy - 3.4, cx + 3.4, cy + 3.4, fill=BRASS, outline="")

    def _draw_readout(self) -> None:
        canvas = self.readout
        canvas.delete("all")
        state = self.state()
        items = (
            ("转子", "-".join(state["rotors"]), TEXT_SOFT, False),
            ("反射器", state["reflector"], TEXT_SOFT, False),
            ("环设定", state["rings"], TEXT_SOFT, True),
            ("窗口", state["positions"], AMBER, True),
            ("接线", f"{state['cables']}/{Plugboard.MAX_PAIRS}", TEXT_SOFT, False),
        )
        width = 560
        cell = width / len(items)
        for index, (label, value, colour, mono) in enumerate(items):
            x = index * cell + 12
            if index:
                canvas.create_line(index * cell, 18, index * cell, 42, fill=LINE)
            canvas.create_text(x, 20, text=label, font=self.fonts.ui(7), fill=FAINT, anchor="w")
            canvas.create_text(x, 39, text=value, font=self.fonts.mono(10, "bold") if mono
                               else self.fonts.ui(9, "bold"), fill=colour, anchor="w")

    # ------------------------------------------------------------------ body
    def _build_body(self) -> None:
        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=14, pady=(10, 0))
        body.columnconfigure(0, weight=1, minsize=690)
        body.columnconfigure(1, weight=0, minsize=462)
        body.rowconfigure(0, weight=1)

        machine = tk.Frame(body, bg=BG)
        machine.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        machine_area = ScrollArea(machine, bg=BG)
        machine_area.pack(fill="both", expand=True)
        self._build_machine(machine_area.body)

        workbench = Panel(body, "", "", self.fonts, padding=0)
        workbench.grid(row=0, column=1, sticky="nsew")
        self._build_workbench(workbench.body)

    def _build_machine(self, parent: tk.Frame) -> None:
        rotor_panel = Panel(parent, "机器设置", "Walzenlage · Ringstellung · Grundstellung",
                            self.fonts)
        rotor_panel.pack(fill="x")
        self.rotor_deck = RotorDeck(
            rotor_panel.body, ROTOR_NAMES, REFLECTOR_NAMES,
            on_rotor=self.on_rotor, on_ring=self.on_ring,
            on_window=self.on_window, on_reflector=self.on_reflector,
            fonts=self.fonts,
        )
        self.rotor_deck.pack(fill="x")

        board_panel = Panel(parent, "灯板 · 键盘", "按键后灯泡亮起 · 也可直接敲 A–Z", self.fonts)
        board_panel.pack(fill="x", pady=(8, 0))
        self.lampboard = LetterBoard(board_panel.body, "lamp", fonts=self.fonts)
        self.lampboard.pack(fill="x")
        tk.Frame(board_panel.body, bg=LINE_SOFT, height=1).pack(fill="x", pady=6)
        self.keyboard = LetterBoard(board_panel.body, "key", on_press=self.press, fonts=self.fonts)
        self.keyboard.pack(fill="x")

        plug_panel = Panel(parent, "接线板", "Steckerbrett · 点两个字母接一根电缆", self.fonts)
        plug_panel.pack(fill="both", expand=True, pady=(8, 0))
        tools = tk.Frame(plug_panel.body, bg=PANEL)
        tools.pack(fill="x", pady=(0, 6))
        self.plug_entry = self._entry(tools, width=160, mono=True)
        self.plug_entry.pack(side="left")
        self.plug_entry.bind("<Return>", lambda _e: self.apply_plugboard_text())
        Button(tools, "应用", self.apply_plugboard_text, kind="subtle", fonts=self.fonts,
               height=24, width=54).pack(side="left", padx=(6, 0))
        Button(tools, "清空", self.clear_plugboard, kind="ghost", fonts=self.fonts,
               height=24, width=54).pack(side="left", padx=4)
        tk.Label(tools, text="最多十根 · 同一字母只能用一次", bg=PANEL, fg=FAINT,
                 font=self.fonts.tiny).pack(side="right")

        self.plugboard = PlugboardView(plug_panel.body, on_socket=self.on_socket, fonts=self.fonts)
        self.plugboard.pack(fill="x")

    def _build_workbench(self, parent: tk.Frame) -> None:
        tabs = tk.Frame(parent, bg=PANEL_ALT, height=38)
        tabs.pack(fill="x")
        tabs.pack_propagate(False)
        self.tabs: dict[str, tk.Frame] = {}
        self.tab_buttons: dict[str, Button] = {}
        self.tab_marks: dict[str, tk.Frame] = {}
        for index, (name, caption) in enumerate(
            (("message", "电报"), ("decode", "解码"), ("break", "破译"))
        ):
            holder = tk.Frame(tabs, bg=PANEL_ALT)
            holder.pack(side="left", fill="y", padx=(8 if index == 0 else 2, 0), pady=6)
            button = Button(holder, caption, lambda n=name: self.switch_tab(n),
                            kind="ghost", fonts=self.fonts, height=26, width=86)
            button.pack()
            mark = tk.Frame(holder, bg=BRASS, height=2)
            self.tab_buttons[name] = button
            self.tab_marks[name] = mark

        container = tk.Frame(parent, bg=PANEL)
        container.pack(fill="both", expand=True, padx=12, pady=10)
        container.rowconfigure(0, weight=1)
        container.columnconfigure(0, weight=1)

        self.panels: dict[str, tk.Frame] = {}
        bodies: dict[str, tk.Frame] = {}
        for name in ("message", "decode", "break"):
            frame = tk.Frame(container, bg=PANEL)
            frame.grid(row=0, column=0, sticky="nsew")
            area = ScrollArea(frame)
            area.pack(fill="both", expand=True)
            self.panels[name] = frame
            bodies[name] = area.body

        self._build_message_panel(bodies["message"])
        self._build_decode_panel(bodies["decode"])
        self._build_break_panel(bodies["break"])
        self.switch_tab("message")

    # ------------------------------------------------------------- 电报 panel
    def _build_message_panel(self, parent: tk.Frame) -> None:
        self.direction = "encrypt"
        seg = tk.Frame(parent, bg=PANEL)
        seg.pack(fill="x", pady=(0, 8))
        self.dir_buttons = {}
        for value, caption in (("encrypt", "加密"), ("decrypt", "解密")):
            button = Button(seg, caption, lambda v=value: self.set_direction(v),
                            kind="subtle" if value == "encrypt" else "ghost",
                            fonts=self.fonts, height=28, width=88)
            button.pack(side="left", padx=(0, 4))
            self.dir_buttons[value] = button

        label_row = tk.Frame(parent, bg=PANEL)
        label_row.pack(fill="x")
        self.msg_label = tk.Label(label_row, text="原文", bg=PANEL, fg=TEXT_SOFT,
                                  font=self.fonts.ui(8, "bold"))
        self.msg_label.pack(side="left")
        self.msg_counter = tk.Label(label_row, text="0 字母", bg=PANEL, fg=FAINT,
                                    font=self.fonts.tiny)
        self.msg_counter.pack(side="right")
        Button(label_row, "填入示例", self.fill_example, kind="ghost", fonts=self.fonts,
               height=22, width=64).pack(side="right", padx=6)

        self.msg_input = self._text(parent, height=8)
        self.msg_input.pack(fill="both", expand=True, pady=(4, 8))
        self.msg_input.bind("<KeyRelease>", lambda _e: self._update_counter())

        options = tk.Frame(parent, bg=PANEL)
        options.pack(fill="x", pady=(0, 8))
        self.choice_numbers = self._choice(
            options, "数字", ("自动", "英文文字", "逐位拼写"),
            values=("auto", "words", "digits"), width=132,
        )
        self.choice_numbers.pack(side="left", padx=(0, 8))
        self.choice_space = self._choice(
            options, "空格", ("自动 X/Q", "X", "Q"),
            values=("auto", "X", "Q"), width=92,
        )
        self.choice_space.pack(side="left")

        checks = tk.Frame(parent, bg=PANEL)
        checks.pack(fill="x", pady=(0, 8))
        self.var_join = tk.BooleanVar(value=False)
        self.var_group = tk.BooleanVar(value=True)
        self.var_split = tk.BooleanVar(value=False)
        for text_value, variable in (
            ("数字连写", self.var_join),
            ("五字分组", self.var_group),
            ("按空行拆分", self.var_split),
        ):
            self._check(checks, text_value, variable).pack(side="left", padx=(0, 12))

        self.msg_run = Button(parent, "开始加密", self.run_message, kind="primary",
                              fonts=self.fonts, height=34)
        self.msg_run.pack(fill="x", pady=(0, 8))

        out_row = tk.Frame(parent, bg=PANEL)
        out_row.pack(fill="x")
        tk.Label(out_row, text="结果", bg=PANEL, fg=TEXT_SOFT,
                 font=self.fonts.ui(8, "bold")).pack(side="left")
        self.out_counter = tk.Label(out_row, text="—", bg=PANEL, fg=FAINT, font=self.fonts.tiny)
        self.out_counter.pack(side="right")
        Button(out_row, "保存", self.save_output, kind="ghost", fonts=self.fonts,
               height=22, width=48).pack(side="right", padx=4)
        Button(out_row, "复制", self.copy_output, kind="ghost", fonts=self.fonts,
               height=22, width=48).pack(side="right")

        self.msg_output = self._text(parent, height=8, colour=AMBER, readonly=True)
        self.msg_output.pack(fill="both", expand=True, pady=(4, 6))
        self.msg_stats = tk.Label(parent, text="", bg=PANEL, fg=FAINT, font=self.fonts.tiny,
                                  anchor="w")
        self.msg_stats.pack(fill="x")

    # ------------------------------------------------------------- 解码 panel
    def _build_decode_panel(self, parent: tk.Frame) -> None:
        row = tk.Frame(parent, bg=PANEL)
        row.pack(fill="x")
        tk.Label(row, text="密文", bg=PANEL, fg=TEXT_SOFT,
                 font=self.fonts.ui(8, "bold")).pack(side="left")
        self.dec_counter = tk.Label(row, text="0 字母", bg=PANEL, fg=FAINT, font=self.fonts.tiny)
        self.dec_counter.pack(side="right")
        Button(row, "取自电报", self.decode_from_message, kind="ghost", fonts=self.fonts,
               height=22, width=68).pack(side="right", padx=4)

        self.dec_input = self._text(parent, height=4)
        self.dec_input.pack(fill="both", expand=True, pady=(4, 8))
        self.dec_input.bind("<KeyRelease>", lambda _e: self._update_counter())

        self.keybar = tk.Label(parent, text="", bg=PANEL_ALT, fg=TEXT_SOFT,
                               font=self.fonts.mono(8), anchor="w", padx=10, pady=6,
                               highlightthickness=1, highlightbackground=LINE)
        self.keybar.pack(fill="x", pady=(0, 8))

        switches = tk.Frame(parent, bg=PANEL)
        switches.pack(fill="x", pady=(0, 8))
        self.var_spaces = tk.BooleanVar(value=True)
        self.var_punct = tk.BooleanVar(value=True)
        self.var_solve = tk.BooleanVar(value=False)
        for text_value, variable in (
            ("恢复词间隔", self.var_spaces),
            ("恢复标点", self.var_punct),
            ("搜索接线板", self.var_solve),
        ):
            self._check(switches, text_value, variable).pack(side="left", padx=(0, 12))

        self.dec_run = Button(parent, "解码", self.run_decode, kind="primary",
                              fonts=self.fonts, height=34)
        self.dec_run.pack(fill="x", pady=(0, 8))

        self.dec_progress_holder = tk.Frame(parent, bg=PANEL)
        self.dec_progress_holder.pack(fill="x")
        self.dec_progress = ProgressBar(self.dec_progress_holder)
        self.dec_progress.pack(fill="x")
        self.dec_progress_text = tk.Label(self.dec_progress_holder, text="", bg=PANEL,
                                          fg=FAINT, font=self.fonts.tiny, anchor="w")
        self.dec_progress_text.pack(fill="x", pady=(3, 0))
        self.dec_progress_holder.pack_forget()

        self.dec_result_label = tk.Label(parent, text="解出来的明文会出现在这里", bg=PANEL,
                                         fg=FAINT, font=self.fonts.small, anchor="w")
        self.dec_result_label.pack(fill="x", pady=(10, 0))
        self.dec_output = self._text(parent, height=9, colour="#f2e7d4", readonly=True)
        self.dec_output.pack(fill="both", expand=True, pady=(4, 6))
        self.dec_note = tk.Label(parent, text="", bg=PANEL, fg=FAINT, font=self.fonts.tiny,
                                 anchor="w", justify="left", wraplength=430)
        self.dec_note.pack(fill="x")

    # ------------------------------------------------------------- 破译 panel
    def _build_break_panel(self, parent: tk.Frame) -> None:
        banner = tk.Frame(parent, bg=mix(PANEL, TEAL, 0.06), highlightthickness=1,
                          highlightbackground=mix(PANEL, TEAL, 0.25))
        banner.pack(fill="x", pady=(0, 8))
        tk.Label(banner, text="只给密文，把密钥找回来", bg=banner["bg"], fg=TEXT,
                 font=self.fonts.ui(8, "bold"), anchor="w").pack(fill="x", padx=10, pady=(6, 0))
        tk.Label(banner, text="用一段已知明文反推整副密钥；没有已知明文时，\n"
                              "程序穷举转子位置并用英语统计打分。",
                 bg=banner["bg"], fg=MUTED, font=self.fonts.small, anchor="w",
                 justify="left").pack(fill="x", padx=10, pady=(2, 7))

        row = tk.Frame(parent, bg=PANEL)
        row.pack(fill="x")
        tk.Label(row, text="密文", bg=PANEL, fg=TEXT_SOFT,
                 font=self.fonts.ui(8, "bold")).pack(side="left")
        self.brk_counter = tk.Label(row, text="0 字母", bg=PANEL, fg=FAINT, font=self.fonts.tiny)
        self.brk_counter.pack(side="right")
        Button(row, "取自解码", self.break_from_decode, kind="ghost", fonts=self.fonts,
               height=22, width=68).pack(side="right", padx=4)

        self.brk_input = self._text(parent, height=3)
        self.brk_input.pack(fill="x", pady=(4, 8))
        self.brk_input.bind("<KeyRelease>", lambda _e: self._update_counter())

        crib_row = tk.Frame(parent, bg=PANEL)
        crib_row.pack(fill="x")
        tk.Label(crib_row, text="已知明文（crib）", bg=PANEL, fg=TEXT_SOFT,
                 font=self.fonts.ui(8, "bold")).pack(side="left")
        Button(crib_row, "不用", self.clear_crib, kind="ghost", fonts=self.fonts,
               height=22, width=44).pack(side="right")
        self.brk_crib = self._entry(parent, mono=True)
        self.brk_crib.pack(fill="x", pady=(4, 4))

        chips = tk.Frame(parent, bg=PANEL)
        chips.pack(fill="x", pady=(0, 8))
        for preset in CRIB_PRESETS[:4]:
            Button(chips, preset, lambda value=preset: self.set_crib(value), kind="ghost",
                   font=self.fonts.mono(6), height=22).pack(side="left", padx=(0, 4))

        grid = tk.Frame(parent, bg=PANEL)
        grid.pack(fill="x", pady=(0, 8))
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)
        offset_box = tk.Frame(grid, bg=PANEL)
        offset_box.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        tk.Label(offset_box, text="crib 位置", bg=PANEL, fg=FAINT,
                 font=self.fonts.tiny, anchor="w").pack(fill="x", pady=(0, 2))
        self.brk_offset = self._entry(offset_box, mono=True)
        self.brk_offset.pack(fill="x")
        rings_box = tk.Frame(grid, bg=PANEL)
        rings_box.grid(row=0, column=1, sticky="ew")
        tk.Label(rings_box, text="环设定", bg=PANEL, fg=FAINT,
                 font=self.fonts.tiny, anchor="w").pack(fill="x", pady=(0, 2))
        self.brk_rings = self._entry(rings_box, mono=True)
        self.brk_rings.insert(0, "AAA")
        self.brk_rings.pack(fill="x")

        self.choice_scope = self._choice(
            parent, "转子范围", ("常用 I–III", "全部 I–V", "全部 I–VIII"),
            values=("quick", "full", "all"), width=140, initial=1,
        )
        self.choice_scope.pack(fill="x", pady=(0, 8))

        self.brk_run = Button(parent, "开始破译", self.run_break, kind="primary",
                              fonts=self.fonts, height=34)
        self.brk_run.pack(fill="x", pady=(0, 8))

        self.brk_progress_holder = tk.Frame(parent, bg=PANEL)
        self.brk_progress_holder.pack(fill="x")
        self.brk_progress = ProgressBar(self.brk_progress_holder)
        self.brk_progress.pack(fill="x")
        progress_row = tk.Frame(self.brk_progress_holder, bg=PANEL)
        progress_row.pack(fill="x", pady=(3, 0))
        self.brk_progress_text = tk.Label(progress_row, text="", bg=PANEL, fg=FAINT,
                                          font=self.fonts.tiny, anchor="w")
        self.brk_progress_text.pack(side="left")
        self.brk_stop = Button(progress_row, "停止", self.cancel_job, kind="ghost",
                               fonts=self.fonts, height=20, width=44)
        self.brk_stop.pack(side="right")
        self.brk_progress_holder.pack_forget()

        self.brk_verdict = tk.Label(parent, text="", bg=PANEL, fg=MUTED, font=self.fonts.small,
                                    anchor="w", justify="left", wraplength=430)
        self.brk_verdict.pack(fill="x", pady=(8, 0))
        self.brk_key = tk.Label(parent, text="", bg=PANEL_DEEP, fg=BRASS,
                                font=self.fonts.mono(8), anchor="w", justify="left",
                                padx=10, pady=7, highlightthickness=1,
                                highlightbackground=LINE_SOFT, wraplength=420)
        self.brk_text = self._text(parent, height=5, colour="#f2e7d4", readonly=True)
        self.brk_actions = tk.Frame(parent, bg=PANEL)

    # ----------------------------------------------------------------- footer
    def _build_footer(self) -> None:
        footer = tk.Frame(self, bg=BG, height=58)
        footer.pack(fill="x", side="bottom", padx=14, pady=(6, 10))
        footer.pack_propagate(False)
        self.trace = TraceBar(footer, fonts=self.fonts)
        self.trace.pack(fill="both", expand=True)

    # ================================================================== state
    def state(self) -> dict[str, Any]:
        machine = self.machine
        return {
            "rotors": list(machine.rotor_names),
            "reflector": machine.reflector,
            "rings": machine.ring_settings,
            "positions": machine.positions,
            "plugboard": machine.plugboard.describe(),
            "cables": machine.plugboard.pair_count,
            "notches": [rotor.at_turnover for rotor in machine.rotors],
        }

    def refresh(self, animate: bool = True) -> None:
        state = self.state()
        self._draw_readout()
        self.rotor_deck.update_state(state, animate=animate)
        self.plugboard.update_state(state, self.pending_socket)
        self.keybar.configure(text=self._key_line())
        if self.plug_entry.get() != state["plugboard"] and self.focus_get() is not self.plug_entry:
            self.plug_entry.delete(0, "end")
            self.plug_entry.insert(0, state["plugboard"])

    def _key_line(self) -> str:
        state = self.state()
        cables = state["plugboard"] or "无接线"
        return (f"{'-'.join(state['rotors'])}  ·  UKW {state['reflector']}  ·  "
                f"环 {state['rings']}  ·  起始 {state['positions']}  ·  {cables}")

    def apply_key(self, key: Key) -> None:
        self.key = key
        self.machine = key.machine()
        self.pending_socket = None
        self.refresh(animate=False)

    def rebuild(self, **changes: Any) -> None:
        try:
            key = Key.from_dict({**self.key.to_dict(), **changes})
        except KeyError_ as error:
            self.toast(str(error), "error")
            self.refresh(animate=False)
            return
        self.apply_key(key)

    # ================================================================= events
    def on_rotor(self, slot: int, name: str) -> None:
        rotors = list(self.state()["rotors"])
        if name in rotors:
            other = rotors.index(name)
            rotors[other] = rotors[slot]
        rotors[slot] = name
        self.rebuild(rotors=rotors)

    def on_reflector(self, name: str) -> None:
        self.rebuild(reflector=name)

    def on_ring(self, slot: int, delta: int) -> None:
        rings = list(self.state()["rings"])
        rings[slot] = ALPHABET[(ALPHABET.index(rings[slot]) + delta) % 26]
        self.rebuild(rings="".join(rings))

    def on_window(self, slot: int, delta: int) -> None:
        positions = list(self.state()["positions"])
        positions[slot] = ALPHABET[(ALPHABET.index(positions[slot]) + delta) % 26]
        self.machine.set_positions("".join(positions))
        self.key = self.key.with_(positions=self.machine.positions)
        self.refresh(animate=True)

    def on_socket(self, letter: str) -> None:
        plugged = dict()
        for pair in self.state()["plugboard"].split():
            plugged[pair[0]] = pair[1]
            plugged[pair[1]] = pair[0]

        if self.pending_socket == letter:
            self.pending_socket = None
            self.refresh(animate=False)
            return
        if letter in plugged:
            board = dict(plugged)
            partner = board[letter]
            board.pop(letter, None)
            board.pop(partner, None)
            self.pending_socket = None
            self.rebuild(plugboard=" ".join(f"{a}{b}" for a, b in sorted(board.items())
                                            if a < b))
            return
        if self.pending_socket is None:
            self.pending_socket = letter
            self.refresh(animate=False)
            return

        first = self.pending_socket
        self.pending_socket = None
        pairs = [pair for pair in self.state()["plugboard"].split()
                 if first not in pair and letter not in pair]
        if len(pairs) >= Plugboard.MAX_PAIRS:
            pairs = pairs[1:]
        pairs.append(f"{min(first, letter)}{max(first, letter)}")
        self.rebuild(plugboard=" ".join(pairs))

    def apply_plugboard_text(self) -> None:
        # validating through the key sheet keeps the rules in one place: a
        # letter may only carry one cable, and the board holds ten at most
        self.pending_socket = None
        self.rebuild(plugboard=self.plug_entry.get())

    def clear_plugboard(self) -> None:
        self.pending_socket = None
        self.rebuild(plugboard="")

    # ------------------------------------------------------------- pressing
    def press(self, letter: str) -> None:
        letter = letter.upper()
        if letter not in ALPHABET:
            return
        trace: list = []
        lamp = self.machine.press(letter, trace)
        stages = {"key": "按键", "plugboard": "接线板", "reflector": "反射器"}
        seen: list[str] = []
        steps = []
        for step in trace:
            name = stages.get(step.stage)
            if name is None:
                name = f"转子 {step.stage}"
                if name in seen:
                    name = f"转子 {step.stage} 返回"
                seen.append(f"转子 {step.stage}")
            steps.append({"stage": name, "letter": step.letter})
        self.key = self.key.with_(positions=self.machine.positions)
        self.refresh(animate=True)
        self.lampboard.light(lamp)
        self.keyboard.press_flash(letter)
        self.trace.show(steps, letter, lamp)

    # ------------------------------------------------------------- keyboard
    def _bind_keys(self) -> None:
        self.bind_all("<KeyPress>", self._on_key)

    def _on_key(self, event) -> None:
        widget = self.focus_get()
        if isinstance(widget, (tk.Text, tk.Entry, tk.Spinbox)):
            return
        if event.state & 0x4:  # control held: let the shortcuts through
            return
        letter = (event.keysym or "").upper()
        if len(letter) == 1 and letter in ALPHABET:
            self.press(letter)
            return "break"

    def _focus_hint(self) -> None:
        self.focus_set()

    # ================================================================== tabs
    def switch_tab(self, name: str) -> None:
        for key, frame in self.panels.items():
            if key == name:
                frame.grid()
            else:
                frame.grid_remove()
        for key, button in self.tab_buttons.items():
            active = key == name
            button.set_kind("subtle" if active else "ghost")
            mark = self.tab_marks[key]
            if active:
                mark.pack(fill="x", pady=(2, 0))
            else:
                mark.pack_forget()

    def set_direction(self, value: str) -> None:
        self.direction = value
        for key, button in self.dir_buttons.items():
            button.set_kind("subtle" if key == value else "ghost")
        encrypting = value == "encrypt"
        self.msg_label.configure(text="原文" if encrypting else "密文")
        self.msg_run.set_text("开始加密" if encrypting else "开始解密")

    # ============================================================== widgets
    def _text(self, parent, height: int = 5, colour: str = TEXT, readonly: bool = False) -> tk.Text:
        widget = tk.Text(
            parent, height=height, width=1, bg=PANEL_DEEP, fg=colour, insertbackground=BRASS,
            relief="flat", highlightthickness=1, highlightbackground=LINE,
            highlightcolor=mix(LINE, BRASS, 0.5), font=self.fonts.mono(10),
            padx=9, pady=7, wrap="word", undo=True, spacing1=1, spacing3=2,
            selectbackground=mix(PANEL_DEEP, BRASS, 0.35),
        )
        if readonly:
            widget.configure(state="disabled", cursor="arrow")
        return widget

    def _entry(self, parent, width: int | None = None, mono: bool = False) -> tk.Entry:
        entry = tk.Entry(
            parent, bg=PANEL_DEEP, fg=TEXT, insertbackground=BRASS, relief="flat",
            highlightthickness=1, highlightbackground=LINE,
            highlightcolor=mix(LINE, BRASS, 0.5),
            font=self.fonts.mono(10) if mono else self.fonts.body,
            width=width or 12,
        )
        return entry

    def _check(self, parent, caption: str, variable: tk.BooleanVar) -> Check:
        return Check(parent, caption, variable, fonts=self.fonts)

    def _choice(self, parent, label: str, options: tuple[str, ...],
                values: tuple[str, ...], width: int = 120, initial: int = 0) -> tk.Frame:
        frame = tk.Frame(parent, bg=PANEL)
        tk.Label(frame, text=label, bg=PANEL, fg=FAINT, font=self.fonts.tiny,
                 anchor="w").pack(fill="x")
        holder = tk.Frame(frame, bg=PANEL_ALT, highlightthickness=1,
                          highlightbackground=LINE, cursor="hand2")
        holder.pack(fill="x")
        value = tk.Label(holder, text=options[initial], bg=PANEL_ALT, fg=TEXT_SOFT,
                         font=self.fonts.small, anchor="w", padx=8, pady=4)
        value.pack(side="left", fill="x", expand=True)
        arrow = tk.Label(holder, text="▾", bg=PANEL_ALT, fg=FAINT, font=self.fonts.small,
                         padx=6)
        arrow.pack(side="right")
        frame.value = values[initial]  # type: ignore[attr-defined]

        def open_menu(event=None) -> None:
            menu = tk.Menu(self, tearoff=0, bg=PANEL_ALT, fg=TEXT, bd=0, relief="flat",
                           activebackground=mix(PANEL_ALT, BRASS, 0.3),
                           activeforeground="#ffffff", font=self.fonts.ui(9))
            for caption, option in zip(options, values):
                menu.add_command(
                    label=("●  " if option == frame.value else "   ") + caption,
                    command=lambda o=option, c=caption: pick(o, c),
                )
            try:
                menu.tk_popup(holder.winfo_rootx(), holder.winfo_rooty() + holder.winfo_height())
            finally:
                menu.grab_release()

        def pick(option: str, caption: str) -> None:
            frame.value = option  # type: ignore[attr-defined]
            value.configure(text=caption)

        for widget in (holder, value, arrow):
            widget.bind("<Button-1>", open_menu)
        return frame

    def _set_readonly(self, widget: tk.Text, value: str) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", value)
        widget.configure(state="disabled")

    def _update_counter(self) -> None:
        self.msg_counter.configure(text=f"{len(DEFAULT_MODEL.letters(self.msg_input.get('1.0', 'end')))} 字母")
        self.dec_counter.configure(text=f"{len(DEFAULT_MODEL.letters(self.dec_input.get('1.0', 'end')))} 字母")
        self.brk_counter.configure(text=f"{len(DEFAULT_MODEL.letters(self.brk_input.get('1.0', 'end')))} 字母")

    # ================================================================= toast
    def toast(self, message: str, kind: str = "info", duration: int = 3200) -> None:
        if hasattr(self, "_toast") and self._toast is not None:
            self._toast.destroy()
        colour = {"error": ROSE, "ok": GREEN}.get(kind, BRASS)
        frame = tk.Frame(self, bg=PANEL_ALT, highlightthickness=1,
                         highlightbackground=mix(colour, PANEL_ALT, 0.45))
        bar = tk.Frame(frame, bg=colour, width=3)
        bar.pack(side="left", fill="y")
        tk.Label(frame, text=message, bg=PANEL_ALT, fg=TEXT, font=self.fonts.small,
                 padx=10, pady=7, anchor="w", justify="left").pack(side="left")
        frame.place(relx=0.5, rely=1.0, anchor="s", y=-70)
        frame.lift()
        self._toast = frame
        self.after(duration, lambda: frame.destroy() if frame.winfo_exists() else None)

    # ================================================================ 电报
    def fill_example(self) -> None:
        self.set_direction("encrypt")
        self.msg_input.delete("1.0", "end")
        self.msg_input.insert(
            "1.0",
            "THE CONVOY LEFT THE HARBOUR BEFORE DAWN AND HEADED NORTH WEST. "
            "VISIBILITY IS POOR. REPORT ANY CONTACT AT ONCE.",
        )
        self._update_counter()

    def run_message(self) -> None:
        text = self.msg_input.get("1.0", "end").strip()
        if not DEFAULT_MODEL.letters(text):
            self.toast("先输入一些字母。", "error")
            return
        started = time.perf_counter()
        try:
            if self.direction == "encrypt":
                source = prepare_text(
                    text,
                    number_policy=self.choice_numbers.value,
                    space_letter=self.choice_space.value,
                    join_number_words=self.var_join.get(),
                ).text
                machine = self.machine_copy()
                output = machine.encrypt(source)
                prepared = source
            else:
                source = DEFAULT_MODEL.letters(text)
                machine = self.machine_copy()
                output = machine.encrypt(source)
                prepared = ""

            blocks = 1
            if self.var_split.get() and self.direction == "encrypt":
                pieces = split_messages(text)
                blocks = len(pieces)
                parts = []
                for piece in pieces:
                    statement = prepare_text(
                        piece,
                        number_policy=self.choice_numbers.value,
                        space_letter=self.choice_space.value,
                        join_number_words=self.var_join.get(),
                    ).text
                    parts.append(self.machine_copy().encrypt(statement))
                output = "".join(parts)
        except ValueError as error:
            self.toast(str(error), "error")
            return

        shown = groups(output) if self.var_group.get() else output
        self._set_readonly(self.msg_output, shown)
        self.last_output = output
        self.out_counter.configure(text=f"{len(output)} 字母")
        elapsed = (time.perf_counter() - started) * 1000
        self.msg_stats.configure(
            text=f"字母 {len(output)} · 报文 {blocks} · {elapsed:.1f} ms · "
                 f"转子停在 {machine.positions}"
        )
        if self.direction == "encrypt":
            self.brk_input.delete("1.0", "end")
            self.brk_input.insert("1.0", output)
            self._update_counter()
        if prepared:
            self.msg_stats.configure(
                text=f"字母 {len(output)}（送入 {len(prepared)}）· 报文 {blocks} · "
                     f"{elapsed:.1f} ms · 停在 {machine.positions}"
            )

    def machine_copy(self) -> EnigmaMachine:
        return self.key.with_(positions=self.state()["positions"]).machine()

    def copy_output(self) -> None:
        value = self.msg_output.get("1.0", "end").strip()
        if not value:
            return
        self.clipboard_clear()
        self.clipboard_append(value)
        self.toast("已复制到剪贴板。", "ok")

    def save_output(self) -> None:
        value = self.msg_output.get("1.0", "end").strip()
        if not value:
            self.toast("还没有结果。", "error")
            return
        path = filedialog.asksaveasfilename(
            title="保存密文", defaultextension=".txt",
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")],
        )
        if not path:
            return
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(value)
        self.toast(f"已保存到 {path}", "ok")

    # ================================================================ 解码
    def decode_from_message(self) -> None:
        value = self.msg_output.get("1.0", "end").strip()
        if not value:
            self.toast("电报面板还没有结果。", "error")
            return
        self.dec_input.delete("1.0", "end")
        self.dec_input.insert("1.0", value)
        self._update_counter()
        self.switch_tab("decode")

    def run_decode(self) -> None:
        ciphertext = self.dec_input.get("1.0", "end").strip()
        if not DEFAULT_MODEL.letters(ciphertext):
            self.toast("先粘入要解开的密文。", "error")
            return
        if self.job is not None:
            return

        solve = self.var_solve.get()
        key = self.key.with_(positions=self.state()["positions"])
        spaces = self.var_spaces.get()
        punctuation = self.var_punct.get()

        if not solve:
            result = decode(ciphertext, key.machine(), positions=key.positions,
                            with_spaces=spaces, with_punctuation=punctuation)
            self._show_decode(result)
            return

        self.dec_progress_holder.pack(fill="x", after=self.dec_run)
        self.dec_progress.set(0.02)
        self.dec_progress_text.configure(text="正在搜索接线板…")
        self.dec_run.set_enabled(False)

        def work(job: Job):
            return autosolve.decipher_with_key(
                ciphertext, key, solve=True, with_spaces=spaces,
                with_punctuation=punctuation,
                progress=lambda share, text: self._job_progress(job, share, text),
            )

        self._start_job(work, self._decode_done, self._decode_failed,
                        progress_widget=self.dec_progress,
                        text_widget=self.dec_progress_text,
                        holder=self.dec_progress_holder,
                        button=self.dec_run)

    def _show_decode(self, result) -> None:
        self.decode_result = result
        text = getattr(result, "text", "") or "（解不出可读内容）"
        score = float(getattr(result, "score", 0.0))
        self._set_readonly(self.dec_output, text)
        self.dec_result_label.configure(
            text=f"明文 · 评分 {score:.2f}"
                 f"{' · 读得通' if score > -5.5 else ' · 评分偏低'}"
        )
        board = getattr(result, "plugboard", None)
        board_text = board.describe() if hasattr(board, "describe") else ""
        parts = [getattr(result, "note", "") or ""]
        if board_text and self.var_solve.get():
            parts.append(f"实际接线板：{board_text}")
        if not getattr(result, "confident", True):
            parts.append("密文较短或接线板无法确定，结果仅供参考。")
        self.dec_note.configure(text="    ".join(part for part in parts if part))

    def _decode_done(self, result) -> None:
        self._show_decode(result)

    def _decode_failed(self, message: str) -> None:
        self.toast(message, "error")

    # ================================================================ 破译
    def break_from_decode(self) -> None:
        value = self.dec_input.get("1.0", "end").strip()
        self.brk_input.delete("1.0", "end")
        self.brk_input.insert("1.0", value)
        self._update_counter()

    def set_crib(self, value: str) -> None:
        self.brk_crib.delete(0, "end")
        self.brk_crib.insert(0, value)

    def clear_crib(self) -> None:
        self.brk_crib.delete(0, "end")
        self.brk_offset.delete(0, "end")

    def run_break(self) -> None:
        ciphertext = self.brk_input.get("1.0", "end").strip()
        if len(DEFAULT_MODEL.letters(ciphertext)) < 12:
            self.toast("密文太短，至少要 12 个字母。", "error")
            return
        if not autosolve.has_numpy():
            self.toast("破译需要 numpy：python -m pip install numpy", "error")
            return
        if self.job is not None:
            return

        crib = self.brk_crib.get().strip()
        offset_text = self.brk_offset.get().strip()
        try:
            offset = int(offset_text) if offset_text else None
        except ValueError:
            self.toast("crib 位置要填一个数字，或者留空。", "error")
            return
        rings = (self.brk_rings.get().strip().upper() or "AAA")
        if len(rings) != 3 or any(char not in ALPHABET for char in rings):
            self.toast("环设定需要 3 个字母。", "error")
            return

        scope = self.choice_scope.value
        rotors = {"quick": ("I", "II", "III"),
                  "full": ("I", "II", "III", "IV", "V"),
                  "all": tuple(ROTOR_NAMES)}[scope]

        self.brk_progress_holder.pack(fill="x", after=self.brk_run)
        self.brk_progress.set(0.02)
        self.brk_progress_text.configure(text="准备搜索…")
        self.brk_run.set_enabled(False)
        self.brk_verdict.configure(text="")
        self.brk_key.pack_forget()
        self.brk_text.pack_forget()
        self.brk_actions.pack_forget()

        def work(job: Job):
            return autosolve.auto_decrypt(
                ciphertext, crib=crib or None, offset=offset, rotors=rotors,
                rings=rings,
                progress=lambda share, text: self._job_progress(job, share, text),
                should_stop=job.cancel.is_set,
            )

        self._start_job(work, self._break_done, self._break_failed,
                        progress_widget=self.brk_progress,
                        text_widget=self.brk_progress_text,
                        holder=self.brk_progress_holder,
                        button=self.brk_run)

    def _break_done(self, result: autosolve.AutoResult) -> None:
        self.break_result = result
        if result.cancelled:
            self.toast("已停止。")
            self.brk_verdict.configure(text="搜索已停止。", fg=MUTED)
            return

        if result.key is None:
            self.brk_verdict.configure(text=result.note or "没有结果。", fg=MUTED)
            return

        colour = GREEN if result.confident else AMBER
        self.brk_verdict.configure(text=result.note, fg=colour)
        key = result.key
        self.brk_key.configure(
            text=(f"转子 {key.rotors[0]}-{key.rotors[1]}-{key.rotors[2]}    "
                  f"UKW {key.reflector}    环 {key.rings}    起始 {key.positions}\n"
                  f"接线板  {key.plugboard or '无'}")
        )
        self.brk_key.pack(fill="x", pady=(6, 6))
        self._set_readonly(self.brk_text, result.text or "（没有解出可读的明文）")
        self.brk_text.pack(fill="both", expand=True, pady=(0, 6))

        for child in self.brk_actions.winfo_children():
            child.destroy()
        Button(self.brk_actions, "把这副密钥装到机器上",
               lambda: self.apply_key(key), kind="subtle", fonts=self.fonts,
               height=26, width=170).pack(side="left")
        Button(self.brk_actions, "复制明文",
               lambda: self._copy_text(result.text), kind="ghost", fonts=self.fonts,
               height=26, width=84).pack(side="left", padx=6)
        self.brk_actions.pack(fill="x")

    def _break_failed(self, message: str) -> None:
        self.brk_verdict.configure(text=f"出错：{message}", fg=ROSE)
        self.toast(message, "error")

    def _copy_text(self, value: str) -> None:
        if not value:
            return
        self.clipboard_clear()
        self.clipboard_append(value)
        self.toast("已复制到剪贴板。", "ok")

    # ================================================================== jobs
    def _start_job(
        self,
        work: Callable[[Job], Any],
        on_done: Callable[[Any], None],
        on_error: Callable[[str], None],
        progress_widget: ProgressBar,
        text_widget: tk.Label,
        holder: tk.Frame,
        button: Button,
    ) -> None:
        job = Job()
        self.job = job
        holder.pack(fill="x")

        def runner() -> None:
            try:
                job.result = work(job)
            except Exception as error:  # pragma: no cover - shown to the user
                job.error = str(error) or error.__class__.__name__
            finally:
                job.done = True

        threading.Thread(target=runner, daemon=True).start()

        def poll() -> None:
            if not job.done:
                progress_widget.set(max(0.02, min(0.98, job.progress)))
                elapsed = time.time() - job.started
                text_widget.configure(text=f"{job.message}   {elapsed:.1f}s")
                self.after(90, poll)
                return
            self.job = None
            button.set_enabled(True)
            if job.error:
                holder.pack_forget()
                on_error(job.error)
                return
            progress_widget.set(1.0)
            holder.pack_forget()
            on_done(job.result)

        self.after(90, poll)

    def _job_progress(self, job: Job, share: float, message: str) -> None:
        job.progress = max(0.0, min(1.0, share))
        job.message = message

    def cancel_job(self) -> None:
        if self.job is not None:
            self.job.cancel.set()
            self.brk_progress_text.configure(text="正在停止…")

    # ================================================================ 弹层
    def _modal(self, title: str, width: int, height: int) -> tuple[tk.Toplevel, tk.Frame]:
        window = tk.Toplevel(self)
        window.title(title)
        window.configure(bg=PANEL)
        window.transient(self)
        window.resizable(False, False)
        window.geometry(f"{width}x{height}")
        window.update_idletasks()
        x = self.winfo_rootx() + (self.winfo_width() - width) // 2
        y = self.winfo_rooty() + max(40, (self.winfo_height() - height) // 2)
        window.geometry(f"+{max(20, x)}+{max(20, y)}")
        header = tk.Frame(window, bg=PANEL_ALT, height=44)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text=title, bg=PANEL_ALT, fg=TEXT, font=self.fonts.ui(9, "bold"),
                 padx=14).pack(side="left", pady=12)
        Button(header, "关闭", window.destroy, kind="ghost", fonts=self.fonts,
               height=24, width=54).pack(side="right", padx=10, pady=10)
        body = tk.Frame(window, bg=PANEL)
        body.pack(fill="both", expand=True, padx=16, pady=14)
        window.bind("<Escape>", lambda _e: window.destroy())
        window.grab_set()
        return window, body

    def _doc(self, parent, text_value: str, size: int = 8, colour: str = TEXT_SOFT) -> tk.Label:
        return tk.Label(parent, text=text_value, bg=PANEL, fg=colour,
                        font=self.fonts.ui(size), anchor="w", justify="left",
                        wraplength=560)

    def open_help(self) -> None:
        window, body = self._modal("使用说明", 640, 660)
        canvas = tk.Canvas(body, bg=PANEL, highlightthickness=0)
        scroll = tk.Scrollbar(body, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=PANEL)
        canvas.create_window((0, 0), window=inner, anchor="nw", width=590)
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        inner.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))

        sections = (
            ("① 设定密钥", (
                "转子：点右上角的 W 标签换轮子；同一型号不能装两次，装重复时两个转子自动互换。",
                "环设定：转子下方的 ◀ ▶ 改环；窗口位置用 ▲ ▼ 步进。",
                "接线板：点一个字母再点另一个就接上一根电缆，再点已接线的字母拔掉；"
                "也可以在输入框里写 AV BS CG 回车。最多十根。",
            )),
            ("② 发电报", (
                "在「电报」里输入文字，点开始加密。空格会被换成 X 或 Q，数字写成英文——"
                "真实的恩尼格码只认识 26 个字母。",
                "把密文粘回来、切到解密、用同样的密钥再走一遍就是原文。",
            )),
            ("③ 键盘操作", (
                "焦点不在输入框时，直接敲 A–Z 就是按键：转子先步进，灯泡亮起，"
                "底部「信号路径」显示电流经过的每一跳。",
            )),
            ("④ 解码（已知密钥）", (
                "粘入密文，确认密钥条是加密时那套，点解码；机器补回词间隔与标点。",
                "密钥都对却读不懂，多半是接线板不一致：勾上「搜索接线板」让程序自己找。",
            )),
            ("⑤ 破译（不知道密钥）", (
                "粘入密文，在 crib 里填一段你确信原文里有的文字，点开始破译。"
                "程序用图灵 Bombe 的菜单攻击反推转子、反射器、起始位置与接线板。",
                "crib 留空时改为穷举全部转子位置、用英语统计打分——这条路只对没接插线的电文有效。",
                "注意：crib 必须和报文准备后的写法一致（词间隔用 X 或 Q）；"
                "环设定按历史做法假定已知。",
            )),
        )
        for heading, paragraphs in sections:
            tk.Label(inner, text=heading, bg=PANEL, fg=BRASS, font=self.fonts.ui(9, "bold"),
                     anchor="w").pack(fill="x", pady=(10, 4))
            for paragraph in paragraphs:
                self._doc(inner, "· " + paragraph).pack(fill="x", pady=1)

    def open_samples(self) -> None:
        window, body = self._modal("示例报文", 560, 380)
        self._doc(body, "点一条示例：密文与 crib 会填进破译面板，并问你要不要把它的密钥"
                        "也装到机器上。选「否」就保留当前设置，这样你并不知道答案。").pack(
            fill="x", pady=(0, 10))
        for sample in samples.SAMPLES:
            row = tk.Frame(body, bg=PANEL_ALT, highlightthickness=1,
                           highlightbackground=LINE, cursor="hand2")
            row.pack(fill="x", pady=3)
            text_frame = tk.Frame(row, bg=PANEL_ALT)
            text_frame.pack(side="left", fill="x", expand=True, padx=10, pady=7)
            tk.Label(text_frame, text=sample.title, bg=PANEL_ALT, fg=TEXT,
                     font=self.fonts.ui(8, "bold"), anchor="w").pack(fill="x")
            tk.Label(text_frame, text=sample.subtitle, bg=PANEL_ALT, fg=MUTED,
                     font=self.fonts.tiny, anchor="w").pack(fill="x")
            tk.Label(row, text=f"{len(sample.ciphertext)} 字母", bg=PANEL_ALT, fg=FAINT,
                     font=self.fonts.tiny).pack(side="right", padx=10)
            for widget in (row, text_frame):
                widget.bind("<Button-1>", lambda _e, s=sample: self._load_sample(s, window))

    def _load_sample(self, sample: samples.Sample, window: tk.Toplevel) -> None:
        self.brk_input.delete("1.0", "end")
        self.brk_input.insert("1.0", sample.ciphertext)
        self.brk_crib.delete(0, "end")
        self.brk_crib.insert(0, sample.crib.replace("X", " ").replace("Q", " ").strip())
        self.brk_offset.delete(0, "end")
        if sample.crib_offset is not None:
            self.brk_offset.insert(0, str(sample.crib_offset))
        self.brk_rings.delete(0, "end")
        self.brk_rings.insert(0, sample.key.rings)
        self._update_counter()
        self.switch_tab("break")
        window.destroy()
        if messagebox.askyesno("载入示例", f"已载入「{sample.title}」。\n\n"
                                          "要把它的密钥也装到机器上吗？\n"
                                          "（选「否」保留当前设置，正好用来试破译）"):
            self.apply_key(sample.key)

    def open_keycard(self) -> None:
        window, body = self._modal("密钥卡", 560, 470)
        state = self.state()
        grid = tk.Frame(body, bg=PANEL)
        grid.pack(fill="x")
        for column in range(3):
            grid.columnconfigure(column, weight=1)

        def labelled(parent, caption: str, row: int, column: int, span: int = 1):
            holder = tk.Frame(parent, bg=PANEL)
            holder.grid(row=row, column=column, columnspan=span, sticky="ew",
                        padx=(0, 8), pady=(0, 8))
            tk.Label(holder, text=caption, bg=PANEL, fg=FAINT, font=self.fonts.tiny,
                     anchor="w").pack(fill="x")
            return holder

        rotor_choices = []
        for index, role in enumerate(("左转子", "中转子", "右转子")):
            holder = labelled(grid, role, 0, index)
            choice = self._choice(holder, "", tuple(f"Walze {n}" for n in ROTOR_NAMES),
                                  tuple(ROTOR_NAMES), initial=ROTOR_NAMES.index(state["rotors"][index]))
            choice.pack(fill="x")
            rotor_choices.append(choice)

        holder = labelled(grid, "反射器", 1, 0)
        reflector_choice = self._choice(holder, "", tuple(f"UKW {n}" for n in REFLECTOR_NAMES),
                                        tuple(REFLECTOR_NAMES),
                                        initial=REFLECTOR_NAMES.index(state["reflector"]))
        reflector_choice.pack(fill="x")

        holder = labelled(grid, "环设定 Ringstellung", 1, 1)
        rings_entry = self._entry(holder, mono=True)
        rings_entry.insert(0, state["rings"])
        rings_entry.pack(fill="x")

        holder = labelled(grid, "起始位置 Grundstellung", 1, 2)
        positions_entry = self._entry(holder, mono=True)
        positions_entry.insert(0, state["positions"])
        positions_entry.pack(fill="x")

        holder = labelled(grid, "接线板 Steckerbrett", 2, 0, span=3)
        plug_entry = self._entry(holder, mono=True)
        plug_entry.insert(0, state["plugboard"])
        plug_entry.pack(fill="x")

        def apply() -> None:
            self.rebuild(
                rotors=[choice.value for choice in rotor_choices],
                reflector=reflector_choice.value,
                rings=rings_entry.get().strip().upper(),
                positions=positions_entry.get().strip().upper(),
                plugboard=plug_entry.get().strip(),
            )
            window.destroy()

        def randomise() -> None:
            key = Key.random(cables=Plugboard.MAX_PAIRS)
            self.apply_key(key)
            window.destroy()
            self.toast("已生成随机密钥并装机。", "ok")

        tk.Label(body, text="预设", bg=PANEL, fg=BRASS, font=self.fonts.ui(8, "bold"),
                 anchor="w").pack(fill="x", pady=(8, 4))
        for preset in samples.PRESETS:
            row = tk.Frame(body, bg=PANEL_ALT, highlightthickness=1,
                           highlightbackground=LINE, cursor="hand2")
            row.pack(fill="x", pady=2)
            tk.Label(row, text=preset["name"], bg=PANEL_ALT, fg=TEXT,
                     font=self.fonts.small, anchor="w").pack(side="left", padx=10, pady=6)
            tk.Label(row, text=preset["detail"], bg=PANEL_ALT, fg=FAINT,
                     font=self.fonts.tiny, anchor="w").pack(side="left")
            row.bind("<Button-1>", lambda _e, p=preset: (
                self.apply_key(Key.from_dict(p)), window.destroy(),
                self.toast(f"已套用「{p['name']}」。", "ok")))

        actions = tk.Frame(body, bg=PANEL)
        actions.pack(fill="x", side="bottom", pady=(12, 0))
        Button(actions, "装到机器上", apply, kind="primary", fonts=self.fonts,
               height=32, width=120).pack(side="right")
        Button(actions, "随机生成", randomise, kind="subtle", fonts=self.fonts,
               height=32, width=100).pack(side="right", padx=6)


def main() -> int:
    app = EnigmaApp()
    app.mainloop()
    return 0
