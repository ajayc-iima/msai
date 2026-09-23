# Lab 3 — Runsheet

**Follow this top to bottom.** Every step says *why* it exists, *what* to do,
and how you know you are finished.

| | |
|---|---|
| [`README.md`](README.md) | **the brief** — problem, targets, rubric (read first) |
| [`CONCEPTS.md`](CONCEPTS.md) | **the reference** — concept → code → theory |
| [`report.md`](report.md) | **the form** — fill by hand as you go |
| this file | **the actions** — follow it during the lab |

**Pairs.** Swap driver at each part.

**Pick one track and ignore the other:** Track N = [`lab3.ipynb`](lab3.ipynb)
(numbered *your turn* cells), Track S = `search.py` (the same TODOs as
docstrings).

---

## The lab in one line

> Find the retrieval configuration that maximises nDCG@10 — and justify it
> against cost and latency, one axis at a time.

---

## Before you sit down

- [ ] `pip install -r requirements.txt` (and `chromadb` if D1/D2 should run)
- [ ] `GEMINI_API_KEY` in `.env`
- [ ] [`README.md`](README.md) read; [`CONCEPTS.md`](CONCEPTS.md) open in a second pane
- [ ] You know: **n = 42**, and **`hit_rate@5` is saturated**

---

## What you may call from `aip/`

| You need | It lives in | Signature |
|---|---|---|
| Four chunkers + markdown heading paths | `aip.chunking` | `STRATEGIES`, `Chunk`, `markdown_chunks(...)` |
| Embed a corpus / a query | `aip.embed` | `embed`, `embed_batch` |
| Dense / BM25 / hybrid / HNSW / rerankers | `aip.retrieval` | `DenseRetriever`, `Bm25Retriever`, `HybridRetriever`, `ChromaRetriever`, `CrossEncoderReranker`, `LLMReranker` |
| Retrieval metrics + per-kind breakdown | `aip.evals` | `retrieval_metrics(retrieved, relevant, ks=...)` |
| Cost ceiling for the LLM reranker | `aip.cost` | `Budget`, `global_budget()` |

**Rule of thumb.** `aip/` is the toolkit — you may read it, not change it.
`labs/` is the system you are building.

Two details that matter:

- **`kind_table()` defaults to `hit_rate@5` on purpose** — the saturated
  metric. Pass `col="mrr"` for Part B, or you will see nothing.
- **`evaluate(..., k=30, reranker=..., final_k=5)`** is the two-stage shape:
  retrieve wide, rerank narrow.

---

## `search.py` scaffolding — read, do not rewrite

| Helper | What it does |
|---|---|
| `load_corpus()` / `load_questions()` | 30 docs; 45 questions → **n = 42** (drops Q36/Q38/Q39) |
| `build_chunks(corpus, strategy, size, **kw)` | thin wrapper over `aip.chunking.STRATEGIES` |
| `evaluate(retriever, questions, ...)` | aggregate metrics + `_by_kind` + `_per_question_mrr` |
| `table(rows, cols)` / `kind_table(metrics, col=...)` | pretty-print; note the saturated default |
| `record(sweep, payload)` | merges into `reports/lab3_sweeps.json` (deliverable 3) |
| `snippet`, `time_search`, `hit_at_1` | diagnostics for A4 / D2 / D3 |
| `strip_heading_prefix(chunks)` | A3 only — **do not edit `aip/chunking.py`** |
| `index_and_eval(chunks, questions, ...)` | embed + evaluate; stamps `n_chunks` / `index_s` |
| `best_chunk_cfg()` | freezes your Part A winner for later sweeps |
| `sweep_baseline()` | **run first**; numbers go in `report.md` §0 |

---

# 0 · Setup — 10 min

Open Track N (`jupyter lab labs/lab3/lab3.ipynb`) or Track S
(`labs/lab3/search.py`).

Run the environment / data cells. Expect **30 docs, 45 golden rows, 42 used**.

