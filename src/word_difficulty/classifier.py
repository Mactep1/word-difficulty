"""Local-only paired contextual inference; no implicit network downloads."""

from pathlib import Path

from .models import LEVELS, Occurrence, Prediction

MODEL_REPO = "star092304/cefr-level-deberta-v3-base"
MODEL_REVISION = "895fabc45879f4ce6dd435b11e1bbc39fd9ee4b5"
INPUT_VERSION = "context-pair-window-v1"


def context_pair(tokenizer, occurrence: Occurrence, max_length: int = 256) -> tuple[str, str]:
    """Use offset mappings to retain the actual target, even late in a long sentence."""
    if occurrence.sentence[occurrence.start : occurrence.end] != occurrence.surface:
        raise ValueError("目标词位置与原句不匹配。")
    encoded = tokenizer(occurrence.sentence, add_special_tokens=False, return_offsets_mapping=True)
    offsets = encoded["offset_mapping"]
    target_ids = tokenizer(occurrence.surface, add_special_tokens=False)["input_ids"]
    budget = max_length - len(target_ids) - tokenizer.num_special_tokens_to_add(pair=True) - 8
    if budget < 8:
        raise ValueError("目标词过长，无法构造模型输入。")
    indices = [i for i, (a, b) in enumerate(offsets) if b > occurrence.start and a < occurrence.end]
    if not indices:
        raise ValueError("模型分词器无法定位目标词。")
    if len(offsets) <= budget:
        return occurrence.sentence, occurrence.surface
    midpoint = (indices[0] + indices[-1]) // 2
    left = max(0, midpoint - budget // 2)
    right = min(len(offsets), left + budget)
    left = max(0, right - budget)
    if not (left <= indices[0] <= indices[-1] < right):
        raise ValueError("目标词超出上下文窗口。")
    return occurrence.sentence[offsets[left][0] : offsets[right - 1][1]], occurrence.surface


class ContextClassifier:
    def __init__(self, model_path: Path, device: str = "cpu"):
        if not (model_path / "config.json").exists():
            raise ValueError("上下文模型未配置，请先执行：word-difficulty setup --with-model")
        try:
            import torch
            import transformers
            from transformers import AutoModelForSequenceClassification, AutoTokenizer
        except ImportError as exc:
            raise ValueError(
                '请先安装模型依赖：uv pip install --python .venv/Scripts/python.exe -e ".[model]"'
            ) from exc
        if device == "cuda" and not torch.cuda.is_available():
            raise ValueError("当前环境没有可用的 CUDA 设备，请选择 CPU。")
        self.torch = torch
        self.device = device
        if device == "cpu":
            torch.set_num_threads(min(torch.get_num_threads(), 8))
        self.tokenizer = AutoTokenizer.from_pretrained(
            model_path, local_files_only=True, use_fast=True
        )
        self.model = (
            AutoModelForSequenceClassification.from_pretrained(
                model_path,
                local_files_only=True,
                use_safetensors=True,
            )
            .to(device)
            .eval()
        )
        if set(self.model.config.id2label.values()) != set(LEVELS):
            raise ValueError("模型标签不是预期的六级 CEFR 标签。")
        self.version = (
            f"{MODEL_REPO}@{MODEL_REVISION}:{INPUT_VERSION}:transformers-{transformers.__version__}"
        )

    def predict(self, occurrences: list[Occurrence]) -> list[Prediction]:
        if not occurrences:
            return []
        pairs = [context_pair(self.tokenizer, occurrence) for occurrence in occurrences]
        encoded = self.tokenizer(
            [pair[0] for pair in pairs],
            [pair[1] for pair in pairs],
            padding=True,
            truncation="only_first",
            max_length=256,
            return_tensors="pt",
        ).to(self.device)
        with self.torch.inference_mode():
            probabilities = self.model(**encoded).logits.softmax(dim=-1).cpu().tolist()
        result = []
        for row in probabilities:
            mapping = {self.model.config.id2label[i]: value for i, value in enumerate(row)}
            level = max(mapping, key=mapping.get)
            result.append(Prediction(level, "model", mapping[level], mapping))
        return result
