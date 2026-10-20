# Reproducibility Package — Vidhi Guardian / Statistical Evidence & Validity Firewall

**ConfAI 2026, Plaksha University — Track 06 Responsible & Ethical AI**  
**Author:** Ajay Choudhary, MSAI @ Plaksha University  
**Conference dates:** 30 Oct – 1 Nov 2026

This package lets any reviewer reproduce every number in the paper and poster, offline, with no API key and no GPU.

---

## 1. What ships where

| Artifact | Path | Purpose |
|----------|------|---------|
| Firewall package | `vidhi/` | Core code: claims, rules, store, answer, pipeline, service, agent, mcp_server |
| Ground truth | `vidhi/store.json` | 1708 verified rows with provenance + per-row audit note |
| Golden queries | `evaluation/vidhi_golden.jsonl` | 100 golden verdict/reason/value expectations |
| Danger pairs | `evaluation/danger_pairs.jsonl` | 19 semantic danger pairs that must not collide |
| Attack suite | `data/attacks/attack_suite.jsonl` | 17 attacks + 4 controls for red-team evaluation |
| Unit tests | `tests/test_vidhi.py`, `tests/test_aip.py` | Offline regression tests |
| Eval harness | `vidhi/eval.py` | One-command: golden + danger + Safety-B + store audit |
| Lab 7 gate | `labs/lab7/gate.py` + `thresholds.yml` | CI regression gate |
| Service | `vidhi/service.py` | FastAPI: `POST /ask`, `GET /demo`, `GET /health`, `GET /metrics` |
| Demo UI | `vidhi/demo.html` | Single-file visual UI (6 live scenarios) |
| MCP server | `vidhi/mcp_server.py` | JSON-RPC 2.0 stdio, 4 governance tools |
| Policy agent | `vidhi/agent.py` | Autonomous policy-briefing agent |
| CI workflow | `.github/workflows/vidhi.yml` | pytest + eval on push/PR |
| Deck builder | `scripts/build_confai_deck.py` | Builds the 7-slide ConfAI deck live from pipeline output |
| Paper | `vidhi/CONF_AI_PAPER.md` | Full conference paper |
| Submission info | `vidhi/ConfAI_Submission.md` | Abstract + track + format |
| Readiness checklist | `vidhi/CONF_AI_SUBMISSION_READINESS.md` | Go/no-go gate before submission |

---

## 2. Environment

- Python >= 3.11 (verified on 3.13 and 3.14)
- No virtualenv required (system Python works)
- No API key, no GPU, no network for the core path
- Install: `pip install -r requirements.txt`

Core dependencies: `fastapi`, `uvicorn`, `pydantic`, `pytest`, `pyyaml`, `python-pptx` (deck only), `sentence-transformers` (optional; cache works without embeddings)

---

## 3. Step-by-step reproduction

### 3.1 Install

```bash
cd <repo>/aip-lab
pip install -r requirements.txt
```

### 3.2 Unit tests (offline, no key)

```bash
python -m pytest tests/ -q
```

Expected: all tests pass (~45 tests covering firewall, cache, Safety-B, API, consistency, MCP, agent, store provenance).

### 3.3 Full evaluation harness

```bash
python vidhi/eval.py
```

Expected output (all green, exit code 0):

```
=== Golden Battery (100 queries) ===
  verdict_acc=1.000 [0.963-1.000] reason_acc=1.000 [0.963-1.000] numeric_acc=1.000 citation_acc=1.000
  decisions: {'PASS': 64, 'REFUSE': 8, 'WARN': 28}
  stages: {'comparability': 6, 'metadata': 5, 'numeric': 82, 'safety': 1, 'scope': 6}
  golden answerability: 64/100 PASS (64.0%) · WARN_NO_DATA=15
  row utilization: 55/1708 verified rows touched (3.2%)
  danger_canon=19/19 danger_pipe=19/19 safety_b=ok deterministic=ok
  latency_ms p50=... p95=... p99=... max=... cost_per_query=$0.0000
```

What this checks:
- **100 golden queries:** verdict, reason code, numeric value, citation validity
- **19 danger pairs:** canonical guard no collision + pipeline-level no same-figure collision
- **Safety-B:** direct `Firewall.adjudicate()` hash == full pipeline hash (proves freeze precedes retrieval)
- **Determinism:** identical question → identical hash, decision, value
- **Store audit:** 1708/1708 rows verified, unique IDs, provenance present

