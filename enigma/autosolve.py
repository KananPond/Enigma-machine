"""Automatic recovery of a message - from a ciphertext back to the plaintext.

Three ways lead from a ciphertext to readable text, and this module picks the
right one for the situation:

1. **The key is known.**  Then the message only has to be deciphered and the
   lost word boundaries put back (:func:`decipher_with_key`).

2. **A plaintext guess is known** (a *crib*).  That is the historical Bombe
   attack in :mod:`enigma.crack`: the crib is dragged over the ciphertext and
   the rotor settings that survive the menu test are kept.  This recovers the
   *whole* key - rotors, reflector, starting position and plugboard - and is
   the reliable way to open a wartime message.

3. **Only the ciphertext is known.**  There is no crib to hold on to, so the
   attack has to lean on the language itself: every rotor order, reflector
   and starting position is tried, the message is read without a plugboard
   and rated with the quadgram model of :mod:`enigma.english`.  The best
   positions are then refined by searching the plugboard.  This works well
   for messages sent with a light or empty plugboard, which is how most
   training messages, museum demonstrations and hobby nets are sent; a
   message with ten cables and no crib stays out of reach, exactly as it did
   for Bletchley Park.

All three end in an :class:`AutoResult`, which carries the key that was found,
the readable text and how much the result can be trusted.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Sequence

from .data import ALPHABET, ROTORS
from .decode import decode, solve_plugboard
from .english import DEFAULT_MODEL, EnglishModel
from .keys import Key

#: Rotors searched when no explicit list is given: the five wheels of the
#: Wehrmacht machine, in every order (60 combinations).
SCAN_ROTORS: tuple[str, ...] = ("I", "II", "III", "IV", "V")

#: Reflectors searched by the ciphertext only attack.
SCAN_REFLECTORS: tuple[str, ...] = ("B", "C")

#: How many letters are used to rate a rotor position.  Longer samples make
#: the ranking better and the scan slower; 110 letters is a good balance.
SAMPLE = 110

#: How many positions per rotor order and reflector survive the first pass.
KEEP_PER_ORDER = 6

#: How many of the best positions are refined by a plugboard search.
REFINE = 3

#: A rotor position that reads this well without a plugboard is almost
#: certainly the right one, and the remaining reflectors need not be tried.
GOOD_HIT = -5.2

#: Below this score nothing in the sweep looked like language at all, and the
#: plugboard search is not worth starting.
HOPELESS_HIT = -6.6

#: The same cut-off for a crib: a survivor that reads worse than this is a
#: coincidence of the menu test, not a key.
HOPELESS_CRIB = -6.3

#: A crib finding that reads this well is the key; the remaining rotor orders
#: do not have to be tried.
GOOD_CRIB = -5.2

#: Below this many letters the language model cannot tell a right key from a
#: wrong one.
MIN_LETTERS = 24

Progress = Callable[[float, str], None]
Stop = Callable[[], bool]


def has_numpy() -> bool:
    """Return ``True`` when the fast array code of the attacks is available."""
    try:  # pragma: no cover - depends on the environment
        import numpy  # noqa: F401
    except Exception:
        return False
    return True


def _require_numpy() -> Any:
    try:
        import numpy as np
    except Exception as exc:  # pragma: no cover - depends on the environment
        raise RuntimeError(
            "This attack needs numpy. Install it with: python -m pip install numpy"
        ) from exc
    return np


# ------------------------------------------------------------------ results
@dataclass
class Candidate:
    """A key that came out of a search, with the score it earned."""

    key: Key
    score: float = 0.0
    """Language score of the message read with this key (higher is better)."""

    note: str = ""
    """Where the candidate came from, e.g. ``"菜单攻击"``."""

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key.to_dict(),
            "score": round(self.score, 4),
            "note": self.note,
            "describe": self.key.describe(),
        }


@dataclass
class AutoResult:
    """What came out of an automatic recovery."""

    key: Key | None = None
    """The key that reads the message best, if one was found."""

    letters: str = ""
    """The plaintext letters, without word boundaries."""

    text: str = ""
    """The plaintext with word boundaries and punctuation."""

    score: float = 0.0
    """Language score of :attr:`letters` (English sits near -4, noise near -7)."""

    method: str = ""
    """``"key"``, ``"crib"`` or ``"ciphertext"``."""

    confident: bool = False
    """``True`` when the result is clearly better than the alternatives."""

    note: str = ""
    """A sentence for the interface, explaining what happened."""

    elapsed: float = 0.0
    candidates: list[Candidate] = field(default_factory=list)
    tried: int = 0
    """How many keys the search looked at."""

    cancelled: bool = False
    """``True`` when the caller stopped the search before it finished."""

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key.to_dict() if self.key else None,
            "letters": self.letters,
            "text": self.text,
            "score": round(self.score, 4),
            "method": self.method,
            "confident": self.confident,
            "note": self.note,
            "elapsed": round(self.elapsed, 3),
            "tried": self.tried,
            "cancelled": self.cancelled,
            "candidates": [item.to_dict() for item in self.candidates],
            "describe": self.key.describe() if self.key else "",
        }


# --------------------------------------------------------------- known key
def decipher_with_key(
    ciphertext: str,
    key: Key,
    solve: bool = False,
    with_spaces: bool = True,
    with_punctuation: bool = True,
    progress: Progress | None = None,
) -> AutoResult:
    """Read *ciphertext* with a known key.

    With *solve* the plugboard of the key is treated as a starting point and
    searched properly - that is what an operator does when the cable list is
    missing from the sheet but the wheels are known.
    """
    started = time.perf_counter()
    machine = key.machine()
    if solve:
        result = solve_plugboard(
            ciphertext,
            machine,
            positions=key.positions,
            with_spaces=with_spaces,
            with_punctuation=with_punctuation,
            progress=lambda round_index, score: progress and progress(
                0.1 + 0.8 * min(1.0, round_index / 12), "正在搜索接线板…"
            ),
        )
    else:
        result = decode(
            ciphertext,
            machine,
            positions=key.positions,
            with_spaces=with_spaces,
            with_punctuation=with_punctuation,
        )

    found = key.with_(plugboard=result.plugboard_description)
    return AutoResult(
        key=found,
        letters=result.letters,
        text=result.text,
        score=result.score,
        method="key",
        confident=result.confident,
        note="" if result.confident else "密文较短或接线板无法确定，结果仅供参考。",
        elapsed=time.perf_counter() - started,
        candidates=[Candidate(found, result.score, "已知密钥")],
        tried=1,
    )


def crib_letters(crib: str) -> str:
    """Turn a crib into the letters the machine actually saw.

    Operators wrote the separators as letters too, so a crib typed with real
    spaces is read with ``X`` where a space stood - the caller tries the ``Q``
    reading as well, because the two were used interchangeably.
    """
    spaced = "".join("X" if character.isspace() else character for character in crib.upper())
    return EnglishModel.letters(spaced)


# ------------------------------------------------------------ crib attack
def break_with_crib(
    ciphertext: str,
    crib: str,
    offset: int | None = None,
    rotors: Sequence[str] = SCAN_ROTORS,
    reflectors: Sequence[str] = SCAN_REFLECTORS,
    rings: str = "AAA",
    max_candidates: int = 3,
    deadline: float = 60.0,
    progress: Progress | None = None,
    should_stop: Stop | None = None,
) -> AutoResult:
    """Recover the key of *ciphertext* from a plaintext guess.

    The menu attack of :mod:`enigma.crack` narrows the rotor settings down to
    a handful of survivors; every survivor is then completed with a plugboard
    search and rated on the whole message.  The best of them is the answer.
    """
    from .crack import menu_attack, quick_score

    started = time.perf_counter()
    model = DEFAULT_MODEL
    guess = crib_letters(crib)
    if len(guess) < 3:
        return AutoResult(
            method="crib",
            note="已知明文片段太短，至少要 3 个字母。",
            elapsed=time.perf_counter() - started,
        )

    # The operator replaced every space with X or Q, and which of the two was
    # used is decided per message.  A crib that contains one of them is
    # therefore tried both ways - the wrong letter would shift every word
    # boundary in the crib and the attack would never connect.
    variants = [guess]
    if "X" in guess or "Q" in guess:
        swapped = guess.translate(str.maketrans("XQ", "QX"))
        if swapped != guess:
            variants.append(swapped)

    best: AutoResult | None = None
    for index, variant in enumerate(variants):
        share = 1.0 / len(variants)
        offset_share = index * share
        if index and best is not None and best.elapsed > deadline * 0.4:
            # The first reading of the crib already used most of the time and
            # found nothing; the other reading is almost certainly wrong too.
            break
        result = _crib_pass(
            ciphertext,
            variant,
            offset=offset,
            rotors=rotors,
            reflectors=reflectors,
            rings=rings,
            max_candidates=max_candidates,
            model=model,
            menu_attack=menu_attack,
            quick_score=quick_score,
            progress=(
                None
                if progress is None
                else (
                    lambda part, text="", _base=offset_share: progress(
                        _base + share * 0.5 * max(0.0, min(1.0, part)), text
                    )
                )
            ),
            refine_progress=(
                None
                if progress is None
                else (
                    lambda part, text, _base=offset_share: progress(
                        _base + share * (0.5 + 0.5 * part), text
                    )
                )
            ),
            should_stop=should_stop,
            deadline=deadline,
        )
        if best is None:
            best = result
        elif result.key is not None and (
            best.key is None or result.score > best.score
        ):
            best = result
        if best.key is not None and best.confident:
            break

    assert best is not None
    best.elapsed = time.perf_counter() - started
    if best.key is None and not best.note:
        best.note = (
            "没有任何转子设置能解释这段 crib。检查拼写（空格在报文里写作 "
            "X 或 Q）、位置，或放宽转子与反射器的搜索范围。"
        )
    return best


def _menu_search(
    ciphertext: str,
    guess: str,
    offset: int | None,
    rotors: Sequence[str],
    reflectors: Sequence[str],
    rings: str,
    model: EnglishModel,
    menu_attack,
    quick_score,
    progress: Progress | None,
    should_stop: Stop | None,
    deadline: float = 60.0,
) -> tuple[list, bool]:
    """Run the menu attack one rotor order at a time.

    Trying the rotor orders one after another instead of all at once buys two
    things: the search can stop as soon as a setting reads like language,
    which is the normal case because the most common wheel order is tried
    first, and it can be interrupted in between.
    """
    orders = _orders(rotors)
    total = max(1, len(orders))
    found: list = []
    short = len(EnglishModel.letters(ciphertext)) < 60
    started = time.perf_counter()
    timed_out = False

    for index, order in enumerate(orders):
        if should_stop is not None and should_stop():
            break
        if time.perf_counter() - started > deadline:
            timed_out = not found
            break
        if progress is not None:
            progress(
                index / total,
                f"菜单检验 {'-'.join(order)}（{index + 1}/{total}）",
            )
        part = menu_attack(
            ciphertext,
            guess,
            offsets=None if offset is None else [offset],
            orders=[order],
            reflectors=tuple(reflectors),
            ring_settings=(rings[0], rings[1], rings[2]),
            model=model,
            budget=0.3 if short else 0.9,
            cap_per_position=True,
        )
        if part:
            found.extend(part)
            best = max(quick_score(item, ciphertext, model) for item in part)
            if best > GOOD_CRIB:
                break

    if progress is not None:
        progress(1.0, "菜单检验完成")
    return found, timed_out


def _crib_pass(
    ciphertext: str,
    guess: str,
    offset: int | None,
    rotors: Sequence[str],
    reflectors: Sequence[str],
    rings: str,
    max_candidates: int,
    model: EnglishModel,
    menu_attack,
    quick_score,
    progress: Progress | None,
    refine_progress: Callable[[float, str], None] | None,
    should_stop: Stop | None,
    deadline: float = 60.0,
) -> AutoResult:
    """Run the menu attack and the plugboard search once, for one crib."""
    started = time.perf_counter()
    findings, timed_out = _menu_search(
        ciphertext,
        guess,
        offset=offset,
        rotors=rotors,
        reflectors=reflectors,
        rings=rings,
        model=model,
        menu_attack=menu_attack,
        quick_score=quick_score,
        progress=progress,
        should_stop=should_stop,
        deadline=deadline,
    )

    def key_of(finding) -> Key:
        return Key(
            rotors=finding.rotor_order,
            reflector=finding.reflector,
            rings="".join(finding.ring_settings),
            positions=finding.positions,
            plugboard=" ".join(f"{a}{b}" for a, b in finding.plugboard_pairs),
        )

    if not findings:
        return AutoResult(
            method="crib",
            note=(
                "搜索超时：在这一范围内没有找到能解释 crib 的转子设置。"
                "可以缩小转子范围，或核对 crib 的拼写与位置。"
                if timed_out
                else ""
            ),
            elapsed=time.perf_counter() - started,
        )

    ranked = sorted(
        findings,
        key=lambda item: (-quick_score(item, ciphertext, model), -item.crib_hits),
    )
    candidates = [Candidate(key_of(item), float(item.crib_hits), "菜单攻击")
                  for item in ranked[:8]]

    # A crib that does not fit produces survivors that decipher the message
    # into noise.  Completing their plugboard would cost many seconds for
    # nothing, so the search only goes on when the best survivor already
    # reads like language.
    if quick_score(ranked[0], ciphertext, model) < HOPELESS_CRIB:
        return AutoResult(
            method="crib",
            note="",
            elapsed=time.perf_counter() - started,
            candidates=candidates,
        )

    if should_stop is not None and should_stop():
        return AutoResult(method="crib", note="已取消。", cancelled=True,
                          elapsed=time.perf_counter() - started)

    best: AutoResult | None = None
    best_hits = 0
    tried = 0
    for number, finding in enumerate(ranked[:max_candidates], start=1):
        if should_stop is not None and should_stop():
            break
        tried += 1
        key = key_of(finding)
        if refine_progress is not None:
            refine_progress(
                (number - 1) / max(1, max_candidates),
                f"补齐接线板 {number}/{min(max_candidates, len(ranked))}："
                f"{'-'.join(finding.rotor_order)} · {finding.positions}",
            )

        seed_pairs = tuple(
            (ALPHABET.index(first), ALPHABET.index(second))
            for first, second in finding.plugboard_pairs
        )
        try:
            result = solve_plugboard(
                ciphertext,
                key.machine(),
                positions=key.positions,
                model=model,
                sample=min(500, max(120, len(EnglishModel.letters(ciphertext)))),
                beam=6,
                max_rounds=10,
                seeds=(seed_pairs,) if seed_pairs else (),
            )
        except ValueError:
            continue

        # The plugboard search refuses to trust itself on a short message and
        # falls back to the board it was given.  For a crib attack that board
        # is the set of cables the menu attack pinned down, which is a far
        # better guess than nothing - so it is read directly and kept when it
        # beats the search.
        seeded = decode(
            ciphertext,
            key.machine(),
            positions=key.positions,
            model=model,
        )
        if seeded.score > result.score:
            result = seeded

        found = key.with_(plugboard=result.plugboard_description)
        candidates.append(Candidate(found, result.score, "菜单攻击 + 接线板搜索"))
        if best is None or result.score > best.score:
            best_hits = finding.crib_hits
            best = AutoResult(
                key=found,
                letters=result.letters,
                text=result.text,
                score=result.score,
                method="crib",
                confident=result.confident,
                elapsed=time.perf_counter() - started,
                candidates=candidates,
                tried=tried,
            )
        if best is not None and best.score > -4.2:
            break  # this reads like language; nothing better is coming

    if best is None:
        return AutoResult(
            method="crib",
            note="找到了能通过菜单检验的设置，但没能补出可读的接线板。",
            elapsed=time.perf_counter() - started,
            candidates=candidates,
            tried=tried,
        )

    best.candidates = candidates
    readable = best.score > -5.0
    # Every survivor explains the crib; only the message itself can tell the
    # real key from a coincidence.  A key that reads the whole message *and*
    # accounts for the crib is right, short message or not.
    explained = best_hits >= max(4, int(round(0.8 * len(guess))))
    best.confident = bool(readable and explained)
    if best.confident:
        best.note = "整副密钥已还原：转子、反射器、起始位置与接线板。"
    elif readable:
        best.note = "找到一组读得通的密钥，但证据还不够硬；建议核对 crib 是否准确。"
    else:
        best.note = "找到的密钥解不出可读的全文，crib 可能不在这个位置或拼写不符。"
    best.elapsed = time.perf_counter() - started
    return best


# ------------------------------------------------- ciphertext only attack
@dataclass
class _Hit:
    order: tuple[str, str, str]
    reflector: str
    positions: str
    score: float


_NEXT_CACHE: dict[tuple[str, str, str], Any] = {}


def _next_states(order: tuple[str, str, str]):
    """Return the step table of a rotor order: state index -> next state index.

    A state is the window position written as one number, ``L*676 + M*26 + R``.
    The stepping rules of the machine - including the double step - do not
    depend on where the rotors start, so the table is built once per rotor
    order and then used for all 26**3 start positions at once.
    """
    np = _require_numpy()
    cached = _NEXT_CACHE.get(order)
    if cached is not None:
        return cached

    indices = np.arange(26 * 26 * 26, dtype=np.int32)
    left = indices // 676
    middle = (indices // 26) % 26
    right = indices % 26

    notch_middle = np.zeros(26, dtype=bool)
    notch_right = np.zeros(26, dtype=bool)
    for index in ROTORS[order[1]].turnover_indices:
        notch_middle[index] = True
    for index in ROTORS[order[2]].turnover_indices:
        notch_right[index] = True

    middle_at_notch = notch_middle[middle]
    right_at_notch = notch_right[right]
    following = (
        (left + middle_at_notch) % 26 * 676
        + (middle + (right_at_notch | middle_at_notch)) % 26 * 26
        + (right + 1) % 26
    ).astype(np.int32)
    _NEXT_CACHE[order] = following
    return following


_OFFSET_CACHE: dict[tuple[tuple[str, str, str], str], Any] = {}


def _offset_table(order: tuple[str, str, str], rings: str):
    """Return a table that turns a window position into a core table row.

    The core table of :func:`enigma.crack._core_table` is indexed by the
    wiring *offsets* (position minus ring), so every start position has to be
    translated once.  The translation does not depend on the message, only on
    the rotor order and the ring settings.
    """
    np = _require_numpy()
    cached = _OFFSET_CACHE.get((order, rings))
    if cached is not None:
        return cached

    indices = np.arange(26 * 26 * 26, dtype=np.int32)
    ring_left, ring_middle, ring_right = (ALPHABET.index(letter) for letter in rings)
    left = (indices // 676 - ring_left) % 26
    middle = ((indices // 26) % 26 - ring_middle) % 26
    right = (indices % 26 - ring_right) % 26
    table = (left * 26 + middle) * 26 + right
    _OFFSET_CACHE[(order, rings)] = table
    return table


def _scan_order(
    order: tuple[str, str, str],
    reflector: str,
    rings: str,
    cipher,
    quadgrams,
    keep: int,
) -> list[tuple[int, float]]:
    """Rate all 26**3 start positions of one rotor order and reflector.

    The message is read one letter at a time, for every start position at
    once: the rotors step (one lookup in :func:`_next_states`), the core
    permutation of the new position is applied, and the quadgram score is
    accumulated.  Nothing of size ``positions x letters`` is ever built, so
    the whole sweep stays in cache and runs in milliseconds.
    """
    from .crack import _core_table

    np = _require_numpy()
    size = 26 * 26 * 26
    core = _core_table(order, reflector).reshape(size, 26)
    offsets = _offset_table(order, rings)
    # Fold the ring setting into the table once, so the inner loop only has
    # to look up the window position.
    core_by_position = core[offsets]
    following = _next_states(order)

    current = np.arange(size, dtype=np.int32)
    total = np.zeros(size, dtype=np.float32)
    base = None
    for index, letter in enumerate(cipher):
        current = following[current]
        plain = core_by_position[current, int(letter)].astype(np.int32)
        if index >= 3:
            total += quadgrams[base * 26 + plain]  # type: ignore[operator]
        base = plain if base is None else (base % 676) * 26 + plain

    width = max(1, len(cipher) - 3)
    total /= float(width)
    keep = max(1, min(keep, size))
    best = np.argpartition(-total, keep - 1)[:keep]
    return [(int(index), float(total[index])) for index in best]


_QUAD_CACHE: dict[int, Any] = {}


def _quadgram_table(model: EnglishModel):
    """Return the quadgram log probabilities as a flat ``26**4`` array."""
    np = _require_numpy()
    cached = _QUAD_CACHE.get(id(model))
    if cached is not None:
        return cached

    table = np.full(26**4, model.quadgram_floor, dtype=np.float32)
    for gram, value in model.quadgram_table.items():
        if len(gram) != 4:
            continue
        index = 0
        for char in gram.upper():
            position = ord(char) - 65
            if not 0 <= position < 26:
                index = -1
                break
            index = index * 26 + position
        if index >= 0:
            table[index] = value
    _QUAD_CACHE[id(model)] = table
    return table


def _positions_of(index: int) -> str:
    """Return the window letters of a core-table row index."""
    return (
        ALPHABET[index // 676] + ALPHABET[(index // 26) % 26] + ALPHABET[index % 26]
    )


def scan_positions(
    ciphertext: str,
    rotors: Sequence[str] = SCAN_ROTORS,
    reflectors: Sequence[str] = SCAN_REFLECTORS,
    rings: str = "AAA",
    sample: int = SAMPLE,
    keep: int = KEEP_PER_ORDER,
    model: EnglishModel | None = None,
    progress: Progress | None = None,
    should_stop: Stop | None = None,
) -> list[_Hit]:
    """Rate every rotor order, reflector and starting position.

    The message is read as if the plugboard were empty; the quadgram model
    then says which positions produce something that looks like language.
    Almost nothing does, so the survivors are a short list even though more
    than a million keys were tried.
    """
    from .crack import _core_table  # noqa: F401 - keeps the numpy check close

    np = _require_numpy()
    model = model or DEFAULT_MODEL
    letters = EnglishModel.letters(ciphertext)[:sample]
    if len(letters) < MIN_LETTERS:
        return []

    cipher = np.frombuffer(letters.encode("ascii"), dtype=np.uint8) - 65
    quadgrams = _quadgram_table(model)
    orders = _orders(rotors)
    reflectors = tuple(reflectors) or SCAN_REFLECTORS
    total = max(1, len(orders) * len(reflectors))

    hits: list[_Hit] = []
    done = 0
    for order in orders:
        for reflector in reflectors:
            if should_stop is not None and should_stop():
                hits.sort(key=lambda hit: hit.score, reverse=True)
                return hits
            for index, score in _scan_order(
                order, reflector, rings, cipher, quadgrams, keep
            ):
                hits.append(_Hit(order, reflector, _positions_of(index), score))
            done += 1
            if progress is not None:
                progress(
                    done / total,
                    f"扫描 {'-'.join(order)} · UKW {reflector}",
                )

    hits.sort(key=lambda hit: hit.score, reverse=True)
    return hits


def _orders(rotors: Sequence[str]) -> list[tuple[str, str, str]]:
    """Return every ordered triple of three rotors out of *rotors*."""
    from itertools import permutations

    names = [name for name in rotors if name in ROTORS]
    seen: set[tuple[str, str, str]] = set()
    result: list[tuple[str, str, str]] = []
    for triple in permutations(names, 3):
        if triple not in seen:
            seen.add(triple)
            result.append(triple)
    return result


def break_ciphertext(
    ciphertext: str,
    rotors: Sequence[str] = SCAN_ROTORS,
    reflectors: Sequence[str] = SCAN_REFLECTORS,
    rings: str = "AAA",
    refine: int = REFINE,
    progress: Progress | None = None,
    should_stop: Stop | None = None,
) -> AutoResult:
    """Recover a message from the ciphertext alone."""
    started = time.perf_counter()
    model = DEFAULT_MODEL
    letters = EnglishModel.letters(ciphertext)
    if len(letters) < MIN_LETTERS:
        return AutoResult(
            method="ciphertext",
            note=f"密文太短。只凭密文破译至少需要 {MIN_LETTERS} 个字母。",
            elapsed=time.perf_counter() - started,
        )

    # The reflectors are scanned one after the other and the scan stops as
    # soon as something clearly readable turns up - UKW B was the standard,
    # so the common case never pays for the second pass.
    hits: list[_Hit] = []
    for number, reflector in enumerate(tuple(reflectors) or SCAN_REFLECTORS):
        if number and hits and hits[0].score > GOOD_HIT:
            break
        more = scan_positions(
            ciphertext,
            rotors=rotors,
            reflectors=(reflector,),
            rings=rings,
            model=model,
            progress=lambda share, text: progress and progress(
                0.05 * (number + share) / max(1, len(reflectors)), text
            ),
            should_stop=should_stop,
        )
        hits.extend(more)
        hits.sort(key=lambda hit: hit.score, reverse=True)
        hits = hits[: KEEP_PER_ORDER * 4]
    if not hits:
        return AutoResult(
            method="ciphertext",
            note="扫描没有找到像语言的转子位置。请换一段更长的密文，或提供一段已知明文。",
            elapsed=time.perf_counter() - started,
        )
    if should_stop is not None and should_stop():
        return AutoResult(method="ciphertext", note="已取消。", cancelled=True,
                          elapsed=time.perf_counter() - started)

    # Nothing in the sweep looked like language.  Refining the best of them
    # would only burn seconds on noise, so stop here and say so.
    if hits[0].score < HOPELESS_HIT:
        return AutoResult(
            method="ciphertext",
            note=(
                "仅凭密文没能还原：所有转子位置读出来都是乱码。若这段电文用了完整"
                "接线板（10 根电缆），历史上也必须借助一段已知明文才能破译。"
            ),
            elapsed=time.perf_counter() - started,
            tried=len(hits),
            candidates=[
                Candidate(
                    Key(
                        rotors=hit.order,
                        reflector=hit.reflector,
                        rings=rings,
                        positions=hit.positions,
                    ),
                    hit.score,
                    "仅密文扫描",
                )
                for hit in hits[:3]
            ],
        )

    # The first pass rated the message without a plugboard, so the ranking is
    # only a hint.  The best few positions are refined properly.
    best: AutoResult | None = None
    candidates: list[Candidate] = []
    for number, hit in enumerate(hits[: max(1, refine)], start=1):
        if should_stop is not None and should_stop():
            break
        key = Key(
            rotors=hit.order,
            reflector=hit.reflector,
            rings=rings,
            positions=hit.positions,
        )
        if progress is not None:
            progress(
                0.05 + 0.9 * (number - 1) / max(1, refine),
                f"检验候选 {number}/{min(refine, len(hits))}："
                f"{'-'.join(hit.order)} · {hit.positions}",
            )
        try:
            result = solve_plugboard(
                ciphertext,
                key.machine(),
                positions=key.positions,
                model=model,
                sample=min(400, max(120, len(letters))),
                beam=6,
                max_rounds=10,
            )
        except ValueError:
            continue

        found = key.with_(plugboard=result.plugboard_description)
        candidates.append(Candidate(found, result.score, "仅密文扫描"))
        if best is None or result.score > best.score:
            best = AutoResult(
                key=found,
                letters=result.letters,
                text=result.text,
                score=result.score,
                method="ciphertext",
                confident=result.confident,
                elapsed=time.perf_counter() - started,
                candidates=candidates,
                tried=len(hits),
            )

    if best is None:
        return AutoResult(
            method="ciphertext",
            note="扫描到一些可能的位置，但都无法解出可读的文本。",
            elapsed=time.perf_counter() - started,
        )

    # A result is only worth announcing when it is clearly ahead of the
    # runner up and reads like language on its own.  The first pass is the
    # strongest evidence - it compares more than a million keys - so a wide
    # gap there counts even when the plugboard search had nothing to add.
    candidates.sort(key=lambda item: item.score, reverse=True)
    best.candidates = candidates
    runner_up = candidates[1].score if len(candidates) > 1 else float("-inf")
    scan_margin = hits[0].score - hits[1].score if len(hits) > 1 else 9.0
    readable = best.score > -5.8
    strong_scan = scan_margin > 0.6 and hits[0].score > -6.0
    best.confident = bool(readable and (best.score - runner_up > 0.12 or strong_scan))
    if best.confident:
        best.note = "只凭密文还原出了密钥与明文。"
    elif readable:
        best.note = "找到一个读得通的候选，但证据不足以确认；建议提供一段已知明文复核。"
    else:
        best.note = (
            "仅凭密文没能还原。若这段电文用了完整接线板（10 根电缆），"
            "历史上也必须借助已知明文才能破译 —— 请提供一段原文片段。"
        )
    best.elapsed = time.perf_counter() - started
    return best


# ------------------------------------------------------------- the one call
def auto_decrypt(
    ciphertext: str,
    crib: str | None = None,
    offset: int | None = None,
    rotors: Sequence[str] = SCAN_ROTORS,
    reflectors: Sequence[str] = SCAN_REFLECTORS,
    rings: str = "AAA",
    progress: Progress | None = None,
    should_stop: Stop | None = None,
) -> AutoResult:
    """Recover *ciphertext* by whichever route is available.

    A crib, when one is given, is by far the strongest lever - it opens a
    fully plugged message.  Without one the rotor sweep is tried, which
    covers messages sent with a light plugboard.
    """
    if crib and crib_letters(crib):
        return break_with_crib(
            ciphertext,
            crib,
            offset=offset,
            rotors=rotors,
            reflectors=reflectors,
            rings=rings,
            progress=progress,
            should_stop=should_stop,
        )
    return break_ciphertext(
        ciphertext,
        rotors=rotors,
        reflectors=reflectors,
        rings=rings,
        progress=progress,
        should_stop=should_stop,
    )
