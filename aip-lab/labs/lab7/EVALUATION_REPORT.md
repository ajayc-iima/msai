# Lab 7 — Evaluation Report: Aurora Policy Assistant service (Part E)

Reproduce: `AIP_OFFLINE=1 python labs/lab7/gate.py --config labs/lab7/thresholds.yml`
(no network, no API key). CI runs the same command on every push
(`.github/workflows/eval.yml`).

## 1. What it does

Ask it a question about Aurora's policy documents over HTTP and it answers
from those documents, with citations you can expand and check. If the
documents do not cover the question, it says so instead of guessing. Every
response carries its cost and a trace id, so any bad answer can be looked up
later and anyone paying for the system can see what a query costs.

## 2. How well it works

Gate output, `AIP_OFFLINE=1`, golden set (`evaluation/vidhi_golden.jsonl`):

| Metric | Measured | Gate |
|---|---|---|
| correctness | 1.0000 | ≥ 0.75 ok |
| faithfulness | 1.0000 | ≥ 0.90 ok |
| citation_validity | 1.0000 | ≥ 0.98 ok |
| refusal_recall | 1.0000 | ≥ 0.80 ok |
| refusal_precision | 1.0000 | ≥ 0.75 ok |
| hit_rate_at_5 | 1.0000 | ≥ 0.85 ok |
| cost_per_query_usd | 0.0000 | ≤ 0.010 ok |
| p95_latency_ms | 24.0 | ≤ 6000 ok |

Result: **GATE PASSED (exit 0)**. Unit tests: `tests/test_vidhi.py` covers
the firewall, extraction, guards, service 422 contract, and the pipeline;
`python -m pytest tests/ -q` is green in CI alongside the gate.

## 3. Where it fails

- **Correctness 1.0000 at top_k 3, 5 and 10.** An earlier 0.8571 residual
  (6 MPCE PASSes downgraded at top_k=5) traced to three attribution bugs
  in `vidhi/consistency.py`, all fixed with regression tests: (i) % gap
  figures (69.7) treated as Rs levels — now filtered by unit; (ii) pure
  proximity misattributed 6,459 (2022-23) to a nearer following round —
  preceding round tokens now govern; (iii) unlabeled excerpts assumed an
  imputation basis — unknown basis is now non-attribution, never
  contradiction. Verdicts are retrieval-depth stable.
- **Semantic cache is guarded, not trusted.** One-field-different claims
  embed at cosine 0.93–0.99, so *no* pure cosine threshold is safe; the
  `field_compatible` guard rejects cross-field hits whatever the cosine.
  Measured danger-pair canonical collisions: 0/5.
- **Streaming trades TTFT for safety** (B3: buffer, validate, then stream),
  so first-token latency ≈ full-answer latency. No unvalidated token is ever
  sent — a deliberate, defended cost.

## 4. What it costs

$0.00/query on the deterministic path (0 model calls; templated generation).
Per 1,000 queries: $0.00. Per year at 10,000/day: $0.00 plus hosting. The
gate enforces this with a cost ceiling (≤ $0.010/query): swapping in a paid
model to chase the correctness residual would pass quality gates and be
caught by the cost gate — that is why the ceiling exists.

## 5. How fast it is

| Path | Measured |
|---|---|
| In-process pipeline, uncached | ~60 ms |
| Exact-cache hit | ~1 ms |
| Live `POST /ask`, uncached (localhost) | ~33–60 ms |
| Gate p95 over golden set | 24 ms (SLO: ≤ 6,000 ms uncached, ≤ 800 ms cached) |
| `POST /ask/stream` TTFT | ≈ full-answer latency (validate-before-stream, B3) |

Stage breakdown (from `vidhi.ask` traces): extract ≈ firewall ≈ retrieve ≈
render ≈ single-digit ms each; validate sub-ms. No single stage dominates
because generation is templated, not autoregressive — there is nothing to
optimise until a paid model enters the path, at which point generation
becomes ~98% of p95 and answer length is the first lever.

## 6. What it is not safe for

- **Coverage decisions without human review.** The system answers only from
  its committed corpus/excerpts plus verified truth rows; anything outside
  that (valid but uncovered state/sex-disaggregated questions, exotic
  phrasings the heuristic extractor misreads) gets WARN/REFUSE, never a
  guess — but a refusal is not advice, and a WARN with a frozen verdict hash
  still needs a human to read the cited caveat. Precisely: never treat PASS
  as approval, only as "defensible on the cited sources".
- **2025-vs-older comparisons without the revamp/method caveat** (WARN, never
  PASS — the comparability rules exist because the numbers are not comparable).
- **Microdata/unit-row re-identification**: INFERENCE-only, REFUSEd by rule.
- **Semantic-cache hits above any cosine threshold without the field guard**:
  measured 0.93–0.99 on danger pairs; the guard, not the threshold, carries
  safety. Do not raise the threshold to buy hit rate.

## 7. What you would do next (ranked, with expected value)

1. **Provenance audit for every new truth row** (`scripts/vidhi_audit_truth.py`
   → 88/88 traced, 16 duplicate IDs repaired) — highest value: the firewall
   is only as honest as its ground truth, and each added table must arrive
   with a passing audit, not a claim.
2. **Add a load test (20 concurrent users)** to find what breaks first under
   concurrency (expected: SQLite cache lock contention, not the pipeline) —
   unmeasured today and the likeliest demo-day surprise.
3. **Wire the review queue (`review_queue.jsonl`, thumbs-down button) into
   the golden set**, so real failures become regression tests — this is how
   the gate keeps its bite after shipping.
