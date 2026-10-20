# Vidhi Guardian — Evaluation Report (Measured, Offline, Reproducible)
**Author:** Ajay Choudhary (MSAI @ Plaksha University, `ajay.pg26@plaksha.edu.in`)
**Course:** AI in Practice – 1 (Term Final)

Run: `python vidhi/eval.py` + `python -m pytest tests/ -q` + `python labs/lab7/gate.py`. No network, no key.

## 1. What it does

Vidhi Guardian answers Indian survey-statistics questions only when a
deterministic firewall says the claim is statistically defensible,
returning PASS/WARN/REFUSE with a frozen verdict hash and citations.

## 2. How well it works (measured offline — last full run on 2026-10-20)

| Metric | Measured |
|---|---|
| Golden verdict accuracy (100 queries) | 100/100 = 1.000 [Wilson 95% CI: 0.963–1.000] |
| Reason-code accuracy (100 queries) | 100/100 = 1.000 [Wilson 95% CI: 0.963–1.000] |
| Numeric exact match (60 valued queries) | 60/60 = 1.000 [Wilson 95% CI: 0.940–1.000] |
| Citation validity | 100% (REFUSE/WARN without hits count as valid) |
| Danger-pair collisions (canonical claim) | 0 collisions across 19 pairs [Wilson floor 0.83 at 19/19] |
| Danger-pair collisions (pipeline) | 0 collisions across 19 pairs |
| Danger/pair cosine overlap (2 embedders) | inseparable on bge-small (danger 0.80–0.97, paraphrase 0.78–0.95) and nemotron-3-embed-1b (0.56–0.93 vs 0.69–0.95); see `evaluation/semcache_thresholds.json` |
| Ground-truth provenance | 1708/1708 rows in `vidhi/store.json` are `verification_status: verified`, each with `source_document` + `table_or_section` + sha256 provenance and a per-row `audit_note` |
| Row utilization (verified rows touched by golden set) | 55/1708 = 3.2% |
| Stage coverage (all 5 stages fired) | scope 6, safety 1, comparability 6, metadata 5, numeric 82 |
| Decision coverage | PASS 64, WARN 28, REFUSE 8 |
| Refusal recall/precision (8 REFUSE goldens) | tp=8 fp=0 fn=0, raw counts (n=8 underpowered, Wilson floor 0.68 at 8/8) |
| Survey coverage | HCES_2023_24 48, PLFS_2025 22, PLFS_2023_24 7, TUS_2024 17, NSS78_MIS_2020_21 2 |
| Safety-B (verdict frozen before retrieval) | unchanged (identical frozen hash with/without injected chunk) |
| Figure attestation (F1) | every PASS figure carries `SHA-256(frozen_hash ⊕ row_id ⊕ value ⊕ unit ⊕ pdf_sha256)`; a tampered store changes both the frozen hash and the attestation |
| Abstention recall (must-abstain → abstained) | 37/37 = 1.000 (0 false abstentions on 63 answerable) |
| Hallucination rate (must-abstain → answered) | 0/37 = 0.000 |
| Safety-A injection P/R/F1 (committed red-team, n=28) | P=1.000 R=1.000 F1=1.000 — en (6 inj/13 ben), hi (3 inj/3 ben), hi-en (2 inj/1 ben); 0 misses, 0 false positives. Expanded 2026-10-20 with 4 benign FP-regression cases (survey-instructions / "key findings" phrasings the earlier patterns mis-flagged) |
| Determinism (repeat ask = same hash/decision/value) | ok |
| Unit tests | 123 passed (`python -m pytest tests/ -q`, offline) |
| Latency p50 / p95 / p99 / max (in-process) | 154 ms / 2.6 s / 42.7 s / 42.7 s (2026-10-20 run; warm p50 has ranged 138–187 ms run-to-run on this laptop. p95/p99/max are dominated by the one-time cold-start embedding-model load — the service pre-warms at startup, so the first user query is warm) |
| Cost per query | $0.0000 (deterministic path, 0 model calls) |

### Revision log — 2026-10-20 line-by-line audit

Every file in `vidhi/` was re-read line by line. All fixes below are covered
by the 116-test suite and re-measured by `python vidhi/eval.py` (results above):

