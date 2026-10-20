"""Capture demo screenshots for the ConfAI deck. Real UI, real answers."""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "vidhi" / "deck_shots"
OUT.mkdir(exist_ok=True)

SHOTS = [
    ("shot_pass.png", "What was all-India LFPR for age 15+ in usual status in PLFS 2025?"),
    ("shot_bihar.png", "mpce for bihar"),
    ("shot_warn.png", "What was female LFPR in Bihar in PLFS 2025?"),
    ("shot_refuse.png", "Will unemployment fall in 2027?"),
]

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1280, "height": 900})
    pg.goto("http://127.0.0.1:8001/demo", wait_until="networkidle")
    pg.evaluate("() => {localStorage.setItem('vidhi-theme','light');"
                "document.documentElement.dataset.theme='light';}")
    pg.wait_for_timeout(400)
    pg.screenshot(path=str(OUT / "shot_home.png"))
    print("home ok")
    for fname, question in SHOTS:
        pg.fill("#q", question)
        pg.press("#q", "Enter")
        pg.wait_for_selector("#resH", timeout=90000)
        pg.wait_for_timeout(600)
        pg.evaluate("() => {if(document.activeElement)document.activeElement.blur();}")
        pg.wait_for_timeout(200)
        pg.locator("article.card").first.screenshot(path=str(OUT / fname))
        print(fname, "ok")
    b.close()
print("done")
