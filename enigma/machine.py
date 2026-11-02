"""The Enigma machine: rotors, reflector, plugboard and the stepping rules.

Model
-----
A key press drives the current through the machine and back:

    plugboard -> right rotor -> middle rotor -> left rotor -> reflector
              -> left rotor -> middle rotor -> right rotor -> plugboard

Each rotor is modelled as the real machine: the alphabet ring can be rotated
relative to the wired core (the *ring setting*), so the wiring offset of a
rotor is ``position - ring``.  For a rotor at that offset ``e`` the forward
(entering from the right) transformation of a letter ``l`` is

    W[(l + e) mod 26] - e

and the return transformation is its inverse,
``W^-1[(l + e) mod 26] - e``.

The rotors step *before* each character is enciphered.  The right rotor always
steps; the middle rotor steps when the right rotor is at one of its turnover
notches **or** when the middle rotor itself is at a notch; the left rotor
steps when the middle rotor is at a notch.  This is the well known
"double stepping" anomaly of the Enigma.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .data import (
    ALPHABET,
    REFLECTORS,
    ROTORS,
    RotorSpec,
    index_to_letter,
    letter_to_index,
)
from .plugboard import Plugboard


@dataclass
class TraceStep:
    """One hop of the electrical signal, used by the GUI's signal path view."""

    stage: str
    letter: str


class Rotor:
    """A single cipher rotor with a position (window letter) and a ring setting."""

    def __init__(
        self,
        spec: RotorSpec,
        position: int = 0,
        ring: int = 0,
    ) -> None:
        self.spec = spec
        self.position = position % 26
        self.ring = ring % 26
        self._forward: list[int] = [ord(c) - 65 for c in spec.wiring]
        self._inverse: list[int] = [0] * 26
        for index, target in enumerate(self._forward):
            self._inverse[target] = index

    # ------------------------------------------------------------- geometry
    @property
    def offset(self) -> int:
        """Wiring offset of the rotor: ``position - ring``."""
        return (self.position - self.ring) % 26

    @property
    def position_letter(self) -> str:
        """The letter currently shown in the window."""
        return index_to_letter(self.position)

    @property
    def ring_letter(self) -> str:
        """The letter of the ring setting (Ringstellung)."""
        return index_to_letter(self.ring)

    @property
    def at_turnover(self) -> bool:
        """``True`` when the rotor sits on one of its turnover notches."""
        return self.position in self.spec.turnover_indices

    # -------------------------------------------------------------- actions
    def step(self) -> None:
        """Advance the rotor by one letter."""
        self.position = (self.position + 1) % 26

    def forward(self, letter: int) -> int:
        """Pass *letter* through the rotor from right to left."""
        offset = self.offset
        return (self._forward[(letter + offset) % 26] - offset) % 26

    def reverse(self, letter: int) -> int:
        """Pass *letter* back through the rotor from left to right."""
        offset = self.offset
        return (self._inverse[(letter + offset) % 26] - offset) % 26

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"Rotor({self.spec.name!r}, pos={self.position_letter}, ring={self.ring_letter})"


