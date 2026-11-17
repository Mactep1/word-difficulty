import csv
import io
import json

from .models import LEVELS, Analysis, Entry

COLUMNS = [
    "单词",
    "原始形式",
    "词性",
    "CEFR",
    "频次",
    "例句",
    "来源位置",
    "判定来源",
    "最低模型概率",
    "说明",
    "专有名词",
]
SOURCE_NAMES = {"wordlist": "词表", "model": "模型", "proper": "专有名词", "uncertain": "待确认"}


def rows(entries: list[Entry]) -> list[dict]:
    return [
        dict(
            zip(
                COLUMNS,
                [
                    e.lemma,
                    ", ".join(e.forms),
                    e.pos,
                    e.level or ("专有名词" if e.proper else "待确认"),
                    e.count,
                    "\n".join(x["sentence"] for x in e.examples),
                    "\n".join(x["location"] for x in e.examples),
                    ", ".join(SOURCE_NAMES[s] for s in e.sources),
                    round(e.confidence, 4) if e.confidence is not None else None,
                    "; ".join(e.reasons),
                    "是" if e.proper else "否",
                ],
                strict=True,
            )
        )
        for e in entries
    ]


def _literal(value):
    # Source text must remain text when opened in spreadsheet applications.
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def csv_bytes(entries: list[Entry]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=COLUMNS)
    writer.writeheader()
    writer.writerows({key: _literal(value) for key, value in row.items()} for row in rows(entries))
    return stream.getvalue().encode("utf-8-sig")


def txt_bytes(entries: list[Entry]) -> bytes:
    words = dict.fromkeys(entry.lemma for entry in entries)
    return "".join(f"{word}\n" for word in words).encode("utf-8")


def json_bytes(analysis: Analysis, entries: list[Entry] | None = None) -> bytes:
    from dataclasses import asdict

    payload = analysis.to_dict()
    if entries is not None:
        payload["entries"] = [asdict(entry) for entry in entries]
    payload["export_scope"] = "complete" if entries is None else "filtered"
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")


def xlsx_bytes(analysis: Analysis, entries: list[Entry] | None = None) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    entries = analysis.entries if entries is None else entries
    workbook = Workbook()
    summary = workbook.active
    summary.title = "摘要"
    summary.append(["文件", _literal(analysis.filename)])
    summary.append(["导出词条数", len(entries)])
    summary.append(["范围说明", "下方分析统计针对完整文件，等级页仅包含本次导出范围。"])
    for key, value in analysis.summary.items():
        summary.append(
            [key, json.dumps(value, ensure_ascii=False) if isinstance(value, dict) else value]
        )
    for warning in analysis.warnings:
        summary.append(["提示", _literal(warning)])
    for level in (*LEVELS, "待确认", "专有名词"):
        sheet = workbook.create_sheet(level)
        sheet.append(COLUMNS)
        for entry in entries:
            target = "专有名词" if entry.proper else entry.level or "待确认"
            if target == level:
                sheet.append([_literal(value) for value in rows([entry])[0].values()])
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions
        for i, width in enumerate((22, 30, 14, 14, 10, 70, 40, 20, 18, 36, 14), 1):
            sheet.column_dimensions[get_column_letter(i)].width = width
        for cell in sheet[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="174F4A")
        for row in sheet.iter_rows(min_row=2):
            for cell in row:
                cell.alignment = Alignment(vertical="top", wrap_text=True)
    summary.column_dimensions["A"].width = 25
    summary.column_dimensions["B"].width = 100
    result = io.BytesIO()
    workbook.save(result)
    return result.getvalue()
