#!/usr/bin/env python3
"""Render the ConfAI markdown documents to print-ready PDFs.

    python scripts/render_md_pdfs.py

Uses the same Playwright/Chromium engine as the A1 poster (no extra
dependency, no network). Re-run after editing CONF_AI_PAPER.md or
POSTER_ABSTRACT.md so the shipped PDFs never drift from the sources.

Outputs:
    vidhi/ConfAI_Vidhi_Firewall_Report.pdf   <- vidhi/CONF_AI_PAPER.md
    vidhi/ConfAI_Vidhi_Firewall_Abstract.pdf <- vidhi/POSTER_ABSTRACT.md
"""
from __future__ import annotations

import html
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DOCS = [
    (ROOT / "vidhi" / "CONF_AI_PAPER.md", ROOT / "vidhi" / "ConfAI_Vidhi_Firewall_Report.pdf", False),
    (ROOT / "vidhi" / "POSTER_ABSTRACT.md", ROOT / "vidhi" / "ConfAI_Vidhi_Firewall_Abstract.pdf", True),
]


def css(compact: bool) -> str:
    """Editorial stylesheet. `compact` fits the one-page abstract."""
    body, tbl, code = (9.5, 8.5, 8.5) if compact else (10.5, 9.5, 9)
    h1, h2, h3 = (17, 12.5, 11) if compact else (19, 13.5, 11.5)
    lh, gap = ("1.3", "3px") if compact else ("1.45", "6px")
    cell, li_m, h2_m = (("2px 5px", "1px", "10px 0 3px") if compact
                        else ("3px 6px", "2px", "14px 0 4px"))
    return f"""
body{{font:{body}pt/{lh} Georgia,'Times New Roman',serif;color:#22302B;margin:0}}
h1{{font-size:{h1}pt;color:#92400E;border-bottom:2px solid #E3DCCB;padding-bottom:5px;margin:0 0 8px}}
h2{{font-size:{h2}pt;color:#B4530A;margin:{h2_m}}}
h3{{font-size:{h3}pt;color:#134E4A;margin:10px 0 3px}}
h4{{font-size:10.5pt;color:#3E4A44;margin:8px 0 3px}}
p{{margin:{gap} 0}}
code{{font:{code}pt ui-monospace,SFMono-Regular,Consolas,monospace;background:#F5EFE0;
     padding:1px 3px;border-radius:3px}}
pre{{background:#F5EFE0;padding:8px;border-radius:6px;overflow:auto;margin:6px 0}}
pre code{{background:none;padding:0}}
table{{border-collapse:collapse;width:100%;margin:8px 0;font-size:{tbl}pt}}
th,td{{border:1px solid #E3DCCB;padding:{cell};text-align:left;vertical-align:top}}
th{{background:#F5EFE0}}
blockquote{{border-left:3px solid #B4530A;margin:8px 0;padding:3px 10px;
           color:#3E4A44;background:#FAF6EE}}
ul,ol{{margin:4px 0 4px 20px;padding:0}}
li{{margin:{li_m}}}
hr{{border:none;border-top:1px solid #E3DCCB;margin:12px 0}}
a{{color:#B4530A;text-decoration:none}}
"""


def _esc(s: str) -> str:
    return html.escape(s, quote=False)


def _inline(s: str) -> str:
    s = _esc(s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<![\w*])\*([^*\n]+)\*(?![\w*])", r"<em>\1</em>", s)
    s = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<a href="\2">\1</a>', s)
    s = re.sub(r"(?<!['\">=(/])\b(https?://[^\s<)\]]+)", r'<a href="\1">\1</a>', s)
    return s


def _cells(row: str) -> list[str]:
    return [c.strip() for c in row.strip().strip("|").split("|")]


def md_to_html(md: str) -> str:
    lines = md.replace("\r\n", "\n").split("\n")
    out: list[str] = []
    i, para = 0, []

    def flush():
        if para:
            out.append("<p>" + "<br>".join(_inline(x) for x in para) + "</p>")
            para.clear()

    while i < len(lines):
        ln = lines[i]
        s = ln.strip()
        if not s:
            flush()
            i += 1
            continue
        if s.startswith("```"):
            flush()
            i += 1
            code = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code.append(lines[i])
                i += 1
            i += 1
            out.append("<pre><code>" + _esc("\n".join(code)) + "</code></pre>")
            continue
        m = re.match(r"^(#{1,6})\s+(.*)$", s)
        if m:
            flush()
            lvl = min(len(m.group(1)), 4)
            out.append(f"<h{lvl}>{_inline(m.group(2))}</h{lvl}>")
            i += 1
            continue
        if re.fullmatch(r"-{3,}|_{3,}|\*{3,}", s):
            flush()
            out.append("<hr>")
            i += 1
            continue
        if s.startswith("|") and i + 1 < len(lines) and re.fullmatch(
            r"\|?[\s:|-]+\|?", lines[i + 1].strip()
        ):
            flush()
            head = _cells(s)
            i += 2
            body = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                body.append(_cells(lines[i].strip()))
                i += 1
            out.append(
                "<table><thead><tr>"
                + "".join(f"<th>{_inline(c)}</th>" for c in head)
                + "</tr></thead><tbody>"
                + "".join(
                    "<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in r) + "</tr>"
                    for r in body
                )
                + "</tbody></table>"
            )
            continue
        if s.startswith(">"):
            flush()
            quote = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                quote.append(lines[i].strip().lstrip(">").strip())
                i += 1
            out.append(
                "<blockquote>" + "<br>".join(_inline(x) for x in quote if x) + "</blockquote>"
            )
            continue
        if re.match(r"^[-*]\s+", s) or re.match(r"^\d+\.\s+", s):
            flush()
            ordered = bool(re.match(r"^\d+\.", s))
            items = []
            while i < len(lines):
                m2 = re.match(r"^([-*]|\d+\.)\s+(.*)$", lines[i].strip())
                if not m2:
                    break
                items.append(_inline(m2.group(2)))
                i += 1
            tag = "ol" if ordered else "ul"
            out.append(f"<{tag}>" + "".join(f"<li>{x}</li>" for x in items) + f"</{tag}>")
            continue
        para.append(s)
        i += 1
    flush()
    return "\n".join(out)


def render(md_path: Path, pdf_path: Path, compact: bool = False) -> None:
    body = md_to_html(md_path.read_text(encoding="utf-8"))
    html_doc = (
        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
        f"<style>{css(compact)}</style></head><body>{body}</body></html>"
    )
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content(html_doc, wait_until="load")
        page.pdf(
            path=str(pdf_path),
            format="A4",
            print_background=True,
            scale=0.92 if compact else 1.0,
            margin={
                "top": "10mm" if compact else "16mm",
                "bottom": "10mm" if compact else "16mm",
                "left": "11mm" if compact else "16mm",
                "right": "11mm" if compact else "16mm",
            },
        )
        browser.close()
    print(f"saved {pdf_path} ({pdf_path.stat().st_size / 1024:.1f} KB)")


def main() -> int:
    missing = [str(m) for m, _, _ in DOCS if not m.exists()]
    if missing:
        print("missing sources:", missing, file=sys.stderr)
        return 1
    for md_path, pdf_path, compact in DOCS:
        render(md_path, pdf_path, compact)
    return 0


if __name__ == "__main__":
    sys.exit(main())