### 3.4 Lab 7 regression gate

```bash
python labs/lab7/gate.py --config labs/lab7/thresholds.yml
```

Expected: `GATE PASSED` (correctness ≥ 0.75, citation validity ≥ 0.98, refusal recall ≥ 0.80, cost ≤ $0.01, p95 ≤ 6000 ms).

### 3.5 Service + demo

```bash
python -m uvicorn vidhi.service:app --port 8001
```

Open `http://localhost:8001/demo`. Six live scenarios:

| # | Scenario | Expected |
|---|----------|----------|
| A | All-India LFPR age 15+ usual status in PLFS 2025 | `PASS_WITH_NUMBER / R_OK`, 59.3% + frozen hash |
| B | Compare average MPCE 2011-12 vs 2023-24 | `WARN_COMPARABILITY / R_COMPARABILITY_HCES_METHOD` |
| C | "Will unemployment fall in 2027?" | `REFUSE_SCOPE / R_FORECAST` |
| D | "female LFPR in Bihar in PLFS 2025" | `WARN_NO_DATA / R_NO_CURATED_ROW` + coverage note (state-level labour figures are not in the Highlights battery) |
| E | Poisoned excerpt planted with scenario B | Byte-identical frozen hash (Safety-B immune) |
| F | Hindi prompt-injection ("पिछले निर्देशों को अनदेखा करो…") | `REFUSE_SAFETY / R_PROMPT_INJECTION` (multilingual Safety-A) |

Endpoints:
- `POST /ask` — JSON `{question, top_k}` → verdict + figure + citations + trace_id + cost + latency
- `POST /ask/stream` — SSE streaming (verdict validated before tokens emitted)
- `GET /health` — status, uptime, rules hash, index stats
- `GET /metrics` — cost, call count, latency percentiles
- `GET /demo` — single-file visual UI
- `POST /analyze` — autonomous policy-briefing agent

### 3.6 MCP server

```bash
python -m vidhi.mcp_server
```

Speaks JSON-RPC 2.0 over stdio. Four tools:
- `adjudicate_statistical_claim` — full firewall verdict
- `check_survey_comparability` — two-round comparability check
- `lookup_verified_ground_truth` — verified store lookup
- `get_survey_metadata` — survey taxonomy from `survey_metadata.yaml`

Compatible with Claude Desktop, Cursor, Windsurf, any MCP client.

### 3.7 Build the ConfAI deck (optional, for poster session)

```bash
pip install python-pptx
python scripts/build_confai_deck.py
```

Output: `vidhi/ConfAI_Vidhi_Firewall_7Slides_v3.pptx` — all demo text generated live from `P.ask()` runs; nothing hardcoded.

---

## 4. CI

`.github/workflows/vidhi.yml` runs on push/PR:
1. `python -m pytest tests/ -q`
2. `python vidhi/eval.py`

Any failure → non-zero exit → build fails. This is the gate that prevents regressions.

---

## 5. Honest limits (stated in the paper)

- **Coverage is the limit, not logic:** 1708 verified rows cover the PLFS Highlights battery (11 rounds × usual/CWS × LFPR/WPR/UR × 15+/all-ages × 9 sector-sex cells), the TUS 2024 battery (9 divisions × gender/sector/age × participation/per-participant/per-person + group rows) and HCES 2023-24 MPCE (state + all-India + 2011-12 trend legs). State-level labour figures, non-badge rounds (e.g. 2016-17) and MIS numerics return `WARN_NO_DATA` — never a guess.
- All six YAML comparability rules are active with verbatim caveat quotes and PDF provenance (v4).
- Heuristic extraction misreads exotic phrasings; LLM translator port exists but is unmeasured.
- No load test yet; first expected bottleneck is the file-cache lock.
- eSankhyiki live-API path inherits cert-verification weakness; query-time path is offline.

---

## 6. Go / No-Go before ConfAI submission

See `vidhi/CONF_AI_SUBMISSION_READINESS.md`. GO if R1–R6 all green and all five demo scenarios behave correctly.
