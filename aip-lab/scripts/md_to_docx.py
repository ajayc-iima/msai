#!/usr/bin/env python3
"""Render the ConfAI markdown documents to editable .docx files.

    python scripts/md_to_docx.py

The shipped PDFs (scripts/render_md_pdfs.py) are laid out by Chromium, so
they are not editable. These .docx files are the SAME source rendered with
native Word constructs - real heading styles, real tables, real lists,
live hyperlinks - so the document can be edited in Word, Google Docs or
LibreOffice and re-exported to PDF from there.

Outputs:
    vidhi/ConfAI_Vidhi_Firewall_Report.docx   <- vidhi/CONF_AI_PAPER.md
    vidhi/ConfAI_Vidhi_Firewall_Abstract.docx <- vidhi/POSTER_ABSTRACT.md
"""
from __future__ import annotations

import re
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ROOT = Path(__file__).resolve().parents[1]

DOCS = [
    (ROOT / "vidhi" / "CONF_AI_PAPER.md", ROOT / "vidhi" / "ConfAI_Vidhi_Firewall_Report.docx"),
    (ROOT / "vidhi" / "POSTER_ABSTRACT.md", ROOT / "vidhi" / "ConfAI_Vidhi_Firewall_Abstract.docx"),
]

INK = RGBColor(0x22, 0x30, 0x2B)
ACCENT = RGBColor(0xB4, 0x53, 0x0A)
ACCENT_DK = RGBColor(0x92, 0x40, 0x0E)
TEAL = RGBColor(0x13, 0x4E, 0x4A)
SOFT = RGBColor(0x3E, 0x4A, 0x44)
MUTED = RGBColor(0x6B, 0x72, 0x80)
TINT = "F5EFE0"
PAPER = "FAF6EE"
LINE = "E3DCCB"

SERIF = "Georgia"
MONO = "Consolas"


# --------------------------------------------------------------------------
# low-level docx helpers
# --------------------------------------------------------------------------
def _shade(el, fill: str) -> None:
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    el.append(shd)


def shade_paragraph(p, fill: str) -> None:
    _shade(p._p.get_or_add_pPr(), fill)


def shade_cell(cell, fill: str) -> None:
    _shade(cell._tc.get_or_add_tcPr(), fill)


def para_border(p, edge: str, color: str, size: int = 6, space: int = 6) -> None:
    pPr = p._p.get_or_add_pPr()
    bdr = pPr.find(qn("w:pBdr"))
    if bdr is None:
        bdr = OxmlElement("w:pBdr")
        pPr.append(bdr)
    el = OxmlElement(f"w:{edge}")
    el.set(qn("w:val"), "single")
    el.set(qn("w:sz"), str(size))
    el.set(qn("w:space"), str(space))
    el.set(qn("w:color"), color)
    bdr.append(el)


def set_run_font(run, name: str, size: Pt | None = None, color: RGBColor | None = None) -> None:
    run.font.name = name
    rPr = run._element.get_or_add_rPr()
    rf = rPr.find(qn("w:rFonts"))
    if rf is None:
        rf = OxmlElement("w:rFonts")
        rPr.append(rf)
    for a in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        rf.set(qn(a), name)
    if size is not None:
        run.font.size = size
    if color is not None:
        run.font.color.rgb = color


def add_hyperlink(par, url: str, text: str, size: Pt, bold: bool = False):
    part = par.part
    r_id = part.relate_to(
        url,
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink",
        is_external=True,
    )
    link = OxmlElement("w:hyperlink")
    link.set(qn("r:id"), r_id)
    r = OxmlElement("w:r")
    rPr = OxmlElement("w:rPr")
    rf = OxmlElement("w:rFonts")
    for a in ("w:ascii", "w:hAnsi", "w:cs"):
        rf.set(qn(a), MONO if url.startswith("http") else SERIF)
    rPr.append(rf)
    col = OxmlElement("w:color")
    col.set(qn("w:val"), "B4530A")
    rPr.append(col)
    u = OxmlElement("w:u")
    u.set(qn("w:val"), "single")
    rPr.append(u)
    sz = OxmlElement("w:sz")
    sz.set(qn("w:val"), str(int(size.pt * 2)))
    rPr.append(sz)
    if bold:
        rPr.append(OxmlElement("w:b"))
    r.append(rPr)
    t = OxmlElement("w:t")
    t.text = text
    t.set(qn("xml:space"), "preserve")
    r.append(t)
    link.append(r)
    par._p.append(link)
    return link


def add_field(par, instr: str) -> None:
    """Insert a Word field (TOC, PAGE, ...)."""
    r1 = par.add_run()
    fc = OxmlElement("w:fldChar")
    fc.set(qn("w:fldCharType"), "begin")
    r1._r.append(fc)
    r2 = par.add_run()
    it = OxmlElement("w:instrText")
    it.set(qn("xml:space"), "preserve")
    it.text = instr
    r2._r.append(it)
    r3 = par.add_run()
    fc = OxmlElement("w:fldChar")
    fc.set(qn("w:fldCharType"), "separate")
    r3._r.append(fc)
    r4 = par.add_run("...")
    r5 = par.add_run()
    fc = OxmlElement("w:fldChar")
    fc.set(qn("w:fldCharType"), "end")
    r5._r.append(fc)


