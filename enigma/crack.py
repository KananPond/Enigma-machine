"""Breaking Enigma: from a ciphertext alone to the key.

Decoding a message needs the key; breaking it means finding the key first.
The classical way of doing that is the *menu attack* that Turing's Bombe
performed: a guess about the plaintext (a *crib*) is put next to the
ciphertext, and the two together say something about the rotors.

The relation behind it
----------------------

A key press goes through the plugboard, through the rotors and the
reflector, and through the plugboard again.  Writing ``P`` for the plugboard
and ``S`` for the machine core (rotors and reflector, no plugboard) that is

    cipher = P(S(P(plain)))

and because the plugboard is an involution (``P(P(x)) = x``)

    P(cipher) = S(P(plain))                                   (1)

So for every crib position the plugboard value of the ciphertext letter is
the core permutation of the plugboard value of the plaintext letter.  The
core permutation is an involution as well, so (1) works in both directions:
the two letters of a crib position are linked by the core.

The crib and the ciphertext form a graph: one letter per node, one edge per
crib position, joining the plaintext letter to the ciphertext letter.  Along
the edges of that graph the plugboard values are chained, and one free value
- the plugboard value of the root of a connected part - decides all the
others.

What separates the right settings from the wrong ones is the plugboard
itself: it is a bijection (two letters never share a partner) and it is
involutory (a letter plugged to ``B`` is plugged back to ``A``).  A wrong
rotor setting derives partners that contradict those rules, and the setting
is thrown away.  The setting that survives is the one that was really used.

The attack therefore needs a crib - a guess about the plaintext - and
knows where in the message the crib sits.  That was true for the Bombe as
well; the crib was found by dragging it over the message and watching for
a position that produced readable German.

What this module does *not* do is guess the crib.  It takes the plaintext
guess, the possible positions and the rotors and reflectors to try, and
returns the rotor settings that survive together with the plugboard cables
the attack was able to pin down.  The rest of the plugboard is then found
with the language model of :mod:`enigma.english`.

This module needs :mod:`numpy`; the rest of the package does not.
"""

from __future__ import annotations

import functools
import time
from collections import deque
from dataclasses import dataclass, field
from itertools import permutations
from typing import Iterable, Iterator, Sequence

import numpy as np

from .data import ALPHABET, REFLECTORS, ROTORS, index_to_letter, letter_to_index
from .machine import EnigmaMachine
from .plugboard import Plugboard, PlugboardError

#: The number of rotor start positions that are searched at once.
START_POSITIONS = 26 * 26 * 26

#: The rotors of the Wehrmacht machine, the ones a broken message used.
DEFAULT_ROTORS: tuple[str, ...] = ("I", "II", "III")

#: The reflectors of the Wehrmacht machine.
DEFAULT_REFLECTORS: tuple[str, ...] = ("B", "C", "B thin", "C thin")

#: The letters of the alphabet as numbers.
GRID = np.arange(26)


# ------------------------------------------------------------------ findings
@dataclass
class MenuFinding:
    """A rotor setting that survived the menu attack."""

    rotor_order: tuple[str, str, str]
    """The three rotors, left to right."""

    reflector: str
    """The reflector that was used."""

    ring_settings: tuple[str, str, str]
    """The ring settings, left to right."""

    positions: str
    """The starting position of the rotors, for example ``"BMU"``."""

    crib_offset: int = 0
    """Where in the message the crib was found."""

    plugboard_pairs: tuple[tuple[str, str], ...] = ()
    """The plugboard cables the attack was able to pin down."""

    crib_hits: int = 0
    """How many letters of the crib the finding deciphers correctly."""

    def describe(self) -> str:
        """Return a one line summary of the finding."""
        cables = " ".join(f"{first}{second}" for first, second in self.plugboard_pairs)
        return (
            f"Walzenlage {'-'.join(self.rotor_order)} | Umkehrwalze {self.reflector} | "
            f"Ringstellung {''.join(self.ring_settings)} | Grundstellung {self.positions} | "
            f"Stecker {cables or 'none'}"
        )