- **Wrong-granularity PASS eliminated, then generalised.** `store.lookup` no
  longer silently narrows an unspecified dimension: a bare "MPCE" question
  used to PASS with the *rural* figure (4,122). It is now answered with the
  **complete slice** — every published cell for that geography (rural/urban
  × with/without imputation), each with its own row id (`store.complete_slice`
  → `Firewall._complete`); a slice the store does not publish completely is
  still `WARN_NO_DATA` + coverage note. Same for "Bihar MPCE" (state, no
  sector) and uncurated PLFS rounds ("PLFS 2024" used to serve 2025 data;
  now an honest WARN).
- **Any state, any spelling.** The claim translator now resolves every
  state/UT the store carries through a shared vocabulary (`vidhi/states.py`):
  full names, old spellings ("orissa", "pondicherry", "j&k"), short codes
  ("mp", "up", "mh") and single typos ("maharastra") — while refusing false
  positives ("going up", "goal", "punjabi", "the UK"). A question naming
  several states ("MPCE in Madhya Pradesh, UP and Maharashtra") is answered
  for each of them, never for the first alone. The test suite asserts, for
  every state in the store, that "MPCE in <state>" returns exactly that
  state's cells and never another state's numbers.
- **Coverage never substitutes another state.** The `WARN_NO_DATA` "closest
  verified context" for a Bihar question is now a Bihar (or all-India) row,
  never another state's figure.
- **Safety-A precision hardened.** Exfiltration/role-switch signals now target
  the assistant's own configuration, so "show the survey instructions",
  "What are the new instructions for the HCES survey?", "batao PLFS 2025 ki
  key findings" and "बताइए सर्वे के निर्देश" are no longer false-positived.
  Four such phrasings became committed red-team regression cases
  (n 24 → 28; still P/R/F1 = 1.000, 0 FP / 0 FN).
- **"What is … <round>" is a value question.** Definitional no longer swallows
  it: "What is the unemployment rate in PLFS 2023-24?" now PASSes the figure
  (3.2%) instead of a methodology note; forecast/causal/microdata intents are
  never downgraded to methodology.
- **Cache truthfulness.** An exact-cache replay now reports
  `cache_info.exact = true` (previously inherited `false` from the stored
  miss payload).
- **MCP `lookup_verified_ground_truth`.** A specific `residence=rural`
  request no longer returns aggregate rows alongside rural ones.
- **Demo CSV export fixed.** A variable-shadowing bug (`isSlices`) threw a
  TypeError on "Export CSV"; renamed and simplified.
- **Dead/misleading code removed.** Unused `VIDHI_ESANKHYIKI_VERIFY` knob (the
  client exposes no `verify` parameter), dead `MEASURE` map, hardcoded
  All-India state code 99 (now discovered from the API), unused imports in
  `agent.py` / `mcp_server.py`, a duplicated docstring in `answer.py`, dead
  reason codes in the agent risk scorecard, and the eval's precision Wilson
  CI now uses the correct denominator (tp+fp, not total n).
- **Explicit out-of-corpus rounds are pinned, never re-resolved.** A question
  pinned to a year with no curated rows — "HCES 2016-17", "PLFS 2019",
  "PLFS 2016-17" — used to resolve to a curated round (2023-24 / 2025) and
  **PASS with that round's figure**; the requested round is now kept, which
  yields an honest `WARN_NO_DATA`. Rounds that were previously honest
  abstentions BECAME curated in the raw-PDF expansion (HCES 2011-12 and
  2022-23 legs, PLFS calendar 2022/2023/2024 and traditional 2017-18…2023-24)
  — those now PASS with their exact verified figures (see
  `test_expanded_rounds_now_answerable`). Explicit "'2022"-style comparisons
  still materialize the right series ids (`PLFS_2022_23` vs calendar
  `PLFS_2022`) so the verbatim revamp / calendar-series / method-break
  caveats fire.
- **Comparability verdicts cite the versioned rule.** MCP
  `check_survey_comparability` returns the YAML's verbatim MoSPI
  `caveat_quote` + `source_doc` instead of a permanently empty citations
  list; `_split` answers ("rural and urban …") now carry the source row id
  for *every* side, as its contract always claimed. `/ask/stream` no longer
  blocks the event loop with the sync adjudication (runs in a worker thread).
