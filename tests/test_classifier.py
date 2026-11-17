import re

import pytest

from word_difficulty.classifier import context_pair
from word_difficulty.models import Occurrence


class WordTokenizer:
    def __call__(self, text, **kwargs):
        matches = list(re.finditer(r"\S+", text))
        return {
            "input_ids": list(range(len(matches))),
            "offset_mapping": [m.span() for m in matches],
        }

    def num_special_tokens_to_add(self, pair=False):
        return 3


def test_context_window_retains_target_late_in_long_sentence():
    sentence = " ".join(["ordinary"] * 500 + ["extraordinary"] + ["ordinary"] * 10)
    start = sentence.index("extraordinary")
    occurrence = Occurrence(
        "extraordinary", "extraordinary", "ADJ", sentence, start, start + 13, "1"
    )
    context, target = context_pair(WordTokenizer(), occurrence)
    assert target == "extraordinary"
    assert target in context
    assert len(context.split()) < 256


def test_invalid_target_span_is_rejected():
    with pytest.raises(ValueError, match="位置"):
        context_pair(WordTokenizer(), Occurrence("bank", "bank", "NOUN", "a bank", 0, 4, "1"))