@dataclass
class BreakResult:
    """The outcome of a break run."""

    finding: MenuFinding | None = None
    """The rotor settings that were found, if the attack found any."""

    text: str = ""
    """The deciphered message, with word boundaries and punctuation."""

    letters: str = ""
    """The deciphered message, without word boundaries."""

    score: float = 0.0
    """How English the deciphered message looks (higher is better)."""

    plugboard: Plugboard = field(default_factory=Plugboard)
    """The plugboard that deciphers the message."""

    positions: str = ""
    """The starting position of the rotors."""

    elapsed: float = 0.0
    """How long the run took, in seconds."""

    candidates: list[MenuFinding] = field(default_factory=list)
    """Every rotor setting that survived the attack."""

    confident: bool = False
    """``False`` when nothing convincing was found."""

    def describe(self) -> str:
        """Return a one line summary of the result."""
        if self.finding is None:
            return "nothing found"
        return self.finding.describe()


# --------------------------------------------------------------- core tables
def _rotor_tables(spec) -> tuple[np.ndarray, np.ndarray]:
    """Return the forward and backward map of a rotor for every ring offset."""
    wiring = [ord(char) - 65 for char in spec.wiring]
    inverse = [0] * 26
    for index, target in enumerate(wiring):
        inverse[target] = index

    forward = np.empty((26, 26), dtype=np.int16)
    backward = np.empty((26, 26), dtype=np.int16)
    for offset in range(26):
        for letter in range(26):
            forward[offset, letter] = (wiring[(letter + offset) % 26] - offset) % 26
            backward[offset, letter] = (inverse[(letter + offset) % 26] - offset) % 26
    return forward, backward


def core_table(order: tuple[str, str, str], reflector: str) -> np.ndarray:
    """Return ``core[oL, oM, oR, letter]`` for one rotor order and reflector.

    ``oL``, ``oM`` and ``oR`` are the wiring offsets of the three rotors, the
    letter is the one that enters the core.  The table is the core
    permutation of :meth:`enigma.machine.EnigmaMachine.core_permutation`,
    written out for every combination of the three offsets.
    """
    return _core_table(order, reflector)


@functools.lru_cache(maxsize=8)
def _core_table(order: tuple[str, str, str], reflector: str) -> np.ndarray:
    """Return the core table, cached because it is used over and over."""
    tables = [_rotor_tables(ROTORS[name]) for name in order]
    reflector_map = np.array(
        [ord(char) - 65 for char in REFLECTORS[reflector]], dtype=np.int16
    )

    o_left, o_middle, o_right = np.meshgrid(GRID, GRID, GRID, indexing="ij")
    o_left = o_left[..., None]
    o_middle = o_middle[..., None]
    o_right = o_right[..., None]
    letter = np.broadcast_to(GRID, (26, 26, 26, 26))

    value = tables[2][0][o_right, letter]
    value = tables[1][0][o_middle, value]
    value = tables[0][0][o_left, value]
    value = reflector_map[value]
    value = tables[0][1][o_left, value]
    value = tables[1][1][o_middle, value]
    value = tables[2][1][o_right, value]
    return value.astype(np.int8)


def _sample_permutations(
    order: tuple[str, str, str],
    reflector: str,
    rings: tuple[int, int, int],
    start: tuple[int, int, int],
    length: int,
) -> list[np.ndarray]:
    """Return the core permutation of the first *length* characters.

    This is the single machine version of :class:`_Stepping` and is used to
    rate a candidate quickly - the whole message does not have to be
    deciphered to see whether it looks like English.
    """
    core = _core_table(order, reflector)

    notch_middle = np.zeros(26, dtype=bool)
    notch_right = np.zeros(26, dtype=bool)
    for index in ROTORS[order[1]].turnover_indices:
        notch_middle[index] = True
    for index in ROTORS[order[2]].turnover_indices:
        notch_right[index] = True

    left, middle, right = start
    result: list[np.ndarray] = []
    for _ in range(length):
        middle_at_notch = bool(notch_middle[middle])
        right_at_notch = bool(notch_right[right])
        left = (left + middle_at_notch) % 26
        middle = (middle + (right_at_notch or middle_at_notch)) % 26
        right = (right + 1) % 26
        result.append(
            core[
                (left - rings[0]) % 26,
                (middle - rings[1]) % 26,
                (right - rings[2]) % 26,
            ]
        )
    return result


