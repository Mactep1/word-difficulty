import csv
import hashlib
import io
from pathlib import Path

from .models import LEVELS

LEXICON_REPO = "w3nabil/english-cefr-wordlist"
LEXICON_REVISION = "e25277c3caf04b938de7b99f191ec86ed92abbcc"
LEXICON_URL = f"https://huggingface.co/datasets/{LEXICON_REPO}/resolve/{LEXICON_REVISION}/words.csv"

POS_MAP = {
    "n": "NOUN",
    "noun": "NOUN",
    "v": "VERB",
    "verb": "VERB",
    "aux": "VERB",
    "adj": "ADJ",
    "adjective": "ADJ",
    "adv": "ADV",
    "adverb": "ADV",
    "prep": "ADP",
    "preposition": "ADP",
    "pron": "PRON",
    "pronoun": "PRON",
    "det": "DET",
    "determiner": "DET",
    "conj": "CONJ",
    "conjunction": "CONJ",
    "interj": "INTJ",
    "interjection": "INTJ",
    "number": "NUM",
    "numeral": "NUM",
    "modal verb": "VERB",
    "auxiliary verb": "VERB",
    "exclamation": "INTJ",
    "modal auxiliary": "VERB",
    "be-verb": "VERB",
    "do-verb": "VERB",
    "have-verb": "VERB",
    "infinitive-to": "PART",
}


def normalize_pos(raw: str) -> str:
    raw = raw.strip().casefold().rstrip(".")
    if raw in POS_MAP:
        return POS_MAP[raw]
    upper = raw.upper()
    if upper in {"NOUN", "VERB", "ADJ", "ADV", "ADP", "PRON", "DET", "NUM", "INTJ", "PART"}:
        return upper
    return "UNKNOWN"


class Lexicon:
    def __init__(self, path: Path):
        if not path.is_file():
            raise ValueError("缺少 CEFR 词表，请先运行：word-difficulty setup")
        content = path.read_bytes()
        self.fingerprint = hashlib.sha256(content).hexdigest()
        self.index: dict[tuple[str, str], set[str]] = {}
        self.by_word: dict[str, set[str]] = {}
        rows = csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
        fields = set(rows.fieldnames or [])
        if not {"word", "type"} <= fields or not ({"CEFR", "level"} & fields):
            raise ValueError("词表需要 word、type、CEFR（或 level）列。")
        self.row_count = 0
        for row in rows:
            word = row["word"].strip().casefold()
            level = (row.get("CEFR") or row.get("level") or "").strip().upper()
            if level not in LEVELS or not word:
                continue
            self.row_count += 1
            pos = normalize_pos(row["type"])
            self.index.setdefault((word, pos), set()).add(level)
            self.by_word.setdefault(word, set()).add(level)
        if not self.row_count:
            raise ValueError("词表没有有效的 CEFR 词条。")

    def lookup(self, lemma: str, pos: str) -> set[str]:
        pos = "CONJ" if pos in ("CCONJ", "SCONJ") else pos
        exact = self.index.get((lemma.casefold(), pos))
        if exact:
            return exact.copy()
        # Unknown POS entries cannot silently override a known conflicting POS.
        if pos in ("", "X", "UNKNOWN"):
            return self.by_word.get(lemma.casefold(), set()).copy()
        return set()
