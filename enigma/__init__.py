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
from .message import format_groups, group, normalize, split_messages
from .numbers import digits_to_words, expand_numbers, number_to_words
from .plugboard import Plugboard, PlugboardError
from .preparation import PreparedText, choose_space_letter, prepare_text

__all__ = [
    "ALPHABET",
    "REFLECTORS",
    "ROTORS",
    "EnigmaMachine",
    "Plugboard",
    "PlugboardError",
    "PreparedText",
    "Rotor",
    "RotorSpec",
    "TraceStep",
    "choose_space_letter",
    "digits_to_words",
    "expand_numbers",
    "format_groups",
    "group",
    "index_to_letter",
    "letter_to_index",
    "normalize",
    "number_to_words",
    "prepare_text",
    "split_messages",
]

__version__ = "1.0.0"
