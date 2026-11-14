"""تصدير تقارير «استشراف» إلى صيغ قابلة للتحميل.

الصيغ المدعومة: Markdown، نص عادي، HTML، Word (docx)، PDF.

كل الدوال تعمل على نص التقرير بصيغة Markdown فقط، بلا أي اتصال بالشبكة:
- النص العادي وHTML: معالجة سطور بسيطة بلا اعتماديات.
- Word: نُولّد حزمة OOXML بأنفسنا (zipfile) بلا مكتبة خارجية.
- PDF: fpdf2 + uharfbuzz لتشكيل الحروف العربية، مع خط Cairo مضمّن في المستودع.
"""

from __future__ import annotations

import html as html_lib
import io
import os
import re
import unicodedata
import zipfile
from typing import Iterable, List, Tuple
from xml.sax.saxutils import escape as xml_escape

FONT_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "Cairo.ttf")

SUPPORTED_FORMATS = ("md", "txt", "html", "docx", "pdf")

CONTENT_TYPES = {
    "md": ("text/markdown; charset=utf-8", ".md"),
    "txt": ("text/plain; charset=utf-8", ".txt"),
    "html": ("text/html; charset=utf-8", ".html"),
    "docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", ".docx"),
    "pdf": ("application/pdf", ".pdf"),
}


class ExportError(RuntimeError):
    """فشل التصدير برسالة عربية صالحة للعرض للمستخدم."""


# --------------------------------------------------------------------------
# تحليل Markdown
# --------------------------------------------------------------------------
_INLINE_RE = re.compile(r"(\*\*.+?\*\*|\*.+?\*|`[^`]+`)")


def _strip_inline(text: str) -> str:
    """إزالة رموز التنسيق السطري مع إبقاء النص."""
    text = text.replace("**", "").replace("__", "")
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"(?<!\*)\*(?!\s)(.+?)(?<!\s)\*(?!\*)", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    return text.strip()


def _is_table_sep(line: str) -> bool:
    stripped = line.strip()
    return bool(stripped) and set(stripped) <= set("|-: ") and "-" in stripped


def parse_blocks(markdown_text: str) -> List[Tuple[str, str]]:
    """يحوّل Markdown إلى قائمة (نوع، نص) بأنواع: h1 h2 h3 quote bullet numbered paragraph."""
    blocks: List[Tuple[str, str]] = []
    for raw in (markdown_text or "").splitlines():
        line = raw.rstrip()
        stripped = line.strip()

        if not stripped:
            blocks.append(("blank", ""))
            continue
        if set(stripped) == {"-"} and len(stripped) >= 3:  # --- فاصل
            blocks.append(("rule", ""))
            continue
        if _is_table_sep(stripped):
            continue
        if stripped.startswith("|") and stripped.endswith("|"):
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            blocks.append(("table_row", " · ".join(_strip_inline(c) for c in cells if c)))
            continue
        if stripped.startswith("### "):
            blocks.append(("h3", _strip_inline(stripped[4:])))
            continue
        if stripped.startswith("## "):
            blocks.append(("h2", _strip_inline(stripped[3:])))
            continue
        if stripped.startswith("# "):
            blocks.append(("h1", _strip_inline(stripped[2:])))
            continue
        if stripped.startswith("> "):
            blocks.append(("quote", _strip_inline(stripped[2:])))
            continue
        if re.match(r"^[-*+]\s+", stripped):
            blocks.append(("bullet", _strip_inline(re.sub(r"^[-*+]\s+", "", stripped))))
            continue
        if re.match(r"^\d+[.)]\s+", stripped):
            blocks.append(("numbered", _strip_inline(stripped)))
            continue
        blocks.append(("paragraph", _strip_inline(stripped)))
    return blocks


