#!/usr/bin/env python3
"""Render the A1 ConfAI poster (HTML) to a print-ready PDF.

Uses Playwright/Chromium. Output: vidhi/ConfAI_Vidhi_A1_Poster.pdf
A1 = 594mm x 841mm portrait, exact page size, backgrounds printed.

Run: python scripts/render_poster.py
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "vidhi" / "ConfAI_Vidhi_A1_Poster.html"
OUT = ROOT / "vidhi" / "ConfAI_Vidhi_A1_Poster.pdf"


def main() -> int:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 2245, "height": 3179})
        page.goto(SRC.as_uri())
        # Let fonts/layout settle.
        page.wait_for_timeout(300)
        page.pdf(
            path=str(OUT),
            prefer_css_page_size=True,
            print_background=True,
            margin={"top": "0", "bottom": "0", "left": "0", "right": "0"},
        )
        browser.close()
    print(f"saved {OUT} ({OUT.stat().st_size / 1024:.1f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
