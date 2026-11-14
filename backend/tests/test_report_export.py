"""اختبارات تصدير التقارير إلى الصيغ القابلة للتحميل."""

import io
import zipfile

import pytest

from app.services import report_export as rx

SAMPLE = """# تقرير تجريبي

> ملخص قصير.

## القسم الأول

نص عادي فيه **تشديد** وكلمة `كود`.

- نقطة أولى
- نقطة ثانية

1. أولًا
2. ثانيًا

---

## القسم الثاني

سطر أخير.
"""


def test_text_export_removes_markdown_markers():
    out = rx.to_text(SAMPLE)
    assert "**" not in out
    assert "#" not in out
    assert "تقرير تجريبي" in out
    assert "• نقطة أولى" in out


def test_html_export_is_rtl_and_self_contained():
    out = rx.to_html(SAMPLE, "تقرير تجريبي")
    assert 'dir="rtl"' in out
    assert "<h2>القسم الأول</h2>" in out
    assert "<ul>" in out and "<ol>" in out
    assert "http://" not in out.split("<body>")[1]


def test_docx_export_is_valid_ooxml_package():
    data = rx.to_docx(SAMPLE, "تقرير تجريبي")
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        names = set(zf.namelist())
        assert "[Content_Types].xml" in names
        assert "word/document.xml" in names
        document = zf.read("word/document.xml").decode("utf-8")
    assert "<w:bidi/>" in document
    assert "تقرير تجريبي" in document


def test_pdf_export_produces_pdf_bytes():
    data = rx.to_pdf(SAMPLE, "تقرير تجريبي")
    assert data.startswith(b"%PDF")
    assert len(data) > 1000


@pytest.mark.parametrize("fmt,prefix", [("md", "# تقرير"), ("txt", "تقرير"), ("html", "<!DOCTYPE html>"), ("docx", "PK"), ("pdf", "%PDF")])
def test_build_export_supported_formats(fmt, prefix):
    data, mime, ext = rx.build_export(SAMPLE, fmt)
    assert data[:40].decode("utf-8", "ignore").startswith(prefix[:12]) or data.startswith(b"PK") or data.startswith(b"%PDF")
    assert ext == "." + fmt


def test_build_export_rejects_unknown_format():
    with pytest.raises(rx.ExportError):
        rx.build_export(SAMPLE, "xlsx")


def test_build_export_rejects_empty_report():
    with pytest.raises(rx.ExportError):
        rx.build_export("   ", "pdf")


def test_split_title_extracts_heading():
    title, body = rx.split_title(SAMPLE)
    assert title == "تقرير تجريبي"
    assert not body.strip().startswith("# تقرير تجريبي")
