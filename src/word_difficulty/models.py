from dataclasses import asdict, dataclass, field
from typing import Any

LEVELS = ("A1", "A2", "B1", "B2", "C1", "C2")


@dataclass(frozen=True)
class Segment:
    text: str
    location: str
    raw_text: str = ""


@dataclass
class Document:
    name: str
    segments: list[Segment]
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Occurrence:
    lemma: str
    surface: str
    pos: str
    sentence: str
    start: int
    end: int
    location: str
    proper: bool = False


@dataclass(frozen=True)
class Prediction:
    level: str | None
    source: str
    confidence: float | None = None
    probabilities: dict[str, float] = field(default_factory=dict)
    reason: str = ""


@dataclass
class Entry:
    lemma: str
    pos: str
    level: str | None
    proper: bool
    count: int = 0
    forms: list[str] = field(default_factory=list)
    examples: list[dict[str, str]] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    confidence: float | None = None
    reasons: list[str] = field(default_factory=list)


@dataclass
class Analysis:
    filename: str
    entries: list[Entry]
    summary: dict[str, Any]
    warnings: list[str]
    metadata: dict[str, Any]

    def filtered(
        self,
        minimum: str = "B1",
        include_uncertain: bool = True,
        include_proper: bool = False,
        query: str = "",
    ) -> list[Entry]:
        threshold = LEVELS.index(minimum)
        query = query.strip().casefold()
        return [
            entry
            for entry in self.entries
            if (
                (entry.proper and include_proper)
                or (
                    not entry.proper
                    and (
                        (entry.level is None and include_uncertain)
                        or (entry.level is not None and LEVELS.index(entry.level) >= threshold)
                    )
                )
            )
            and (
                not query
                or query in entry.lemma.casefold()
                or any(query in form.casefold() for form in entry.forms)
            )
        ]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
