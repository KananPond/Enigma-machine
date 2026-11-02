"""The Enigma desktop application.

Run it with ``python run.py`` (or ``python -m enigma_gui``).
"""

from __future__ import annotations

import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from enigma import EnigmaMachine, Plugboard, PlugboardError
from enigma.data import ALPHABET
from enigma.message import format_groups, normalize, split_messages
from enigma.preparation import prepare_text

from . import theme
from .widgets import Keyboard, LampField, PlugboardWidget, RotorControl, SignalTrace

APP_TITLE = "ENIGMA  ·  Wehrmacht Enigma I"
APP_SUBTITLE = (
    "three rotors · reflector · Steckerbrett · reciprocal cipher  —  "
    "type A-Z on your keyboard or click the keys"
)

NUMBER_POLICIES = {
    "auto": "Auto: words / digits",
    "words": "Words (readable)",
    "digits": "Digits (exact)",
}

SPACE_LETTERS = {
    "auto": "Auto (X/Q)",
    "X": "X",
    "Q": "Q",
}

CHUNK_SIZE = 2000


class EnigmaApp(tk.Tk):
    """Main window of the simulator."""

    def __init__(self) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.configure(bg=theme.BG)
        self.minsize(1000, 720)
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

    # ------------------------------------------------------------- layout
    def _fit_to_screen(self) -> None:
        """Size the window so that it always fits on the screen."""
        width = min(1480, max(1000, self.winfo_screenwidth() - 16))
        height = min(900, max(700, self.winfo_screenheight() - 60))
        self.geometry(f"{width}x{height}+0+0")

    def _focus_window(self) -> None:
        """Make sure the window grabs the focus so typing works right away."""
        self.focus_set()

    def _panel(self, master: tk.Misc, title: str) -> tuple[tk.Frame, tk.Frame]:
        """Create a titled panel frame and return it with its content area."""
        frame = tk.Frame(master, bg=theme.PANEL, highlightbackground=theme.PANEL_LINE,
                         highlightthickness=1, bd=0)
        tk.Label(
            frame,
            text=title.upper(),
            bg=theme.PANEL,
            fg=theme.TEXT_DIM,
            font=theme.Fonts.SECTION,
        ).pack(anchor="w", padx=12, pady=(10, 6))
        body = tk.Frame(frame, bg=theme.PANEL)
        body.pack(fill="both", expand=True, padx=0, pady=0)
        return frame, body

    def _build_header(self) -> None:
        header = tk.Frame(self, bg=theme.BG)
        header.grid(row=0, column=0, columnspan=2, sticky="ew", padx=22, pady=(16, 8))
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
            text=APP_SUBTITLE,
            bg=theme.BG,
            fg=theme.TEXT_FAINT,
            font=theme.Fonts.SMALL,
            anchor="w",
            justify="left",
            wraplength=640,
        ).grid(row=1, column=0, columnspan=2, sticky="w")

        tk.Button(
            header,
            text="Reset everything",
            command=self._reset_all,
            bg=theme.PANEL_HI,
            fg=theme.TEXT_DIM,
            activebackground=theme.KEY_ACTIVE,
            activeforeground=theme.TEXT,
            relief="flat",
            bd=0,
            font=theme.Fonts.SMALL,
            cursor="hand2",
            padx=10,
            pady=5,
        ).grid(row=0, column=2, rowspan=2, sticky="e")

    def _build_machine_panel(self) -> None:
        panel, body = self._panel(self, "machine settings")
        panel.grid(row=1, column=0, columnspan=2, sticky="ew", padx=22, pady=6)
        body.grid_columnconfigure(0, weight=0, minsize=215)
        body.grid_columnconfigure(1, weight=1)
        body.grid_columnconfigure(2, weight=0, minsize=215)

        # --- reflector ---
        reflector_frame = tk.Frame(body, bg=theme.PANEL)
        reflector_frame.grid(row=0, column=0, sticky="nsew", padx=(12, 18), pady=(0, 12))
        tk.Label(
            reflector_frame,
            text="REFLECTOR (UKW)",
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
            text="A reflector never connects a letter to\nitself — that is why a letter can\nnever be enciphered as itself.",
            bg=theme.PANEL,
            fg=theme.TEXT_FAINT,
            font=theme.Fonts.SMALL,
            justify="left",
        ).pack(anchor="w", pady=(10, 0))

        # --- rotors ---
        rotors_frame = tk.Frame(body, bg=theme.PANEL)
        rotors_frame.grid(row=0, column=1, sticky="nsew")
        titles = ("LEFT ROTOR", "MIDDLE ROTOR", "RIGHT ROTOR")
        self.rotor_controls: list[RotorControl] = []
        for index, title in enumerate(titles):
            control = RotorControl(
                rotors_frame,
                title=title,
                on_rotor_change=lambda name, i=index: self._rotor_changed(i, name),
                on_ring_change=lambda delta, i=index: self._ring_changed(i, delta),
                on_position_change=lambda delta, i=index: self._position_changed(i, delta),
            )
            control.grid(row=0, column=index, padx=(0, 14), sticky="nsew")
            rotors_frame.grid_columnconfigure(index, weight=1, minsize=160)
            self.rotor_controls.append(control)

        # --- notches ---
        step_frame = tk.Frame(body, bg=theme.PANEL)
        step_frame.grid(row=0, column=2, sticky="nsew", padx=(0, 12), pady=(0, 12))
        tk.Label(
            step_frame,
            text="TURNOVER NOTCHES",
            bg=theme.PANEL,
            fg=theme.TEXT_FAINT,
            font=theme.Fonts.SMALL,
        ).pack(anchor="w")
        self.notch_summary = tk.Label(
            step_frame,
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
        self.grid_columnconfigure(1, weight=0, minsize=460)

        lamps_panel, lamps_body = self._panel(console, "lamp field")
        lamps_panel.pack(fill="x")
        self.lamps = LampField(lamps_body)
        self.lamps.pack(padx=10, pady=(0, 10))

        keyboard_panel, keyboard_body = self._panel(console, "keyboard")
        keyboard_panel.pack(fill="x", pady=(10, 0))
        self.keyboard = Keyboard(keyboard_body, on_press=self._press_key)
        self.keyboard.pack(padx=10, pady=(0, 10))

        output_panel, output_body = self._panel(console, "keyed output")
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
        self.output_label.pack(anchor="w", padx=12, pady=(0, 6))

        trace_panel, trace_body = self._panel(console, "signal path")
        trace_panel.pack(fill="x", pady=(10, 0))
        self.trace = SignalTrace(trace_body)
        self.trace.pack(fill="x", padx=12, pady=(0, 12))

    def _build_side_panel(self) -> None:
        """The right hand column: plugboard, message and batch processing.

        It is scrollable so that everything stays reachable even on small
        screens.
        """
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
            if isinstance(event.widget, (tk.Text, ttk.Combobox)):
                return
            canvas.yview_scroll(int(-event.delta / 60), "units")

        canvas.bind_all("<MouseWheel>", _on_wheel)
        self._side_canvas = canvas

        # --- plugboard ---
        plug_panel, plug_body = self._panel(inner, "plugboard (steckerbrett)")
        plug_panel.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        self.plugboard_widget = PlugboardWidget(plug_body, on_change=self._plug_changed)
        self.plugboard_widget.pack(padx=10)
        plug_actions = tk.Frame(plug_body, bg=theme.PANEL)
        plug_actions.pack(fill="x", padx=12, pady=(6, 10))
        tk.Button(
            plug_actions,
            text="Clear cables",
            command=self._clear_plugboard,
            bg=theme.KEY_BG,
            fg=theme.TEXT_DIM,
            activebackground=theme.KEY_ACTIVE,
            activeforeground=theme.TEXT,
            relief="flat",
            bd=0,
            font=theme.Fonts.SMALL,
            cursor="hand2",
            padx=8,
            pady=3,
        ).pack(side="left")
        self.plug_summary = tk.Label(
            plug_actions,
            text="no cables",
            bg=theme.PANEL,
            fg=theme.TEXT_FAINT,
            font=theme.Fonts.SMALL,
            anchor="e",
        )
        self.plug_summary.pack(side="right")

        # --- message ---
        message_panel, message_body = self._panel(inner, "message")
        message_panel.grid(row=1, column=0, sticky="ew")

        options = tk.Frame(message_body, bg=theme.PANEL)
        options.pack(fill="x", padx=12, pady=(0, 8))

        numbers_row = tk.Frame(options, bg=theme.PANEL)
        numbers_row.pack(fill="x")
        tk.Label(
            numbers_row, text="Numbers", bg=theme.PANEL, fg=theme.TEXT_FAINT,
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
            space_row, text="Space", bg=theme.PANEL, fg=theme.TEXT_FAINT,
            font=theme.Fonts.SMALL,
        ).pack(side="left")
        self.space_letter = ttk.Combobox(
            space_row,
            values=list(SPACE_LETTERS.values()),
            state="readonly",
            width=9,
            font=theme.Fonts.SMALL,
            style="Enigma.TCombobox",
        )
        self.space_letter.current(0)
        self.space_letter.pack(side="left", padx=(4, 10))

        self.join_words = tk.BooleanVar(value=False)
        tk.Checkbutton(
            space_row,
            text="join number words",
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

        tk.Label(
            message_body,
            text="PLAIN TEXT",
            bg=theme.PANEL,
            fg=theme.TEXT_FAINT,
            font=theme.Fonts.SMALL,
        ).pack(anchor="w", padx=12)
        self.plain_text = tk.Text(
            message_body,
            height=3,
            bg=theme.PANEL_HI,
            fg=theme.TEXT,
            insertbackground=theme.AMBER,
            relief="flat",
            font=theme.Fonts.MONO,
            wrap="word",
            padx=8,
            pady=6,
        )
        self.plain_text.pack(fill="both", expand=True, padx=12, pady=(2, 8))

        file_row = tk.Frame(message_body, bg=theme.PANEL)
        file_row.pack(fill="x", padx=12, pady=(0, 8))
        self._button(file_row, "Open file…", self._open_file).pack(side="left", padx=(0, 6))
        self._button(file_row, "Save cipher…", self._save_cipher).pack(side="left", padx=(0, 6))
        self._button(file_row, "Clear", self._clear_message).pack(side="left")

        tk.Label(
            message_body,
            text="PREPARED TEXT  (letters that go into the machine)",
            bg=theme.PANEL,
            fg=theme.TEXT_FAINT,
            font=theme.Fonts.SMALL,
        ).pack(anchor="w", padx=12)
        self.prepared_text = tk.Text(
            message_body,
            height=2,
            bg=theme.PANEL_HI,
            fg=theme.CYAN,
            relief="flat",
            font=theme.Fonts.MONO,
            wrap="word",
            padx=8,
            pady=6,
        )
        self.prepared_text.pack(fill="both", expand=False, padx=12, pady=(2, 8))

        tk.Label(
            message_body,
            text="CIPHER TEXT",
            bg=theme.PANEL,
            fg=theme.TEXT_FAINT,
            font=theme.Fonts.SMALL,
        ).pack(anchor="w", padx=12)
        self.cipher_text = tk.Text(
            message_body,
            height=3,
            bg=theme.PANEL_HI,
            fg=theme.AMBER,
            relief="flat",
            font=theme.Fonts.MONO,
            wrap="word",
            padx=8,
            pady=6,
        )
        self.cipher_text.pack(fill="both", expand=True, padx=12, pady=(2, 8))

        buttons = tk.Frame(message_body, bg=theme.PANEL)
        buttons.pack(fill="x", padx=12, pady=(0, 12))
        self._button(buttons, "Encipher / Decipher", self._encrypt_message).pack(
            side="left", padx=(0, 6)
        )
        self._button(buttons, "Group in fives", self._group_message).pack(side="left")

        # --- batch ---
        batch_panel, batch_body = self._panel(inner, "batch processing")
        batch_panel.grid(row=2, column=0, sticky="ew", pady=(10, 0))

        self.split_messages = tk.BooleanVar(value=False)
        self.restart_rotors = tk.BooleanVar(value=False)
        for text, variable in (
            ("Split on blank lines (one message per block)", self.split_messages),
            ("Restart rotors for every message", self.restart_rotors),
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
            ).pack(fill="x", padx=12, pady=(0, 4))

        self.progress = ttk.Progressbar(
            batch_body, mode="determinate", maximum=100, length=320
        )
        self.progress.pack(fill="x", padx=12, pady=(6, 0))

        self.stats_label = tk.Label(
            batch_body,
            text="",
            bg=theme.PANEL,
            fg=theme.TEXT_FAINT,
            font=theme.Fonts.SMALL,
            anchor="w",
            justify="left",
        )
        self.stats_label.pack(fill="x", padx=12, pady=(4, 12))

    def _build_status_bar(self) -> None:
        status = tk.Label(
            self,
            text="",
            bg=theme.PANEL,
            fg=theme.TEXT_DIM,
            font=theme.Fonts.STATUS,
            anchor="w",
            padx=16,
            pady=6,
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
            padx=10,
            pady=5,
        )

    # -------------------------------------------------------------- helpers
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

    # ------------------------------------------------------------- actions
    def _press_key(self, letter: str) -> None:
        """Press a key on the machine."""
        trace: list[tuple[str, str]] = []
        result = self.machine.press(letter, trace=trace)
        self._keyed_output.append(result)
        self.lamps.light(result)
        self.trace.show([(step.stage, step.letter) for step in trace])
        self.output_label.configure(text="".join(self._keyed_output[-120:]))
        self._refresh()

    def _on_physical_key(self, event) -> None:
        """Handle a key pressed on the real keyboard."""
        if isinstance(event.widget, (tk.Text, ttk.Entry, ttk.Combobox)):
            return
        character = event.char or ""
        if not character:
            # Some keyboard layouts deliver the keysym but no character.
            keysym = getattr(event, "keysym", "") or ""
            if len(keysym) == 1:
                character = keysym
        character = character.upper()
        if len(character) == 1 and character in ALPHABET:
            self._press_key(character)

    def _rotor_changed(self, index: int, name: str) -> None:
        names = list(self.machine.rotor_names)
        # A rotor can only sit in the machine once.  Choosing one that is
        # already installed swaps the two wheels.
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

    def _position_changed(self, index: int, delta: int) -> None:
        rotor = self.machine.rotors[index]
        rotor.position = (rotor.position + delta) % 26
        self._home_positions = self.machine.positions
        self._refresh()

    def _reflector_selected(self, _event=None) -> None:
        self.machine.reflector = self.reflector_box.get()
        self._refresh()

    def _plug_changed(self, first: str, second: str) -> None:
        try:
            self.machine.plugboard.toggle(first, second)
        except PlugboardError as error:
            messagebox.showwarning("Plugboard", str(error), parent=self)
        self._refresh()

    def _clear_plugboard(self) -> None:
        self.machine.plugboard.clear()
        self.plugboard_widget.clear_pending()
        self._refresh()

    def _open_file(self) -> None:
        path = filedialog.askopenfilename(
            parent=self,
            title="Open plain text",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as handle:
                text = handle.read()
        except OSError as error:
            messagebox.showerror("Open file", str(error), parent=self)
            return
        self.plain_text.delete("1.0", "end")
        self.plain_text.insert("1.0", text)
        self.stats_label.configure(text=f"loaded {len(text)} characters from {path}")

    def _save_cipher(self) -> None:
        cipher = self.cipher_text.get("1.0", "end").strip()
        if not cipher:
            messagebox.showinfo("Save cipher", "There is no cipher text yet.", parent=self)
            return
        path = filedialog.asksaveasfilename(
            parent=self,
            title="Save cipher text",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(cipher + "\n")
        except OSError as error:
            messagebox.showerror("Save cipher", str(error), parent=self)
            return
        self.stats_label.configure(text=f"cipher text written to {path}")

    def _encrypt_message(self) -> None:
        """Prepare the plain text and run it through the machine."""
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
        """Encrypt *messages*, keeping the interface responsive."""
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
        """Encrypt a slice of the current message, then come back for more."""
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
                break  # give the interface a chance to breathe

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
                f"{letters} letters · {messages} message"
                f"{'s' if messages != 1 else ''} · {elapsed:.2f} s"
            )
        )
        self.progress["value"] = 100
        self._refresh()

    def _group_message(self) -> None:
        """Show the cipher text in groups of five, as it was transmitted."""
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
        self._refresh()

    # -------------------------------------------------------------- refresh
    def _refresh(self) -> None:
        """Push the machine state into the widgets."""
        machine = self.machine
        self.reflector_box.set(machine.reflector)
        for control, rotor in zip(self.rotor_controls, machine.rotors):
            control.set_rotor(rotor.spec.name)
            control.set_ring(rotor.ring_letter)
            control.set_position(rotor.position_letter)
            control.set_notch_active(rotor.at_turnover)

        plugged = [letter for pair in machine.plugboard.pairs for letter in pair]
        self.plugboard_widget.set_plugged(plugged)
        self.plug_summary.configure(text=machine.plugboard.describe() or "no cables")

        self.notch_summary.configure(
            text="  ".join(
                f"{rotor.spec.name}:{'/'.join(rotor.spec.turnover)}"
                for rotor in machine.rotors
            )
        )

        self.status_label.configure(
            text=(
                f"  {machine.describe()}   |   position {machine.positions}   |   "
                f"lamp {self.lamps._lit or '—'}   |   type A-Z to press the keys"
            )
        )


def main() -> None:
    """Start the application."""
    app = EnigmaApp()
    app.mainloop()


if __name__ == "__main__":  # pragma: no cover
    main()
