"""Ready made messages, so the machine has something to work on at once.

Every sample is generated from its own plaintext and key when the module is
imported, so the ciphertext always matches the key sheet that is shown next
to it - nothing can drift apart.  The crib of a sample is cut out of the
*prepared* text, which is why it carries ``X`` (or ``Q``) where the original
message had a space; that is exactly the form the attack needs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .keys import Key
from .preparation import prepare_text


@dataclass(frozen=True)
class Sample:
    """One demonstration message."""

    id: str
    title: str
    subtitle: str
    plaintext: str
    key: Key
    ciphertext: str
    crib: str = ""
    crib_offset: int | None = None
    note: str = ""

    @property
    def has_crib(self) -> bool:
        return bool(self.crib)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "subtitle": self.subtitle,
            "plaintext": self.plaintext,
            "key": self.key.to_dict(),
            "ciphertext": self.ciphertext,
            "crib": self.crib,
            "cribOffset": self.crib_offset,
            "note": self.note,
            "letters": len(self.ciphertext),
        }


def _sample(
    id: str,
    title: str,
    subtitle: str,
    plaintext: str,
    key: Key,
    crib_phrase: str = "",
    note: str = "",
) -> Sample:
    """Build a sample: prepare the text, encipher it, cut the crib out."""
    prepared = prepare_text(plaintext).text
    ciphertext = key.machine().encrypt(prepared)

    crib, offset = "", None
    if crib_phrase:
        for separator in ("X", "Q"):
            candidate = crib_phrase.upper().replace(" ", separator)
            where = prepared.find(candidate)
            if where >= 0:
                crib, offset = candidate, where
                break
    return Sample(
        id=id,
        title=title,
        subtitle=subtitle,
        plaintext=plaintext,
        key=key,
        ciphertext=ciphertext,
        crib=crib,
        crib_offset=offset,
        note=note,
    )


SAMPLES: tuple[Sample, ...] = (
    _sample(
        "weather",
        "气象报告 · 西部航道",
        "没有接线板，可以只凭密文破译",
        "WEATHER REPORT FOR THE WESTERN APPROACHES. VISIBILITY GOOD, WIND NORTH "
        "WEST FORCE FOUR, EXPECT NO CHANGE BEFORE DAWN.",
        Key(rotors=("III", "I", "II"), reflector="B", rings="AAA", positions="QWE"),
        crib_phrase="",
        note="这段电文没有插线，是唯一能用『仅凭密文』直接破译的一类。",
    ),
    _sample(
        "africa",
        "北非军团 · 作战命令",
        "十根电缆，需要一段已知明文",
        "PANZER GROUP THREE WILL ATTACK AT FIRST LIGHT. THE SUPPLY COLUMN FROM "
        "TOBRUK IS DELAYED BY TWO DAYS. REPORT FUEL STATE AT ONCE.",
        Key(
            rotors=("II", "IV", "I"),
            reflector="B",
            rings="AAA",
            positions="BMU",
            plugboard="AT BL DF GJ HM NW OP QY RZ VX",
        ),
        crib_phrase="ATTACK AT FIRST LIGHT",
        note="接线板满接，必须借助 crib —— 图灵的 Bombe 也是这么做的。",
    ),
    _sample(
        "uboat",
        "U 艇 · 接敌报告",
        "八根电缆，环设定不是 AAA",
        "CONVOY SIGHTED IN GRID SQUARE AJ NINE FOUR. COURSE SOUTH EAST AT EIGHT "
        "KNOTS. AM ATTACKING AT NIGHT.",
        Key(
            rotors=("V", "II", "III"),
            reflector="B",
            rings="BUL",
            positions="KLM",
            plugboard="AV BS CG DL FU HZ IN KM OW",
        ),
        crib_phrase="CONVOY SIGHTED",
        note="环设定 BUL 需要在上方『环设定』里填对，否则 crib 对不上。",
    ),
    _sample(
        "training",
        "训练报文 · 最经典的一条",
        "教科书里的 ATTACK AT DAWN",
        "ATTACK AT DAWN",
        Key(rotors=("I", "II", "III"), reflector="B", rings="AAA", positions="AAA"),
        crib_phrase="ATTACK AT DAWN",
        note="最短的演示：7 根转子位置全试一遍也只要几秒。",
    ),
)

#: A few key sheets that could have come off a real desk.
PRESETS: tuple[dict[str, str], ...] = (
    {
        "name": "Heer · 1940 标准",
        "detail": "Walzenlage I-II-III · UKW B · 无接线",
        "rotors": "I II III",
        "reflector": "B",
        "rings": "AAA",
        "positions": "AAA",
        "plugboard": "",
    },
    {
        "name": "Heer · 十线满接",
        "detail": "IV-II-V · UKW B · 十根电缆",
        "rotors": "IV II V",
        "reflector": "B",
        "rings": "BUL",
        "positions": "ADU",
        "plugboard": "AV BS CG DL FU HZ IN KM OW RX",
    },
    {
        "name": "Kriegsmarine · 三转子",
        "detail": "V-II-III · UKW B · 八根电缆",
        "rotors": "V II III",
        "reflector": "B",
        "rings": "KLM",
        "positions": "BMU",
        "plugboard": "AV BS CG DL FU HZ IN KM",
    },
    {
        "name": "演示 · 只用反射器 C",
        "detail": "VI-VII-VIII · UKW C · 四根电缆",
        "rotors": "VI VII VIII",
        "reflector": "C",
        "rings": "ZZZ",
        "positions": "XYZ",
        "plugboard": "AB CD EF GH",
    },
)


def get(sample_id: str) -> Sample | None:
    """Return the sample with *sample_id*, or ``None``."""
    for sample in SAMPLES:
        if sample.id == sample_id:
            return sample
    return None


def listing() -> list[dict[str, Any]]:
    """Return a light list of the samples, without the full key and plaintext."""
    return [
        {
            "id": sample.id,
            "title": sample.title,
            "subtitle": sample.subtitle,
            "note": sample.note,
            "letters": len(sample.ciphertext),
            "hasCrib": sample.has_crib,
        }
        for sample in SAMPLES
    ]
