"""Helpers for turning plain text into Enigma traffic.

Historical procedure removed spaces and punctuation, enciphered the letters in
groups of five and transmitted the groups separately, so the same helpers are
useful for reproducing that behaviour.
"""

from __future__ import annotations

from .data import ALPHABET


def normalize(text: str) -> str:
    """Return only the letters of *text*, upper cased."""
    return "".join(ch for ch in text.upper() if ch in ALPHABET)


def group(text: str, size: int = 5) -> list[str]:
    """Split *text* into groups of *size* letters."""
    if size <= 0:
        raise ValueError("Group size must be positive.")
    letters = normalize(text)
    return [letters[i : i + size] for i in range(0, len(letters), size)]


def format_groups(text: str, size: int = 5, separator: str = " ") -> str:
    """Return *text* as space separated groups of *size* letters."""
    return separator.join(group(text, size))
