import json
import os
import tempfile
from pathlib import Path
from urllib.request import Request, urlopen

from .classifier import MODEL_REPO, MODEL_REVISION
from .lexicon import LEXICON_REPO, LEXICON_REVISION, LEXICON_URL, Lexicon


def _download(url: str, destination: Path) -> None:
    request = Request(url, headers={"User-Agent": "word-difficulty/0.1"})
    descriptor, temporary = tempfile.mkstemp(dir=destination.parent, suffix=".download")
    try:
        with os.fdopen(descriptor, "wb") as output, urlopen(request, timeout=60) as response:
            while block := response.read(1024 * 1024):
                output.write(block)
        Path(temporary).replace(destination)
    finally:
        Path(temporary).unlink(missing_ok=True)


def setup_data(root: Path, with_model: bool = False) -> dict:
    root.mkdir(parents=True, exist_ok=True)
    wordlist = root / "words.csv"
    if not wordlist.exists():
        print("下载 CEFR 词表…", flush=True)
        _download(LEXICON_URL, wordlist)
    lexicon = Lexicon(wordlist)
    if not (root / "wordlist-README.md").exists():
        _download(
            f"https://huggingface.co/datasets/{LEXICON_REPO}/resolve/{LEXICON_REVISION}/README.md",
            root / "wordlist-README.md",
        )
    metadata = {
        "lexicon": {
            "repo": LEXICON_REPO,
            "revision": LEXICON_REVISION,
            "sha256": lexicon.fingerprint,
            "rows": lexicon.row_count,
        },
    }
    if with_model:
        try:
            from huggingface_hub import snapshot_download
        except ImportError as exc:
            raise ValueError("缺少模型依赖，请先运行 uv sync --extra model") from exc
        print("下载上下文模型（约 772 MB）；中断后重新执行可续传…", flush=True)
        snapshot_download(
            repo_id=MODEL_REPO,
            revision=MODEL_REVISION,
            local_dir=root / "model",
            allow_patterns=["*.json", "*.model", "*.safetensors", "README.md"],
        )
        metadata["model"] = {"repo": MODEL_REPO, "revision": MODEL_REVISION}
    elif (root / "resources.json").exists():
        previous = json.loads((root / "resources.json").read_text(encoding="utf-8"))
        if "model" in previous:
            metadata["model"] = previous["model"]
    (root / "resources.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata
