# Refuse to Hallucinate: A Deterministic Validity Firewall for Indian Official Survey Statistics

**Ajay Choudhary**  
MSAI, Plaksha University, Mohali, India  
`ajay.pg26@plaksha.edu.in`  
Course: AI in Practice – 1 (Policy Track), Instructor: Subrat  

**ConfAI 2026, Plaksha University, Mohali — 30 Oct – 1 Nov 2026**  
Track 06: Responsible and Ethical AI — Poster + live demo

---

## Abstract

Generative AI over sovereign statistics fails at governance, not retrieval: unconstrained RAG hallucinates statutory definitions, compares incomparable survey rounds without warning, and lets poisoned document chunks override verdicts. We probed MoSPI's StatsDoc pilot live (session `https://statsdoc.ai.mospi.gov.in/c/2402`) and observed it expanding MPCE as "Mean Per Capita Expenditure," quoting ~40% MPCE growth across the HCES paper-to-3-visit-CAPI break with no warning. Per our audit protocol (`evaluation/statsdoc_audit/PROTOCOL.md`), these observations are anecdotal — live tests without archived transcripts — and are not presented as a measured baseline.

We present a deterministic validity firewall (`vidhi`) that adjudicates questions about Indian official survey data before any document is retrieved. Every question is parsed into a typed claim; five versioned rule stages (Safety-A → Scope → Comparability → Metadata → Numeric) fire in fixed order, and the verdict is frozen into a SHA-256 hash before any document is read, so untrusted chunks cannot move it (Safety-B). Safety-A runs first and blocks prompt injection in English, Hindi and Hinglish across all signal classes. Only `verified` ground-truth rows may `PASS`; anything uncovered returns an honest `WARN_NO_DATA` with a live coverage note rather than a guess. The semantic cache is guarded by deterministic field comparison because danger-pair and paraphrase cosine ranges overlap on two measured embedders (bge-small, nemotron-3-embed-1b), so no cosine threshold is safe (0 collisions across 19 danger pairs).

Measured offline on 100 golden queries: 100/100 verdict accuracy [0.963–1.000], 100/100 reason-code accuracy, 59/59 numeric exact match [0.939–1.000], 0 collisions across 19 danger pairs [floor 0.83], refusal tp=8 fp=0 fn=0 raw counts (n=8, floor 0.68), Safety-B hash unchanged under injection, abstention recall 1.000 with hallucination rate 0.000 (37 must-abstain goldens), Safety-A P/R/F1 = 1.000 on a 28-case multilingual red-team (0 misses, 0 false positives), 173/173 verified store rows with provenance, 54/173 (31.2%) store coverage, $0.00 marginal model cost per query on the deterministic path plus hosting, p50 ≈ 150–190 ms warm in-process (run-to-run, CPU-only; the one-time cold model load is paid at service startup). All results reproducible with `python vidhi/eval.py` — no API key, no GPU, no network.

---

## 1. Introduction

