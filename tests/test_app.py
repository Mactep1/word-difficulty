from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_demo_analyze_filter_and_export(monkeypatch, tmp_path):
    # UI smoke test uses a real CEFR fixture and the actual spaCy pipeline.
    root = Path(__file__).resolve().parents[1]
    (tmp_path / "words.csv").write_text(
        "word,type,CEFR\ninvestigate,verb,B1\nmechanism,noun,B2\nabolish,verb,C2\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("WORD_DIFFICULTY_DATA", str(tmp_path))
    app = AppTest.from_file(str(root / "src/word_difficulty/app.py"), default_timeout=60).run()
    assert not app.exception
    next(button for button in app.button if button.label == "使用示例文本").click().run()
    next(button for button in app.button if button.label == "开始分析").click().run()
    assert not app.exception
    assert len(app.metric) == 4
    assert app.dataframe
    assert any(button.label == "下载 TXT" for button in app.get("download_button"))
    app.sidebar.selectbox[0].select("C2").run()
    assert not app.exception
    assert "abolish" in app.dataframe[0].value["单词"].tolist()
    assert "investigate" not in app.dataframe[0].value["单词"].tolist()
