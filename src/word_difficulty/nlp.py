import re
from collections.abc import Iterator

import spacy

from .models import Document, Occurrence, Segment

NLP_MODEL = "en_core_web_sm"
NLP_RULE_VERSION = "2"


class NLPError(RuntimeError):
    pass


class EnglishAnalyzer:
    def __init__(self, model: str = NLP_MODEL):
        try:
            self.nlp = spacy.load(model, disable=["ner"])
        except OSError as exc:
            raise NLPError(
                "缺少英文语言模型。请先执行：python -m spacy download en_core_web_sm"
            ) from exc
        self.version = (
            f"{model}:{self.nlp.meta['version']}:spacy-{spacy.__version__}:rules-{NLP_RULE_VERSION}"
        )

    def occurrences(self, document: Document) -> Iterator[Occurrence]:
        chunks = []
        for segment in document.segments:
            # Bound spaCy memory usage for very long paragraphs without silently truncating them.
            parts = re.findall(r"[\s\S]{1,20000}(?:\s|$)|[\s\S]{1,20000}", segment.text)
            chunks.extend(
                Segment(p, segment.location, segment.raw_text) for p in parts if p.strip()
            )
        texts = (chunk.text for chunk in chunks)
        for doc, chunk in zip(self.nlp.pipe(texts, batch_size=16), chunks, strict=True):
            for sent in doc.sents:
                for token in sent:
                    surface = token.text
                    if not re.fullmatch(r"[A-Za-z]+(?:['’][A-Za-z]+)*", surface):
                        if surface != "n't":
                            continue
                    if token.pos_ == "PART" and surface in ("'s", "’s"):
                        continue
                    lemma = token.lemma_.casefold().replace("’", "'")
                    if surface == "n't":
                        lemma = "not"
                    if lemma == "-pron-":
                        lemma = surface.casefold()
                    if not lemma or not re.search(r"[a-z]", lemma):
                        continue
                    pos = "VERB" if token.pos_ == "AUX" else token.pos_
                    yield Occurrence(
                        lemma,
                        surface,
                        pos,
                        sent.text,
                        token.idx - sent.start_char,
                        token.idx - sent.start_char + len(surface),
                        chunk.location,
                        token.pos_ == "PROPN",
                    )
