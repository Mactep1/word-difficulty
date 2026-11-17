from collections import Counter
from collections.abc import Callable
from dataclasses import replace
from typing import Protocol

from . import __version__
from .cache import PredictionCache
from .lexicon import Lexicon
from .models import LEVELS, Analysis, Document, Entry, Occurrence, Prediction
from .nlp import EnglishAnalyzer

Progress = Callable[[float, str], None]


class Classifier(Protocol):
    version: str

    def predict(self, occurrences: list[Occurrence]) -> list[Prediction]: ...


def analyze(
    document: Document,
    analyzer: EnglishAnalyzer,
    lexicon: Lexicon,
    classifier: Classifier | None = None,
    cache: PredictionCache | None = None,
    confidence_threshold: float = 0.6,
    batch_size: int = 16,
    progress: Progress | None = None,
) -> Analysis:
    if not 0 <= confidence_threshold <= 1:
        raise ValueError("置信度阈值必须位于 0–1。")
    if batch_size < 1:
        raise ValueError("批量大小必须大于零。")
    progress = progress or (lambda fraction, message: None)
    progress(0.05, "分句、词形还原和词性分析…")
    occurrences = list(analyzer.occurrences(document))
    progress(0.35, f"查询词表，共 {len(occurrences):,} 次词语出现…")
    predictions: list[Prediction | None] = []
    pending: dict[str, tuple[Occurrence, list[int]]] = {}
    hits = 0
    cache_version = f"{getattr(classifier, 'version', '')}:nlp-{analyzer.version}"
    for index, occurrence in enumerate(occurrences):
        candidates = lexicon.lookup(occurrence.lemma, occurrence.pos)
        if occurrence.proper:
            predictions.append(Prediction(None, "proper", reason="专有名词"))
        elif len(candidates) == 1:
            predictions.append(Prediction(next(iter(candidates)), "wordlist"))
        elif classifier is None:
            reason = "词表有多个等级" if candidates else "词表未收录或词性不匹配"
            predictions.append(Prediction(None, "uncertain", reason=reason))
        else:
            key = PredictionCache.key(occurrence, cache_version)
            cached = cache.get(key) if cache else None
            if cached is not None:
                predictions.append(cached)
                hits += 1
            else:
                predictions.append(None)
                if key not in pending:
                    pending[key] = (occurrence, [])
                pending[key][1].append(index)
    warnings = document.warnings.copy()
    items = list(pending.items())
    failed = 0
    for start in range(0, len(items), batch_size):
        batch = items[start : start + batch_size]
        progress(
            0.4 + 0.5 * start / max(1, len(items)), f"上下文模型分析 {start:,} / {len(items):,}…"
        )
        try:
            outputs = classifier.predict([item[1][0] for item in batch])
            if len(outputs) != len(batch):
                raise ValueError("模型返回数量不匹配。")
        except Exception as exc:
            # Preserve every affected occurrence and all successful lexical results.
            outputs = [Prediction(None, "uncertain", reason="模型推理失败") for _ in batch]
            if failed == 0:
                warnings.append(f"部分模型推理失败，相关词语已保留在待确认列表：{exc}")
            failed += len(batch)
        for (key, (_, indices)), prediction in zip(batch, outputs, strict=True):
            if cache and prediction.source == "model":
                cache.put(key, prediction)
            for index in indices:
                predictions[index] = prediction
    progress(0.95, "汇总分级词表…")
    groups: dict[tuple, Entry] = {}
    source_counts = Counter()
    for occurrence, prediction in zip(occurrences, predictions, strict=True):
        if prediction is None:
            raise RuntimeError("存在未处理词语。")
        if prediction.source == "model" and (
            prediction.confidence is None or prediction.confidence < confidence_threshold
        ):
            prediction = replace(prediction, level=None, reason="模型置信度低于阈值")
        source_counts[prediction.source] += 1
        key = (occurrence.lemma, occurrence.pos, prediction.level, occurrence.proper)
        entry = groups.setdefault(key, Entry(*key))
        entry.count += 1
        if occurrence.surface not in entry.forms:
            entry.forms.append(occurrence.surface)
        example = {"sentence": occurrence.sentence, "location": occurrence.location}
        if len(entry.examples) < 3 and example not in entry.examples:
            entry.examples.append(example)
        if prediction.source not in entry.sources:
            entry.sources.append(prediction.source)
        if prediction.reason and prediction.reason not in entry.reasons:
            entry.reasons.append(prediction.reason)
        if prediction.confidence is not None:
            entry.confidence = (
                min(entry.confidence, prediction.confidence)
                if entry.confidence is not None
                else prediction.confidence
            )
    entries = sorted(
        groups.values(),
        key=lambda e: (LEVELS.index(e.level) if e.level else 6, -e.count, e.lemma, e.pos),
    )
    ordinary = [entry for entry in entries if not entry.proper]
    summary = {
        "characters": sum(len(segment.text) for segment in document.segments),
        "segments": len(document.segments),
        "occurrences": len(occurrences),
        "vocabulary_entries": len(ordinary),
        "unique_lemmas": len({entry.lemma for entry in ordinary}),
        "graded_entries": sum(entry.level is not None for entry in ordinary),
        "uncertain_entries": sum(entry.level is None for entry in ordinary),
        "proper_entries": sum(entry.proper for entry in entries),
        "by_level": {level: sum(entry.level == level for entry in ordinary) for level in LEVELS},
        "source_occurrences": dict(source_counts),
        "cache_hits": hits,
        "model_contexts": len(items),
        "failed_contexts": failed,
    }
    if classifier is None:
        warnings.append("当前为词表模式；未收录词保留在待确认列表，尚未使用上下文模型补充分级。")
    if not occurrences:
        warnings.append("未识别到英文单词，请检查文本预览或文件语言。")
    metadata = {
        "app_version": __version__,
        "nlp": analyzer.version,
        "lexicon_sha256": lexicon.fingerprint,
        "classifier": getattr(classifier, "version", None),
        "confidence_threshold": confidence_threshold,
        "confidence_aggregation": "minimum model probability within group",
        "group_by": ["lemma", "pos", "level", "proper"],
    }
    progress(1.0, "分析完成")
    return Analysis(document.name, entries, summary, warnings, metadata)