@dataclass
class EnigmaMachine:
    """A three-rotor Enigma machine.

    Parameters
    ----------
    rotors:
        The three rotors **from left to right** as they sit in the machine.
    reflector:
        Name of the reflector, e.g. ``"B"``.
    plugboard:
        The Steckerbrett wiring.
    """

    rotors: list[Rotor] = field(
        default_factory=lambda: [Rotor(ROTORS[n]) for n in ("I", "II", "III")]
    )
    reflector: str = "B"
    plugboard: Plugboard = field(default_factory=Plugboard)

    # ----------------------------------------------------------- construction
    @classmethod
    def create(
        cls,
        rotor_order: tuple[str, str, str] = ("I", "II", "III"),
        reflector: str = "B",
        plugboard: Plugboard | None = None,
        ring_settings: tuple[str, str, str] = ("A", "A", "A"),
        positions: tuple[str, str, str] = ("A", "A", "A"),
    ) -> "EnigmaMachine":
        """Build a machine from human readable settings.

        *rotor_order*, *ring_settings* and *positions* are given **left to
        right**, exactly as they are written on the settings sheet of a
        real operator.
        """
        rotors = [
            Rotor(
                ROTORS[name],
                position=letter_to_index(positions[i]),
                ring=letter_to_index(ring_settings[i]),
            )
            for i, name in enumerate(rotor_order)
        ]
        return cls(rotors=rotors, reflector=reflector, plugboard=plugboard or Plugboard())

    # ------------------------------------------------------------- settings
    @property
    def rotor_names(self) -> tuple[str, str, str]:
        return tuple(rotor.spec.name for rotor in self.rotors)  # type: ignore[return-value]

    @property
    def positions(self) -> str:
        """The three window letters, left to right."""
        return "".join(rotor.position_letter for rotor in self.rotors)

    @property
    def ring_settings(self) -> str:
        """The three ring settings, left to right."""
        return "".join(rotor.ring_letter for rotor in self.rotors)

    def set_positions(self, positions: str) -> None:
        """Set the three window letters, e.g. ``"ADU"``."""
        letters = positions.strip().upper()
        if len(letters) != len(self.rotors):
            raise ValueError(
                f"Expected {len(self.rotors)} position letters, got {len(letters)!r}."
            )
        for rotor, letter in zip(self.rotors, letters):
            rotor.position = letter_to_index(letter)

    def set_ring_settings(self, ring_settings: str) -> None:
        """Set the three ring settings, e.g. ``"BLQ"``."""
        letters = ring_settings.strip().upper()
        if len(letters) != len(self.rotors):
            raise ValueError(
                f"Expected {len(self.rotors)} ring letters, got {len(letters)!r}."
            )
        for rotor, letter in zip(self.rotors, letters):
            rotor.ring = letter_to_index(letter)

    def set_rotors(self, rotor_order: tuple[str, str, str]) -> None:
        """Replace the rotors, keeping the current positions and ring settings."""
        for rotor, name in zip(self.rotors, rotor_order):
            rotor.spec = ROTORS[name]

    # ------------------------------------------------------------- stepping
    def step_rotors(self) -> None:
        """Advance the rotors the way a key press does, including double stepping."""
        left, middle, right = self.rotors
        middle_at_notch = middle.at_turnover
        right_at_notch = right.at_turnover

        if middle_at_notch:
            left.step()
        if right_at_notch:
            middle.step()
        elif middle_at_notch:
            middle.step()
        right.step()

    # -------------------------------------------------------------- encipher
    def press(self, letter: str, trace: list[TraceStep] | None = None) -> str:
        """Press a key and return the letter that lights up.

        The rotors step first, then the signal travels through the machine.
        When *trace* is given, every hop of the signal is appended to it.
        """
        if not isinstance(letter, str) or len(letter) != 1 or letter.upper() not in ALPHABET:
            raise ValueError(f"{letter!r} is not a letter.")
        letter = letter.upper()

        self.step_rotors()

        value = letter_to_index(letter)
        if trace is not None:
            trace.append(TraceStep("key", index_to_letter(value)))

        value = self.plugboard.swap(value)
        if trace is not None:
            trace.append(TraceStep("plugboard", index_to_letter(value)))

        for rotor in reversed(self.rotors):  # right -> left
            value = rotor.forward(value)
            if trace is not None:
                trace.append(TraceStep(rotor.spec.name, index_to_letter(value)))

        value = letter_to_index(REFLECTORS[self.reflector][value])
        if trace is not None:
            trace.append(TraceStep("reflector", index_to_letter(value)))

        for rotor in self.rotors:  # left -> right
            value = rotor.reverse(value)
            if trace is not None:
                trace.append(TraceStep(rotor.spec.name, index_to_letter(value)))

        value = self.plugboard.swap(value)
        if trace is not None:
            trace.append(TraceStep("plugboard", index_to_letter(value)))

        return index_to_letter(value)

    def encrypt(self, text: str) -> str:
        """Encipher (or decipher) *text*.

        Everything that is not a letter is ignored; the machine state is kept,
        so the result depends on where the rotors stood when the call was
        made.
        """
        result: list[str] = []
        for character in text.upper():
            if character in ALPHABET:
                result.append(self.press(character))
        return "".join(result)

    # ------------------------------------------------------------- helpers
    def describe(self) -> str:
        """Return a one line summary of the current settings."""
        return (
            f"Reflector {self.reflector} | Walzenlage "
            f"{'-'.join(self.rotor_names)} | Ringstellung {self.ring_settings} | "
            f"Grundstellung {self.positions} | Stecker {self.plugboard.describe() or 'none'}"
        )

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"<EnigmaMachine {self.describe()}>"
