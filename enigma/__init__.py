"""A faithful simulation of the Enigma cipher machine.

The package contains no GUI code; :mod:`enigma_gui` provides the desktop
application on top of it.
"""

from .data import (
    ALPHABET,
    REFLECTORS,
    ROTORS,
    RotorSpec,
    index_to_letter,
    letter_to_index,
)
from .machine import EnigmaMachine, Rotor, TraceStep
from .plugboard import Plugboard, PlugboardError

__all__ = [
    "ALPHABET",
    "REFLECTORS",
    "ROTORS",
    "EnigmaMachine",
    "Plugboard",
    "PlugboardError",
    "Rotor",
    "RotorSpec",
    "TraceStep",
    "index_to_letter",
    "letter_to_index",
]

__version__ = "1.0.0"
