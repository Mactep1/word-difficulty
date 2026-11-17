import os
from pathlib import Path


def data_dir() -> Path:
    # Independent of the launching shell's working directory.
    default = Path(__file__).resolve().parents[2] / ".data"
    return Path(os.environ.get("WORD_DIFFICULTY_DATA", default)).resolve()
