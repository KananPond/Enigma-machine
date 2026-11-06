"""Decoding: turning a ciphertext back into readable English.

Two jobs live here.

**Deciphering.**  The Enigma is reciprocal, so running the cipher backwards
is the same as running it forwards.  :func:`decode` deciphers a ciphertext
with the settings of a machine and then puts the lost structure back: the
word boundaries (see :mod:`enigma.english`) and the punctuation.

**Recovering an unknown plugboard.**  When the rotors, the reflector, the
ring settings and the starting position are known but the Steckerbrett is
not, the plugboard can be searched: every candidate wiring is tried and the
one that produces the most English looking text wins.  The search is a hill
climb over the cables, scored with the quadgram model of
:mod:`enigma.english`.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Iterable

from .data import index_to_letter, letter_to_index
from .english import DEFAULT_MODEL, EnglishModel
from .machine import EnigmaMachine
from .plugboard import Plugboard

#: A table that turns 0..25 into the letters A..Z.
_INDEX_TO_ASCII = bytes(
    ord("A") + value if value < 26 else 0 for value in range(256)
)

#: The plugboard is an involution, so a board can be stored as a list of pairs.
Pairs = tuple[tuple[int, int], ...]

#: A message has to be at least this long before a plugboard can be read from
#: it.  With a handful of letters every wiring looks good by chance.
MIN_LETTERS = 40

#: How much better the found wiring has to be than no wiring at all before it
#: is accepted.
SCORE_MARGIN = 0.4


@dataclass
class DecodeResult:
    """The outcome of a decoding run."""

    letters: str = ""
    """The deciphered letters, without word boundaries."""

    words: list[str] = field(default_factory=list)
    """The deciphered text, split into words."""

    text: str = ""
    """The deciphered text, with word boundaries and punctuation."""

    score: float = 0.0
    """How English the deciphered text looks (higher is better)."""

    plugboard: Plugboard = field(default_factory=Plugboard)
    """The plugboard that was used - and, for a search, the one that was found."""

    positions: str = ""
    """The starting position the rotors were set to."""

    elapsed: float = 0.0
    """How long the run took, in seconds."""

    rounds: int = 0
    """How many rounds the plugboard search took."""

    evaluations: int = 0
    """How many candidate wirings were tried."""

    confident: bool = True
    """``False`` when the message was too short to read a plugboard from."""

    @property
    def plugboard_description(self) -> str:
        """The plugboard in the ``AV BS CG`` notation."""
        return self.plugboard.describe()


# --------------------------------------------------------------------- core
def core_permutations(machine: EnigmaMachine, count: int) -> list[list[int]]:
    """Return the core permutation of the machine for every letter of a message.

    The rotors step before every character, so the permutation has to be
    rebuilt for each position.  It does not depend on the plugboard, which
    makes it the expensive part of a decoding that only has to be done once.
    """
    permutations: list[list[int]] = []
    for _ in range(count):
        machine.step_rotors()
        permutations.append(machine.core_permutation())
    return permutations


def _swap_table(pairs: Pairs) -> list[int]:
    """Return the 26 entry swap table of a plugboard."""
    table = list(range(26))
    for first, second in pairs:
        table[first] = second
        table[second] = first
    return table


def _apply_plugboard(
    permutations: list[list[int]], cipher: list[int], table: list[int]
) -> list[int]:
    """Decipher *cipher* with the core permutations and a plugboard table.

    The machine core is an involution, so deciphering is the same operation
    as enciphering: ``p = plugboard(core(plugboard(c)))``.
    """
    return [table[permutations[index][table[value]]] for index, value in enumerate(cipher)]


def _as_letters(indices: list[int]) -> str:
    """Turn 0..25 indices into a string of letters."""
    return bytes(indices).translate(_INDEX_TO_ASCII).decode("ascii")


def machine_copy(
    machine: EnigmaMachine,
    positions: str | None = None,
    plugboard: Plugboard | None = None,
) -> EnigmaMachine:
    """Return a machine with the same settings, ready to read a message.

    The rotors are set to *positions* (the current window by default), so the
    copy starts from a defined state no matter what the original machine did.
    """
    return EnigmaMachine.create(
        rotor_order=machine.rotor_names,
        reflector=machine.reflector,
        plugboard=plugboard if plugboard is not None else machine.plugboard,
        ring_settings=machine.ring_settings,
        positions=positions if positions is not None else machine.positions,
    )


# ------------------------------------------------------------------ decoding
def decipher(
    ciphertext: str,
    machine: EnigmaMachine,
    positions: str | None = None,
    plugboard: Plugboard | None = None,
) -> tuple[str, Plugboard, str]:
    """Decipher *ciphertext* and return the letters, the plugboard and the start.

    The rotors, the reflector, the ring settings and the starting position are
    taken from *machine*; only the plugboard can be replaced.
    """
    letters = EnglishModel.letters(ciphertext)
    work = machine_copy(machine, positions, plugboard)
    start = work.positions
    if not letters:
        return "", work.plugboard, start

    permutations = core_permutations(work, len(letters))
    cipher = [letter_to_index(letter) for letter in letters]
    table = _swap_table(
        tuple(
            (letter_to_index(first), letter_to_index(second))
            for first, second in work.plugboard.pairs
        )
    )
    plain = _apply_plugboard(permutations, cipher, table)
    return _as_letters(plain), work.plugboard, start


def decode(
    ciphertext: str,
    machine: EnigmaMachine,
    positions: str | None = None,
    plugboard: Plugboard | None = None,
    model: EnglishModel | None = None,
    with_spaces: bool = True,
    with_punctuation: bool = True,
) -> DecodeResult:
    """Decipher *ciphertext* and restore the spaces and the punctuation.

    Parameters
    ----------
    ciphertext:
        The enciphered message.
    machine:
        The machine whose settings are used (rotors, reflector, ring
        settings and, unless *plugboard* says otherwise, the Steckerbrett).
    positions:
        The starting position of the rotors.  Defaults to the current window
        of the machine.
    plugboard:
        A plugboard to use instead of the one of the machine.
    model:
        The language model used for the word boundaries and the punctuation.
    with_spaces:
        Put the word boundaries back.
    with_punctuation:
        Add sentence punctuation and capitalisation.
    """
    started = time.perf_counter()
    model = model or DEFAULT_MODEL

    letters, used_plugboard, start = decipher(
        ciphertext, machine, positions=positions, plugboard=plugboard
    )

    if not letters:
        return DecodeResult(plugboard=used_plugboard, positions=start)

    words = model.restore_spaces_tokens(letters) if with_spaces else [letters]
    spaced = " ".join(words)
    text = model.restore_punctuation(spaced) if with_punctuation else spaced

    return DecodeResult(
        letters=letters,
        words=words,
        text=text,
        score=model.score(letters),
        plugboard=used_plugboard,
        positions=start,
        elapsed=time.perf_counter() - started,
    )


# ------------------------------------------------------------ plugboard hunt
def _plugboard_pairs(plugboard: Plugboard) -> Pairs:
    """Return the cables of a plugboard as a tuple of index pairs."""
    return tuple(
        (letter_to_index(first), letter_to_index(second))
        for first, second in plugboard.pairs
    )


def _pairs_to_plugboard(pairs: Pairs) -> Plugboard:
    """Turn a tuple of index pairs back into a plugboard."""
    return Plugboard(
        {index_to_letter(first): index_to_letter(second) for first, second in pairs}
    )


def _moves(pairs: Pairs, max_pairs: int) -> list[Pairs]:
    """Return every wiring that is one cable away from *pairs*."""
    plugged = {letter for pair in pairs for letter in pair}
    free = [letter for letter in range(26) if letter not in plugged]

    moves: list[Pairs] = []

    # Rewire a plugged letter to a free one.
    for pair in pairs:
        rest = tuple(other for other in pairs if other != pair)
        for first in pair:
            for second in free:
                moves.append(
                    tuple(sorted(rest + ((min(first, second), max(first, second)),)))
                )

    # Add a cable between two free letters.
    if len(pairs) < max_pairs:
        for index, first in enumerate(free):
            for second in free[index + 1 :]:
                moves.append(tuple(sorted(pairs + ((first, second),))))

    # Remove a cable.
    for pair in pairs:
        moves.append(tuple(other for other in pairs if other != pair))

    return moves


class _Search:
    """The hill climb over the cables of the plugboard."""

    def __init__(
        self,
        permutations: list[list[int]],
        cipher: list[int],
        model: EnglishModel,
        sample: int,
    ) -> None:
        self.permutations = permutations
        self.cipher = cipher
        self.model = model
        self.sample = sample
        self.evaluations = 0
        self._quadgram_logp = model.quadgram_table
        self._quadgram_floor = model.quadgram_floor
        self._permutations_sample = permutations[:sample]
        self._cipher_sample = cipher[:sample]

    def plaintext(self, pairs: Pairs) -> str:
        """Return the deciphered sample for a candidate wiring."""
        table = _swap_table(pairs)
        indices = _apply_plugboard(self._permutations_sample, self._cipher_sample, table)
        return _as_letters(indices)

    def score(self, pairs: Pairs) -> float:
        """Return the language score of a candidate wiring."""
        self.evaluations += 1
        text = self.plaintext(pairs)
        if len(text) < 4:
            return self._quadgram_floor
        table = self._quadgram_logp
        floor = self._quadgram_floor
        total = 0.0
        for index in range(len(text) - 3):
            total += table.get(text[index : index + 4], floor)
        return total / (len(text) - 3)


def solve_plugboard(
    ciphertext: str,
    machine: EnigmaMachine,
    positions: str | None = None,
    model: EnglishModel | None = None,
    max_pairs: int = Plugboard.MAX_PAIRS,
    sample: int = 600,
    beam: int = 8,
    max_rounds: int = 12,
    with_spaces: bool = True,
    with_punctuation: bool = True,
    seeds: Iterable[Pairs] = (),
    progress=None,
) -> DecodeResult:
    """Search for the plugboard that deciphers *ciphertext* best.

    The rotors, the reflector, the ring settings and the starting position
    are taken from *machine* and are assumed to be correct - only the
    Steckerbrett is unknown.  Every candidate wiring is deciphered and rated
    with the quadgram model of :mod:`enigma.english`; the search climbs from
    the best wiring it has seen so far and keeps the best of several runs.

    Parameters
    ----------
    sample:
        How many letters of the message are used while searching.  The final
        result is always rated with the whole message.
    beam:
        How many wirings are carried into the next round of the search.
    max_rounds:
        How many rounds the search may take.
    seeds:
        Wirings the search starts from, on top of the empty board and the
        board of the machine.  The menu attack of :mod:`enigma.break` uses
        this to hand over the cables it was able to pin down.
    progress:
        Optional callback that is called with ``(round, best_score)`` after
        every round.
    """
    started = time.perf_counter()
    model = model or DEFAULT_MODEL

    letters = EnglishModel.letters(ciphertext)
    work = machine_copy(machine, positions)
    start = work.positions
    if len(letters) < 4:
        return DecodeResult(
            letters=letters,
            words=[letters] if letters else [],
            text=letters,
            score=model.score(letters),
            plugboard=work.plugboard,
            positions=start,
            elapsed=time.perf_counter() - started,
        )

    permutations = core_permutations(work, len(letters))
    cipher = [letter_to_index(letter) for letter in letters]
    search = _Search(permutations, cipher, model, min(sample, len(letters)))

    starts: list[Pairs] = [()]
    current = _plugboard_pairs(work.plugboard)
    if current:
        starts.append(current)
    for seed in seeds:
        seed_pairs = tuple(sorted(seed))
        if seed_pairs not in starts:
            starts.append(seed_pairs)

    best_pairs: Pairs = ()
    best_score = float("-inf")

    for initial in starts:
        states: list[tuple[float, Pairs]] = [(search.score(initial), initial)]
        previous_best = float("-inf")
        for round_index in range(max_rounds):
            children: dict[Pairs, float] = {}
            for _, pairs in states:
                for move in _moves(pairs, max_pairs):
                    if move in children:
                        continue
                    children[move] = search.score(move)

            if not children:
                break

            ranked = sorted(children.items(), key=lambda item: item[1], reverse=True)
            states = [(score, pairs) for pairs, score in ranked[:beam]]

            round_best_score, round_best_pairs = states[0]
            if round_best_score > best_score:
                best_score = round_best_score
                best_pairs = round_best_pairs

            if progress is not None:
                progress(round_index + 1, best_score)

            if round_best_score <= previous_best + 1e-9 and round_index > 0:
                # The search did not get any better; more rounds would only
                # walk over the same ground again.
                break
            previous_best = max(previous_best, round_best_score)

    plugboard = _pairs_to_plugboard(best_pairs)
    result = decode(
        ciphertext,
        machine,
        positions=start,
        plugboard=plugboard,
        model=model,
        with_spaces=with_spaces,
        with_punctuation=with_punctuation,
    )
    result.rounds = max_rounds
    result.evaluations = search.evaluations

    # A wiring that barely beats no wiring at all is not a finding but a
    # coincidence - and a message that is too short cannot tell the
    # difference anyway.
    baseline = decode(
        ciphertext,
        machine,
        positions=start,
        plugboard=Plugboard(),
        model=model,
        with_spaces=with_spaces,
        with_punctuation=with_punctuation,
    )
    if len(letters) < MIN_LETTERS or result.score < baseline.score + SCORE_MARGIN:
        result = baseline
        result.rounds = max_rounds
        result.evaluations = search.evaluations
        result.confident = False

    result.elapsed = time.perf_counter() - started
    return result
