"""Build the embedded English language model used by :mod:`enigma.english`.

The decoder needs a statistical model of English in order to

* score a candidate decryption (for the plugboard hill climb), and
* put the word boundaries back into a letter-only decryption.

Both need real English statistics, so they are derived here from public
domain sources and frozen into :mod:`enigma.english_data`:

* **Corpus** - a handful of Project Gutenberg books (English, public domain).
  Used for letter frequencies, space aware bigrams and word internal
  quadgrams.
* **Vocabulary** - the ``hermitdave/FrequencyWords`` list of the 50 000 most
  common English words with their frequencies.  Used for the dictionary that
  drives the word segmentation.

Running the script regenerates ``enigma/english_data.py``::

    python tools/build_english_model.py

The generated file is checked in, so an end user never has to run this.
"""

from __future__ import annotations

import http.client
import re
import sys
import time
import urllib.request
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "enigma" / "english_data.py"
CACHE = Path(__file__).resolve().parent / ".cache"

#: Project Gutenberg ids of public domain English books.
BOOKS = [
    (11, "Alice's Adventures in Wonderland"),
    (16, "Peter Pan"),
    (43, "Dr. Jekyll and Mr. Hyde"),
    (74, "The Adventures of Tom Sawyer"),
    (84, "Frankenstein"),
    (98, "A Tale of Two Cities"),
    (345, "Dracula"),
    (1342, "Pride and Prejudice"),
    (1400, "Great Expectations"),
    (1661, "The Adventures of Sherlock Holmes"),
    (2701, "Moby Dick"),
    (2814, "Dubliners"),
    (2600, "War and Peace"),
]

GUTENBERG_URL = "https://www.gutenberg.org/files/{id}/{id}-0.txt"
GUTENBERG_URL_ALT = "https://www.gutenberg.org/ebooks/{id}.txt.utf-8"
GUTENBERG_URL_ALT2 = "https://www.gutenberg.org/cache/epub/{id}/pg{id}.txt"

WORDLIST_URL = (
    "https://raw.githubusercontent.com/hermitdave/FrequencyWords/"
    "master/content/2018/en/en_50k.txt"
)

#: How many words of the frequency list are kept for the dictionary.  The
#: common words are not enough: "nineteen" or "foxes" have to be in there as
#: well, or the segmenter cuts them apart.
VOCABULARY_SIZE = 20000

#: How many quadgrams are kept.  The whole table is small enough to keep,
#: and every quadgram that really occurs must be there - a missing one would
#: be scored like a mistake.
QUADGRAM_LIMIT = 200000

SPACE = " "


def _download(url: str, attempts: int = 5) -> str:
    """Fetch *url* and return its text.

    Gutenberg regularly drops long connections half way through a book.  The
    bytes that did arrive are still usable, so an interrupted transfer is
    accepted instead of being thrown away.
    """
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            request = urllib.request.Request(
                url, headers={"User-Agent": "enigma-model-builder"}
            )
            with urllib.request.urlopen(request, timeout=120) as response:
                return response.read().decode("utf-8", errors="replace")
        except http.client.IncompleteRead as error:
            partial = getattr(error, "partial", b"") or b""
            if len(partial) > 20_000:
                print(f"    (partial transfer, {len(partial)} bytes)")
                return partial.decode("utf-8", errors="replace")
            last_error = error
        except Exception as error:  # pragma: no cover - network dependent
            last_error = error
        time.sleep(2 + 3 * attempt)
    raise RuntimeError(f"could not download {url}: {last_error}")


def _strip_boilerplate(text: str) -> str:
    """Cut the Gutenberg header and footer off a book."""
    index = text.find("*** START OF")
    if index != -1:
        line_end = text.find("\n", index)
        if line_end == -1:
            line_end = index
        end = text.find("***", line_end)
        if end != -1:
            text = text[index:end]
    end = text.find("*** END OF")
    if end != -1:
        text = text[:end]
    return text


def fetch_book(book_id: int) -> str:
    """Return the plain text of one Gutenberg book, without the boilerplate.

    Every book is cached on its own, so a rebuild does not download anything
    twice.
    """
    CACHE.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE / f"book_{book_id}.txt"
    if cache_file.exists():
        return cache_file.read_text(encoding="utf-8")

    text = ""
    for url in (
        GUTENBERG_URL.format(id=book_id),
        GUTENBERG_URL_ALT.format(id=book_id),
        GUTENBERG_URL_ALT2.format(id=book_id),
    ):
        try:
            text = _download(url)
            break
        except Exception as error:  # pragma: no cover - network dependent
            print(f"  ! {book_id}: {url} failed ({error})", file=sys.stderr)
    if not text:
        return ""

    text = _strip_boilerplate(text)
    cache_file.write_text(text, encoding="utf-8")
    return text


def fetch_wordlist() -> list[tuple[str, int]]:
    """Return ``(word, count)`` pairs of the English frequency list."""
    CACHE.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE / "words.txt"
    if cache_file.exists():
        raw = cache_file.read_text(encoding="utf-8")
    else:
        raw = _download(WORDLIST_URL)
        cache_file.write_text(raw, encoding="utf-8")

    pairs: list[tuple[str, int]] = []
    for line in raw.splitlines():
        parts = line.split()
        if len(parts) != 2:
            continue
        word, count = parts[0].lower(), parts[1]
        if not word.isalpha() or not 1 <= len(word) <= 25:
            continue
        # Only "a" and "i" are one letter words in English.  The frequency
        # list also holds the single letters of the alphabet itself, and
        # those would be a magnet for the segmenter.
        if len(word) == 1 and word not in ("a", "i"):
            continue
        try:
            pairs.append((word, int(count)))
        except ValueError:
            continue
    return pairs


