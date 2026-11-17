import pytest

from word_difficulty.lexicon import Lexicon
from word_difficulty.nlp import EnglishAnalyzer


@pytest.fixture(scope="session")
def analyzer():
    return EnglishAnalyzer()


@pytest.fixture
def lexicon(tmp_path):
    path = tmp_path / "words.csv"
    path.write_text(
        "word,type,CEFR\n"
        "the,determiner,A1\nchild,noun,A1\nbook,noun,A1\nread,verb,A1\n"
        "investigate,verb,B1\nmechanism,noun,B2\nabolish,verb,C2\n"
        "address,noun,A1\naddress,verb,B1\n",
        encoding="utf-8",
    )
    return Lexicon(path)