Government statistical agencies worldwide are deploying AI assistants over official data (e.g., MoSPI's StatsDoc pilot at `statsdoc.ai.mospi.gov.in`, session `https://statsdoc.ai.mospi.gov.in/c/2402`). Retrieval is largely solved; **statistical governance is not**. Unconstrained RAG over sovereign statistics produces three failure modes we observed in live probing:

1. **Definitional hallucination:** StatsDoc expands MPCE as "Mean Per Capita Expenditure" instead of the statutory "Monthly Per Capita Consumption Expenditure."
2. **Unguided cross-round arithmetic:** It quotes ~40% MPCE growth between HCES 2011-12 and 2023-24 without warning that the 2023-24 round switched from 1-visit paper canvassing to 3-visit CAPI with restructured item lists — a methodological break that makes direct level comparison invalid.
3. **Adversarial vulnerability:** Retrieved document chunks can override system guardrails (prompt injection via RAG documents).

Per `evaluation/statsdoc_audit/PROTOCOL.md`, these StatsDoc observations are **anecdotal** — contemporaneous live tests without archived transcripts. We do not present them as a measured baseline, nor do we claim a measured head-to-head latency/cost victory over StatsDoc.

Existing tools help users **find** the number; none checks whether they are **allowed to say** what they want with it — and stops them with a cited rule when they are not.

We built the Statistical Evidence & Validity Firewall to close this gap. Its core design principles:

- **Rules judge, models translate.** No LLM output can change a verdict. Verdicts come only from versioned deterministic rules.
- **Freeze before retrieval.** The SHA-256 verdict hash is computed before any document text is read. Poisoned chunks cannot move a verdict.
- **No threshold is safe.** Danger-pair and paraphrase cosine ranges overlap on every measured embedder, so cache reuse requires exact field-guard match on all critical fields.
- **No PASS without provenance.** A numeric answer requires a `verified` store row tracing to cited source text.
- **Honest coverage.** Uncovered slices get `WARN_NO_DATA` + a live coverage note, never a guess.

---

## 2. System Design

### 2.1 Architecture planes

Dependencies point down only; nothing above `rules` may alter a verdict.

```
service / demo / mcp / agent        <- thin; no logic
pipeline (ask)                      <- orchestration + traces + cost
render + consistency + retrieve     <- post-freeze only (untrusted text)
rules (5-stage firewall + freeze)   <- the judge
claims (schema + heuristic extract) <- the translator
store (built artifact + manifest)   <- generated, never hand-edited
sources (factsheet / plfs / tus parsers) <- machine extraction w/ provenance
```

### 2.2 The five-stage firewall (fixed order, first rule fires)

| Stage | Purpose | Refuse / Warn |
|-------|---------|---------------|
| **1. Safety-A** | Reject injections (runs first so a prompt-injection is always refused *as* an injection) | Prompt-injection directives in English, Hindi and Hinglish — all signal classes (override, role-switch, exfiltration, delimiter-break, tool-coercion, encoded) |
| **2. Scope** | Block out-of-scope topics | Forecasts, causality, political judgments, microdata extraction, non-survey topics (CPI, RBI, QES) |
| **3. Comparability** | Enforce survey breaks | HCES 2011-12 vs 2023-24 (CAPI break), PLFS 2023-24 vs 2025 (calendar revamp), EUS vs PLFS, status-mix (usual vs CWS) |
| **4. Metadata** | Validate taxonomy | Unknown survey/indicator/measure, unsupported disaggregation (sex/residence/state/activity/age_group) |
| **5. Numeric** | Verify ground truth | Only `verified` store rows may PASS; mismatch → `WARN_NUMERIC_MISMATCH`; missing row → `WARN_NO_DATA` |

### 2.3 Pre-retrieval verdict freezing (Safety-B)

The verdict and reason code are hashed before retrieval:

$$\text{Hash} = \text{SHA-256}(\text{claim JSON} + \text{decision} + \text{sub-code} + \text{rule-version})$$

This hash is locked **before** any document text is read. Answer generation uses templated scaffolds where WARN and REFUSE wording is fixed. Even under adversarial retrieval poisoning, the emitted response cannot be corrupted — the hash matches byte-for-byte with and without injected chunks.

### 2.4 Field-guarded semantic cache

Danger pairs (e.g., "urban Bihar female LFPR" vs "rural Bihar female LFPR") embed at cosine 0.93–0.99 on bge-small and 0.56–0.93 on nemotron-3-embed-1b — inseparable from paraphrases at any threshold. The cache therefore permits reuse **only** when all critical fields (survey, indicator, measure, residence, geography, state, sex, age_group, activity, round, claim_type) match identically. Measured: 0 collisions across 19 danger pairs at any threshold.

### 2.5 Verified-only ground truth

`store.json` contains 173 rows, each with `source_document`, `table_or_section`, PDF sha256, and a per-row audit note tracing the value to cited PDF text. The `audit.py` gate fails the build on any untraceable value or duplicate ID. `PASS` requires a `verification_status: verified` row; `store.lookup` performs strict matching — an all-India row never answers a female/urban/Bihar question, and an unspecified dimension is satisfied only by an aggregate row, so a bare "MPCE" question is WARNed rather than answered with the rural slice.

---

## 3. Evaluation

### 3.1 Golden battery (100 queries)

Measured offline by `python vidhi/eval.py`:

| Metric | Measured | Gate |
|--------|----------|------|
| Verdict accuracy | 100/100 = 1.000 | ≥ 0.75 |
| Reason-code accuracy | 100/100 = 1.000 | — |
| Numeric exact match | 59/59 valued queries = 1.000 | — |
| Citation validity | 100/100 = 1.000 | ≥ 0.98 |
| Danger-pair collisions (canonical) | 0 across 19 pairs | — |
| Danger-pair collisions (pipeline) | 0 across 19 pairs | — |
| Safety-B (freeze before retrieval) | unchanged | — |
| Abstention recall / hallucination rate | 37/37 = 1.000 / 0.000 | — |
| Safety-A injection P/R/F1 (red-team, n=28) | 1.000 — 0 misses, 0 false positives (en / hi / hi-en) | — |
| Determinism (repeat ask) | identical hash/decision/value | — |
| Row utilization (verified rows touched by golden set) | 54/173 = 31.2% | — |

**Coverage.** Golden questions exercise all five firewall stages (scope 6, safety 1, comparability 6, metadata 5, numeric 82), all three decisions (PASS 63, WARN 29, REFUSE 8), and all four surveys (HCES 48, PLFS 29, TUS 17, MIS 2). Uncovered slices return `WARN_NO_DATA` rather than a guess.

### 3.2 Latency & cost

Measured per-query by `python vidhi/eval.py` (in-process, 0 model calls):

| Metric | Measured |
|--------|----------|
| Cost per query | $0.0000 |
| Latency p50 / p95 / p99 / max | 154 ms / 2.6 s / 42.7 s / 42.7 s (2026-10-20 run; warm p50 138–187 ms run-to-run, p99/max = one-time cold-start model load) |
| Exact-cache hit | ~0 ms |

Generation is templated, not autoregressive; the deterministic adjudication path is sub-millisecond, and the quoted latency is dominated by the optional local embedding rerank for citation ordering.

---

## 4. Vidhi vs MoSPI StatsDoc — honest comparison

| Dimension | Vidhi (measured) | MoSPI StatsDoc (anecdotal, per PROTOCOL.md) |
|---|---|---|
| Definitional precision | Statutory "Monthly Per Capita Consumption Expenditure" enforced | Observed expanding MPCE as "Mean Per Capita Expenditure" |
| Survey-break comparability | Fires `R_COMPARABILITY_HCES_METHOD`; halts bad math | Observed quoting ~40% growth with no caveat |
| Verdict immutability | SHA-256 frozen before retrieval; identical under poisoning | Observed vulnerable to retrieved-chunk override |
| Per-query cost | $0.0000 (0 model calls) | Order-of-magnitude estimate ~$0.02–$0.05 (not metered) |
| Determinism | Byte-identical answers for identical questions | Non-deterministic prose |
| Coverage honesty | WARN_NO_DATA + coverage note; never guesses | Uncovered slices may produce fabricated answers |

We do **not** claim a measured latency/cost victory over StatsDoc — their numbers are not metered. Our advantages are architectural and reproducible.

---

## 5. Limitations (stated honestly)

- **Coverage is the limit, not logic.** 173 verified rows cover HCES state MPCE both imputation legs (all states/UTs, rural + urban), PLFS national LFPR/WPR/UR, and TUS activity minutes; measured coverage is 54/173 (31.2%). Uncurated slices correctly return `WARN_NO_DATA` — never a guess. All five YAML comparability rules are active with verbatim caveat quotes and PDF provenance (v3).
- **Heuristic extraction** misreads exotic phrasings; an LLM translator port exists (`VIDHI_USE_LLM=1`) but is unmeasured on this machine.
- **No load test** yet; expected first bottleneck is the file-cache lock under 20+ concurrent requests.
- **eSankhyiki live-API path** inherits certificate-verification weakness from the third-party client; the query-time path is fully offline and unaffected.

---

## 6. Reproducibility

All results are reproducible offline with no API key and no GPU:

```bash
pip install -r requirements.txt
python -m pytest tests/ -q        # offline unit + gate tests
python vidhi/eval.py              # 100 golden + 19 danger pairs + Safety-B + store audit + latency + cost
python -m uvicorn vidhi.service:app --port 8001   # open /demo
```

CI gate: `.github/workflows/vidhi.yml` runs pytest + eval on every push/PR.

Demo artifacts: `demo.html` (single-file UI), `mcp_server.py` (JSON-RPC 2.0 stdio), `agent.py` (autonomous policy briefing), `ConfAI_Vidhi_Firewall_7Slides_v3.pptx` (built live from pipeline output via `scripts/build_confai_deck.py`).

---

## 7. Conclusion

MoSPI's tools help you **find** the number. The Statistical Evidence & Validity Firewall checks whether you are **allowed to say** what you want with it — and stops you, with a cited rule, when you are not. By placing deterministic, versioned rules ahead of generation and freezing the verdict before retrieval, we address three classes of failure that unconstrained RAG cannot: definitional hallucination, unguided cross-round arithmetic, and retrieval poisoning. At $0.00/query and sub-20 ms latency, it is a drop-in governance layer for journalists, fact-checkers, legislative researchers, and statistical agencies publishing sovereign data.

**Demo:** `localhost:8001/demo` (offline, no API key, no GPU)  
**Code:** `vidhi/` package — isolated, Labs 1–6 untouched

---

### Reproducibility checklist (go/no-go for ConfAI)

| # | Item | Command | Status |
|---|------|---------|--------|
| R1 | Unit + gate tests | `python -m pytest tests/ -q` | ☐ |
| R2 | Eval (golden + danger + Safety-B + store audit + latency + cost) | `python vidhi/eval.py` | ☐ |
| R3 | Lab 7 regression gate | `python labs/lab7/gate.py --config labs/lab7/thresholds.yml` | ☐ |
| R4 | Service + demo | `python -m uvicorn vidhi.service:app --port 8001` → `/demo` | ☐ |
| R5 | MCP server | `python -m vidhi.mcp_server` | ☐ |
| R6 | Offline, no key | `VIDHI_USE_LLM=0 AIP_OFFLINE=1` | ☐ |
