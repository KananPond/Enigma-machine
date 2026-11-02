"""Preparing plain text for the machine.

Enigma operators never sent digits or spaces.  Numbers were written out and
spaces were replaced by a letter that the message itself did not use.

This module implements that preparation:

1. Numbers are expanded - either as readable English words or digit by digit
   (see :mod:`enigma.numbers`).
2. Every space is replaced by ``X`` or ``Q``.  Which one is used is decided
   automatically: the letter that occurs *less often* in the prepared text
   wins, so the space substitute never collides with the message.
3. Everything that is not a letter is dropped - the machine only knows 26
   characters.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .data import ALPHABET
from .numbers import expand_numbers

#: The two letters that are used as a stand-in for spaces.
SPACE_LETTERS = ("X", "Q")


@dataclass(frozen=True)
class PreparedText:
    """The result of preparing a text for the machine."""

    text: str
    """The letters that are handed to the machine."""

    expanded: str
    """The text after the numbers were written out, before spaces were replaced."""

    space_letter: str
    """The letter that was used in place of spaces."""

    number_policy: str
    join_number_words: bool
    letters_removed: int = 0
    digits_expanded: int = 0

    @property
    def length(self) -> int:
        return len(self.text)


def choose_space_letter(text: str) -> str:
    """Return the letter to use for spaces in *text*.

    The letter that appears less often in the text is used, so that the
    substitute for a space cannot be confused with a real letter.  Ties are
    resolved in favour of ``X``, the letter traditionally used for spaces.
    """
    q_count = text.upper().count("Q")
    x_count = text.upper().count("X")
    return "Q" if q_count < x_count else "X"


def prepare_text(
    text: str,
    number_policy: str = "auto",
    space_letter: str = "auto",
    join_number_words: bool = False,
) -> PreparedText:
    """Prepare *text* for the machine.

    Parameters
    ----------
    text:
        The plain text as typed by the operator.
    number_policy:
        ``"auto"``, ``"words"`` or ``"digits"`` - see :mod:`enigma.numbers`.
    space_letter:
        ``"auto"`` to let :func:`choose_space_letter` decide, or ``"X"``/``"Q"``
        to force one of them.
    join_number_words:
        Write the words of a number without spaces (``NINETEENTHIRTYTWO``).
    """
    expanded = expand_numbers(text, policy=number_policy, join_words=join_number_words)

    if space_letter == "auto":
        substitute = choose_space_letter(expanded)
    else:
        substitute = space_letter.upper()
        if substitute not in SPACE_LETTERS:
            raise ValueError(
                f"The space substitute must be one of {SPACE_LETTERS}, not {space_letter!r}."
            )

    spaced = expanded.replace(" ", substitute).replace("\t", substitute)
    letters = "".join(character for character in spaced.upper() if character in ALPHABET)

    digits_expanded = sum(1 for character in text if character.isdigit())
    removed = sum(1 for character in text if not character.isalnum() and not character.isspace())

    return PreparedText(
        text=letters,
        expanded=expanded,
        space_letter=substitute,
        number_policy=number_policy,
        join_number_words=join_number_words,
        letters_removed=removed,
        digits_expanded=digits_expanded,
    )