# --------------------------------------------------------------------------
# inline markdown -> runs
# --------------------------------------------------------------------------
_INLINE = re.compile(
    r"(`[^`]+`)"                                  # code
    r"|(\*\*[^*]+\*\*)"                           # bold
    r"|(?<!\*)\*([^*\n]+)\*(?!\*)"                 # italic
    r"|(\[[^\]]+\]\(https?://[^)\s]+\))"           # link
    r"|((?<![\w>])https?://[^\s<)\]]+)"            # bare url
)


def add_inline(par, text: str, size: Pt, base_color: RGBColor = INK, bold: bool = False) -> None:
    pos = 0
    for m in _INLINE.finditer(text):
        if m.start() > pos:
            r = par.add_run(text[pos:m.start()])
            set_run_font(r, SERIF, size, base_color)
            r.bold = bold
        if m.group(1):
            code = m.group(1)[1:-1]
            if re.fullmatch(r"https?://[^\s]+", code):
                # a URL written in backticks should still be clickable
                add_hyperlink(par, code, code, Pt(size.pt - 1))
            else:
                r = par.add_run(code)
                set_run_font(r, MONO, Pt(size.pt - 1))
                r.font.color.rgb = ACCENT_DK
                _shade(r._element.get_or_add_rPr(), TINT)
        elif m.group(2):
            r = par.add_run(m.group(2)[2:-2])
            set_run_font(r, SERIF, size, base_color)
            r.bold = True
        elif m.group(3):
            r = par.add_run(m.group(3))
            set_run_font(r, SERIF, size, base_color)
            r.italic = True
        elif m.group(4):
            label, url = re.match(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", m.group(4)).groups()
            add_hyperlink(par, url, label, size)
        else:
            add_hyperlink(par, m.group(5), m.group(5), size)
        pos = m.end()
    if pos < len(text):
        r = par.add_run(text[pos:])
        set_run_font(r, SERIF, size, base_color)
        r.bold = bold


# --------------------------------------------------------------------------
# markdown blocks
# --------------------------------------------------------------------------
def _cells(row: str) -> list[str]:
    return [c.strip().replace("\\|", "|") for c in row.strip().strip("|").split("|")]


def convert(md: str, doc: Document) -> None:
    lines = md.replace("\r\n", "\n").split("\n")
    i = 0
    body_size = Pt(10.5)

    while i < len(lines):
        raw = lines[i]
        s = raw.strip()

        if not s:
            i += 1
            continue

        # code block
        if s.startswith("```"):
            i += 1
            code = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code.append(lines[i])
                i += 1
            i += 1
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(4)
            p.paragraph_format.space_after = Pt(8)
            p.paragraph_format.left_indent = Cm(0.2)
            r = p.add_run("\n".join(code))
            set_run_font(r, MONO, Pt(8.5), SOFT)
            shade_paragraph(p, TINT)
            continue

        # heading
        m = re.match(r"^(#{1,6})\s+(.*)$", s)
        if m:
            lvl = len(m.group(1))
            text = m.group(2)
            if lvl == 1:
                p = doc.add_paragraph()
                p.paragraph_format.space_after = Pt(8)
                r = p.add_run(text)
                set_run_font(r, SERIF, Pt(19), ACCENT_DK)
                r.bold = True
                para_border(p, "bottom", LINE, size=8, space=4)
                p.style = doc.styles["Title"]
                for rr in p.runs:
                    set_run_font(rr, SERIF, Pt(19), ACCENT_DK)
                    rr.bold = True
            else:
                p = doc.add_paragraph()
                p.paragraph_format.space_before = Pt(14 if lvl == 2 else 10)
                p.paragraph_format.space_after = Pt(4)
                p.paragraph_format.keep_with_next = True
                r = p.add_run(text)
                if lvl == 2:
                    set_run_font(r, SERIF, Pt(13.5), ACCENT)
                    r.bold = True
                elif lvl == 3:
                    set_run_font(r, SERIF, Pt(11.5), TEAL)
                    r.bold = True
                else:
                    set_run_font(r, SERIF, Pt(10.5), SOFT)
                    r.bold = True
            i += 1
            continue

        # horizontal rule
        if re.fullmatch(r"-{3,}|_{3,}|\*{3,}", s):
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(6)
            p.paragraph_format.space_after = Pt(8)
            para_border(p, "bottom", LINE, size=6, space=1)
            i += 1
            continue

        # table
        if s.startswith("|") and i + 1 < len(lines) and re.fullmatch(r"\|?[\s:|-]+\|?", lines[i + 1].strip()):
            head = _cells(s)
            i += 2
            body = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                body.append(_cells(lines[i].strip()))
                i += 1
            t = doc.add_table(rows=1, cols=len(head))
            t.style = "Table Grid"
            t.autofit = True
            for j, c in enumerate(head):
                cell = t.rows[0].cells[j]
                cell.text = ""
                p = cell.paragraphs[0]
                p.paragraph_format.space_before = Pt(1)
                p.paragraph_format.space_after = Pt(1)
                add_inline(p, c, Pt(9), SOFT, bold=True)
                shade_cell(cell, TINT)
            for row in body:
                cells = t.add_row().cells
                for j, c in enumerate(row[: len(head)]):
                    cells[j].text = ""
                    p = cells[j].paragraphs[0]
                    p.paragraph_format.space_before = Pt(1)
                    p.paragraph_format.space_after = Pt(1)
                    add_inline(p, c, Pt(9))
            doc.add_paragraph().paragraph_format.space_after = Pt(2)
            continue

        # blockquote
        if s.startswith(">"):
            quote = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                quote.append(lines[i].strip().lstrip(">").strip())
                i += 1
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(4)
            p.paragraph_format.space_after = Pt(8)
            p.paragraph_format.left_indent = Cm(0.4)
            add_inline(p, " ".join(x for x in quote if x), Pt(10), SOFT)
            shade_paragraph(p, PAPER)
            para_border(p, "left", "B4530A", size=18, space=6)
            continue

        # list
        if re.match(r"^[-*]\s+", s) or re.match(r"^\d+\.\s+", s):
            ordered = bool(re.match(r"^\d+\.", s))
            while i < len(lines):
                m2 = re.match(r"^([-*]|\d+\.)\s+(.*)$", lines[i].strip())
                if not m2:
                    break
                p = doc.add_paragraph(style="List Number" if ordered else "List Bullet")
                p.paragraph_format.space_before = Pt(0)
                p.paragraph_format.space_after = Pt(2)
                p.paragraph_format.left_indent = Cm(0.7)
                add_inline(p, m2.group(2), body_size)
                i += 1
            continue

        # paragraph
        para = []
        while i < len(lines):
            t = lines[i].strip()
            if not t or t.startswith(("#", "|", ">", "```")) or re.match(r"^[-*]\s+", t) or re.match(r"^\d+\.\s+", t):
                break
            para.append(t)
            i += 1
        if para:
            p = doc.add_paragraph()
            p.paragraph_format.space_after = Pt(6)
            p.paragraph_format.line_spacing = 1.35
            add_inline(p, " ".join(para), body_size)


def build(md_path: Path, out_path: Path) -> None:
    doc = Document()

    # page setup: A4, 16mm margins (same as the PDF render)
    sec = doc.sections[0]
    sec.page_width = Cm(21.0)
    sec.page_height = Cm(29.7)
    for attr in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
        setattr(sec, attr, Cm(1.6))

    # base style
    normal = doc.styles["Normal"]
    normal.font.name = SERIF
    normal.font.size = Pt(10.5)
    normal.font.color.rgb = INK
    rf = normal.element.rPr.rFonts
    for a in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        rf.set(qn(a), SERIF)

    # a TOC the user can refresh (F9) - Word needs the field updated
    toc_head = doc.add_paragraph()
    r = toc_head.add_run("Contents")
    set_run_font(r, SERIF, Pt(13.5), ACCENT)
    r.bold = True
    toc_head.paragraph_format.space_after = Pt(4)
    toc = doc.add_paragraph()
    add_field(toc, r'TOC \o "1-2" \h \z \u')
    hint = doc.add_paragraph()
    r = hint.add_run("(right-click → Update Field to build the table of contents)")
    set_run_font(r, SERIF, Pt(8.5), MUTED)
    r.italic = True
    doc.add_page_break()

    convert(md_path.read_text(encoding="utf-8"), doc)

    # footer: title + page number
    footer = sec.footer
    fp = footer.paragraphs[0]
    fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = fp.add_run(f"{md_path.stem.replace('_', ' ')}  ·  page ")
    set_run_font(r, SERIF, Pt(8.5), MUTED)
    add_field(fp, "PAGE")
    for rr in fp.runs:
        set_run_font(rr, SERIF, Pt(8.5), MUTED)

    core = doc.core_properties
    core.title = md_path.stem.replace("_", " ")
    core.author = "Ajay Choudhary"
    core.comments = "Editable Word version generated from the markdown source by scripts/md_to_docx.py."

    doc.save(out_path)
    print(f"saved {out_path} ({out_path.stat().st_size / 1024:.1f} KB)")


def main() -> int:
    missing = [str(m) for m, _ in DOCS if not m.exists()]
    if missing:
        print("missing sources:", missing)
        return 1
    for md_path, out_path in DOCS:
        build(md_path, out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