# --------------------------------------------------------------------------
# نص عادي
# --------------------------------------------------------------------------
def to_text(markdown_text: str) -> str:
    out: List[str] = []
    for kind, text in parse_blocks(markdown_text):
        if kind == "blank":
            out.append("")
        elif kind == "rule":
            out.append("=" * 40)
        elif kind == "h1":
            out.append(text)
            out.append("=" * max(10, min(len(text), 60)))
        elif kind == "h2":
            out.append(text)
            out.append("-" * max(10, min(len(text), 60)))
        elif kind == "h3":
            out.append(f"◆ {text}")
        elif kind == "quote":
            out.append(f"  “{text}”")
        elif kind == "bullet":
            out.append(f"  • {text}")
        elif kind == "numbered":
            out.append(f"  {text}")
        else:
            out.append(text)
    return "\n".join(out).strip() + "\n"


# --------------------------------------------------------------------------
# HTML (مستقل بذاته، RTL، بلا أي ملفات خارجية)
# --------------------------------------------------------------------------
_HTML_STYLE = """
:root { color-scheme: light; }
* { box-sizing: border-box; }
body { margin: 0; padding: 32px 18px; background: #f5f6f8;
  font-family: "Cairo", "Fustat", "Segoe UI", Tahoma, sans-serif; color: #1b1d22; }
.page { max-width: 820px; margin: 0 auto; background: #fff; border-radius: 18px;
  padding: 36px 30px 44px; box-shadow: 0 10px 40px rgba(15,20,35,.08); }
h1 { font-size: 30px; line-height: 1.45; margin: 0 0 10px; }
h2 { font-size: 22px; margin: 34px 0 12px; padding-inline-start: 12px;
  border-inline-start: 4px solid #FF4500; }
h3 { font-size: 18px; margin: 22px 0 8px; color: #3a3f4b; }
p { font-size: 16.5px; line-height: 2; margin: 10px 0; text-align: justify; }
ul, ol { padding-inline-start: 22px; }
li { font-size: 16.5px; line-height: 1.95; margin: 6px 0; }
blockquote { margin: 16px 0; padding: 14px 16px; background: #fff6f2;
  border-inline-start: 4px solid #FF4500; border-radius: 10px; color: #444; }
blockquote p { margin: 0; font-size: 16px; }
hr { border: 0; border-top: 1px solid #e8eaef; margin: 26px 0; }
.brand { display: flex; align-items: center; gap: 8px; font-size: 13px; color: #8b909c;
  margin-bottom: 18px; letter-spacing: .3px; }
.brand b { color: #FF4500; }
@media print {
  body { background: #fff; padding: 0; }
  .page { box-shadow: none; border-radius: 0; padding: 0; max-width: none; }
}
"""


def _inline_html(text: str) -> str:
    safe = html_lib.escape(text)
    safe = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", safe)
    return safe


def to_html(markdown_text: str, title: str = "تقرير استشراف") -> str:
    blocks = parse_blocks(markdown_text)
    body: List[str] = []
    list_kind = None
    for kind, text in blocks:
        if kind in ("bullet", "numbered"):
            want = "ul" if kind == "bullet" else "ol"
            if list_kind != want:
                if list_kind:
                    body.append(f"</{list_kind}>")
                body.append(f"<{want}>")
                list_kind = want
            body.append(f"<li>{_inline_html(text)}</li>")
            continue
        if list_kind:
            body.append(f"</{list_kind}>")
            list_kind = None
        if kind == "h1":
            body.append(f"<h1>{_inline_html(text)}</h1>")
        elif kind == "h2":
            body.append(f"<h2>{_inline_html(text)}</h2>")
        elif kind == "h3":
            body.append(f"<h3>{_inline_html(text)}</h3>")
        elif kind == "quote":
            body.append(f"<blockquote><p>{_inline_html(text)}</p></blockquote>")
        elif kind == "rule":
            body.append("<hr>")
        elif kind == "table_row":
            body.append(f"<p>{_inline_html(text)}</p>")
        elif kind == "paragraph":
            body.append(f"<p>{_inline_html(text)}</p>")
    if list_kind:
        body.append(f"</{list_kind}>")

    return (
        "<!DOCTYPE html>\n<html lang=\"ar\" dir=\"rtl\">\n<head>\n"
        "<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        f"<title>{html_lib.escape(title)}</title>\n<style>{_HTML_STYLE}</style>\n</head>\n<body>\n"
        f"<div class=\"page\">\n<div class=\"brand\"><b>◈</b> استشراف المستقبل</div>\n"
        + "\n".join(body)
        + "\n</div>\n</body>\n</html>\n"
    )


