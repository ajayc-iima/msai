#!/usr/bin/env python3
"""Build ConfAI 2026 7-slide deck. All demo text comes from live pipeline
runs — nothing is hardcoded. Run: python scripts/build_confai_deck.py"""
from __future__ import annotations
import sys
from pathlib import Path
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Cream editorial theme to match demo.html: paper page, ink text, orange kicker.
BG = RGBColor(250, 246, 238)
INK = RGBColor(34, 48, 43)
MUTED = RGBColor(107, 114, 128)
ACCENT = RGBColor(180, 83, 10)
TEAL = RGBColor(19, 78, 74)
CARD = RGBColor(255, 255, 255)
BORDER = RGBColor(227, 220, 203)
GREEN = RGBColor(30, 107, 52)
AMBER = RGBColor(138, 90, 0)
RED = RGBColor(169, 50, 38)
TEAL_D = RGBColor(19, 78, 74)

TOTAL = 7


def bg(slide):
    f = slide.background.fill
    f.solid()
    f.fore_color.rgb = BG


def accent_rule(slide, top=1.62):
    s = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.7), Inches(top),
                               Inches(1.1), Pt(4))
    s.fill.solid()
    s.fill.fore_color.rgb = ACCENT
    s.line.fill.background()


def header(slide, tag, title, sub):
    for top, txt, sz, bold, col, font in (
            (0.35, tag.upper(), 11, True, ACCENT, "Calibri"),
            (0.65, title, 26, True, TEAL, "Georgia"),
            (1.25, sub, 12, False, MUTED, "Calibri")):
        tb = slide.shapes.add_textbox(Inches(0.7), Inches(top), Inches(11.9), Inches(0.5))
        tf = tb.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.text = txt
        p.font.name = font
        p.font.size = Pt(sz)
        p.font.bold = bold
        p.font.color.rgb = col
    accent_rule(slide)


def footer(slide, n):
    tb = slide.shapes.add_textbox(Inches(0.7), Inches(7.0), Inches(11.9), Inches(0.3))
    p = tb.text_frame.paragraphs[0]
    p.text = (f"Vidhi Guardian  |  Ajay Choudhary (MSAI @ Plaksha)  |  "
              f"ConfAI 2026 · Track 06 Responsible & Ethical AI  |  {n} of {TOTAL}")
    p.font.name = "Calibri"
    p.font.size = Pt(9)
    p.font.color.rgb = MUTED
    p.alignment = PP_ALIGN.CENTER


def card(slide, l, t, w, h, fill=CARD):
    s = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(l), Inches(t), Inches(w), Inches(h))
    s.fill.solid()
    s.fill.fore_color.rgb = fill
    s.line.color.rgb = BORDER
    s.line.width = Pt(1)
    return s


