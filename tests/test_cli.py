import json

from word_difficulty.cli import main


def test_cli_preserves_outputs_for_same_name_different_formats(tmp_path, monkeypatch):
    resources = tmp_path / "resources"
    resources.mkdir()
    (resources / "words.csv").write_text(
        "word,type,CEFR\ninvestigate,verb,B1\nmechanism,noun,B2\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("WORD_DIFFICULTY_DATA", str(resources))
    text = tmp_path / "story.txt"
    text.write_text("We investigate mechanisms.", encoding="utf-8")
    subtitle = tmp_path / "story.srt"
    subtitle.write_text(
        "1\n00:00:01,000 --> 00:00:03,000\nWe investigate mechanisms.\n", encoding="utf-8"
    )
    output = tmp_path / "output"
    assert main(["analyze", str(text), "-o", str(output)]) == 0
    assert main(["analyze", str(subtitle), "-o", str(output)]) == 0
    assert (output / "story.txt.csv").exists()
    assert (output / "story.srt.csv").exists()
    text_analysis = json.loads((output / "story.txt.complete.json").read_bytes())
    subtitle_analysis = json.loads((output / "story.srt.complete.json").read_bytes())
    assert text_analysis["filename"] == "story.txt"
    assert subtitle_analysis["filename"] == "story.srt"
    for name in ("story.txt", "story.srt"):
        words = (output / f"{name}.txt").read_text(encoding="utf-8").splitlines()
        assert {"investigate", "mechanism"} <= set(words)
        assert len(words) == len(set(words))
        assert "mechanisms" not in words