> **Done when:** the data-check assert passes and you have noted which
> optional packages are missing (`sentence-transformers` → skip C1;
> `chromadb` → skip D1/D2; **D3 works either way**).

---

# 1 · Baseline — 10 min

**Why.** Every later claim is relative to this number. Write it down before
you change anything.

**1.1** Run:

```bash
python labs/lab3/search.py --baseline
```

(or the Baseline cell in the notebook).

**1.2** Copy nDCG@10, recall@5, hit_rate@1, MRR, chunks, p95 into
`report.md` §0.

> **Done when:** `report.md` §0 has numbers, not blanks.

---

# 2 · Part A — chunking — 40 min

**Why.** Chunking is usually the biggest single lever, and it is the axis you
must freeze before Parts B–D (greedy sweep).

### `sweep_chunking()` — TODO A1–A4

| Step | What | Done when |
|---|---|---|
| **A1** | four strategies at size=800 via `run_cfg`/`index_and_eval` | markdown-800 clearly beats fixed-800 on nDCG@10 (else you have a bug) |
| **A2** | winner at {400, 800, 1600} | three rows + shape explained (dilution vs incomplete rules) |
| **A3** | markdown prefix on/off via `strip_heading_prefix` | delta on nDCG@10 / hit_rate@1 / hit_rate@5 reported |
| **A4** | one failure case | chunk that should have matched vs chunks that did |

**2.1 — A1.** Four strategies at size=800:

| Step | Call |
|---|---|
| A1.1 | `run_cfg("fixed", 800)` |
| A1.2 | `run_cfg("sliding", 800, overlap=150)` |
| A1.3 | `run_cfg("recursive", 800, overlap=100)` |
| A1.4 | `run_cfg("markdown", 800)` |
| A1.5 | `print(table(rows_a1, cols))` |

Store metrics in `rows_a1` and `(chunks, retriever)` in `cfgs` (A4 reuses them).

> **Checkpoint.** markdown-800 must beat fixed-800 by a clear margin on
> nDCG@10. If all four are within a point, your chunker is not being applied —
> a bug, not a finding. Print chunk counts.

**2.2 — A2.** Take the A1 winner (highest nDCG@10) and run it at
**400 / 800 / 1600**. The curve is **not** monotonic.

> Explain the shape in `report.md` A2: dilution vs incomplete rules.
> [CONCEPTS.md](CONCEPTS.md) has the argument.

**2.3 — A3.** Markdown **with** and **without** the `[heading > path]`
prefix. Use `strip_heading_prefix()` — **do not edit `aip/chunking.py`**.

Report the delta on nDCG@10, hit_rate@1, hit_rate@5.

> hit_rate@5 may **fall** while hit_rate@1 **rises**. That is not a
> contradiction: the prefix improves ranking, not recall. Say which one moved.

**2.4 — A4.** Find the qid whose per-question MRR swings most across the four
@800 strategies. Fill the printed template into `report.md` A4.

> **Done when:** `record("chunking", ...)` has `a1`–`a4` and a `winner`.

---

# 3 · Part B — dense vs BM25 vs hybrid — 40 min

**Why.** Dense and BM25 fail on **different** questions. The aggregate hides
that; the per-kind breakdown does not.

### `sweep_retrieval()` — TODO B1–B5

| Step | What | Done when |
|---|---|---|
| **B1** | dense / bm25 / hybrid on the frozen chunker | overall table printed |
| **B2** | **by kind, using MRR** + Q44/Q41 mechanisms | two sentences each; never `hit_rate@5` |
| **B3** | RRF `k` ∈ {10, 30, 60, 100} | flatness reported as the finding |
| **B4** | unequal fusion weights | honesty about noise at n=42 |
| **B5** | dense vs hybrid **whichever way it lands** | count of questions where dense beat BM25 |

**3.1 — B1.** Freeze the Part A winner and run dense / bm25 / hybrid.

