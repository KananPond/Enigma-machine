"""A faithful simulation of the Enigma cipher machine, and the tools to break it.

The package contains no interface code: :mod:`enigma_gui` draws the desktop
window on top of it, and :mod:`enigma.autosolve` puts the attacks on top of
the machine.

Quick tour
----------

    from enigma import Key, prepare_text, auto_decrypt

    key = Key(rotors=("I", "II", "III"), positions="AAA", plugboard="AV BS CG")
    cipher = key.machine().encrypt(prepare_text("ATTACK AT DAWN").text)

    result = auto_decrypt(cipher, crib="ATTACK AT DAWN", offset=0)
    print(result.key.describe())
    print(result.text)
"""

from .data import (
    ALPHABET,
    REFLECTORS,
    ROTORS,
    RotorSpec,
    index_to_letter,
    letter_to_index,
)
from .decode import DecodeResult, decode, decipher, solve_plugboard
from .english import (
    DEFAULT_MODEL,
    EnglishModel,
    restore_punctuation,
    restore_spaces,
    restore_text,
    score_text,
)
from .keys import Key, REFLECTOR_NAMES, ROTOR_NAMES, KeyError_
from .machine import EnigmaMachine, Rotor, TraceStep
from .message import format_groups, group, normalize, split_messages
from .numbers import digits_to_words, expand_numbers, number_to_words
from .plugboard import Plugboard, PlugboardError
from .preparation import PreparedText, choose_space_letter, prepare_text
from .autosolve import (
    AutoResult,
    Candidate,
    auto_decrypt,
    break_ciphertext,
    break_with_crib,
    crib_letters,
    decipher_with_key,
    has_numpy,
)

try:  # the menu attack needs numpy; everything else does not
    from .crack import (
        BreakResult,
        MenuFinding,
        break_enigma,
        crib_matches,
        menu_attack,
    )

    HAS_NUMPY = True
except ImportError:  # pragma: no cover - depends on the environment
    HAS_NUMPY = False

__all__ = [
    "ALPHABET",
    "AutoResult",
    "Candidate",
    "DEFAULT_MODEL",
    "Key",
    "KeyError_",
    "REFLECTOR_NAMES",
    "ROTOR_NAMES",
    "HAS_NUMPY",
    "REFLECTORS",
    "ROTORS",
    "BreakResult",
    "DecodeResult",
    "EnglishModel",
    "EnigmaMachine",
    "MenuFinding",
    "Plugboard",
    "PlugboardError",
    "PreparedText",
    "Rotor",
    "RotorSpec",
    "TraceStep",
    "auto_decrypt",
    "break_ciphertext",
    "break_enigma",
    "break_with_crib",
    "choose_space_letter",
    "crib_letters",
    "decipher_with_key",
    "crib_matches",
    "decode",
    "decipher",
    "digits_to_words",
    "expand_numbers",
    "format_groups",
    "group",
    "has_numpy",
    "index_to_letter",
    "letter_to_index",
    "menu_attack",
    "normalize",
    "number_to_words",
    "prepare_text",
    "restore_punctuation",
    "restore_spaces",
    "restore_text",
    "score_text",
    "solve_plugboard",
    "split_messages",
]

__version__ = "2.0.0"