# --------------------------------------------------------------------------
# Word (docx) — OOXML مولّد يدويًا
# --------------------------------------------------------------------------
def _docx_run(text: str, *, bold: bool = False, size_half_points: int = 24,
              color: str | None = None) -> str:
    props = [
        "<w:rFonts w:ascii=\"Cairo\" w:hAnsi=\"Cairo\" w:cs=\"Cairo\"/>",
        f"<w:sz w:val=\"{size_half_points}\"/>",
        f"<w:szCs w:val=\"{size_half_points}\"/>",
        "<w:rtl/>",
    ]
    if bold:
        props.append("<w:b/><w:bCs/>")
    if color:
        props.append(f"<w:color w:val=\"{color}\"/>")
    text = xml_escape(text)
    return (
        "<w:r><w:rPr>" + "".join(props) + "</w:rPr>"
        f"<w:t xml:space=\"preserve\">{text}</w:t></w:r>"
    )


def _docx_paragraph(text: str, *, bold: bool = False, size: int = 24,
                    color: str | None = None, spacing_before: int = 0,
                    spacing_after: int = 80, indent: int = 0) -> str:
    ppr = (
        "<w:pPr><w:bidi/><w:jc w:val=\"right\"/>"
        f"<w:spacing w:before=\"{spacing_before}\" w:after=\"{spacing_after}\" w:line=\"360\" w:lineRule=\"auto\"/>"
        + (f"<w:ind w:right=\"{indent}\"/>" if indent else "")
        + "</w:pPr>"
    )
    return "<w:p>" + ppr + _docx_run(text, bold=bold, size_half_points=size, color=color) + "</w:p>"


def to_docx(markdown_text: str, title: str = "تقرير استشراف") -> bytes:
    parts: List[str] = []
    parts.append(_docx_paragraph(title, bold=True, size=40, spacing_after=200))
    for kind, text in parse_blocks(markdown_text):
        if kind in ("blank", "rule"):
            continue
        if kind == "h1":
            parts.append(_docx_paragraph(text, bold=True, size=36, spacing_before=160, spacing_after=140))
        elif kind == "h2":
            parts.append(_docx_paragraph(text, bold=True, size=30, color="C2410C",
                                         spacing_before=240, spacing_after=120))
        elif kind == "h3":
            parts.append(_docx_paragraph(text, bold=True, size=26, spacing_before=160, spacing_after=100))
        elif kind == "quote":
            parts.append(_docx_paragraph(text, size=24, color="4B5563", indent=360))
        elif kind == "bullet":
            parts.append(_docx_paragraph("• " + text, size=24, indent=280))
        elif kind == "numbered":
            parts.append(_docx_paragraph(text, size=24, indent=280))
        else:
            parts.append(_docx_paragraph(text, size=24, spacing_after=120))

    document_xml = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>\n"
        "<w:document xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\">"
        "<w:body>" + "".join(parts) +
        "<w:sectPr><w:pgSz w:w=\"11906\" w:h=\"16838\"/>"
        "<w:pgMar w:top=\"1134\" w:right=\"1134\" w:bottom=\"1134\" w:left=\"1134\"/></w:sectPr>"
        "</w:body></w:document>"
    )

    content_types = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>\n"
        "<Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\">"
        "<Default Extension=\"rels\" ContentType=\"application/vnd.openxmlformats-package.relationships+xml\"/>"
        "<Default Extension=\"xml\" ContentType=\"application/xml\"/>"
        "<Override PartName=\"/word/document.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml\"/>"
        "</Types>"
    )
    rels = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>\n"
        "<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">"
        "<Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument\" Target=\"word/document.xml\"/>"
        "</Relationships>"
    )

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels)
        zf.writestr("word/document.xml", document_xml)
    return buffer.getvalue()