class _Stepping:
    """The rotor offsets of every start position, character by character.

    The rotors step before every character, exactly as
    :meth:`enigma.machine.EnigmaMachine.step_rotors` does it, including the
    double stepping.  All ``26**3`` start positions are simulated at once,
    and every step yields the wiring offsets of the three rotors.
    """

    def __init__(self, order: tuple[str, str, str], rings: tuple[int, int, int]) -> None:
        self.rings = rings

        notch_middle = np.zeros(26, dtype=bool)
        notch_right = np.zeros(26, dtype=bool)
        for index in ROTORS[order[1]].turnover_indices:
            notch_middle[index] = True
        for index in ROTORS[order[2]].turnover_indices:
            notch_right[index] = True

        start_left, start_middle, start_right = np.meshgrid(
            GRID, GRID, GRID, indexing="ij"
        )
        self.pos_left = start_left.reshape(-1).astype(np.int16)
        self.pos_middle = start_middle.reshape(-1).astype(np.int16)
        self.pos_right = start_right.reshape(-1).astype(np.int16)
        self.notch_middle = notch_middle
        self.notch_right = notch_right

    def __iter__(self) -> Iterator[tuple[np.ndarray, np.ndarray, np.ndarray]]:
        """Yield the rotor offsets of every character of the message."""
        while True:
            middle_at_notch = self.notch_middle[self.pos_middle]
            right_at_notch = self.notch_right[self.pos_right]
            self.pos_left = (self.pos_left + middle_at_notch) % 26
            self.pos_middle = (
                self.pos_middle + (right_at_notch | middle_at_notch)
            ) % 26
            self.pos_right = (self.pos_right + 1) % 26
            yield (
                (self.pos_left - self.rings[0]) % 26,
                (self.pos_middle - self.rings[1]) % 26,
                (self.pos_right - self.rings[2]) % 26,
            )


# ----------------------------------------------------------------- the graph
def _graph(plain: Sequence[int], cipher: Sequence[int]) -> dict[int, list[tuple[int, int]]]:
    """Return the crib/ciphertext graph: letter -> list of (other, position)."""
    adjacency: dict[int, list[tuple[int, int]]] = {}
    for index, (first, second) in enumerate(zip(plain, cipher)):
        adjacency.setdefault(first, []).append((second, index))
        adjacency.setdefault(second, []).append((first, index))
    return adjacency


def _components(
    adjacency: dict[int, list[tuple[int, int]]]
) -> list[list[int]]:
    """Return the connected parts of the graph, the largest one first."""
    seen: set[int] = set()
    parts: list[list[int]] = []
    for start in sorted(adjacency):
        if start in seen:
            continue
        stack = [start]
        seen.add(start)
        part: list[int] = []
        while stack:
            letter = stack.pop()
            part.append(letter)
            for other, _ in adjacency[letter]:
                if other not in seen:
                    seen.add(other)
                    stack.append(other)
        part.sort()
        parts.append(part)
    parts.sort(key=len, reverse=True)
    return parts


def _tree(
    adjacency: dict[int, list[tuple[int, int]]], part: Sequence[int]
) -> list[tuple[int, int, int]]:
    """Return a part of the graph as a list of (letter, parent, position)."""
    root = part[0]
    tree: list[tuple[int, int, int]] = []
    queue = [root]
    seen = {root}
    while queue:
        letter = queue.pop(0)
        for other, position in adjacency[letter]:
            if other in seen:
                continue
            seen.add(other)
            tree.append((other, letter, position))
            queue.append(other)
    return tree


def _self_loops(
    adjacency: dict[int, list[tuple[int, int]]]
) -> dict[int, list[int]]:
    """Return the letters that were enciphered into themselves.

    A letter that is its own cipher partner gives a strong condition: the
    core permutation at that position has to leave the plugboard value of
    the letter alone.
    """
    loops: dict[int, list[int]] = {}
    for letter, edges in adjacency.items():
        for other, position in edges:
            if other == letter and position not in loops.setdefault(letter, []):
                loops[letter].append(position)
    return loops


