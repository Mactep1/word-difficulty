"""Parse source files without extracting archives to the filesystem."""

import io
import posixpath
import re
import zipfile
from pathlib import Path
from urllib.parse import unquote, urlsplit
from xml.etree import ElementTree as ET

from bs4 import BeautifulSoup
from charset_normalizer import from_bytes

from .models import Document, Segment

SUPPORTED = ("txt", "epub", "srt", "vtt", "docx", "pdf", "ass", "ssa")


class ParseError(ValueError):
    pass


def decode_text(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-16" if data[:2] in (b"\xff\xfe", b"\xfe\xff") else "utf-8"):
        try:
            return data.decode(encoding)
        except UnicodeError:
            pass
    match = from_bytes(data).best()
    if match is None:
        raise ParseError("无法识别文本编码，请转换为 UTF-8 后重试。")
    return str(match)


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _paragraphs(text: str, prefix: str) -> list[Segment]:
    paragraphs = re.split(r"\n\s*\n", text.replace("\r\n", "\n"))
    return [
        Segment(_clean(p), f"{prefix} · 段落 {i}", p)
        for i, p in enumerate(paragraphs, 1)
        if p.strip()
    ]


def _epub(data: bytes) -> list[Segment]:
    result = []
    with zipfile.ZipFile(io.BytesIO(data)) as book:
        container = ET.fromstring(book.read("META-INF/container.xml"))
        rootfile = container.find(".//{*}rootfile")
        if rootfile is None or not rootfile.get("full-path"):
            raise ParseError("EPUB 缺少正文索引。")
        opf_path = rootfile.attrib["full-path"]
        package = ET.fromstring(book.read(opf_path))
        manifest = {node.attrib["id"]: node for node in package.findall(".//{*}manifest/{*}item")}
        spine = package.findall(".//{*}spine/{*}itemref")
        for chapter, ref in enumerate(spine, 1):
            if ref.get("linear", "yes") == "no":
                continue
            item = manifest.get(ref.get("idref"))
            if item is None or "nav" in item.get("properties", "").split():
                continue
            href = unquote(urlsplit(item.attrib["href"]).path)
            path = posixpath.normpath(posixpath.join(posixpath.dirname(opf_path), href))
            soup = BeautifulSoup(book.read(path), "html.parser")
            for node in soup.select("script, style, nav, head"):
                node.decompose()
            body = soup.body or soup
            # Reading order follows the spine, not archive filename order.
            # Block boundaries delimit paragraphs; inline emphasis must retain sentence context.
            for node in body.find_all(
                ["p", "div", "section", "article", "h1", "h2", "h3", "li", "tr"]
            ):
                node.insert_after("\n\n")
            for node in body.find_all("br"):
                node.replace_with("\n")
            result.extend(_paragraphs(body.get_text(), f"章节 {chapter} ({path})"))
    return result


def _timestamp(milliseconds: int) -> str:
    seconds, ms = divmod(milliseconds, 1000)
    minutes, sec = divmod(seconds, 60)
    hour, minute = divmod(minutes, 60)
    return f"{hour:02}:{minute:02}:{sec:02}.{ms:03}"


def _subtitles(data: bytes, suffix: str) -> list[Segment]:
    import pysubs2

    text = decode_text(data)
    # WebVTT NOTE/STYLE/REGION blocks are metadata, not dialogue.
    if suffix == "vtt":
        text = re.sub(
            r"^(?:NOTE(?:[ \t][^\n]*)?|STYLE|REGION)[ \t]*\r?\n.*?(?=\n[ \t]*\r?\n|\Z)",
            "",
            text,
            flags=re.M | re.S,
        )
    subtitles = pysubs2.SSAFile.from_string(text, format_=suffix)
    cues = []
    for cue in subtitles:
        if cue.is_comment:
            continue
        clean = BeautifulSoup(cue.plaintext, "html.parser").get_text(" ")
        clean = re.sub(r"\[(?:music|applause|laughter|sighs?|inaudible)\]", "", clean, flags=re.I)
        clean = re.sub(r"(?m)^\s*(?:[-–]\s*|[A-Z][A-Z ]{1,25}:\s*)", "", clean)
        clean = _clean(clean.replace("♪", ""))
        if not clean:
            continue
        # Suppress only duplicate/overlapping adjacent cues, not later repetitions.
        if cues and cues[-1][2] == clean and cue.start <= cues[-1][1] + 250:
            start, end, previous, raw = cues[-1]
            cues[-1] = (start, max(end, cue.end), previous, raw)
        else:
            cues.append((cue.start, cue.end, clean, cue.text))
    result = []
    pending = None
    for start, end, clean, raw in cues:
        if pending is not None:
            ps, pe, pt, pr = pending
            if (
                start - pe <= 1500
                and not re.search(r"[.!?][\"\u201d\u2019]*$", pt)
                and len(pt) < 800
            ):
                pending = (ps, max(pe, end), f"{pt} {clean}", f"{pr}\n{raw}")
                continue
            result.append(Segment(pt, f"{_timestamp(ps)} → {_timestamp(pe)}", pr))
        pending = (start, end, clean, raw)
    if pending:
        start, end, clean, raw = pending
        result.append(Segment(clean, f"{_timestamp(start)} → {_timestamp(end)}", raw))
    return result


def parse_document(name: str, data: bytes) -> Document:
    suffix = Path(name).suffix.lower().lstrip(".")
    if suffix not in SUPPORTED:
        raise ParseError(f"不支持 .{suffix or '(无后缀)'} 文件。支持：{', '.join(SUPPORTED)}")
    if not data:
        raise ParseError("文件为空。")
    if len(data) > 100 * 1024 * 1024:
        raise ParseError("文件超过 100 MB，请拆分后再试。")
    warnings = []
    try:
        if suffix == "txt":
            segments = _paragraphs(decode_text(data), "正文")
        elif suffix == "epub":
            segments = _epub(data)
        elif suffix in ("srt", "vtt", "ass", "ssa"):
            segments = _subtitles(data, suffix)
        elif suffix == "docx":
            from docx import Document as WordDocument

            doc = WordDocument(io.BytesIO(data))
            # iter_inner_content retains the order of paragraphs and tables.
            segments = []
            for i, block in enumerate(doc.iter_inner_content(), 1):
                text = (
                    block.text
                    if hasattr(block, "text")
                    else "\n".join(
                        " | ".join(cell.text for cell in row.cells) for row in block.rows
                    )
                )
                if text.strip():
                    segments.append(Segment(_clean(text), f"正文块 {i}", text))
        else:
            from pypdf import PdfReader

            pdf = PdfReader(io.BytesIO(data))
            if pdf.is_encrypted and not pdf.decrypt(""):
                raise ParseError("PDF 已加密，请先移除密码。")
            segments = []
            for i, page in enumerate(pdf.pages, 1):
                text = page.extract_text() or ""
                if text.strip():
                    segments.extend(_paragraphs(text, f"第 {i} 页"))
                else:
                    warnings.append(f"第 {i} 页没有可提取正文，可能需要 OCR。")
            warnings.append("PDF 提取顺序可能受分栏、页眉页脚影响，请检查文本预览。")
    except ParseError:
        raise
    except Exception as exc:
        raise ParseError(f"解析失败，请检查文件是否损坏或格式是否正确：{exc}") from exc
    if not segments:
        raise ParseError("未提取到正文；扫描 PDF 需要先进行 OCR，空字幕或图片书籍无法直接分析。")
    return Document(Path(name).name, segments, warnings)