# --------------------------------------------------------------------------
# PDF
# --------------------------------------------------------------------------
def to_pdf(markdown_text: str, title: str = "تقرير استشراف") -> bytes:
    try:
        from fpdf import FPDF
        from fpdf.enums import Align
    except Exception as exc:  # pragma: no cover - يعتمد على بيئة النشر
        raise ExportError("مكتبة PDF غير متوفرة على الخادم") from exc

    if not os.path.exists(FONT_PATH):
        raise ExportError("ملف خط PDF غير موجود على الخادم")

    try:
        pdf = FPDF(format="A4")
        pdf.set_text_shaping(True)  # تشكيل الحروف العربية + الاتجاه
    except Exception as exc:  # pragma: no cover
        raise ExportError("تعذر تشغيل محرك تشكيل الحروف العربية") from exc

    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_font("cairo", "", FONT_PATH)
    pdf.add_page()
    pdf.set_margins(18, 18, 18)

    usable = pdf.w - 36

    def write(text: str, size: int, *, color=(27, 29, 34), gap: float = 4,
              justify: bool = False):
        pdf.set_font("cairo", "", size)
        pdf.set_text_color(*color)
        align = Align.J if justify else Align.R
        pdf.multi_cell(usable, size * 0.62, text, align=align, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(gap)

    write("استشراف المستقبل", 9, color=(150, 155, 165), gap=2)
    write(title, 19, gap=6)

    for kind, text in parse_blocks(markdown_text):
        if kind in ("blank", "rule"):
            continue
        if kind == "h1":
            write(text, 17, gap=6)
        elif kind == "h2":
            write(text, 14, color=(194, 65, 12), gap=5)
        elif kind == "h3":
            write(text, 12, gap=4)
        elif kind == "quote":
            write(text, 10.5, color=(75, 85, 99), gap=4)
        elif kind == "bullet":
            write("• " + text, 11, gap=2)
        elif kind == "numbered":
            write(text, 11, gap=2)
        else:
            write(text, 11, gap=3, justify=True)

    out = pdf.output()
    return bytes(out)


# --------------------------------------------------------------------------
# واجهة موحّدة
# --------------------------------------------------------------------------
def split_title(markdown_text: str, fallback: str = "تقرير استشراف") -> Tuple[str, str]:
    """يفصل أول عنوان H1 ليكون عنوان المستند، ويعيد (العنوان، بقية النص)."""
    lines = (markdown_text or "").splitlines()
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("# "):
            title = _strip_inline(stripped[2:])
            rest = "\n".join(lines[index + 1:]).lstrip("\n")
            return (title or fallback), rest
        break
    return fallback, markdown_text


def build_export(markdown_text: str, fmt: str, title: str = "تقرير استشراف") -> Tuple[bytes, str, str]:
    """يعيد (المحتوى، نوع MIME، الامتداد) للصيغة المطلوبة."""
    fmt = (fmt or "md").lower().strip()
    if fmt not in SUPPORTED_FORMATS:
        raise ExportError(f"صيغة غير مدعومة: {fmt}")
    mime, ext = CONTENT_TYPES[fmt]
    if not (markdown_text or "").strip():
        raise ExportError("لا يوجد نص للتقرير")

    doc_title, body_md = split_title(markdown_text, title)
    if fmt == "md":
        data = markdown_text.encode("utf-8")
    elif fmt == "txt":
        data = to_text(markdown_text).encode("utf-8")
    elif fmt == "html":
        data = to_html(markdown_text, doc_title).encode("utf-8")
    elif fmt == "docx":
        data = to_docx(body_md, doc_title)
    else:
        data = to_pdf(body_md, doc_title)
    return data, mime, ext