# --------------------------------------------------------------- the attack
@dataclass
class _Candidates:
    """The plugboard hypotheses of one part of the crib graph."""

    letters: list[int]
    """The letters of the part."""

    states: np.ndarray
    """The start positions the hypotheses belong to."""

    hypotheses: np.ndarray
    """The plugboard value of the root letter."""

    values: np.ndarray
    """The plugboard value of every letter, one row per hypothesis."""


def _candidates(
    tables: list[np.ndarray],
    letters: Sequence[int],
    tree: Sequence[tuple[int, int, int]],
    root: int,
    loops: dict[int, list[int]] | None = None,
) -> _Candidates:
    """Return the plugboard hypotheses of one part of the crib graph.

    The plugboard value of the root is the free parameter; the values of the
    other letters follow along the edges of the graph.  A hypothesis is
    thrown away when the derived partners are not a bijection and not
    involutory - which is what happens for a wrong rotor setting.
    """
    count = tables[0].shape[0]
    rows = np.arange(count)[:, None]

    values: dict[int, np.ndarray] = {
        root: np.broadcast_to(GRID.astype(np.int8), (count, 26)).copy()
    }
    for letter, parent, position in tree:
        values[letter] = tables[position][rows, values[parent]]

    arrays = [values[letter] for letter in letters]

    alive = np.ones((count, 26), dtype=bool)
    # the plugboard is a bijection: two letters never share a partner
    for first in range(len(letters)):
        for second in range(first + 1, len(letters)):
            alive &= arrays[first] != arrays[second]

    # a letter that was enciphered into itself sits on a fixed point of the
    # core permutation at that position
    for letter, positions in (loops or {}).items():
        if letter not in values:
            continue
        for position in positions:
            alive &= tables[position][rows, values[letter]] == values[letter]

    states, hypotheses = np.nonzero(alive)
    if states.size:
        # the plugboard is involutory: A plugged to B means B plugged to A
        lookup = np.full(26, -1, dtype=np.int16)
        for index, letter in enumerate(letters):
            lookup[letter] = index
        stacked = np.stack([array[states, hypotheses] for array in arrays])

        for index, letter in enumerate(letters):
            partner = lookup[stacked[index]]
            known = partner >= 0
            if not known.any():
                continue
            safe = np.where(known, partner, 0)
            got = stacked[safe, np.arange(states.size)]
            broken = known & (got != letter)
            if broken.any():
                alive[states[broken], hypotheses[broken]] = False

        states, hypotheses = np.nonzero(alive)

    if states.size == 0:
        return _Candidates(list(letters), states, hypotheses, np.zeros((0, len(letters)), np.int8))

    stacked = np.stack([array[states, hypotheses] for array in arrays], axis=1)
    return _Candidates(list(letters), states, hypotheses, stacked)


def _combine(parts: Sequence[_Candidates], state: int, limit: int = 32) -> list[dict[int, int]]:
    """Return the consistent plugboard maps of one start position.

    The parts of the crib graph are independent as long as their plugboard
    values stay inside them.  Once a value points into another part the two
    have to agree, so the combinations are checked against each other.  The
    parts are walked one after the other and a combination that already
    contradicts itself is dropped right away - that keeps the search small.
    """
    options: list[list[dict[int, int]]] = []
    for part in parts:
        # the states are sorted, so the candidates of one start position can
        # be looked up instead of scanned
        begin = int(np.searchsorted(part.states, state, side="left"))
        end = int(np.searchsorted(part.states, state, side="right"))
        choices = [
            {
                letter: int(part.values[row, index])
                for index, letter in enumerate(part.letters)
            }
            for row in range(begin, end)
        ]
        if not choices:
            return []
        options.append(choices)

    results: list[dict[int, int]] = []
    merged: dict[int, int] = {}
    partners: dict[int, int] = {}

    def walk(index: int) -> None:
        if len(results) >= limit:
            return
        if index == len(options):
            results.append(dict(merged))
            return
        for mapping in options[index]:
            added: list[int] = []
            broken = False
            for letter, partner in mapping.items():
                if letter in merged and merged[letter] != partner:
                    broken = True
                    break
                if partner in partners and partners[partner] != letter:
                    broken = True
                    break
                # the plugboard is involutory, also across the parts
                if partner in merged and merged[partner] != letter:
                    broken = True
                    break
                # a letter that is already the partner of somebody else
                # cannot be plugged to somebody else as well
                if letter in partners and partners[letter] != partner:
                    broken = True
                    break
                merged[letter] = partner
                partners[partner] = letter
                added.append(letter)
            if not broken:
                walk(index + 1)
            for letter in added:
                partner = merged.pop(letter)
                partners.pop(partner, None)

    walk(0)
    return results