**3.2 — B2. THE IMPORTANT PART.** Break down **by kind using MRR**:

```python
kind_table(m, col="mrr")          # never the default hit_rate@5
m["_per_question_mrr"]["Q44"]     # exact identifier
m["_per_question_mrr"]["Q41"]     # paraphrase, zero lexical overlap
```

Two sentences of **mechanism** each, then what hybrid did to each. Reference
pattern (full numbers in [CONCEPTS.md](CONCEPTS.md)): Q44 rescued, Q41 damaged.

**3.3 — B3.** RRF `k` ∈ {10, 30, 60, 100}. Expect a small spread —
**flatness is the finding**. Chasing 0.008 at n=42 is fitting to noise.

**3.4 — B4.** Unequal weights (`[2.0, 1.0]`, `[1.0, 2.0]`). Does anything
beat 1:1? Be honest about noise.

**3.5 — B5.** Report dense vs hybrid **whichever way it lands**, with the
count of questions where dense beat BM25 among those they differ.

> **Do not suppress a loss.** A technique that is right on average can be
> wrong on your data. That is why you measure.

> **Done when:** `record("retrieval", ...)` has `b1`, `b3`, `b4`, `b5` and
> `report.md` B2/B5 blanks are filled.

---

# 4 · Part C — reranking — 35 min

**Why.** Retrieve wide, rerank narrow — and ask whether the quality buys the
latency (and, for the LLM reranker, the dollars).

### `sweep_rerank()` — TODO C1–C4

| Step | What | Done when |
|---|---|---|
| **C1** | cross-encoder, k=30 → 5 | Δ nDCG@5 / hit_rate@1 / recall@5 + p95 ms |
| **C2** | LLM reranker | quality + latency + **$/1k queries** |
| **C3** | decision table | **two different** deployment answers (interactive vs batch) |
| **C4** | a query where reranking got **worse** | was the gold doc in the k=30 pool? |

**4.1 — C1.** Cross-encoder: `evaluate(..., k=30, reranker=ce, final_k=5)`.
Report Δ nDCG@5, hit_rate@1, recall@5 and added p95 ms.
(Skip-with-note if `sentence-transformers` will not install.)

**4.2 — C2.** LLM reranker, **same shape**, plus cost:

```python
b0 = cost.global_budget().as_dict()
m = evaluate(...)
spend = cost.global_budget().as_dict()["cost_usd"] - b0["cost_usd"]
usd_per_1k = spend / len(questions) * 1000
```

30 calls **in series** per question — tens of seconds. Run once, late.

**4.3 — C3.** Fill the decision table, then give **two different** answers:

| Config | nDCG@5 | hit_rate@1 | p95 ms | $/1k queries |
|---|---|---|---|---|

- **(a) interactive agent-facing search box** → latency budget first
- **(b) overnight batch job** → quality/cost budget first

If they come out the same, explain why the budgets do not change the call.

**4.4 — C4.** Find a query where reranking made per-question MRR **worse**.
Was the relevant doc in the k=30 pool? Diagnose the failure mode.

> **Done when:** `record("rerank", ...)` has C1/C2 metrics, cost, and
> `c4_worst`; `report.md` C3 has two defended answers.

---

# 5 · Part D — index and metadata — 25 min

### `sweep_index()` — TODO D1–D3

| Step | What | Done when |
|---|---|---|
| **D1** | Chroma HNSW vs exact (needs `chromadb`) | recall gap + latency; or skip-with-note |
| **D2** | scale with random unit-vector ballast to ~160 / ~4k / ~40k | crossover found + mechanism |
| **D3** | status filter on Q29/Q30/Q31 | hit_rate@1 before → after; **no retriever change** |

**5.1 — D1.** Exact NumPy vs Chroma HNSW on your best config. Report the
recall gap and p95. (Skip-with-note without `chromadb`.)

**5.2 — D2.** Scale with **inline ballast** (random unit vectors — index
only, no golden answers). Time exact vs HNSW at ~160 / ~4k / ~40k. Find the
crossover.

