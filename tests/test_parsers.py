import io
import zipfile

import pytest

from word_difficulty.parsers import ParseError, parse_document


def test_txt_preserves_paragraphs_and_utf16():
    document = parse_document("book.txt", "First paragraph.\n\nSecond paragraph.".encode("utf-16"))
    assert [segment.text for segment in document.segments] == [
        "First paragraph.",
        "Second paragraph.",
    ]
    assert "2" in document.segments[1].location


def test_subtitle_boundaries_deduplication_and_later_repetition():
    data = b"""1
00:00:01,000 --> 00:00:03,000
We investigate

2
00:00:03,000 --> 00:00:04,000
the <i>mechanism.</i>

3
00:00:04,000 --> 00:00:05,000
the <i>mechanism.</i>

4
00:00:10,000 --> 00:00:12,000
the mechanism.
"""
    document = parse_document("movie.srt", data)
    assert len(document.segments) == 2
    assert document.segments[0].text == "We investigate the mechanism."
    assert document.segments[0].location == "00:00:01.000 → 00:00:05.000"
    assert document.segments[1].text == "the mechanism."


def test_vtt_ignores_metadata():
    data = b"""WEBVTT

NOTE Ignore these words.
More metadata.

STYLE
::cue { color: red; }

00:00:01.000 --> 00:00:02.000
<v Alice>We investigate.</v>
"""
    document = parse_document("movie.vtt", data)
    assert [segment.text for segment in document.segments] == ["We investigate."]


@pytest.mark.parametrize("suffix", ["ass", "ssa"])
def test_ass_tags_and_comments(suffix):
    import pysubs2

    subtitles = pysubs2.SSAFile()
    subtitles.append(
        pysubs2.SSAEvent(start=1000, end=2000, text=r"{\i1}Investigate{\i0}\Nthe mechanism.")
    )
    subtitles.append(pysubs2.SSAEvent(start=3000, end=4000, text="Ignore comment.", type="Comment"))
    document = parse_document(f"movie.{suffix}", subtitles.to_string(suffix).encode())
    assert document.segments[0].text == "Investigate the mechanism."
    assert len(document.segments) == 1


def test_epub_follows_spine_not_archive_order():
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr(
            "META-INF/container.xml",
            '<container><rootfiles><rootfile full-path="OPS/book.opf"/></rootfiles></container>',
        )
        archive.writestr(
            "OPS/book.opf",
            '<package><manifest><item id="a" href="first.xhtml"/><item id="b" href="second.xhtml"/></manifest><spine><itemref idref="b"/><itemref idref="a"/></spine></package>',
        )
        archive.writestr(
            "OPS/first.xhtml",
            "<html><head><title>Not body</title></head><body><p>First.</p></body></html>",
        )
        archive.writestr(
            "OPS/second.xhtml",
            "<html><body><p>Second <em>chapter</em>.</p><script>Ignore.</script></body></html>",
        )
    document = parse_document("book.epub", output.getvalue())
    assert [segment.text for segment in document.segments] == ["Second chapter.", "First."]


def test_docx_preserves_tables_and_paragraph_order():
    from docx import Document

    word = Document()
    word.add_paragraph("Before.")
    word.add_table(rows=1, cols=1).cell(0, 0).text = "Inside."
    word.add_paragraph("After.")
    output = io.BytesIO()
    word.save(output)
    document = parse_document("book.docx", output.getvalue())
    assert [segment.text for segment in document.segments] == ["Before.", "Inside.", "After."]


def test_pdf_extracts_text_and_page_location():
    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

    writer = PdfWriter()
    page = writer.add_blank_page(width=600, height=800)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})}
    )
    stream = DecodedStreamObject()
    stream.set_data(b"BT /F1 12 Tf 50 700 Td (Investigate the mechanism.) Tj ET")
    page[NameObject("/Contents")] = stream
    result = io.BytesIO()
    writer.write(result)
    document = parse_document("book.pdf", result.getvalue())
    assert "Investigate the mechanism." in document.segments[0].text
    assert "1" in document.segments[0].location


def test_scan_pdf_is_not_fake_success():
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=600, height=800)
    result = io.BytesIO()
    writer.write(result)
    with pytest.raises(ParseError, match="OCR"):
        parse_document("scan.pdf", result.getvalue())


@pytest.mark.parametrize(
    ("name", "data"), [("empty.txt", b""), ("bad.epub", b"broken"), ("bad.exe", b"x")]
)
def test_invalid_files_fail_with_actionable_errors(name, data):
    with pytest.raises(ParseError):
        parse_document(name, data)