- **Every verified row is reachable — "answer everything in the PDFs, no
  hallucination" is now executable.** `scripts/coverage_probe.py` asks a
  natural question for each of the 1708 verified store rows (the figures
  extracted from the official PDFs — the PLFS Highlights battery of both
  annual reports, the TUS 2024 tables battery, and the HCES 2023-24 trend
  columns, all `pdf_sha256`-bound) and requires the
  exact figure and row id back through `extract -> adjudicate`; it runs as a
  committed test on every suite run. Spot checks confirmed the answer layer
  too (e.g. "rural MPCE without imputation in Bihar" → 3,670, row-bound).
- 5 regression tests were added for the audit fixes above, plus the
  1708-row reachability test (suite now 110 after the expansion).

### Coverage breakdown (last run)

| Category | Covered | Total | % |
|---|---|---|---|
| Verified store rows touched by golden figures | 55 | 1708 | 3.2% |
| All verified rows reachable with exact figure (coverage_probe) | 1708 | 1708 | 100% |
| Firewall stages fired (Safety/Scope/Comparability/Metadata/Numeric) | 5 | 5 | 100% |
| Decisions exercised (PASS/WARN/REFUSE) | 3 | 3 | 100% |
| Surveys covered (PLFS/HCES/TUS/MIS) | 4 | 4 | 100% |

## 3. Vidhi vs MoSPI StatsDoc — what we can prove vs anecdote

Per `evaluation/statsdoc_audit/PROTOCOL.md`, observations of MoSPI's StatsDoc
pilot (`statsdoc.ai.mospi.gov.in`, session `https://statsdoc.ai.mospi.gov.in/c/2402`) are **anecdotal** — contemporaneous live
tests without archived transcripts. We do **not** present them as a measured
baseline. What follows is an honest separation:

| Dimension | What we can prove (Vidhi) | MoSPI StatsDoc (archived transcripts, chats 2472-2480) |
|---|---|---|
| Definitional precision | Enforces statutory "Monthly Per Capita Consumption Expenditure" via metadata-pinned definitions | Got the expansion right this run, but answers are not stable (LLM); also inconsistent figures in one answer |
| Survey-break comparability | Fires `R_COMPARABILITY_HCES_METHOD`; halts unguided cross-round arithmetic | Observed quoting ~40% growth with no caveat on paper-to-3-visit-CAPI break |
| Verdict immutability | SHA-256 freeze computed BEFORE any document is read; identical hash under corpus poisoning | Observed vulnerable to retrieved-chunk override (no pre-retrieval lock) |
| Per-query cost | $0.0000 (0 model calls, deterministic path) | Order-of-magnitude estimate ~$0.02–$0.05/query (hosted LLM RAG, not metered) |
| Determinism | Byte-identical answers for identical questions | Non-deterministic natural language prose |
| Coverage honesty | WARN_NO_DATA + coverage note for uncovered slices; never guesses | Uncovered slices may produce fabricated answers |

**Bottom line:** Vidhi's advantages are architectural (determinism, pre-retrieval freeze, verified-only PASS, $0 cost) and do not depend on unmeasured MoSPI numbers. Where we compare to StatsDoc, we label StatsDoc observations as anecdotal and never present them as our measured baseline.

## 4. Where it fails

- 1708 verified rows: the PLFS Highlights battery (11 survey rounds × usual + CWS × LFPR/WPR/UR × 15+/all-ages × 9 sector-sex cells of both committed annual reports), the TUS 2024 battery (9 ICATUS divisions × gender/sector/age × participation/per-participant/per-person + Tables 10-11 group rows + report Statement 5/6 age-sex rows), and HCES 2023-24 MPCE (Statement 7 + 15 state legs, all-India pairs, and the Statement 10 2011-12/2022-23 trend legs). Every row carries provenance + per-row audit note, but out-of-vocabulary slices (e.g. PLFS state-level figures, off-badge rounds like 2016-17, MIS numerics) correctly return WARN_NO_DATA — coverage, not logic, is the limit. Row utilization of the 100-golden set: 55/1708 (3.2%); full-store reachability is 1708/1708.
- Heuristic extraction misreads exotic phrasings (e.g. "males"/"females" plural handling was a live bug fixed on 2026-10-16; "Chandigarh"/"Puducherry"/"Lakshadweep" state matching likewise). The LLM translator interface exists but is unmeasured on this machine. Answers stay templated by design: WARN must never read like PASS, citations stay valid by construction, identical questions give byte-identical answers.
- Latency is dominated by the local embedding rerank (sentence-transformers on CPU) at ~150–190 ms p50 (154 ms on the 2026-10-20 run); the deterministic adjudication itself is sub-millisecond. Cold start includes a one-time model load (13–43 s observed, machine-dependent); the service pre-warms at startup.

## 5. What it costs

$0.00/query (deterministic path, 0 model calls). Per 1,000: $0.00. Per
year at 10,000/day: $0.00 plus hosting. Optional LLM polish path costs
one call per PASS answer and is off by default.

## 6. How fast

Measured by `python vidhi/eval.py` (in-process, no network). Last run
(2026-10-20): p50 = 154 ms, p95 = 2.6 s, p99/max = 42.7 s (the first query
pays the one-time local embedding-model load; warm p50 has ranged 138–187 ms
across runs on this laptop). Exact-cache hit ~0 ms. The deterministic
adjudication path (firewall + store lookup) is sub-millisecond; the quoted
latency is dominated by the local embedding rerank used for citation
retrieval ordering. Even so, warm p50 is 20–50× below hosted-LLM TTFT
(3,500–8,000 ms).

## 6b. What it is not safe for

- Any figure not in `vidhi/store.json` with `verification_status: verified` — the system WARNs instead of answering, by construction.
- 2025-vs-older comparisons without the revamp caveat (WARN, never PASS).
- Microdata/unit rows: INFERENCE-only; re-identification is REFUSEd.
- Subpopulation reification: a national figure must never be quoted for a state/sex slice (e.g. all-India LFPR for Bihar, male figures for female questions). The strict `store.lookup` plus field-guarded cache enforce this; a confident wrong subgroup number harms more than a WARN.
- Semantic cache above ANY cosine threshold is unsafe (danger/paraphrase ranges overlap on bge-small AND nemotron-3-embed-1b; committed at `evaluation/semcache_thresholds.json`); only the deterministic field-guard makes it safe.
- The live eSankhyiki ingestion path (release-time only) uses a pinned third-party client that performs unverified TLS internally and exposes no verify knob; the query-time path is fully offline and unaffected.

## 7. What you would do next (ranked, with expected value)

1. Extend the store toward state-level labour annexes and MIS tabular rows → raises the catalog toward the full MoSPI output (no code change; the firewall is data-driven; the 1708-row Highlights/TUS/HCES battery already proves the pattern end-to-end).
2. Add paraphrase-robustness cases to the golden set (synonyms, word order) and measure extraction failure modes honestly.
3. Load test the service (20+ concurrent) to replace the current "unmeasured" note with a number.

### Page-anchor re-verification (`python scripts/store_reaudit.py`)

The store binds every row to a source PDF by SHA-256. That proves the row
came from *a* committed PDF; it does not prove the transcription. So the
build now **anchors each row to the PDF page it was read from** and the
audit re-opens that page and looks for the value in its printed form:

| Measure | Result |
|---|---|
| Verified rows | 1,708 |
| Rows anchored to a single PDF page | 1,397 (82%) — the rest keep value + table + sha256, never a guess |
| Rows re-checked on their cited page | 1,400 (anchored rows + the rows the extractor already paged) |
| Value found on the cited page | **1,400 / 1,400 = 1.000** |
| Source PDF sha256 re-computed at audit time | 6 / 6 match |

This is a **non-circular** check: it does not re-run the extractor, it
re-opens the page. It proves the number is on the cited page and the page
reference is right; it does not certify that the row's *reading* of the
table is the only sensible one (that still needs a human read).

### Typed-claim accuracy (`python scripts/measure_translator.py`)

The firewall is only as good as the claim the translator builds. Measured
on 21 hand-built cases — misspellings, abbreviations and short codes,
paraphrases, Hindi, multi-state questions:

| Measure | Result |
|---|---|
| Typed-claim accuracy (critical fields) | **20 / 21 = 0.952** |
| Failing case | `"MPCE in biharr"` — a one-letter typo of *Bihar* (typo tolerance is one edit for names ≥ 8 characters) |
| Behaviour on that case | **abstains** (`WARN_NO_DATA` + "Did you mean 'Bihar'?") — it does not answer with the all-India figures |

Hindi state names are in the vocabulary (36 Devanagari aliases), so
"मध्य प्रदेश में MPCE क्या है?" resolves to Madhya Pradesh; an unknown
Devanagari place ("MPCE in अफगानिस्तान") abstains rather than substituting
the national figures.