> At small n HNSW is **slower** (graph traversal + Python overhead vs one
> BLAS matmul). Report the mechanism, not just the crossover number.

**5.3 — D3. THE TRAP.** Q29/Q30/Q31: correct doc in `claims-timelines`,
wrong doc in `claims-timelines-2024-ARCHIVED`.

- **Path A** (chromadb): `hit_at_1(retriever, trap_qs, where={"status": "current"})`
- **Path B** (dense only): wrap `DenseRetriever` in `WhereDense` so
  `search(..., where=...)` filters on `chunk.meta` (scaffold in the notebook)

Report hit_rate@1 **before → after**.

> **This fix required no change to the retriever at all.** What does that tell
> you about where to look first when retrieval quality is poor? Answer in
> `report.md` D3.

> **Done when:** `record("index", ...)` has `d3` before/after (D1/D2 may be
> null if skipped — say so).

---

# 6 · Submit — 10 min

- [ ] Four `sweep_*` bodies in `search.py` complete (0 remaining
      `NotImplementedError`)
- [ ] `reports/lab3_sweeps.json` has baseline, chunking, retrieval, rerank, index
- [ ] [`report.md`](report.md) filled **by hand** (never regenerate):
  - [ ] n = 42 stated (Q36/Q38/Q39 excluded)
  - [ ] A1 table + A2 size curve + dilution explanation
  - [ ] A3 prefix delta (both halves)
  - [ ] B2 by-kind **MRR** + Q44/Q41 mechanisms
  - [ ] B5 hybrid **whichever way it lands**
  - [ ] C3 **two different** deployment answers
  - [ ] D3 before/after + the metadata insight
  - [ ] final recommended configuration + greedy-sweep limitation
  - [ ] one thing that surprised you

Run the notebook **Submit check** cell (or count stubs in `search.py`).

---

## Deliverables checklist

- [ ] `search.py` — completed sweeps
- [ ] `report.md` — ≤ 3 pages
- [ ] `reports/lab3_sweeps.json`

---

## The traps

1. **`hit_rate@5` saturation.** Every retriever scores 0.93–0.98. Use
   nDCG@10 / recall@5 / hit_rate@1 / MRR. Full mechanics:
   [CONCEPTS.md](CONCEPTS.md).
2. **All four chunkers within a point.** Your chunker is not being applied —
   usually rebuilding while reading a cached index. Print chunk counts.
3. **Reporting hybrid as a win because the literature says so.** On this
   corpus the reference measures dense 0.846 vs hybrid 0.830. Report what you
   measure, whichever way it lands.
4. **Editing `aip/chunking.py` for A3.** Other labs depend on it. Use
   `strip_heading_prefix()`.
5. **Same answer for both C3 deployments.** Interactive and batch have
   different budgets; if they converge, say why.
6. **Leaving `sweep_*` as `NotImplementedError`.** The submit check counts
   remaining stubs in `search.py`.

---

## If something goes wrong

| Symptom | Cause |
|---|---|
| `NotImplementedError: TODO A1...` | Scaffold still commented — fill the numbered blocks |
| `assert ... needs 4 entries` | One strategy/sizes missing from `rows_*` |
| All four chunkers within a point | Chunker not applied / stale cached index. Print counts |
| Part B table looks flat | You are on `hit_rate@5`. Use `col="mrr"` |
| Hybrid "wins" only on hit_rate@5 | Saturated metric. Re-read CONCEPTS saturation section |
| C1 / D1 / D2 skip messages | Missing optional package — note it in `report.md` |
| D3 `after is None` | Uncomment Path A or Path B |
| `reports/lab3_sweeps.json` missing keys | A `record(...)` never ran — re-run that part |
| Submit check: N stubs left | Finish the four `sweep_*` bodies |

---

## The sentence to leave with

> ### A saturated metric does not report "no difference" — it reports nothing.
