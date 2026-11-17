import hashlib
import json
import sqlite3
from dataclasses import asdict
from pathlib import Path

from .models import Occurrence, Prediction


class PredictionCache:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        connection = self._connection()
        try:
            with connection:
                connection.execute(
                    "CREATE TABLE IF NOT EXISTS predictions (key TEXT PRIMARY KEY, payload TEXT NOT NULL)"
                )
        finally:
            connection.close()

    def _connection(self):
        return sqlite3.connect(self.path, timeout=30)

    @staticmethod
    def key(occurrence: Occurrence, version: str) -> str:
        content = [
            version,
            occurrence.sentence,
            occurrence.start,
            occurrence.end,
            occurrence.surface,
            occurrence.lemma,
            occurrence.pos,
        ]
        return hashlib.sha256(json.dumps(content, ensure_ascii=False).encode()).hexdigest()

    def get(self, key: str) -> Prediction | None:
        connection = self._connection()
        try:
            row = connection.execute(
                "SELECT payload FROM predictions WHERE key = ?", (key,)
            ).fetchone()
            return Prediction(**json.loads(row[0])) if row else None
        finally:
            connection.close()

    def put(self, key: str, prediction: Prediction) -> None:
        connection = self._connection()
        try:
            with connection:
                connection.execute(
                    "INSERT OR REPLACE INTO predictions VALUES (?, ?)",
                    (key, json.dumps(asdict(prediction))),
                )
        finally:
            connection.close()
