from word_difficulty.cache import PredictionCache
from word_difficulty.lexicon import normalize_pos
from word_difficulty.models import Occurrence, Prediction
from word_difficulty.parsers import parse_document
from word_difficulty.pipeline import analyze


def test_inflections_counts_beginner_filter_and_unknowns(analyzer, lexicon):
    document = parse_document(
        "sample.txt",
        b"The children read books. They investigated mechanisms. We investigate the mechanism. A zephyrium glimmered.",
    )
    result = analyze(document, analyzer, lexicon)
    by_word = {entry.lemma: entry for entry in result.entries}
    assert by_word["investigate"].count == 2
    assert set(by_word["investigate"].forms) == {"investigated", "investigate"}
    assert by_word["mechanism"].count == 2
    assert by_word["child"].level == "A1"
    assert by_word["zephyrium"].level is None
    displayed = result.filtered()
    assert "child" not in {entry.lemma for entry in displayed}
    assert "investigate" in {entry.lemma for entry in displayed}
    assert sum(entry.count for entry in result.entries) == result.summary["occurrences"]
    assert by_word["investigate"].examples[0]["location"]


def test_pos_lookup_and_unknown_pos(lexicon):
    assert lexicon.lookup("address", "NOUN") == {"A1"}
    assert lexicon.lookup("address", "VERB") == {"B1"}
    assert lexicon.lookup("address", "UNKNOWN") == {"A1", "B1"}
    assert lexicon.lookup("address", "ADJ") == set()
    assert normalize_pos("be-verb") == "VERB"
    assert normalize_pos("modal auxiliary") == "VERB"


class RecordingClassifier:
    version = "test-model-v1"

    def __init__(self, confidence=0.9):
        self.calls = []
        self.confidence = confidence

    def predict(self, occurrences):
        self.calls.extend(occurrences)
        return [
            Prediction("C1", "model", self.confidence, {"C1": self.confidence}) for _ in occurrences
        ]


def test_model_cache_threshold_and_version_invalidation(analyzer, lexicon, tmp_path):
    document = parse_document("sample.txt", b"We investigate the zephyrium.")
    model = RecordingClassifier(0.55)
    cache = PredictionCache(tmp_path / "cache.sqlite3")
    first = analyze(document, analyzer, lexicon, model, cache, 0.6)
    unknown = next(entry for entry in first.entries if entry.lemma == "zephyrium")
    assert unknown.level is None
    assert unknown.confidence == 0.55
    assert model.calls
    model.calls.clear()
    second = analyze(document, analyzer, lexicon, model, cache, 0.5)
    assert next(entry for entry in second.entries if entry.lemma == "zephyrium").level == "C1"
    assert not model.calls
    assert second.summary["cache_hits"] > 0
    model.version = "test-model-v2"
    analyze(document, analyzer, lexicon, model, cache)
    assert model.calls


def test_target_span_distinguishes_repeated_words():
    a = Occurrence("bank", "bank", "NOUN", "bank bank", 0, 4, "1")
    b = Occurrence("bank", "bank", "NOUN", "bank bank", 5, 9, "1")
    assert PredictionCache.key(a, "v1") != PredictionCache.key(b, "v1")


def test_model_failure_preserves_unknown_and_lexical_results(analyzer, lexicon):
    class FailingClassifier:
        version = "fail"

        def predict(self, occurrences):
            raise RuntimeError("intentional failure")

    document = parse_document("sample.txt", b"We investigate the zephyrium.")
    result = analyze(document, analyzer, lexicon, FailingClassifier())
    assert next(entry for entry in result.entries if entry.lemma == "investigate").level == "B1"
    assert next(entry for entry in result.entries if entry.lemma == "zephyrium").level is None
    assert result.summary["failed_contexts"] > 0
    assert any("intentional failure" in warning for warning in result.warnings)


def test_proper_names_can_be_recovered(analyzer, lexicon):
    result = analyze(
        parse_document("x.txt", b"Alice investigates mechanisms in London."), analyzer, lexicon
    )
    assert all(not entry.proper for entry in result.filtered())
    assert any(entry.proper for entry in result.filtered(include_proper=True))
    assert any(
        entry.proper for entry in result.filtered(include_proper=True, include_uncertain=False)
    )


def test_no_silent_cap_for_long_paragraphs(analyzer, lexicon):
    text = "We investigate mechanisms. " * 1000
    result = analyze(parse_document("long.txt", text.encode()), analyzer, lexicon)
    assert next(entry for entry in result.entries if entry.lemma == "investigate").count == 1000
    assert next(entry for entry in result.entries if entry.lemma == "mechanism").count == 1000
