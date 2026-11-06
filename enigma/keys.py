"""Key sheets - the settings a message was enciphered with.

A key sheet is the five things an operator wrote down before sending:

    Walzenlage    the three rotors, left to right        ("IV", "II", "I")
    Umkehrwalze   the reflector                          ("B")
    Ringstellung  the ring settings, left to right        ("BUL")
    Grundstellung the window letters at the start         ("ADU")
    Steckerbrett  the plugboard cables                    ("AV BS CG")

:class:`Key` is the immutable, validated form of that sheet.  It is what the
interface sends around, what the breaking routines return and what the
:class:`~enigma.machine.EnigmaMachine` is built from.
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass, replace
from typing import Any, Mapping, Sequence

from .data import ALPHABET, REFLECTORS, ROTORS, letter_to_index
from .machine import EnigmaMachine
from .plugboard import Plugboard

#: Rotors that can be fitted to the machine, in the order they are listed.
ROTOR_NAMES: tuple[str, ...] = tuple(ROTORS)

#: Reflectors that can be fitted.  The thin ones belonged to the four rotor
#: naval machine and are kept for completeness.
REFLECTOR_NAMES: tuple[str, ...] = tuple(REFLECTORS)

#: The reflector most wartime messages used.
DEFAULT_REFLECTOR = "B"

#: Rotors of the Wehrmacht machine.
DEFAULT_ROTORS: tuple[str, str, str] = ("I", "II", "III")

#: A plugboard holds at most ten cables.
MAX_CABLES = Plugboard.MAX_PAIRS


class KeyError_(ValueError):
    """Raised when a key sheet cannot be read."""


def _clean_letters(value: Any, length: int, field: str) -> str:
    """Return *value* as exactly *length* upper case letters."""
    if isinstance(value, (list, tuple)):
        value = "".join(str(part) for part in value)
    if not isinstance(value, str):
        raise KeyError_(f"{field} must be letters, got {value!r}.")
    letters = "".join(ch for ch in value.upper() if ch in ALPHABET)
    if len(letters) != length:
        raise KeyError_(
            f"{field} needs {length} letters, got {value!r}."
        )
    return letters


def _clean_rotors(value: Any) -> tuple[str, str, str]:
    """Return the three rotor names, left to right."""
    if isinstance(value, str):
        parts = [part for part in re.split(r"[\s,/|-]+", value) if part]
    elif isinstance(value, Sequence):
        parts = [str(part).strip() for part in value]
    else:
        raise KeyError_(f"Rotors must be a list of three names, got {value!r}.")

    if len(parts) != 3:
        raise KeyError_("Exactly three rotors are needed.")
    names: list[str] = []
    for part in parts:
        name = part.strip().upper().replace(" ", "")
        if name not in ROTORS:
            raise KeyError_(f"{part!r} is not a rotor of this machine.")
        names.append(name)
    if len(set(names)) != 3:
        raise KeyError_("A rotor cannot be fitted twice.")
    return (names[0], names[1], names[2])


def _clean_reflector(value: Any) -> str:
    """Return the reflector name as it is spelled in :data:`REFLECTORS`."""
    text = str(value).strip()
    for name in REFLECTORS:
        if text.upper() == name.upper():
            return name
    raise KeyError_(f"{value!r} is not a reflector of this machine.")


def _clean_plugboard(value: Any) -> str:
    """Return the plugboard in the canonical ``AV BS CG`` notation."""
    if isinstance(value, Mapping):
        value = " ".join(f"{a}{b}" for a, b in value.items())
    if isinstance(value, (list, tuple)):
        value = " ".join(
            part if isinstance(part, str) else "".join(part) for part in value
        )
    if not isinstance(value, str):
        raise KeyError_(f"The plugboard must be text like 'AV BS CG', got {value!r}.")

    letters = [ch for ch in value.upper() if ch in ALPHABET]
    if not letters:
        return ""
    if len(letters) % 2:
        raise KeyError_("Plugboard cables come in pairs - one letter is left over.")

    # Reading "AVBSCG" as pairs is a convenience, but a repeated letter is a
    # mistake the operator has to see.
    pairs: list[tuple[str, str]] = []
    for index in range(0, len(letters), 2):
        first, second = letters[index], letters[index + 1]
        if first == second:
            raise KeyError_(f"{first} cannot be plugged into itself.")
        pairs.append((first, second))

    used: set[str] = set()
    for first, second in pairs:
        for letter in (first, second):
            if letter in used:
                raise KeyError_(
                    f"{letter} is used by more than one cable."
                )
            used.add(letter)
    if len(pairs) > MAX_CABLES:
        raise KeyError_(f"A plugboard holds at most {MAX_CABLES} cables.")

    board = Plugboard({first: second for first, second in pairs})
    return board.describe()


@dataclass(frozen=True)
class Key:
    """A complete, validated key sheet."""

    rotors: tuple[str, str, str] = DEFAULT_ROTORS
    reflector: str = DEFAULT_REFLECTOR
    rings: str = "AAA"
    positions: str = "AAA"
    plugboard: str = ""

    # ------------------------------------------------------------ validation
    def __post_init__(self) -> None:
        object.__setattr__(self, "rotors", _clean_rotors(self.rotors))
        object.__setattr__(self, "reflector", _clean_reflector(self.reflector))
        object.__setattr__(self, "rings", _clean_letters(self.rings, 3, "Ringstellung"))
        object.__setattr__(self, "positions", _clean_letters(self.positions, 3, "Grundstellung"))
        object.__setattr__(self, "plugboard", _clean_plugboard(self.plugboard))

    # ---------------------------------------------------------- constructors
    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | "Key" | None) -> "Key":
        """Build a key from a dictionary produced by :meth:`to_dict`.

        Unknown keys are ignored and missing keys fall back to the default,
        so a partial settings object from the interface is always accepted.
        """
        if isinstance(data, Key):
            return data
        if data is None:
            return cls()
        rotors = data.get("rotors", data.get("rotor_order", DEFAULT_ROTORS))
        return cls(
            rotors=rotors,  # type: ignore[arg-type]
            reflector=data.get("reflector", DEFAULT_REFLECTOR),
            rings=data.get("rings", data.get("ring_settings", "AAA")),
            positions=data.get("positions", data.get("grundstellung", "AAA")),
            plugboard=data.get("plugboard", data.get("stecker", "")),
        )

    @classmethod
    def random(
        cls,
        cables: int = 10,
        rotors: Sequence[str] = ROTOR_NAMES,
        reflectors: Sequence[str] = ("B", "C"),
        rng: random.Random | None = None,
    ) -> "Key":
        """Return a plausible random key - the daily sheet of a net."""
        rng = rng or random.Random()
        pool = [name for name in rotors if name in ROTORS] or list(DEFAULT_ROTORS)
        fitted = tuple(rng.sample(pool, min(3, len(pool))))
        while len(fitted) < 3:  # pragma: no cover - defensive
            fitted += (DEFAULT_ROTORS[len(fitted)],)

        letters = list(ALPHABET)
        rng.shuffle(letters)
        cables = max(0, min(cables, MAX_CABLES))
        pairs = [
            f"{letters[2 * i]}{letters[2 * i + 1]}" for i in range(cables)
        ]
        return cls(
            rotors=fitted,  # type: ignore[arg-type]
            reflector=rng.choice(list(reflectors)),
            rings="".join(rng.choice(ALPHABET) for _ in range(3)),
            positions="".join(rng.choice(ALPHABET) for _ in range(3)),
            plugboard=" ".join(pairs),
        )

    # --------------------------------------------------------------- machine
    def machine(self, positions: str | None = None) -> EnigmaMachine:
        """Return a fresh machine built from this key.

        The rotors of the returned machine start at *positions* (the key's
        own starting position by default); the live machine of the interface
        is never touched, so a decode cannot disturb what is on the bench.
        """
        return EnigmaMachine.create(
            rotor_order=self.rotors,
            reflector=self.reflector,
            plugboard=Plugboard.parse(self.plugboard),
            ring_settings=self.rings,
            positions=positions or self.positions,
        )

    # ----------------------------------------------------------- conversions
    def to_dict(self) -> dict[str, Any]:
        """Return the key as a dictionary, ready to be sent as JSON."""
        return {
            "rotors": list(self.rotors),
            "reflector": self.reflector,
            "rings": self.rings,
            "positions": self.positions,
            "plugboard": self.plugboard,
            "cables": self.cable_count,
        }

    def with_(self, **changes: Any) -> "Key":
        """Return a copy with some fields replaced."""
        return replace(self, **changes)

    # ------------------------------------------------------------- notation
    @property
    def cable_count(self) -> int:
        """How many cables the plugboard holds."""
        return len(self.plugboard.split()) if self.plugboard else 0

    @property
    def offsets(self) -> tuple[int, int, int]:
        """The rotor offsets ``position - ring`` of the three rotors."""
        return tuple(
            (letter_to_index(self.positions[i]) - letter_to_index(self.rings[i])) % 26
            for i in range(3)
        )  # type: ignore[return-value]

    def describe(self) -> str:
        """Return the key in the notation of a German key sheet."""
        return (
            f"Walzenlage {'-'.join(self.rotors)} | UKW {self.reflector} | "
            f"Ringstellung {self.rings} | Grundstellung {self.positions} | "
            f"Stecker {self.plugboard or 'keine'}"
        )

    def compact(self) -> str:
        """Return the key on one short line, e.g. for a list."""
        return (
            f"{'-'.join(self.rotors)} / {self.reflector} / {self.rings} / "
            f"{self.positions} / {self.plugboard or '-'}"
        )

    def __str__(self) -> str:  # pragma: no cover - display helper
        return self.compact()
