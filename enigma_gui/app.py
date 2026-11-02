"""恩尼格码模拟器 —— 桌面界面（中文）。"""

from __future__ import annotations

import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from enigma import EnigmaMachine, Plugboard, PlugboardError
from enigma.data import ALPHABET
from enigma.message import format_groups, split_messages
from enigma.preparation import prepare_text

from . import theme
from .widgets import Keyboard, LampField, PlugboardWidget, RotorControl, SignalTrace

APP_TITLE = "恩尼格码 ENIGMA · 三转子密码机模拟器"

HELP_TEXT = """【怎么操作这台机器】

· 窗口获得焦点时，直接在键盘上敲 A–Z 就是按键，机器会步进并点亮灯泡；
  也可以用鼠标点击屏幕上的按键。
· 在报文输入框里打字只是录入文本，不会触发按键。

【设置机器】
· 反射器（UKW）：A / B / C，历史上最常用的是 B。
· 转子：三个下拉框分别是左、中、右转子。选中机器里已有的转子会自动与之互换。
· 环设定与窗口位置：可以直接输入字母（回车确认），也可以用 ▲ ▼ 微调。
· 「缺口」指示灯亮起表示该转子正停在缺口上，下一次按键会带动左边转子。

【接线板】
· 在输入框里写接线，例如 AV BS CG，回车即可应用。
· 也可以直接点击字母：先点一个字母，再点另一个即接上一根电缆；
  再次点击已接线的字母可以拔掉。
· 真实机器最多 10 根电缆，同一个字母不能重复使用。

【报文】
· 「明文 → 准备后的文本 → 密文」三者一一对应，可以逐段核对。
· 数字：默认把 1–4 位数字写成英文文字（如 1932 → NINETEEN THIRTY TWO），
  5 位以上的数字串逐位拼写以保证精确（如 48152 → FOUREIGHTONEFIVETWO）。
· 空格：自动模式下用文本里出现较少的那个字母作替代（X 或 Q）。
· 「加密·解密」两个方向都能用 —— 恩尼格码是互反的，同一设置下解密即还原。
· 「五字分组」按历史上传输的样子，每 5 个字母一组。

【批量处理】
· 「按空行拆分报文」把整份文件按空行分成多条报文逐条加密。
· 「每条报文复位转子」在每条报文前把转子复位，模拟每条报文都换新密钥。

【校验】
默认设置（转子 I-II-III、反射器 B、环设定 AAA、起始 AAA）下：
    AAAAA  →  BDZGO
这是公开的历史参考向量，可用来检查实现是否正确。
"""


