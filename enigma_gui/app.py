"""The Enigma desktop application.

Run it with ``python run.py`` (or ``python -m enigma_gui``).
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from enigma import EnigmaMachine, Plugboard, PlugboardError
from enigma.data import ALPHABET
from enigma.message import format_groups, normalize

from . import theme
from .widgets import Keyboard, LampField, PlugboardWidget, RotorControl, SignalTrace

APP_TITLE = "ENIGMA  ·  Wehrmacht Enigma I"
APP_SUBTITLE = (
    "three rotors · reflector · Steckerbrett · reciprocal cipher  —  "
    "type on your keyboard or click the keys"
)


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

        self._build_header()
        self._build_machine_panel()
        self._build_console()
        self._build_side_panel()
        self._build_status_bar()

        self._refresh()
        self.bind("<KeyPress>", self._on_physical_key)
        self.after(60, self._fit_to_screen)
        self.after(60, self._focus_canvas)

    def _fit_to_screen(self) -> None:
        """Size the window so that it always fits on the screen."""
        width = min(1240, max(1000, self.winfo_screenwidth() - 40))
        height = min(860, max(720, self.winfo_screenheight() - 80))
        self.geometry(f"{width}x{height}")

    # ------------------------------------------------------------------ UI
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

        # --- step hint ---
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
        side = tk.Frame(self, bg=theme.BG)
        side.grid(row=2, column=1, sticky="nsew", padx=(10, 22), pady=6)
        side.grid_columnconfigure(0, weight=1)

        # --- plugboard ---
        plug_panel, plug_body = self._panel(side, "plugboard (steckerbrett)")
        plug_panel.grid(row=0, column=0, sticky="ew")
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
        message_panel, message_body = self._panel(side, "message")
        message_panel.grid(row=1, column=0, sticky="nsew", pady=(10, 0))
        side.grid_rowconfigure(1, weight=1)

        tk.Label(
            message_body,
            text="PLAIN TEXT",
            bg=theme.PANEL,
            fg=theme.TEXT_FAINT,
            font=theme.Fonts.SMALL,
        ).pack(anchor="w", padx=12)
        self.plain_text = tk.Text(
            message_body,
            height=4,
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

        tk.Label(
            message_body,
            text="CIPHER TEXT",
            bg=theme.PANEL,
            fg=theme.TEXT_FAINT,
            font=theme.Fonts.SMALL,
        ).pack(anchor="w", padx=12)
        self.cipher_text = tk.Text(
            message_body,
            height=4,
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
        self._button(buttons, "Group in fives", self._group_message).pack(
            side="left", padx=(0, 6)
        )
        self._button(buttons, "Clear", self._clear_message).pack(side="left")

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

    def _focus_canvas(self) -> None:
        """Make sure the keyboard grabs the focus so typing works right away."""
        self.focus_set()

    # ------------------------------------------------------------- actions
    def _press_key(self, letter: str) -> None:
        """Press a key on the machine."""
        trace: list[tuple[str, str]] = []
        result = self.machine.press(letter, trace=trace)
        self._keyed_output.append(result)
        self.lamps.light(result)
        self.trace.show([(step.stage, step.letter) for step in trace])
        self.output_label.configure(
            text=f"{''.join(self._keyed_output[-120:])}"
        )
        self._refresh()

    def _on_physical_key(self, event) -> None:
        """Handle a key pressed on the real keyboard."""
        if isinstance(event.widget, (tk.Text, ttk.Entry)):
            return
        character = (event.char or "").upper()
        if character in ALPHABET and len(character) == 1:
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

    def _encrypt_message(self) -> None:
        """Encipher (or decipher) the whole plain text field."""
        text = self.plain_text.get("1.0", "end")
        letters = normalize(text)
        if not letters:
            return
        cipher = self.machine.encrypt(letters)
        self.cipher_text.delete("1.0", "end")
        self.cipher_text.insert("1.0", cipher)
        self._keyed_output = []
        self.output_label.configure(text="")
        self.lamps.clear()
        self._refresh()

    def _group_message(self) -> None:
        """Show the cipher text in groups of five, as it was transmitted."""
        cipher = self.cipher_text.get("1.0", "end").strip()
        if not cipher:
            plain = normalize(self.plain_text.get("1.0", "end"))
            if not plain:
                return
            cipher = self.machine.encrypt(plain)
            self.cipher_text.delete("1.0", "end")
            self.cipher_text.insert("1.0", cipher)
        self.cipher_text.delete("1.0", "end")
        self.cipher_text.insert("1.0", format_groups(cipher))

    def _clear_message(self) -> None:
        self.plain_text.delete("1.0", "end")
        self.cipher_text.delete("1.0", "end")
        self._keyed_output = []
        self.output_label.configure(text="—")
        self.lamps.clear()

    def _reset_all(self) -> None:
        self.machine = EnigmaMachine.create()
        self._keyed_output = []
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
        self.plug_summary.configure(
            text=machine.plugboard.describe() or "no cables"
        )

        notches = "  ".join(
            f"{rotor.spec.name}:{'/'.join(rotor.spec.turnover)}" for rotor in machine.rotors
        )
        self.notch_summary.configure(text=notches)

        self.status_label.configure(
            text=(
                f"  {machine.describe()}   |   position {machine.positions}   |   "
                f"lamp {self.lamps._lit or '—'}"
            )
        )


def main() -> None:
    """Start the application."""
    app = EnigmaApp()
    app.mainloop()


if __name__ == "__main__":  # pragma: no cover
    main()
