import csv
import io
import json

from openpyxl import load_workbook

from word_difficulty.export import csv_bytes, json_bytes, txt_bytes, xlsx_bytes
from word_difficulty.models import Analysis, Entry


def sample():
    entries = [
        Entry(
            "investigate",
            "VERB",
            "B1",
            False,
            3,
            ["investigated"],
            [{"sentence": "=unsafe()", "location": "正文 · 段落 1"}],
            ["wordlist"],
        ),
        Entry("unknownword", "NOUN", None, False, 1, ["unknownword"], [], ["uncertain"]),
    ]
    return Analysis("sample.txt", entries, {"occurrences": 4}, [], {})


def test_csv_has_bom_and_preserves_unknown_and_counts():
    result = sample()
    data = csv_bytes(result.entries)
    assert data.startswith(b"\xef\xbb\xbf")
    table = list(csv.DictReader(io.StringIO(data.decode("utf-8-sig"))))
    assert table[0]["频次"] == "3"
    assert table[0]["例句"] == "'=unsafe()"
    assert table[0]["最低模型概率"] == ""
    assert table[1]["CEFR"] == "待确认"


def test_xlsx_groups_and_filtered_export_scope():
    result = sample()
    workbook = load_workbook(io.BytesIO(xlsx_bytes(result, result.entries[:1])))
    assert workbook["B1"].max_row == 2
    assert workbook["待确认"].max_row == 1
    assert workbook["B1"]["F2"].data_type != "f"
    assert workbook["B1"]["E2"].value == 3
    assert workbook["B1"].freeze_panes == "A2"


def test_json_distinguishes_complete_and_filtered_results():
    result = sample()
    full = json.loads(json_bytes(result))
    filtered = json.loads(json_bytes(result, result.entries[:1]))
    assert full["export_scope"] == "complete"
    assert len(full["entries"]) == 2
    assert filtered["export_scope"] == "filtered"
    assert len(filtered["entries"]) == 1


def test_txt_one_lemma_per_line_deduplicates_pos_and_levels_in_order():
    entries = [
        Entry("address", "NOUN", "A1", False, forms=["addresses"]),
        Entry("investigate", "VERB", "B1", False, forms=["investigated"]),
        Entry("address", "VERB", "B1", False),
        Entry("investigate", "VERB", "B2", False),
    ]
    assert txt_bytes(entries) == b"address\ninvestigate\n"
    assert txt_bytes(entries[1:2]) == b"investigate\n"


def test_txt_empty_export_is_empty_file():
    assert txt_bytes([]) == b""
