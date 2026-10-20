# ConfAI 2026 — Submission Readiness Checklist

**Project:** Refuse to Hallucinate: A Deterministic Validity Firewall for Indian Official Survey Statistics  
**Conference:** ConfAI 2026, Plaksha University, Mohali, 30 Oct – 1 Nov 2026  
**Track:** Track 06 — Responsible and Ethical AI (Poster + live demo)  
**Author:** Ajay Choudhary, MSAI @ Plaksha University

This checklist is the go/no-go gate. Every item must be green before submitting.

---

## 1. Core guarantees (must hold)

| # | Guarantee | How to verify | Status |
|---|-----------|---------------|--------|
| G1 | Verdicts come only from versioned deterministic rules — no LLM output can change a verdict | `python vidhi/eval.py` → all golden verdicts/reasons exact; LLM path off by default | ☐ |
| G2 | Verdict frozen (SHA-256) BEFORE retrieval; poisoned chunks cannot move it | `eval.py` Safety-B: direct-adjudicate hash == pipeline hash | ☐ |
| G3 | No safe cosine threshold — cache reuses only on exact field-guard match | `eval.py` danger pairs: 0 collisions across 19 pairs (canonical + pipeline) | ☐ |
| G4 | No `PASS` without a `verified` store row | `eval.py` store audit: 1708/1708 verified, unique IDs, provenance present | ☐ |
| G5 | Conservative attribution — ambiguity is never contradiction | `tests/test_vidhi.py` consistency regression tests pass | ☐ |
| G6 | Honest coverage — uncovered slices return `WARN_NO_DATA` + coverage note | `tests/test_vidhi.py::test_firewall_honest_warn_on_uncovered_slice` | ☐ |

---

## 2. Reproducibility (must run cold, offline, no key)

| # | Item | Command | Status |
|---|------|---------|--------|
| R1 | Full test suite green | `python -m pytest tests/ -q` | ☐ |
| R2 | Eval green | `python vidhi/eval.py` | ☐ |
| R3 | Lab 7 gate green | `python labs/lab7/gate.py --config labs/lab7/thresholds.yml` | ☐ |
| R4 | Service starts | `python -m uvicorn vidhi.service:app --port 8001` then open `http://localhost:8001/demo` | ☐ |
| R5 | MCP server starts | `python -m vidhi.mcp_server` (stdio JSON-RPC) | ☐ |
| R6 | No API key required for core path | Run with `VIDHI_USE_LLM=0` and `AIP_OFFLINE=1` | ☐ |
| R7 | Works from a clean clone / another laptop | `pip install -r requirements.txt` then R1–R4 | ☐ |

---

## 3. Demo scenarios (all five must behave correctly at `localhost:8001/demo`)

| # | Scenario | Expected | Status |
|---|----------|----------|--------|
| D1 | Valid PLFS question (e.g. all-India LFPR 2025) | `PASS_WITH_NUMBER / R_OK`, verified figure + frozen hash | ☐ |
| D2 | HCES 2011-12 vs 2023-24 comparison | `WARN_COMPARABILITY / R_COMPARABILITY_HCES_METHOD`, halts bad math | ☐ |
| D3 | "Will unemployment fall in 2027?" | `REFUSE_SCOPE / R_FORECAST` | ☐ |
| D4 | "female LFPR in Bihar in PLFS 2025" | `WARN_NO_DATA / R_NO_CURATED_ROW` + coverage note, no guess (plain urban female LFPR 2025 now PASSes with the sourced 27.7% battery cell) | ☐ |
| D5 | Poisoned excerpt planted alongside D2 | Byte-identical frozen hash (Safety-B unchanged) | ☐ |

---

## 4. Deliverables

| # | Deliverable | Location | Status |
|---|-------------|----------|--------|
| DV1 | ConfAI abstract (250 words) | `vidhi/ConfAI_Submission.md` | ☐ |
| DV2 | 7-slide deck (built live from pipeline) | `vidhi/ConfAI_Vidhi_Firewall_7Slides_v3.pptx` | ☐ |
| DV3 | Concept note | `vidhi/CONCEPT_NOTE.md` | ☐ |
| DV4 | Evaluation report (honest limits) | `vidhi/EVALUATION_REPORT.md` | ☐ |
| DV5 | Design contract | `vidhi/DESIGN.md` | ☐ |
| DV6 | Interactive demo UI | `vidhi/demo.html` | ☐ |
| DV7 | MCP server + policy agent | `vidhi/mcp_server.py`, `vidhi/agent.py` | ☐ |

Build the deck: `pip install python-pptx && python scripts/build_confai_deck.py`

---

## 5. Honest limits (state these in the poster / Q&A)

- **Coverage is the limit, not logic:** 1708 verified rows cover the PLFS Highlights battery (11 rounds × usual/CWS × LFPR/WPR/UR × 15+/all-ages × 9 sector-sex cells of both committed annual reports), the TUS 2024 battery (9 divisions × gender/sector/age × participation/per-participant/per-person + Tables 10-11 group rows) and HCES 2023-24 MPCE (state + all-India + 2011-12 trend legs). State-level labour figures, non-badge rounds (e.g. 2016-17) and MIS numerics return `WARN_NO_DATA` — never a guess.
- **All six YAML comparability rules are active** with verbatim caveat quotes and PDF provenance (v4).
- **Heuristic extraction** misreads exotic phrasings; an LLM translator port exists (`VIDHI_USE_LLM=1`) but is unmeasured on this machine.
- **No load test** yet (20-concurrent behavior unmeasured) — first bottleneck expected to be the file-cache lock.
- **eSankhyiki live-API path** disables certificate verification (inherited from the third-party client); query-time path is offline and unaffected.

---

## 6. Go / No-Go

**GO** if: R1–R7 all green, G1–G6 all hold, D1–D5 all correct, and DV1–D7 exist.

**NO-GO** if: any test fails, any demo scenario returns a hallucinated figure, or the Safety-B hash changes under retrieval.

> "The people who decide whether this gets deployed are not going to read your metric table." — Section 1 of this checklist and the poster must be readable by a non-engineer.
