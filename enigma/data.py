"""Static hardware data for the Enigma machine.

Wiring tables, turnover notches and reflector wirings are taken from the
canonical references listed in :data:`SOURCES` below.  Every table is checked
by the unit tests (``tests/test_data.py``): rotor wirings must be permutations
of the alphabet and reflectors must be fixed-point-free involutions.
"""

from __future__ import annotations

from dataclasses import dataclass

ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

SOURCES = (
    "Rotor wirings, turnover notches and reflector wirings: Wikipedia, "
    "'Enigma machine' (rotor table / turnover notch positions) and "
    "Crypto Museum (https://www.cryptomuseum.com/crypto/enigma/).",
)


@dataclass(frozen=True)
class RotorSpec:
    """Immutable description of a cipher rotor.

    Attributes
    ----------
    name:
        Roman numeral printed on the rotor (``"I"`` ... ``"VIII"``).
    wiring:
        26-letter string.  ``wiring[i]`` is the letter the rotor connects
        contact *i* to, i.e. ``A -> wiring[0]``.
    turnover:
        Window letters at which the rotor engages the pawl of the rotor to its
        left.  When the rotor *steps away from* such a letter, the rotor to the
        left is advanced.  Rotors VI-VIII carry two notches.
    """

    name: str
    wiring: str
    turnover: tuple[str, ...]

    @property
    def turnover_indices(self) -> tuple[int, ...]:
        return tuple(ALPHABET.index(letter) for letter in self.turnover)


#: The eight rotors of the Wehrmacht Enigma I / Navy Enigma.
ROTORS: dict[str, RotorSpec] = {
    spec.name: spec
    for spec in (
        RotorSpec("I", "EKMFLGDQVZNTOWYHXUSPAIBRCJ", ("Q",)),
        RotorSpec("II", "AJDKSIRUXBLHWTMCQGZNPYFVOE", ("E",)),
        RotorSpec("III", "BDFHJLCPRTXVZNYEIWGAKMUSQO", ("V",)),
        RotorSpec("IV", "ESOVPZJAYQUIRHXLNFTGKDCMWB", ("J",)),
        RotorSpec("V", "VZBRGITYUPSDNHLXAWMJQOFECK", ("Z",)),
        RotorSpec("VI", "JPGVOUMFYQBENHZRDKASXLICTW", ("Z", "M")),
        RotorSpec("VII", "NZJHGRCXMYSWBOUFAIVLPEKQDT", ("Z", "M")),
        RotorSpec("VIII", "FKQHTLXOCBJSPDZRAMEWNIUYGV", ("Z", "M")),
    )
}

#: Reflector wirings (Umkehrwalze).  The thin variants were fitted to the
#: four-rotor naval Enigma M4.
REFLECTORS: dict[str, str] = {
    "A": "EJMZALYXVBWFCRQUONTSPIKHGD",
    "B": "YRUHQSLDPXNGOKMIEBFZCWVJAT",
    "C": "FVPJIAOYEDRZXWGCTKUQSBNMHL",
    "B thin": "ENKQAUYWJICOPBLMDXZVFTHRGS",
    "C thin": "RDOBJNTKVEHMLFCWZAXGYIPSUQ",
}


def letter_to_index(letter: str) -> int:
    """Return the 0-based index of *letter* (``A`` -> 0 ... ``Z`` -> 25)."""
    return ALPHABET.index(letter.upper())


def index_to_letter(index: int) -> str:
    """Return the letter for a 0-based alphabet index."""
    return ALPHABET[index % 26]