def _closed(mapping: dict[int, int]) -> dict[int, int]:
    """Return the map with its involution written back.

    A plugboard is an involution: ``A`` plugged to ``B`` means ``B`` is
    plugged to ``A``.  The crib graph only knows the letters that really
    appear in it, so a map can name a partner that is not a node of the
    graph - the way back is then still known and is added here.  Without it
    a deciphered letter would come out wrong whenever the signal runs
    through the missing side of a cable.
    """
    closed: dict[int, int] = {}
    for letter, partner in mapping.items():
        if letter == partner:
            continue
        if closed.get(letter, partner) != partner:
            continue
        if closed.get(partner, letter) != letter:
            continue
        closed[letter] = partner
        closed[partner] = letter
    return closed


def _pairs_of(mapping: dict[int, int]) -> tuple[tuple[str, str], ...]:
    """Turn a plugboard map into the list of its cables."""
    closed = _closed(mapping)
    seen: set[int] = set()
    pairs: list[tuple[str, str]] = []
    for letter in sorted(closed):
        partner = closed[letter]
        if letter == partner or letter in seen:
            continue
        seen.add(letter)
        seen.add(partner)
        pairs.append(
            (index_to_letter(letter), index_to_letter(partner))
        )
    return tuple(pairs)


def _crib_hits(
    mapping: dict[int, int],
    permutations: list[list[int]],
    plain: Sequence[int],
    cipher: Sequence[int],
) -> int:
    """Return how many letters of the crib a plugboard map deciphers.

    The crib is the one thing the sender and the receiver both know, so a
    wiring that decodes it letter by letter is the right one.  The map is
    the one the attack found; the letters it does not mention are left
    alone.
    """
    closed = _closed(mapping)
    table = list(range(26))
    for letter, partner in closed.items():
        table[letter] = partner

    hits = 0
    for index, expected in enumerate(plain):
        value = table[permutations[index][table[cipher[index]]]]
        if value == expected:
            hits += 1
    return hits


