"""Writing numbers the way an Enigma operator had to.

Two conventions are supported:

``words``
    Readable numbers are spelled out in English words, e.g. ``1932`` becomes
    ``NINETEEN THIRTY TWO``.

``digits``
    Numbers that have to survive unchanged are spelled digit by digit and
    concatenated, e.g. ``48152`` becomes ``FOUREIGHTONEFIVETWO``.

The ``auto`` policy combines both: short numbers (up to four digits) read
naturally as words, while long digit runs are treated as identifiers -
serial numbers, codes, grid references - and are therefore spelled out digit
by digit so that they can be recovered exactly.
"""

from __future__ import annotations

import re

UNITS = (
    "ZERO",
    "ONE",
    "TWO",
    "THREE",
    "FOUR",
    "FIVE",
    "SIX",
    "SEVEN",
    "EIGHT",
    "NINE",
)

TEENS = (
    "TEN",
    "ELEVEN",
    "TWELVE",
    "THIRTEEN",
    "FOURTEEN",
    "FIFTEEN",
    "SIXTEEN",
    "SEVENTEEN",
    "EIGHTEEN",
    "NINETEEN",
)

TENS = (
    "",
    "",
    "TWENTY",
    "THIRTY",
    "FORTY",
    "FIFTY",
    "SIXTY",
    "SEVENTY",
    "EIGHTY",
    "NINETY",
)

SCALES = (
    (10**12, "TRILLION"),
    (10**9, "BILLION"),
    (10**6, "MILLION"),
    (10**3, "THOUSAND"),
    (1, ""),
)

#: Number of digits from which a run is considered an exact identifier.
EXACT_DIGIT_THRESHOLD = 5

NUMBER_PATTERN = re.compile(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?")

POLICIES = ("auto", "words", "digits")


def _under_thousand(value: int) -> str:
    """Spell out a number below 1000."""
    parts: list[str] = []
    if value >= 100:
        hundreds, value = divmod(value, 100)
        parts.append(f"{UNITS[hundreds]} HUNDRED")
    if value >= 20:
        tens, ones = divmod(value, 10)
        parts.append(TENS[tens])
        if ones:
            parts.append(UNITS[ones])
    elif value:
        parts.append(TEENS[value - 10] if 10 <= value <= 19 else UNITS[value])
    return " ".join(parts)


def number_to_words(value: int) -> str:
    """Return *value* written in English words.

    >>> number_to_words(1932)
    'NINETEEN THIRTY TWO'
    >>> number_to_words(0)
    'ZERO'
    """
    if value < 0:
        return "MINUS " + number_to_words(-value)
    if value == 0:
        return "ZERO"
    parts: list[str] = []
    for scale, name in SCALES:
        if value >= scale:
            count, value = divmod(value, scale)
            chunk = _under_thousand(count)
            parts.append(f"{chunk} {name}".strip() if name else chunk)
    return " ".join(part for part in parts if part)


def readable_number_words(value: int) -> str:
    """Return the most readable English wording of *value*.

    Four digit numbers are read the British way, the way years are read:
    ``1932`` becomes ``NINETEEN THIRTY TWO`` and ``2001`` becomes
    ``TWENTY OH ONE``.  Everything else uses the plain quantity reading.
    """
    if not 1000 <= value <= 9999:
        return number_to_words(value)

    high, low = divmod(value, 100)
    parts = [_under_thousand(high)]
    if low == 0:
        parts.append("HUNDRED")
    elif low < 10:
        parts.append(f"OH {UNITS[low]}")
    else:
        parts.append(_under_thousand(low))
    return " ".join(parts)


def digits_to_words(text: str) -> str:
    """Spell every digit of *text* out and concatenate the results.

    >>> digits_to_words("48152")
    'FOUREIGHTONEFIVETWO'
    """
    return "".join(UNITS[int(digit)] for digit in text if digit.isdigit())


def _is_exact_identifier(digits: str) -> bool:
    """A long run of digits is treated as an identifier that must survive."""
    return len(digits) >= EXACT_DIGIT_THRESHOLD


def expand_number(match: re.Match[str], policy: str, join_words: bool) -> str:
    """Expand one number match according to *policy*."""
    raw = match.group(0)
    digits = re.sub(r"[^0-9]", "", raw)
    mode = policy
    if mode == "auto":
        mode = "digits" if _is_exact_identifier(digits) else "words"

    if mode == "digits":
        return digits_to_words(digits)

    # words
    integer_part, _, fraction = raw.partition(".")
    has_grouping = "," in integer_part
    integer_part = integer_part.replace(",", "")
    if not integer_part:
        words = "ZERO"
    elif has_grouping:
        # A thousands separator marks a quantity: read it out in full.
        words = number_to_words(int(integer_part))
    else:
        words = readable_number_words(int(integer_part))
    if fraction:
        spelled = " ".join(UNITS[int(digit)] for digit in fraction)
        words = f"{words} POINT {spelled}"
    return words.replace(" ", "") if join_words else words


def expand_numbers(
    text: str, policy: str = "auto", join_words: bool = False
) -> str:
    """Replace every number in *text* with its spelling.

    Parameters
    ----------
    text:
        The text to process.
    policy:
        ``"auto"``, ``"words"`` or ``"digits"`` (see the module docstring).
    join_words:
        When ``True`` the words of a number are joined without spaces, the
        way German operators wrote them (``NINETEENTHIRTYTWO``).
    """
    if policy not in POLICIES:
        raise ValueError(f"Unknown number policy {policy!r}.")
    return NUMBER_PATTERN.sub(
        lambda match: expand_number(match, policy, join_words), text
    )