def build_corpus() -> str:
    """Return the concatenated, upper cased text of every book."""
    chunks: list[str] = []
    for book_id, title in BOOKS:
        print(f"  - {title}", flush=True)
        text = fetch_book(book_id)
        if text:
            chunks.append(text)
        else:
            print(f"  ! {title} could not be fetched", file=sys.stderr)

    corpus = "\n".join(chunks)
    # Keep letters and whitespace only; everything else is noise.
    corpus = re.sub(r"[^A-Za-z\s]+", " ", corpus)
    corpus = re.sub(r"[ \t]+", " ", corpus).upper()
    print(f"  - the corpus holds {len(corpus):,} characters", flush=True)
    return corpus


def statistics(corpus: str) -> tuple[Counter, Counter, Counter]:
    """Return letter frequencies, space aware bigrams and stream quadgrams.

    The quadgrams are counted over the *letter stream* - the whole corpus
    with the spaces removed.  That is the view a decryption has: one long
    string of letters without any word boundaries, so the table has to cover
    the combinations that straddle two words as well.

    The stream is counted three times: as it is, with every space replaced
    by ``X`` and with every space replaced by ``Q``.  Those are the forms a
    message takes on its way through the machine, and a model that only
    knows plain English would consider the space markers rare - which would
    make it prefer a *wrong* decryption.
    """
    letters: Counter = Counter()
    bigrams: Counter = Counter()
    quadgrams: Counter = Counter()

    words = re.findall(r"[A-Z]+", corpus)
    for word in words:
        letters.update(word)
        for index in range(len(word) - 1):
            bigrams[word[index : index + 2]] += 1
            bigrams[word[index : index + 2] + SPACE] += 1
            bigrams[SPACE + word[index : index + 1]] += 1
            bigrams[word[index : index + 1] + SPACE] += 1

    for stream in ("".join(words), "X".join(words), "Q".join(words)):
        for index in range(len(stream) - 3):
            quadgrams[stream[index : index + 4]] += 1

    return letters, bigrams, quadgrams


def format_counter(counter: Counter, limit: int | None = None) -> str:
    """Format a counter as a Python dict literal, most frequent first."""
    items = counter.most_common(limit)
    lines = []
    for key, value in items:
        lines.append(f'    "{key}": {value},')
    return "\n".join(lines)


def format_words(words: list[tuple[str, int]]) -> tuple[str, str]:
    """Format the vocabulary as two parallel strings (words and counts)."""
    words_text = " ".join(word for word, _ in words)
    counts_text = " ".join(str(count) for _, count in words)
    return words_text, counts_text


def main() -> int:
    print("Building the English model ...")
    corpus = build_corpus()
    if len(corpus) < 1_000_000:
        print("  ! the corpus is suspiciously small", file=sys.stderr)

    letters, bigrams, quadgrams = statistics(corpus)

    print("  - fetching the vocabulary")
    wordlist = fetch_wordlist()[:VOCABULARY_SIZE]
    words_text, counts_text = format_words(wordlist)

    total = sum(letters.values())
    letter_freq = [round(letters.get(chr(65 + i), 0) / total, 8) for i in range(26)]

    header = f'''"""English language statistics used by :mod:`enigma.english`.

Generated by ``tools/build_english_model.py`` - do not edit by hand.

Sources
-------
* Text: Project Gutenberg, {len(BOOKS)} public domain English books
  (Alice's Adventures in Wonderland, Peter Pan, Dr. Jekyll and Mr. Hyde,
  The Adventures of Tom Sawyer, Frankenstein, A Tale of Two Cities, Dracula,
  Pride and Prejudice, Great Expectations, The Adventures of Sherlock Holmes,
  Moby Dick, Dubliners, War and Peace).
* Vocabulary: ``hermitdave/FrequencyWords`` (OpenSubtitles corpus, English).

``LETTER_FREQ`` holds the relative frequency of the 26 letters,
``BIGRAM_COUNTS`` the counts of the bigrams ("AB" inside a word, "A " and
" A" around a word boundary), ``QUADGRAM_COUNTS`` the counts of the most
common word internal quadgrams, and ``WORDS``/``WORD_COUNTS`` the most
common English words together with their frequencies.
"""

from __future__ import annotations

#: Relative frequency of A .. Z.
LETTER_FREQ: tuple[float, ...] = (
'''

    body = "".join(f"    {value},\n" for value in letter_freq)

    middle = f'''
)

#: The number of bigrams that were counted.
BIGRAM_TOTAL: int = {sum(bigrams.values())}

#: The number of quadgrams that were counted.
QUADGRAM_TOTAL: int = {sum(quadgrams.values())}

#: Counts of the bigrams: "AB" (inside a word), "A " and " A".
BIGRAM_COUNTS: dict[str, int] = {{
{format_counter(bigrams)}
}}

#: Counts of the most common word internal quadgrams.
QUADGRAM_COUNTS: dict[str, int] = {{
{format_counter(quadgrams, QUADGRAM_LIMIT)}
}}

#: The most common English words, most frequent first.
WORDS: str = (
    "{words_text}"
)

#: The frequencies that belong to :data:`WORDS`, in the same order.
WORD_COUNTS: str = (
    "{counts_text}"
)
'''

    OUTPUT.write_text(header + body + middle, encoding="utf-8")
    size = OUTPUT.stat().st_size
    print(f"Wrote {OUTPUT} ({size / 1024:.0f} KiB)")
    print(
        f"  letters={total:,} bigrams={len(bigrams)} "
        f"quadgrams={len(quadgrams)} words={len(wordlist)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