class EnigmaApp(tk.Tk):
    """模拟器主窗口。"""

    def __init__(self) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.configure(bg=theme.BG)
        self.minsize(1100, 720)
        theme.build_styles(self)

        self.machine = EnigmaMachine.create(
            rotor_order=("I", "II", "III"),
            reflector="B",
            plugboard=Plugboard(),
            ring_settings=("A", "A", "A"),
            positions=("A", "A", "A"),
        )
        self._keyed_output: list[str] = []
        self._home_positions = "AAA"
        self._job: dict | None = None

        self._build_header()
        self._build_machine_panel()
        self._build_console()
        self._build_side_panel()
        self._build_status_bar()

        self._refresh()
        self.bind("<KeyPress>", self._on_physical_key)
        self.after(60, self._fit_to_screen)
        self.after(60, self._focus_window)

    # ------------------------------------------------------------- 布局
    def _fit_to_screen(self) -> None:
        """让窗口大小始终落在屏幕之内。"""
        width = min(1480, max(1000, self.winfo_screenwidth() - 16))
        height = min(900, max(700, self.winfo_screenheight() - 60))
        self.geometry(f"{width}x{height}+0+0")

    def _focus_window(self) -> None:
        """让窗口一开始就能接收键盘输入。"""
        self.focus_set()

    def _panel(self, master: tk.Misc, title: str) -> tuple[tk.Frame, tk.Frame]:
        """创建一个带标题的面板，返回面板本体与内容区。"""
        frame = tk.Frame(master, bg=theme.PANEL, highlightbackground=theme.PANEL_LINE,
                         highlightthickness=1, bd=0)
        tk.Label(
            frame,
            text=title,
            bg=theme.PANEL,
            fg=theme.TEXT_DIM,
            font=theme.Fonts.SECTION,
        ).pack(anchor="w", padx=14, pady=(12, 6))
        body = tk.Frame(frame, bg=theme.PANEL)
        body.pack(fill="both", expand=True, padx=0, pady=0)
        return frame, body

    def _build_header(self) -> None:
        header = tk.Frame(self, bg=theme.BG)
        header.grid(row=0, column=0, columnspan=2, sticky="ew", padx=22, pady=(16, 6))
        header.grid_columnconfigure(1, weight=1)

        tk.Label(
            header,
            text="ENIGMA",
            bg=theme.BG,
            fg=theme.AMBER,
            font=("Consolas", 26, "bold"),
        ).grid(row=0, column=0, sticky="w")
        tk.Label(
            header,
            text="三转子密码机 · 反射器 · 接线板 · 互反密码\n"
                 "直接在键盘上敲字母即可按键，也可以用鼠标点击",
            bg=theme.BG,
            fg=theme.TEXT_FAINT,
            font=theme.Fonts.SUBTITLE,
            anchor="w",
            justify="left",
        ).grid(row=1, column=0, columnspan=2, sticky="w")

        buttons = tk.Frame(header, bg=theme.BG)
        buttons.grid(row=0, column=2, rowspan=2, sticky="e")
        self._button(buttons, "使用说明", self._show_help).pack(side="left", padx=(0, 8))
        self._button(buttons, "全部重置", self._reset_all).pack(side="left")

    def _build_machine_panel(self) -> None:
        panel, body = self._panel(self, "机器设置")
        panel.grid(row=1, column=0, columnspan=2, sticky="ew", padx=22, pady=4)
        body.grid_columnconfigure(0, weight=0, minsize=225)
        body.grid_columnconfigure(1, weight=1)
        body.grid_columnconfigure(2, weight=0, minsize=225)

        # --- 反射器 ---
        reflector_frame = tk.Frame(body, bg=theme.PANEL)
        reflector_frame.grid(row=0, column=0, sticky="nsew", padx=(14, 18), pady=(0, 12))
        tk.Label(
            reflector_frame,
            text="反射器 UKW",
            bg=theme.PANEL,
            fg=theme.TEXT_FAINT,
            font=theme.Fonts.SMALL,
        ).pack(anchor="w")
        self.reflector_box = ttk.Combobox(
            reflector_frame,
            values=["A", "B", "C"],
            state="readonly",
            width=8,
            font=theme.Fonts.MONO,
            style="Enigma.TCombobox",
        )
        self.reflector_box.pack(anchor="w", pady=(4, 0))
        self.reflector_box.bind("<<ComboboxSelected>>", self._reflector_selected)
        tk.Label(
            reflector_frame,
            text="反射器不会把字母连到自己，\n所以任何字母都不会被加密成它自己。",
            bg=theme.PANEL,
            fg=theme.TEXT_FAINT,
            font=theme.Fonts.SMALL,
            justify="left",
        ).pack(anchor="w", pady=(10, 0))

        # --- 转子 ---
        rotors_frame = tk.Frame(body, bg=theme.PANEL)
        rotors_frame.grid(row=0, column=1, sticky="nsew")
        titles = ("左转子", "中转子", "右转子")
        self.rotor_controls: list[RotorControl] = []
        for index, title in enumerate(titles):
            control = RotorControl(
                rotors_frame,
                title=title,
                on_rotor_change=lambda name, i=index: self._rotor_changed(i, name),
                on_ring_change=lambda delta, i=index: self._ring_changed(i, delta),
                on_position_change=lambda delta, i=index: self._position_changed(i, delta),
                on_ring_set=lambda letter, i=index: self._ring_set(i, letter),
                on_position_set=lambda letter, i=index: self._position_set(i, letter),
            )
            control.grid(row=0, column=index, padx=(0, 16), sticky="nsew")
            rotors_frame.grid_columnconfigure(index, weight=1, minsize=165)
            self.rotor_controls.append(control)

        # --- 缺口 ---
        notch_frame = tk.Frame(body, bg=theme.PANEL)
        notch_frame.grid(row=0, column=2, sticky="nsew", padx=(0, 14), pady=(0, 12))
        tk.Label(
            notch_frame,
            text="转子缺口",
            bg=theme.PANEL,
            fg=theme.TEXT_FAINT,
            font=theme.Fonts.SMALL,
        ).pack(anchor="w")
        self.notch_summary = tk.Label(
            notch_frame,
            text="",
            bg=theme.PANEL,
            fg=theme.TEXT_DIM,
            font=theme.Fonts.MONO,
            justify="left",
        )
        self.notch_summary.pack(anchor="w", pady=(6, 0))

    def _build_console(self) -> None:
        console = tk.Frame(self, bg=theme.BG)
        console.grid(row=2, column=0, sticky="nsew", padx=(22, 10), pady=6)
        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0, minsize=470)

        lamps_panel, lamps_body = self._panel(console, "灯泡")
        lamps_panel.pack(fill="x")
        self.lamps = LampField(lamps_body)
        self.lamps.pack(padx=12, pady=(0, 10))

        keyboard_panel, keyboard_body = self._panel(console, "键盘")
        keyboard_panel.pack(fill="x", pady=(10, 0))
        self.keyboard = Keyboard(keyboard_body, on_press=self._press_key)
        self.keyboard.pack(padx=12, pady=(0, 10))

        output_panel, output_body = self._panel(console, "按键输出")
        output_panel.pack(fill="both", expand=True, pady=(10, 0))
        self.output_label = tk.Label(
            output_body,
            text="—",
            bg=theme.PANEL,
            fg=theme.AMBER,
            font=theme.Fonts.MONO,
            anchor="nw",
            justify="left",
            wraplength=640,
        )
        self.output_label.pack(anchor="w", padx=14, pady=(0, 8))

        trace_panel, trace_body = self._panel(console, "信号路径")
        trace_panel.pack(fill="x", pady=(10, 0))
        self.trace = SignalTrace(trace_body)
        self.trace.pack(fill="x", padx=14, pady=(0, 12))

    def _build_side_panel(self) -> None:
        """右侧栏：接线板、报文、批量处理。内容较多，可以滚动。"""
        side = tk.Frame(self, bg=theme.BG)
        side.grid(row=2, column=1, sticky="nsew", padx=(10, 22), pady=6)
        side.grid_columnconfigure(0, weight=1)
        side.grid_rowconfigure(0, weight=1)

        canvas = tk.Canvas(side, bg=theme.BG, highlightthickness=0, bd=0)
        scrollbar = ttk.Scrollbar(side, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=theme.BG)
        window = canvas.create_window((0, 0), window=inner, anchor="nw")

        def _resize(event) -> None:
            canvas.itemconfigure(window, width=canvas.winfo_width())

        def _scroll_region(event) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))

        inner.bind("<Configure>", _scroll_region)
        canvas.bind("<Configure>", _resize)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        inner.grid_columnconfigure(0, weight=1)

        def _on_wheel(event) -> None:
            if isinstance(event.widget, (tk.Text, ttk.Combobox, tk.Entry)):
                return
            canvas.yview_scroll(int(-event.delta / 60), "units")

        canvas.bind_all("<MouseWheel>", _on_wheel)

        # --- 报文（放在最上面，最常用的操作无需滚动） ---
        message_panel, message_body = self._panel(inner, "报文")
        message_panel.grid(row=0, column=0, sticky="ew")

        options = tk.Frame(message_body, bg=theme.PANEL)
        options.pack(fill="x", padx=14, pady=(0, 8))

        numbers_row = tk.Frame(options, bg=theme.PANEL)
        numbers_row.pack(fill="x")
        tk.Label(
            numbers_row, text="数字", bg=theme.PANEL, fg=theme.TEXT_FAINT,
            font=theme.Fonts.SMALL,
        ).pack(side="left")
        self.number_policy = ttk.Combobox(
            numbers_row,
            values=list(NUMBER_POLICIES.values()),
            state="readonly",
            width=20,
            font=theme.Fonts.SMALL,
            style="Enigma.TCombobox",
        )
        self.number_policy.current(0)
        self.number_policy.pack(side="left", padx=(4, 0), fill="x", expand=True)

        space_row = tk.Frame(options, bg=theme.PANEL)
        space_row.pack(fill="x", pady=(4, 0))
        tk.Label(
            space_row, text="空格", bg=theme.PANEL, fg=theme.TEXT_FAINT,
            font=theme.Fonts.SMALL,
        ).pack(side="left")
        self.space_letter = ttk.Combobox(
            space_row,
            values=list(SPACE_LETTERS.values()),
            state="readonly",
            width=10,
            font=theme.Fonts.SMALL,
            style="Enigma.TCombobox",
        )
        self.space_letter.current(0)
        self.space_letter.pack(side="left", padx=(4, 10))

        self.join_words = tk.BooleanVar(value=False)
        tk.Checkbutton(
            space_row,
            text="连写数字文字",
            variable=self.join_words,
            bg=theme.PANEL,
            fg=theme.TEXT_DIM,
            activebackground=theme.PANEL,
            activeforeground=theme.TEXT,
            selectcolor=theme.PANEL_HI,
            font=theme.Fonts.SMALL,
            highlightthickness=0,
            bd=0,
        ).pack(side="left")

        plain_header = tk.Frame(message_body, bg=theme.PANEL)
        plain_header.pack(fill="x", padx=14)
        tk.Label(
            plain_header,
            text="明文",
            bg=theme.PANEL,
            fg=theme.TEXT_FAINT,
            font=theme.Fonts.SMALL,
        ).pack(side="left")
        self._button(plain_header, "打开文件…", self._open_file).pack(
            side="right", padx=(4, 0)
        )
        self._button(plain_header, "保存密文…", self._save_cipher).pack(
            side="right", padx=(4, 0)
        )
        self._button(plain_header, "清空", self._clear_message).pack(side="right")

        self.plain_text = tk.Text(
            message_body,
            height=2,
            bg=theme.PANEL_HI,
            fg=theme.TEXT,
            insertbackground=theme.AMBER,
            relief="flat",
            font=theme.Fonts.MONO,
            wrap="word",
            padx=10,
            pady=8,
        )
        self.plain_text.pack(fill="both", expand=True, padx=14, pady=(2, 8))

        tk.Label(
            message_body,
            text="准备后的文本（真正送进机器的字母）",
            bg=theme.PANEL,
            fg=theme.TEXT_FAINT,
            font=theme.Fonts.SMALL,
        ).pack(anchor="w", padx=14)
        self.prepared_text = tk.Text(
            message_body,
            height=2,
            bg=theme.PANEL_HI,
            fg=theme.CYAN,
            relief="flat",
            font=theme.Fonts.MONO,
            wrap="word",
            padx=10,
            pady=8,
        )
        self.prepared_text.pack(fill="both", expand=False, padx=14, pady=(2, 8))

        tk.Label(
            message_body,
            text="密文",
            bg=theme.PANEL,
            fg=theme.TEXT_FAINT,
            font=theme.Fonts.SMALL,
        ).pack(anchor="w", padx=14)
        self.cipher_text = tk.Text(
            message_body,
            height=2,
            bg=theme.PANEL_HI,
            fg=theme.AMBER,
            relief="flat",
            font=theme.Fonts.MONO,
            wrap="word",
            padx=10,
            pady=8,
        )
        self.cipher_text.pack(fill="both", expand=True, padx=14, pady=(2, 8))

        buttons = tk.Frame(message_body, bg=theme.PANEL)
        buttons.pack(fill="x", padx=14, pady=(0, 12))
        self._primary_button(buttons, "加密 · 解密", self._encrypt_message).pack(
            side="left", padx=(0, 8)
        )
        self._button(buttons, "五字分组", self._group_message).pack(side="left")

        # --- 接线板 ---
        plug_panel, plug_body = self._panel(inner, "接线板 Steckerbrett")
        plug_panel.grid(row=1, column=0, sticky="ew", pady=(10, 0))

        plug_entry_row = tk.Frame(plug_body, bg=theme.PANEL)
        plug_entry_row.pack(fill="x", padx=14, pady=(0, 6))
        self.plug_entry = tk.Entry(
            plug_entry_row,
            bg=theme.PANEL_HI,
            fg=theme.CYAN,
            insertbackground=theme.CYAN,
            relief="flat",
            font=theme.Fonts.MONO,
            highlightthickness=1,
            highlightbackground=theme.PANEL_LINE,
        )
        self.plug_entry.pack(side="left", fill="x", expand=True, ipady=3)
        self.plug_entry.insert(0, "")
        self.plug_entry.bind("<Return>", lambda _e: self._apply_plug_text())
        self._button(plug_entry_row, "应用", self._apply_plug_text).pack(
            side="left", padx=(8, 0)
        )

        self.plugboard_widget = PlugboardWidget(plug_body, on_change=self._plug_changed)
        self.plugboard_widget.pack(padx=14)

        plug_actions = tk.Frame(plug_body, bg=theme.PANEL)
        plug_actions.pack(fill="x", padx=14, pady=(6, 12))
        self._button(plug_actions, "清空接线", self._clear_plugboard).pack(side="left")
        self.plug_summary = tk.Label(
            plug_actions,
            text="未接线",
            bg=theme.PANEL,
            fg=theme.TEXT_FAINT,
            font=theme.Fonts.SMALL,
            anchor="e",
        )
        self.plug_summary.pack(side="right")

        # --- 批量处理 ---
        batch_panel, batch_body = self._panel(inner, "批量处理")
        batch_panel.grid(row=2, column=0, sticky="ew", pady=(10, 0))

        self.split_messages = tk.BooleanVar(value=False)
        self.restart_rotors = tk.BooleanVar(value=False)
        for text, variable in (
            ("按空行拆分报文（一条报文一块）", self.split_messages),
            ("每条报文前复位转子", self.restart_rotors),
        ):
            tk.Checkbutton(
                batch_body,
                text=text,
                variable=variable,
                bg=theme.PANEL,
                fg=theme.TEXT_DIM,
                activebackground=theme.PANEL,
                activeforeground=theme.TEXT,
                selectcolor=theme.PANEL_HI,
                font=theme.Fonts.SMALL,
                highlightthickness=0,
                bd=0,
                anchor="w",
            ).pack(fill="x", padx=14, pady=(0, 4))

        self.progress = ttk.Progressbar(
            batch_body, mode="determinate", maximum=100, length=320
        )
        self.progress.pack(fill="x", padx=14, pady=(8, 0))

        self.stats_label = tk.Label(
            batch_body,
            text="",
            bg=theme.PANEL,
            fg=theme.TEXT_FAINT,
            font=theme.Fonts.SMALL,
            anchor="w",
            justify="left",
        )
        self.stats_label.pack(fill="x", padx=14, pady=(6, 12))

    def _build_status_bar(self) -> None:
        status = tk.Label(
            self,
            text="",
            bg=theme.PANEL,
            fg=theme.TEXT_DIM,
            font=theme.Fonts.STATUS,
            anchor="w",
            padx=18,
            pady=8,
        )
        status.grid(row=3, column=0, columnspan=2, sticky="ew")
        self.status_label = status

    def _button(self, master: tk.Misc, text: str, command) -> tk.Button:
        return tk.Button(
            master,
            text=text,
            command=command,
            bg=theme.KEY_BG,
            fg=theme.TEXT_DIM,
            activebackground=theme.AMBER,
            activeforeground=theme.BG,
            relief="flat",
            bd=0,
            font=theme.Fonts.SMALL,
            cursor="hand2",
            padx=12,
            pady=6,
        )

    def _primary_button(self, master: tk.Misc, text: str, command) -> tk.Button:
        """主要操作按钮（高亮）。"""
        return tk.Button(
            master,
            text=text,
            command=command,
            bg=theme.AMBER,
            fg=theme.BG,
            activebackground="#ffd166",
            activeforeground=theme.BG,
            relief="flat",
            bd=0,
            font=theme.Fonts.SECTION,
            cursor="hand2",
            padx=18,
            pady=7,
        )

    # -------------------------------------------------------------- 帮助
    def _show_help(self) -> None:
        """弹出使用说明。"""
        window = tk.Toplevel(self)
        window.title("使用说明")
        window.configure(bg=theme.PANEL)
        window.geometry("680x680")
        window.transient(self)
        window.minsize(520, 420)

        tk.Label(
            window,
            text="使用说明",
            bg=theme.PANEL,
            fg=theme.AMBER,
            font=theme.Fonts.SECTION,
        ).pack(anchor="w", padx=18, pady=(16, 8))

        text = tk.Text(
            window,
            height=16,
            bg=theme.PANEL_HI,
            fg=theme.TEXT,
            relief="flat",
            font=("Microsoft YaHei UI", 11),
            wrap="word",
            padx=16,
            pady=12,
        )
        text.pack(fill="both", expand=True, padx=18)
        text.insert("1.0", HELP_TEXT)
        text.config(state="disabled")

        tk.Button(
            window,
            text="关闭",
            command=window.destroy,
            bg=theme.AMBER,
            fg=theme.BG,
            relief="flat",
            bd=0,
            font=theme.Fonts.SECTION,
            cursor="hand2",
            padx=20,
            pady=7,
        ).pack(pady=(0, 16))

    # -------------------------------------------------------------- 辅助
    def _set_text(self, widget: tk.Text, value: str) -> None:
        widget.config(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", value)
        widget.config(state="disabled")

    def _policy_key(self) -> str:
        text = self.number_policy.get()
        for key, label in NUMBER_POLICIES.items():
            if label == text:
                return key
        return "auto"

    def _space_key(self) -> str:
        text = self.space_letter.get()
        for key, label in SPACE_LETTERS.items():
            if label == text:
                return key
        return "auto"

    # -------------------------------------------------------------- 操作
    def _press_key(self, letter: str) -> None:
        """按下机器的一个按键。"""
        trace: list[tuple[str, str]] = []
        result = self.machine.press(letter, trace=trace)
        self._keyed_output.append(result)
        self.lamps.light(result)
        self.trace.show([(step.stage, step.letter) for step in trace])
        self.output_label.configure(text="".join(self._keyed_output[-120:]))
        self._refresh()

    def _on_physical_key(self, event) -> None:
        """处理真实键盘的按键。"""
        if isinstance(event.widget, (tk.Text, ttk.Entry, ttk.Combobox)):
            return
        character = event.char or ""
        if not character:
            # 某些键盘布局只给出 keysym，没有字符
            keysym = getattr(event, "keysym", "") or ""
            if len(keysym) == 1:
                character = keysym
        character = character.upper()
        if len(character) == 1 and character in ALPHABET:
            self._press_key(character)

    def _rotor_changed(self, index: int, name: str) -> None:
        names = list(self.machine.rotor_names)
        # 同一个转子不能装两次：选到已装的转子就与之互换
        if name in names and names.index(name) != index:
            other = names.index(name)
            names[index], names[other] = names[other], names[index]
        else:
            names[index] = name
        self.machine.set_rotors(tuple(names))
        self._refresh()

    def _ring_changed(self, index: int, delta: int) -> None:
        rotor = self.machine.rotors[index]
        rotor.ring = (rotor.ring + delta) % 26
        self._refresh()

    def _ring_set(self, index: int, letter: str) -> None:
        self.machine.rotors[index].ring = ord(letter) - 65
        self._refresh()

    def _position_changed(self, index: int, delta: int) -> None:
        rotor = self.machine.rotors[index]
        rotor.position = (rotor.position + delta) % 26
        self._home_positions = self.machine.positions
        self._refresh()

    def _position_set(self, index: int, letter: str) -> None:
        self.machine.rotors[index].position = ord(letter) - 65
        self._home_positions = self.machine.positions
        self._refresh()

    def _reflector_selected(self, _event=None) -> None:
        self.machine.reflector = self.reflector_box.get()
        self._refresh()

    def _plug_changed(self, first: str, second: str) -> None:
        try:
            self.machine.plugboard.toggle(first, second)
        except PlugboardError as error:
            messagebox.showwarning("接线板", str(error), parent=self)
        self._refresh()

    def _apply_plug_text(self) -> None:
        """按输入框里的字母对设置接线板，例如 "AV BS CG"。"""
        text = self.plug_entry.get().strip()
        try:
            board = Plugboard.parse(text)
        except PlugboardError as error:
            messagebox.showwarning("接线板", str(error), parent=self)
            return
        if len(board.pairs) > Plugboard.MAX_PAIRS:
            messagebox.showwarning(
                "接线板", f"最多只能接 {Plugboard.MAX_PAIRS} 根电缆。", parent=self
            )
            return
        self.machine.plugboard = board
        self._refresh()

    def _clear_plugboard(self) -> None:
        self.machine.plugboard.clear()
        self.plugboard_widget.clear_pending()
        self._refresh()

    def _open_file(self) -> None:
        path = filedialog.askopenfilename(
            parent=self,
            title="打开明文文件",
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")],
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as handle:
                text = handle.read()
        except OSError as error:
            messagebox.showerror("打开文件", str(error), parent=self)
            return
        self.plain_text.delete("1.0", "end")
        self.plain_text.insert("1.0", text)
        self.stats_label.configure(text=f"已载入 {len(text)} 个字符：{path}")

    def _save_cipher(self) -> None:
        cipher = self.cipher_text.get("1.0", "end").strip()
        if not cipher:
            messagebox.showinfo("保存密文", "还没有密文可以保存。", parent=self)
            return
        path = filedialog.asksaveasfilename(
            parent=self,
            title="保存密文",
            defaultextension=".txt",
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")],
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(cipher + "\n")
        except OSError as error:
            messagebox.showerror("保存密文", str(error), parent=self)
            return
        self.stats_label.configure(text=f"密文已保存：{path}")

    def _encrypt_message(self) -> None:
        """准备明文并送进机器。"""
        raw = self.plain_text.get("1.0", "end")
        if not raw.strip():
            return

        blocks = split_messages(raw) if self.split_messages.get() else [raw]
        prepared = [
            prepare_text(
                block,
                number_policy=self._policy_key(),
                space_letter=self._space_key(),
                join_number_words=self.join_words.get(),
            )
            for block in blocks
        ]

        self._set_text(self.prepared_text, "\n\n".join(item.text for item in prepared))
        self._keyed_output = []
        self.output_label.configure(text="")
        self.lamps.clear()

        self._start_job([item.text for item in prepared])

    def _start_job(self, messages: list[str]) -> None:
        """开始加密，长文本分块处理以保持界面流畅。"""
        self._job = {
            "queue": list(messages),
            "current": "",
            "output": [],
            "total": sum(len(message) for message in messages),
            "done": 0,
            "messages": len(messages),
            "started": time.perf_counter(),
        }
        self.progress["value"] = 0
        self._process_next_chunk()

    def _process_next_chunk(self) -> None:
        """加密当前报文的一段，然后回来继续。"""
        job = self._job
        if job is None:
            return

        budget = CHUNK_SIZE
        while budget > 0:
            if not job["current"]:
                if not job["queue"]:
                    break
                if self.restart_rotors.get():
                    self.machine.set_positions(self._home_positions)
                job["current"] = job["queue"].pop(0)
                job["output"].append("")
            take = job["current"][:budget]
            job["current"] = job["current"][budget:]
            job["output"][-1] += self.machine.encrypt(take)
            job["done"] += len(take)
            budget -= len(take)
            if job["current"]:
                break  # 让界面有机会刷新

        if job["total"]:
            self.progress["value"] = 100 * job["done"] / job["total"]

        if job["current"] or job["queue"]:
            self.after(1, self._process_next_chunk)
        else:
            self._finish_job()

    def _finish_job(self) -> None:
        job = self._job or {}
        self._job = None
        cipher = "\n\n".join(job.get("output", []))
        self._set_text(self.cipher_text, cipher)

        elapsed = time.perf_counter() - job.get("started", time.perf_counter())
        letters = job.get("done", 0)
        messages = job.get("messages", 0)
        self.stats_label.configure(
            text=(
                f"{letters} 个字母 · {messages} 条报文 · 用时 {elapsed:.2f} 秒"
            )
        )
        self.progress["value"] = 100
        self._refresh()

    def _group_message(self) -> None:
        """把密文按五字母分组显示，与历史上的传输格式一致。"""
        cipher = self.cipher_text.get("1.0", "end").strip()
        if not cipher:
            return
        grouped = "\n\n".join(format_groups(part) for part in cipher.split("\n\n"))
        self._set_text(self.cipher_text, grouped)

    def _clear_message(self) -> None:
        self.plain_text.delete("1.0", "end")
        self._set_text(self.prepared_text, "")
        self._set_text(self.cipher_text, "")
        self._keyed_output = []
        self.output_label.configure(text="—")
        self.lamps.clear()

    def _reset_all(self) -> None:
        self.machine = EnigmaMachine.create()
        self._keyed_output = []
        self._home_positions = "AAA"
        self.output_label.configure(text="—")
        self.lamps.clear()
        self.plugboard_widget.clear_pending()
        self._clear_plugboard()
        self._refresh()

    # -------------------------------------------------------------- 刷新
    def _refresh(self) -> None:
        """把机器状态同步到各个控件。"""
        machine = self.machine
        self.reflector_box.set(machine.reflector)
        for control, rotor in zip(self.rotor_controls, machine.rotors):
            control.set_rotor(rotor.spec.name)
            control.set_ring(rotor.ring_letter)
            control.set_position(rotor.position_letter)
            control.set_notch_active(rotor.at_turnover)

        plugged = [letter for pair in machine.plugboard.pairs for letter in pair]
        self.plugboard_widget.set_plugged(plugged)
        self.plug_summary.configure(
            text=machine.plugboard.describe() or "未接线"
        )
        if self.plug_entry.focus_get() is not self.plug_entry:
            self.plug_entry.delete(0, "end")
            self.plug_entry.insert(0, machine.plugboard.describe())

        self.notch_summary.configure(
            text="  ".join(
                f"{rotor.spec.name}:{'/'.join(rotor.spec.turnover)}"
                for rotor in machine.rotors
            )
        )

        self.status_label.configure(
            text=(
                f"  反射器 {machine.reflector}   |   转子 "
                f"{'-'.join(machine.rotor_names)}   |   环设定 "
                f"{machine.ring_settings}   |   位置 {machine.positions}   |   "
                f"灯泡 {self.lamps._lit or '—'}   |   接线 "
                f"{machine.plugboard.describe() or '无'}"
            )
        )


NUMBER_POLICIES = {
    "auto": "自动（短→文字，长→逐位）",
    "words": "文字（可读）",
    "digits": "逐位拼写（精确）",
}

SPACE_LETTERS = {
    "auto": "自动（X / Q）",
    "X": "X",
    "Q": "Q",
}

CHUNK_SIZE = 2000


def main() -> None:
    """启动程序。"""
    app = EnigmaApp()
    app.mainloop()


if __name__ == "__main__":  # pragma: no cover
    main()
