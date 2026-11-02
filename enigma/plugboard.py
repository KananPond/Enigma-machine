"""The plugboard (Steckerbrett) of the Enigma machine."""

from __future__ import annotations

from .data import ALPHABET, index_to_letter, letter_to_index


class PlugboardError(ValueError):
    """Raised when an invalid plugboard configuration is requested."""


class Plugboard:
    """Letter-for-letter swaps applied before and after the rotor stack.

    A real Steckerbrett holds at most ten double-ended cables, so no letter
    may take part in more than one pair and a letter may not be paired with
    itself.
    """

    MAX_PAIRS = 10

    def __init__(self, pairs: dict[str, str] | None = None) -> None:
        self._swaps: dict[int, int] = {}
        for a, b in (pairs or {}).items():
            self.set_pair(a, b)

    # ------------------------------------------------------------------ API
    def set_pair(self, first: str, second: str) -> None:
        """Plug a cable between *first* and *second*.

        Any cable already attached to either letter is removed first.
        """
        a, b = letter_to_index(first), letter_to_index(second)
        if a == b:
            raise PlugboardError(f"{first!r} cannot be plugged into itself.")

        # How many cables have to give way to make room for the new one?
        displaced = set()
        for letter in (a, b):
            partner = self._swaps.get(letter)
            if partner is not None:
                displaced.update({letter, partner})
        remaining = len(self._swaps) - len(displaced)
        if remaining // 2 + 1 > self.MAX_PAIRS:
            raise PlugboardError(
                f"A Steckerbrett holds at most {self.MAX_PAIRS} cables."
            )

        for letter in (a, b):
            partner = self._swaps.get(letter)
            if partner is not None:
                del self._swaps[partner]
                del self._swaps[letter]
        self._swaps[a] = b
        self._swaps[b] = a

    def remove(self, letter: str) -> None:
        """Remove the cable attached to *letter* (if any)."""
        index = letter_to_index(letter)
        partner = self._swaps.pop(index, None)
        if partner is not None:
            self._swaps.pop(partner, None)

    def toggle(self, first: str, second: str) -> None:
        """Plug a cable, or remove it if the two letters are already paired."""
        if self.paired_with(first) == second.upper():
            self.remove(first)
        else:
            self.set_pair(first, second)

    def clear(self) -> None:
        """Remove all cables."""
        self._swaps.clear()

    def swap(self, index: int) -> int:
        """Return the letter index that *index* is connected to."""
        return self._swaps.get(index, index)

    def paired_with(self, letter: str) -> str | None:
        """Return the partner of *letter*, or ``None`` if it is not plugged."""
        index = letter_to_index(letter)
        partner = self._swaps.get(index)
        return None if partner is None else index_to_letter(partner)

    @property
    def pairs(self) -> list[tuple[str, str]]:
        """The configured cables as a sorted list of letter pairs."""
        seen: set[int] = set()
        result: list[tuple[str, str]] = []
        for a, b in sorted(self._swaps.items()):
            if a in seen:
                continue
            seen.add(a)
            seen.add(b)
            result.append((index_to_letter(a), index_to_letter(b)))
        return result

    @property
    def pair_count(self) -> int:
        return len(self.pairs)

    def __len__(self) -> int:
        return self.pair_count

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"Plugboard({self.pairs!r})"

    def describe(self) -> str:
        """Return a human readable list of cables, e.g. ``"AV BS CG"``."""
        return " ".join(f"{a}{b}" for a, b in self.pairs)

    # -------------------------------------------------------------- helpers
    @staticmethod
    def parse(text: str) -> "Plugboard":
        """Build a plugboard from a string such as ``"AV BS CG DL"``."""
        cleaned = [ch for ch in text.upper() if ch in ALPHABET]
        if len(cleaned) % 2:
            raise PlugboardError("Plugboard pairs must come in twos.")
        return Plugboard(
            {
                cleaned[i]: cleaned[i + 1]
                for i in range(0, len(cleaned), 2)
            }
        )