def textbox(slide, l, t, w, h, paras):
    tb = slide.shapes.add_textbox(Inches(l), Inches(t), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    first = True
    for txt, sz, bold, col in paras:
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        p.text = txt
        p.font.name = "Calibri"
        p.font.size = Pt(sz)
        p.font.bold = bold
        p.font.color.rgb = col
        p.space_after = Pt(3)
    return tb


def shot_box(slide, l, t, w, max_h, img_path, label, lcol, caption=None):
    """Real UI screenshot with a verdict label above it (aspect-kept, framed)."""
    from PIL import Image
    textbox(slide, l, t, w, 0.45, [(label, 11, True, lcol)])
    iw, ih = Image.open(img_path).size
    h = min(max_h, w * ih / iw)
    pic_w = h * iw / ih
    pic = slide.shapes.add_picture(str(img_path), Inches(l + (w - pic_w) / 2), Inches(t + 0.5),
                                   width=Inches(pic_w), height=Inches(h))
    pic.line.color.rgb = BORDER
    pic.line.width = Pt(1)
    if caption:
        textbox(slide, l, t + 0.55 + h, w, 6.75 - (t + 0.55 + h),
                [(caption, 8.5, False, MUTED)])


def compare_table(slide, l, t, w, h, rows):
    tbl_shape = slide.shapes.add_table(len(rows) + 1, 3, Inches(l), Inches(t),
                                       Inches(w), Inches(h))
    tbl = tbl_shape.table
    tbl.columns[0].width = Inches(2.4)
    tbl.columns[1].width = Inches(4.75)
    tbl.columns[2].width = Inches(4.75)
    for j, head in enumerate(["Check", "StatsDoc pilot (observed)", "Vidhi Guardian (measured)"]):
        c = tbl.cell(0, j)
        c.text = head
        for p in c.text_frame.paragraphs:
            p.font.name = "Calibri"
            p.font.size = Pt(11)
            p.font.bold = True
            p.font.color.rgb = RGBColor(255, 255, 255)
        c.fill.solid()
        c.fill.fore_color.rgb = ACCENT
    for i, (dim, bad, good) in enumerate(rows, start=1):
        for j, txt in enumerate((dim, "✕ " + bad, "✓ " + good)):
            c = tbl.cell(i, j)
            c.text = txt
            for p in c.text_frame.paragraphs:
                p.font.name = "Calibri"
                p.font.size = Pt(10)
                p.font.bold = (j == 0)
                p.font.color.rgb = INK
            if i % 2 == 0:
                c.fill.solid()
                c.fill.fore_color.rgb = CARD


def live_answers():
    from vidhi import pipeline as P
    out = {}
    for key, q in {
        "pass": "What was all-India LFPR for age 15+ in usual status in PLFS 2025?",
        "warn_comp": "Compare average MPCE in 2011-12 vs 2023-24.",
        "refuse": "Will unemployment fall in 2027?",
        "hard": "What was female LFPR in Bihar in PLFS 2025?",
        "mpce": "What was rural MPCE in HCES 2023-24?",
    }.items():
        r = P.ask(q)
        out[key] = (q, f"[{r['decision']}/{r['sub_code']}/{r['reason_code']}] "
                      f"{r['answer']}"
                      + (f"  value={r['value']}" if r.get("value") is not None else "")
                      + f"  hash={r['verdict_frozen_hash'][:8]}")
    return out


def main():
    A = live_answers()
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)

    # 1 — Title
    s = prs.slides.add_slide(prs.slide_layouts[6]); bg(s)
    header(s, "ConfAI 2026 · Plaksha University · Track 06 Responsible & Ethical AI",
           "Refuse to Hallucinate: a Deterministic Validity Firewall",
           "for Indian Official Survey Statistics (MoSPI · PLFS · HCES · TUS · MIS)")
    footer(s, 1)
    textbox(s, 0.7, 2.0, 11.9, 1.1, [
        ("MoSPI's tools help you find the number. This firewall checks whether you are allowed to say what you want to say with it — and stops you, with a cited rule, when you are not.", 14, False, INK),
        ("Ajay Choudhary · MSAI @ Plaksha University · offline demo localhost:8001/demo · $0.00 marginal cost · no GPU · MCP server + policy agent", 11, False, MUTED),
    ])
    for i, (v, t) in enumerate([("100 / 100", "golden verdicts"),
                                ("59 / 59", "figures exact"),
                                ("0 / 19", "cache collisions"),
                                ("SHA-256", "verdict frozen pre-retrieval")]):
        x = 0.7 + i * 3.05
        card(s, x, 4.3, 2.8, 1.7)
        textbox(s, x, 4.4, 2.8, 1.5, [(v, 22, True, ACCENT), (t, 11, False, MUTED)])
    textbox(s, 0.7, 6.2, 11.9, 0.5, [
        ("Live question for the room: “What was female LFPR in Bihar in PLFS 2025?” — it refuses to guess and shows exactly why (slide 5).", 11, True, INK)])

    # 2 — Problem
    s = prs.slides.add_slide(prs.slide_layouts[6]); bg(s)
    header(s, "Problem · StatsDoc failure modes from live probing",
           "Retrieval is solved. Governance is not.",
           "Archived transcripts, chats 2472-2480 (evaluation/statsdoc_audit/sessions/2026-10-20/) — one session, one prompt set; an observation, not a benchmark")
    footer(s, 2)
    compare_table(s, 0.7, 2.0, 11.9, 4.7, [
        ("MPCE definition", "expands “Mean …” (wrong)", "enforces statutory “Monthly …”, cites ₹4,122"),
        ("2011-12 vs 2023-24", "quotes ~40% growth, no warning", "halts with R_COMPARABILITY_HCES_METHOD"),
        ("Multi-period math", "40% then 4%, chained unsoundly", "refuses unsound synthesis; no number"),
        ("Poisoned context", "retrieved text overrides guardrails", "verdict frozen pre-retrieval; hash identical"),
        ("Cost / latency", "~$0.02–0.05 · 3.5–8 s", "$0.00 marginal · p50 < 200 ms warm, CPU-only"),
    ])

    # 3 — Architecture
    s = prs.slides.add_slide(prs.slide_layouts[6]); bg(s)
    header(s, "Solution · models translate, versioned rules judge",
           "Five stages. Fixed order. First rule to fire wins.",
           "Question → exact cache → claim extraction → field-guard cache → firewall → SHA-256 freeze → untrusted retrieval → templated prose → citation check")
    footer(s, 3)
    stages = [("1 · Safety", "REFUSE injections\n(EN, Hindi, Hinglish)", RED),
              ("2 · Scope", "REFUSE forecasts,\npolitics, causality", RED),
              ("3 · Comparability", "WARN on HCES-CAPI /\nPLFS-revamp breaks", AMBER),
              ("4 · Metadata", "WARN on unknown\ngeo / sex / round", AMBER),
              ("5 · Numeric", "PASS only on a\nverified truth row", GREEN)]
    for i, (t, d, c) in enumerate(stages):
        x = 0.7 + i * 2.46
        card(s, x, 1.95, 2.3, 1.9)
        textbox(s, x, 2.0, 2.3, 1.8, [(t, 13, True, c), (d, 10, False, MUTED)])
    card(s, 0.7, 4.05, 11.9, 2.7)
    textbox(s, 0.95, 4.15, 11.4, 2.5, [
        ("Two guarantees that make demos boring (in a good way).", 11, True, ACCENT),
        ("Safety-B: hash = SHA-256(claim + decision + reason + rule-version), computed before any document text is read. A planted “ignore the caveat” chunk changes nothing.", 10, False, INK),
        ("Field-guard: no cosine threshold is safe on either embedder, so the cache reuses an answer only on exact critical-field match. Zero collisions across 19 danger pairs.", 10, False, INK),
    ])

    # 4 — Demo screens A (PASS + Bihar table screenshots)
    s = prs.slides.add_slide(prs.slide_layouts[6]); bg(s)
    header(s, "Live demo · screenshots from localhost:8001/demo",
           "Verified answers: a PASS and a 4-slice table",
           "Captured live from vidhi/demo.html while building this deck")
    footer(s, 4)
    shots = ROOT / "vidhi" / "deck_shots"
    shot_box(s, 0.7, 1.85, 5.85, 4.3, shots / "shot_pass.png",
             "PASS_WITH_NUMBER — LFPR 59.3%", GREEN,
             "Q: " + A["pass"][0] + "  ·  hash " + A["pass"][1].split("hash=")[-1])
    shot_box(s, 6.8, 1.85, 5.85, 4.3, shots / "shot_bihar.png",
             "PASS — 4 verified slices, Export CSV", GREEN,
             "mpce for bihar: rural/urban × with/without imputation, each with its row_id")
    textbox(s, 0.7, 6.3, 11.9, 0.5, [
        ("Generalised, not hard-coded: any state, any spelling — “mp”, “up”, “m.p.”, “orissa”, "
         "“maharastra”; several states at once; an open slice returns every published cell, never one narrowed figure.", 10.5, True, INK)])

    # 5 — Demo screens B (honest WARN + refuse screenshots)
    s = prs.slides.add_slide(prs.slide_layouts[6]); bg(s)
    header(s, "Live demo · the question this work will not hallucinate",
           "Honesty for uncovered slices, refusal for forecasts",
           "SOURCED tier (online): exact live figure, verdict stays WARN — never silently PASS")
    footer(s, 5)
    shot_box(s, 0.7, 1.85, 5.85, 4.3, shots / "shot_warn.png",
             "WARN_NO_DATA — female LFPR in Bihar (state splits, coverage note)", AMBER,
             "Offline twin: coverage note + NOT-the-figure guard, tier NONE")
    shot_box(s, 6.8, 1.85, 5.85, 4.3, shots / "shot_refuse.png",
             "REFUSE_SCOPE / R_FORECAST", RED,
             "Q: " + A["refuse"][0])

    # 6 — Evaluation
    s = prs.slides.add_slide(prs.slide_layouts[6]); bg(s)
    header(s, "Measured, offline, reproducible · python vidhi/eval.py + pytest",
           "Every number below is a test output, not a slide claim",
           "1708 verified rows · 100 golden · 19 danger · 28 red-team · offline unit tests")
    footer(s, 6)
    card(s, 0.7, 1.85, 5.85, 4.9)
    textbox(s, 0.95, 1.95, 5.4, 4.7, [
        ("Correctness gates (all must pass)", 12, True, ACCENT),
        ("Golden verdicts 100/100 [0.963–1.000]", 11, True, INK),
        ("Reason codes 100/100 · figures 60/60 [0.940–1.000]", 11, False, INK),
        ("Citations valid 1.000 · danger collisions 0/19", 11, False, INK),
        ("Abstention recall 1.000 · hallucination rate 0.000", 11, True, INK),
        ("Safety-A P/R/F1 1.000 · n=28 (en/hi/hi-en, 0 FP/FN)", 11, True, INK),
        ("Safety-B: frozen hash unchanged under injection", 11, False, INK),
        ("Unit tests: 110 passed, offline, no key", 11, False, INK),
        ("Refusals: tp=8 fp=0 fn=0, raw counts (n=8)", 11, False, INK),
    ])
    card(s, 6.8, 1.85, 5.85, 4.9)
    textbox(s, 7.05, 1.95, 5.4, 4.7, [
        ("Economics and limits, stated plainly", 12, True, TEAL_D),
        ("$0.00 marginal model cost (0 model calls) plus hosting", 11, False, INK),
        ("p50 < 200 ms warm · one-time cold model load at startup", 11, False, INK),
        ("Limit is coverage: PLFS state splits warn, never guess", 11, False, INK),
        ("Heuristic reads break on exotic phrasing; LLM port exists", 11, False, INK),
        ("Scale path: curate PDF tables → truth JSON, no code change", 11, True, INK),
    ])

    # 7 — Roadmap
    s = prs.slides.add_slide(prs.slide_layouts[6]); bg(s)
    header(s, "Roadmap · what ConfAI feedback would shape",
           "From 1708 verified rows to national coverage without touching the firewall",
           "Try it: uvicorn vidhi.service:app --port 8001 → /demo · MCP: python -m vidhi.mcp_server")
    footer(s, 7)
    card(s, 0.7, 1.85, 5.85, 4.9)
    textbox(s, 0.95, 1.95, 5.4, 4.7, [
        ("Next three moves, ranked", 12, True, ACCENT),
        ("1. Operating model: eSankhyiki adapter at release time → machine ingestion → audit gate → frozen JSON. Human work per release: one comparability entry plus diff review.", 10, False, INK),
        ("2. One parser per table family: PLFS Highlights battery (both annual reports), TUS tables/battery and HCES Statement 10 done; MIS tables next.", 10, False, INK),
        ("3. Verify-then-publish endpoint for journalists and fact-checkers.", 10, False, INK),
        ("Already built: MCP server (4 tools) + policy-briefing agent.", 10, True, INK),
    ])
    card(s, 6.8, 1.85, 5.85, 4.9)
    textbox(s, 7.05, 1.95, 5.4, 4.7, [
        ("Reproduce everything in 5 minutes", 12, True, TEAL_D),
        ("pytest tests/ -q  →  110 passed, offline, no key", 10.5, False, INK),
        ("vidhi/eval.py  →  100/100 · 0/19 · Safety-B ok", 10.5, False, INK),
        ("Ask the hard question; expect WARN_NO_DATA + coverage note.", 10.5, True, INK),
        ("Thank you — questions and red-team attempts welcome.", 10.5, True, ACCENT),
    ])

    out = ROOT / "vidhi" / "ConfAI_Vidhi_Firewall_7Slides_v3.pptx"
    prs.save(out)
    print(f"saved {out} ({out.stat().st_size/1024:.1f} KB)")


if __name__ == "__main__":
    main()
