"""Skipped on installations without the optional local checkpoint."""

import importlib.util

import pytest

from word_difficulty.classifier import ContextClassifier, context_pair
from word_difficulty.models import LEVELS, Occurrence
from word_difficulty.paths import data_dir

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not (data_dir() / "model" / "model.safetensors").exists()
        or importlib.util.find_spec("transformers") is None
        or importlib.util.find_spec("torch") is None,
        reason="Local model and optional dependencies are not installed",
    ),
]


@pytest.fixture(scope="module")
def classifier():
    return ContextClassifier(data_dir() / "model")


def test_real_model_offline_inference_and_label_mapping(classifier):
    sentence = "Their investigation revealed an astonishing discrepancy."
    target = "discrepancy"
    start = sentence.index(target)
    occurrence = Occurrence(target, target, "NOUN", sentence, start, start + len(target), "1")
    result = classifier.predict([occurrence])[0]
    assert result.source == "model"
    assert result.level in LEVELS
    assert set(result.probabilities) == set(LEVELS)
    assert sum(result.probabilities.values()) == pytest.approx(1, abs=1e-5)
    assert result.confidence == max(result.probabilities.values())


def test_real_tokenizer_keeps_target_and_pair_within_limit(classifier):
    sentence = "ordinary " * 600 + "the hypothesis was confirmed."
    target = "hypothesis"
    start = sentence.index(target)
    occurrence = Occurrence(target, target, "NOUN", sentence, start, start + len(target), "1")
    context, word = context_pair(classifier.tokenizer, occurrence)
    assert target in context
    assert word == target
    encoded = classifier.tokenizer(context, word)
    assert len(encoded["input_ids"]) <= 256
    assert classifier.predict([occurrence])[0].level in LEVELS