def _positions_of(state: int) -> str:
    """Return the starting position of a start position index."""
    left = state // (26 * 26)
    middle = (state // 26) % 26
    right = state % 26
    return index_to_letter(left) + index_to_letter(middle) + index_to_letter(right)


def crib_matches(finding: MenuFinding, ciphertext: str, crib: str) -> int:
    """Return how many letters of the crib a finding deciphers correctly.

    The menu attack only pins down the cables it could see; a finding that
    really is the right setting deciphers the crib letter by letter.  Note
    that every candidate which survives the attack does so - the crib is
    what they were tested against - so a high count confirms that the
    finding is self consistent, but it does not by itself prove that the
    setting was the real one.  The message decides that; see
    :func:`quick_score`.
    """
    machine = EnigmaMachine.create(
        rotor_order=finding.rotor_order,
        reflector=finding.reflector,
        ring_settings=finding.ring_settings,
        positions=finding.positions,
    )
    try:
        machine.plugboard = Plugboard(
            {first: second for first, second in finding.plugboard_pairs}
        )
    except PlugboardError:
        return 0

    letters = "".join(char for char in ciphertext.upper() if char in ALPHABET)
    guess = "".join(char for char in crib.upper() if char in ALPHABET)
    secret = letters[finding.crib_offset : finding.crib_offset + len(guess)]

    for _ in range(finding.crib_offset):
        machine.step_rotors()

    hits = 0
    for plain, cipher in zip(guess, secret):
        if machine.press(cipher) == plain:
            hits += 1
    return hits


def quick_score(
    finding: MenuFinding, ciphertext: str, model, sample: int = 80
) -> float:
    """Return the language score of the message as the finding deciphers it.

    The finding only knows the cables the menu attack could see, so the text
    is still partly scrambled - but a finding that sits at the right place
    in the message deciphers most of it, while a finding at the wrong place
    deciphers noise.  Only the first *sample* letters are deciphered, which
    is enough to tell the two apart and keeps the search quick.
    """
    letters = "".join(char for char in ciphertext.upper() if char in ALPHABET)
    if len(letters) < 8:
        return float("-inf")
    length = min(sample, len(letters))

    try:
        table = list(range(26))
        for first, second in finding.plugboard_pairs:
            table[letter_to_index(first)] = letter_to_index(second)
            table[letter_to_index(second)] = letter_to_index(first)
    except (PlugboardError, ValueError):
        return float("-inf")

    start = tuple(
        letter_to_index(char) for char in finding.positions
    )
    rings = tuple(letter_to_index(char) for char in finding.ring_settings)
    permutations = _sample_permutations(
        finding.rotor_order, finding.reflector, rings, start, length
    )

    plain: list[int] = []
    for index, permutation in enumerate(permutations):
        value = letter_to_index(letters[index])
        plain.append(table[permutation[table[value]]])

    text = "".join(index_to_letter(value) for value in plain)
    return model.score(text)


# ------------------------------------------------------------------ the menu
def menu_attack(
    ciphertext: str,
    crib: str,
    offsets: Iterable[int] | None = None,
    rotor_names: Sequence[str] = DEFAULT_ROTORS,
    reflectors: Sequence[str] = DEFAULT_REFLECTORS,
    ring_settings: tuple[str, str, str] = ("A", "A", "A"),
    max_per_position: int = 64,
    model=None,
    orders: Sequence[tuple[str, str, str]] | None = None,
    budget: float = 1.5,
    keep_per_state: int = 4,
    cap_per_position: bool = False,
    progress=None,
) -> list[MenuFinding]:
    """Run the menu attack and return the rotor settings that survive it.

    Parameters
    ----------
    ciphertext:
        The enciphered message.
    crib:
        A guess about the plaintext, as it was prepared for the machine -
        the spaces are ``X`` (or ``Q``) in the prepared text, not blanks.
    offsets:
        The positions in the message where the crib may sit.  ``None`` means
        every position.
    rotor_names:
        The rotors that may be used.  Every order of three of them is tried.
    reflectors:
        The reflectors that may be used.
    ring_settings:
        The ring settings.  The historical Bombe assumed they were known,
        so they are not searched here.
    max_per_position:
        How many findings are kept for every position of the crib.  A wrong
        position produces a lot of them; the right one produces very few.
        The language model (if *model* is given) decides which ones are
        kept - it reads the whole message and sees which one looks like
        English.
    orders:
        The rotor orders to try, left to right.  ``None`` means every order
        of three of the *rotor_names*.
    budget:
        How many seconds one combination of rotor order, reflector and crib
        position may take.  A crib that does not fit the message well
        produces a huge number of candidates; the time limit keeps the
        search from running away.  The candidates themselves are still
        looked at afterwards - only the rating of the message, which is
        the expensive part, is skipped.
    keep_per_state:
        How many plugboard hypotheses are kept for every start position
        that survives the attack.
    cap_per_position:
        Stop walking the start positions once *budget* seconds are up and a
        few findings are in hand.  A caller that repeats the attack for every
        rotor order (and only needs the best few results) turns this on to
        keep the worst case bounded; a caller that wants *every* finding
        leaves it off.
    progress:
        Optional callback, called with ``(done, total, message)``.
    """
    letters = "".join(char for char in ciphertext.upper() if char in ALPHABET)
    guess = "".join(char for char in crib.upper() if char in ALPHABET)
    if len(guess) < 3:
        raise ValueError("The crib needs at least three letters.")
    if len(letters) < len(guess):
        raise ValueError("The message is shorter than the crib.")

    if offsets is None:
        wanted = list(range(len(letters) - len(guess) + 1))
    else:
        wanted = sorted(
            {
                offset
                for offset in offsets
                if 0 <= offset <= len(letters) - len(guess)
            }
        )
        if not wanted:
            raise ValueError("No usable position for the crib.")

    plain = [letter_to_index(char) for char in guess]
    rings = tuple(letter_to_index(char) for char in ring_settings)

    if orders is None:
        orders = [
            tuple(order)
            for order in permutations(rotor_names, 3)
            if all(name in ROTORS for name in order)
        ]
    else:
        orders = [tuple(order) for order in orders]
    total = len(orders) * len(reflectors) * len(wanted)
    done = 0

    findings: list[MenuFinding] = []
    for reflector in reflectors:
        for order in orders:
            core = core_table(order, reflector)
            stepping = _Stepping(order, rings)
            window: deque = deque(maxlen=len(guess))
            wanted_set = set(wanted)
            remaining = len(wanted_set)

            for position, offsets_here in enumerate(stepping):
                window.append(offsets_here)
                if position < len(guess) - 1:
                    continue
                start = position - len(guess) + 1
                if start not in wanted_set:
                    continue
                remaining -= 1

                tables = [
                    core[
                        window[index][0],
                        window[index][1],
                        window[index][2],
                        :,
                    ]
                    for index in range(len(guess))
                ]

                secret = [
                    letter_to_index(char)
                    for char in letters[start : start + len(guess)]
                ]
                adjacency = _graph(plain, secret)
                parts = _components(adjacency)
                loops = _self_loops(adjacency)

                candidates: list[_Candidates] = []
                alive = np.ones(START_POSITIONS, dtype=bool)
                for part in parts:
                    tree = _tree(adjacency, part)
                    found = _candidates(tables, part, tree, part[0], loops)
                    mask = np.zeros(START_POSITIONS, dtype=bool)
                    mask[found.states] = True
                    alive &= mask
                    candidates.append(found)

                # The findings of one position of the crib.  A wrong
                # position produces a lot of them, so only the best ones are
                # kept.  The crib itself cannot tell them apart - every
                # candidate that survives the attack deciphers the crib
                # letter by letter, because the crib is what it was tested
                # against.  The message decides instead: the right
                # plugboard deciphers the whole message, a wrong one
                # produces noise.
                here: list[MenuFinding] = []
                deadline = time.perf_counter() + budget
                for state in np.nonzero(alive)[0]:
                    over_time = time.perf_counter() > deadline
                    if (
                        cap_per_position
                        and over_time
                        and len(here) >= max(4, keep_per_state)
                    ):
                        # The time for this position is up and there are
                        # already findings to choose from; walking the rest of
                        # the states would only repeat the same work.
                        break
                    mappings = _combine(candidates, int(state))
                    if not mappings:
                        # Almost every wrong setting dies here, so this loop
                        # is cheap; it is worth going through all of them
                        # even when the time is up, because the one that
                        # really fits is the one that produces a plugboard
                        # at all.
                        continue
                    permutations_here = [
                        tables[index][int(state)].tolist()
                        for index in range(len(guess))
                    ]

                    rows: list[tuple[float, int, tuple[tuple[str, str], ...]]] = []
                    rough: list[tuple[int, int, dict[int, int], tuple[tuple[str, str], ...]]] = []
                    for mapping in mappings:
                        hits = _crib_hits(mapping, permutations_here, plain, secret)
                        pairs = _pairs_of(mapping)
                        if len(pairs) > Plugboard.MAX_PAIRS:
                            # a Steckerbrett cannot hold that many cables
                            continue
                        rough.append((hits, len(pairs), mapping, pairs))

                    if model is None:
                        # without a language model the crib is the only judge
                        rough.sort(key=lambda row: (-row[0], row[1]))
                        for hits, _cables, _mapping, pairs in rough[:keep_per_state]:
                            rows.append((float(hits), hits, pairs))
                    elif over_time:
                        # The time is up.  Rating the message is the
                        # expensive part, so the candidates are kept in the
                        # order of the cheap criterion instead.
                        rough.sort(key=lambda row: (-row[0], row[1]))
                        for hits, _cables, _mapping, pairs in rough[:keep_per_state]:
                            rows.append((float(hits), hits, pairs))
                    else:
                        # The crib cannot tell the candidates apart - they all
                        # decipher it letter by letter, because the crib is
                        # what they were tested against.  The message does,
                        # but rating the message is expensive, so a cheap
                        # preselection comes first: a wrong setting tends to
                        # invent cables that the real one does not have.
                        rough.sort(key=lambda row: (-row[0], row[1]))
                        for hits, _cables, mapping, pairs in rough[:keep_per_state]:
                            finding = MenuFinding(
                                rotor_order=order,
                                reflector=reflector,
                                ring_settings=ring_settings,
                                positions=_positions_of(int(state)),
                                crib_offset=start,
                                plugboard_pairs=pairs,
                                crib_hits=hits,
                            )
                            rows.append(
                                (
                                    quick_score(finding, ciphertext, model),
                                    hits,
                                    pairs,
                                )
                            )

                    rows.sort(key=lambda row: (-row[0], -row[1]))

                    for rank, hits, pairs in rows[:keep_per_state]:
                        here.append(
                            MenuFinding(
                                rotor_order=order,
                                reflector=reflector,
                                ring_settings=ring_settings,
                                positions=_positions_of(int(state)),
                                crib_offset=start,
                                plugboard_pairs=pairs,
                                crib_hits=hits,
                            )
                        )

                if model is not None:
                    # the message itself decides which findings are worth
                    # keeping: the right one deciphers most of it
                    here.sort(
                        key=lambda item: -quick_score(item, ciphertext, model)
                    )
                else:
                    here.sort(key=lambda item: -item.crib_hits)
                findings.extend(here[:max_per_position])

                if remaining <= 0:
                    break

                done += 1
                if progress is not None:
                    progress(
                        done,
                        total,
                        f"{'-'.join(order)} / {reflector} / 位置 {start}",
                    )

    findings.sort(key=lambda item: item.crib_offset)
    return findings


# --------------------------------------------------------------- the breaking
def break_enigma(
    ciphertext: str,
    crib: str,
    offsets: Iterable[int] | None = None,
    rotor_names: Sequence[str] = DEFAULT_ROTORS,
    reflectors: Sequence[str] = DEFAULT_REFLECTORS,
    ring_settings: tuple[str, str, str] = ("A", "A", "A"),
    model=None,
    max_candidates: int = 8,
    orders: Sequence[tuple[str, str, str]] | None = None,
    progress=None,
) -> BreakResult:
    """Break a message: find the rotors, then the plugboard, then the text.

    The menu attack narrows the rotor settings down; every setting that
    survives is then completed with the language model of
    :mod:`enigma.english`, which fills in the plugboard cables the attack
    could not pin down and rates the result.
    """
    from .decode import solve_plugboard
    from .english import DEFAULT_MODEL

    started = time.perf_counter()
    model = model or DEFAULT_MODEL
    findings = menu_attack(
        ciphertext,
        crib,
        offsets=offsets,
        rotor_names=rotor_names,
        reflectors=reflectors,
        ring_settings=ring_settings,
        model=model,
        orders=orders,
    )

    # the finding that deciphers the message best is the one to keep
    scored = [
        (item, quick_score(item, ciphertext, model), item.crib_hits)
        for item in findings
    ]
    scored.sort(key=lambda row: (-row[1], -row[2]))
    ranked = [row[0] for row in scored]

    best: BreakResult = BreakResult(elapsed=time.perf_counter() - started)
    best.candidates = ranked
    best_score = float("-inf")

    for number, finding in enumerate(ranked[:max_candidates], start=1):
        machine = EnigmaMachine.create(
            rotor_order=finding.rotor_order,
            reflector=finding.reflector,
            ring_settings=finding.ring_settings,
            positions=finding.positions,
        )
        seeds = (
            tuple(
                (letter_to_index(first), letter_to_index(second))
                for first, second in finding.plugboard_pairs
            ),
        )
        try:
            result = solve_plugboard(
                ciphertext,
                machine,
                positions=finding.positions,
                model=model,
                seeds=seeds,
            )
        except ValueError:
            continue

        if progress is not None:
            progress(
                number,
                len(ranked),
                f"{finding.rotor_order} / {finding.reflector} / {finding.positions}",
            )

        if result.score > best_score:
            best_score = result.score
            best = BreakResult(
                finding=finding,
                text=result.text,
                letters=result.letters,
                score=result.score,
                plugboard=result.plugboard,
                positions=result.positions,
                elapsed=time.perf_counter() - started,
                candidates=ranked,
                confident=result.confident,
            )

    best.elapsed = time.perf_counter() - started
    return best
