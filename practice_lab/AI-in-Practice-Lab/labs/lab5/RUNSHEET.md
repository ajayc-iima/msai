# Lab 5 — Runsheet

> Docs: [`README.md`](README.md) — the brief (targets, deliverables, rubric) ·
> [`CONCEPTS.md`](CONCEPTS.md) — theory and the full reference run ·
> [`report.md`](report.md) — yours to fill

**Follow this top to bottom.** Every step says *why*, the *actions*, a
*checkpoint*, and *done when*.

**Pairs.** Swap driver at each part.

---

## Read this before anything else

**You are graded on the process, not the score.** The reference solution
diagnosed the dominant cluster correctly, predicted 4–6 recoveries — and
measured **−0.050 correctness**. That is a complete, full-marks Lab 5.
Diagnose before you fix, predict before you measure, report what happened, not
what you hoped. Full story: [`CONCEPTS.md`](CONCEPTS.md).

---

## Before you sit down

- [ ] **`reports/lab4.json` exists.** This is a hard prerequisite — Lab 5 reads it
- [ ] Your ten tagged failures from Lab 4 E3, in hand
- [ ] T4 §5 (the seven failure modes) re-read. The diagnostic tree especially
- [ ] `make check` clean

---

## The code

One file: **`diagnose.py`**. It reads your Lab 4 output, runs the automatable
checks from the diagnostic tree, and leaves you the judgement calls.

> `aip/` is the toolkit — read it, never change it. `labs/` is your system.

### What you will call from `aip/`

| You need | It lives in | Signature |
|---|---|---|
| Re-run retrieval to test a hypothesis | `aip.retrieval` | `DenseRetriever`, `Bm25Retriever`, `HybridRetriever`, `ChromaRetriever` |
| Re-chunk to test a boundary fix | `aip.chunking` | `STRATEGIES`, `markdown_chunks(...)` |
| Retrieval metrics for the before/after | `aip.evals` | `retrieval_metrics(retrieved, relevant, ks=...)` |
| Re-judge after the fix | `aip.evals` | `llm_judge`, `judge_agreement` |
| The query-side fixes in the mode-3 catalogue | `aip.rag` | `hyde(question)`, `multi_query(question, n=3)` |
| Cost ceiling | `aip.cost` | `Budget(limit_usd=..., label=...)` |
| What your Lab 4 pipeline did, per query | `aip.tracing` | `read_traces()` |

**`reports/lab4.json` is the input.** Lab 4's `--full --save` writes it.
Without it this lab does not start.

### `diagnose.py` — the TODOs

#### `answer_in_corpus(gold_answer, corpus, ...)` — **TODO**

Decides **mode 1**, missing content.

> The provided version is a deliberately weak substring test. **It will pass on
> a paraphrase and fail on a rewording** — so it over-reports mode 1, which
> sends you hunting for data problems that are really retrieval problems.
> Improving it is part of the lab: normalise, or check key numbers and entities
> rather than whole strings.

#### `classify(row, q, corpus, ...)` — **TODO, the core of the lab**

Walk the tree from T4 §5. Branches marked TODO:

| Branch | The test | Mode |
|---|---|---|
| gold context does **not** fix it | generation was always going to fail | **6** |
| gold doc in top 30, not in final k | it was found and then buried | **4** (or **5** if a reranker dropped it) |
| gold doc **not** in top 30 | confirm by searching the gold chunk's text verbatim | **3** if that retrieves it, else **2** |

> **The inversion.** `gold_context_fixes_it == True` means **retrieval** failed,
> not generation. The generator was capable; it was starved. Full explanation:
> [`CONCEPTS.md`](CONCEPTS.md).

**Mode 2 cannot be automated.** Mark it `needs_human_check` and go and look at
the chunks around the gold answer.

#### `pareto(tally)` — provided

Ranks the clusters. Use it for A3 and again in D3 after your fix.

#### Runners — provided

| Command | What it does |
|---|---|
| `--input reports/lab4.json` | classify every Lab 4 failure |
| `--pareto` | the cluster chart |
| `--save reports/lab5_diagnosis.json` | persist the tally |

### The traps

1. **Inverting the mode-6 test.** Gold context fixing it means *retrieval*.
2. **Fixing by reflex.** If your fix and your tally disagree, stop.
3. **Changing several things at once.** The number moves and you learn nothing.
4. **Only measuring what you targeted.** D2 exists because better retrieval
   routinely makes refusal precision worse.
5. **Trusting `answer_in_corpus` as shipped.** It is weak on purpose.

---

# 1 · Part A — classify every failure — 50 min

**Why.** *"RAG is bad"* is not a diagnosis. Exactly one stage failed on each
wrong answer. This part is most of the lab, and the rest depends on it.

**Actions.**

**1.1 — `A1`.**

```bash
python labs/lab5/diagnose.py --input reports/lab4.json
```

The script automates what can be automated:

| Check | Automated | Decides |
|---|---|---|
| Is the answer in the corpus at all? | grep | Mode 1 |
| Is the gold chunk retrievable by its own text? | yes | Mode 3 vs 2 |
| Was the gold doc in the top 30? | yes | Mode 4 |
| Dropped by the reranker? | yes | Mode 5 |
| **Does gold context fix the answer?** | yes, one call | **Mode 6** |
| Right answer, wrong citation? | yes | Mode 7 |
| Did the answer straddle a chunk boundary? | **no — you look** | Mode 2 |

Produce the tally across all seven modes.

**1.2 — `A2`.** For every case marked `needs_human_check`, **open the chunks
around the gold answer and look.** Record your judgement *and your reason*.
This is the part no script can do.

**1.3 — `A3`.** `--pareto`. Name the two modes that account for most failures.

**Checkpoint.** Gold context **fixing** the answer means **retrieval** was at
fault — the generator was fine and never got the material. A tally spread
evenly across seven modes means you mis-classified; a heavily concentrated one
is normal. Full tree and the reference's measured distribution:
[`CONCEPTS.md`](CONCEPTS.md).

**Done when.** All seven modes tallied with evidence per case, every
`needs_human_check` opened and judged with a reason, top two modes named.

---

# 2 · Part B — rank by expected value — 20 min

**Why.** The largest cluster is not always the right target.

**Actions.**

**2.1** Build the table:

| Cluster | n | Fix | Est. recovery | Cost Δ | Latency Δ | Effort |
|---|---|---|---|---|---|---|

**2.2** Pick one. **Justify it in one sentence.** A cluster of 9 whose fix costs
3× per query may well lose to a cluster of 6 with a free fix.

**2.3 — write the prediction down, now, before you implement:**

> *"I expect this to recover **N** of the **M** failures in this cluster."*

> Being wrong is informative and is **not** penalised. **Not predicting is.**

**Checkpoint.** Estimate recovery by reading a sample of the cluster case by
case, not by vibes — that number is what your prediction gets compared against.

**Done when.** Ranking table filled, pick justified in one sentence, prediction
written down as N of M (in the report, not in your head).

---

# 3 · Part C — implement the fix — 70 min

**Why.** One change, measured, is worth more than three changes and a moved
number.

**Actions.**

**3.1** Pick from the catalogue below by **mode**, cheapest first:

| Mode | Fixes, cheapest first | `aip/` to reach for |
|---|---|---|
| **1** missing content | none — say what the corpus needs | — |
| **2** chunk boundary | larger chunks · more overlap · markdown-aware · small-to-big | `aip.chunking` |
| **3** embedding mismatch | hybrid · HyDE · multi-query · contextual retrieval | `aip.retrieval.HybridRetriever`, `aip.rag.hyde`, `aip.rag.multi_query` |
| **4** ranking | raise `final_k` · cross-encoder · tune RRF weights | `aip.retrieval.CrossEncoderReranker` |
| **5** reranker | different reranker · always keep stage-1 top-1 · rerank only on a small margin | `aip.retrieval` |
| **6** generation | fewer distractors · best chunk first or last never middle · larger tier · better prompt · decompose multi-hop | `labs/lab4/rag.py` |
| **7** presentation | tighten the contract · validate and repair citations | `aip.guards.enforce_citations` |

**3.2 — three rules:**

1. **One fix at a time, measured each time.** Three fixes and a moved score
   teaches you nothing transferable.
2. **Record the failures too.** A fix that did not work, with the number
   showing it, is a result and scores marks.
3. **Fix what the diagnosis says, not what you reach for by reflex.**

> An earlier draft of the reference "fixed" retrieval — archived filter,
> wider `final_k` — after a tally saying 93% of failures were *generation*. It
> would have measured a change against a problem that was not there. **When your
> fix and your tally disagree, either the tally wins or the tally was wrong.
> Stop and resolve it.**

**3.3** The archived-document trap (Q29–Q31): if those still fail, the fix is
**metadata filtering**, not retrieval tuning, and it is essentially free. If you
did it in Lab 3, say so.

> **Cost discipline:** your fix must cost **≤ 2×** the Lab 4 baseline per query.

**Checkpoint.** One change only, and you can name the mode it targets from the
tally before you started.

**Done when.** The fix is implemented, one variable at a time, and you have
written down mode, exact change, location, and expected cost (report C1).

---

# 4 · Part D — prove it — 25 min

**Why.** The number moving is not evidence. The table, and the regressions,
are.

**Actions.**

**4.1 — `D1`.** Before/after on the **same** questions, **every** Lab 4 metric —
not just the one you targeted:

| Metric | v1 | v2 | Δ |
|---|---|---|---|
| correctness · faithfulness · citation validity | | | |
| refusal recall / precision | | | |
| nDCG@10 / recall@5 | | | |
| cost per query · p95 latency | | | |

**4.2 — `D2`. The regression check. Report anything that got worse,
prominently.** Look specifically at:

- **refusal precision** — better retrieval often makes a system refuse *less*,
  which can make it answer unanswerable questions confidently
- **cost and p95** — HyDE and multi-query each add a call per query
- the question kinds that were already passing

**4.3 — `D3`.** Re-classify the *remaining* failures. Did the distribution shift
as you predicted?

> A fix that moves failures from mode 3 to mode 6 has not created a new problem
> — it has **revealed one that was previously masked.** That is progress. Say so.

**4.4 — `D4`.** State the next fix you would make, and what you expect it to be
worth.

**Checkpoint.** Anything that got worse appears in the report body, not a
footnote.

**Done when.** D1–D4 filled in `report.md`, including the fix that did not work
and your cost against the 2× baseline.

---

# 5 · Show & tell — 4 minutes per pair

1. Your Pareto chart — 1 min
2. Your prediction, and what actually happened — 1 min
3. The regression: what got worse — 1 min
4. Questions — 1 min

---

## Deliverables checklist

- [ ] `labs/lab5/diagnose.py` with your classification and your fix
- [ ] `reports/lab5_before_after.json`
- [ ] `report.md` ≤ 3 pages:
  - [ ] the failure tally and the Pareto chart
  - [ ] the Part B ranking table + your one-sentence justification
  - [ ] **your prediction, and what actually happened**
  - [ ] the D1 before/after table
  - [ ] the D2 regression check, **including anything that got worse**
  - [ ] the D3 re-classification
  - [ ] **the fix that did not work**, with its number

---

## If something goes wrong

| Symptom | Cause |
|---|---|
| `FileNotFoundError: reports/lab4.json` | Lab 4's `--full --save` was never run. Finish Lab 4 first — this is the input |
| Everything classified mode 1 | `answer_in_corpus` is too literal. Improve it |
| Everything `needs_human_check` | The branches in `classify` are still TODO |
| Tally spread evenly across seven modes | Mis-classified. Re-check the mode-6 test ([`CONCEPTS.md`](CONCEPTS.md)) |
| Everything lands in mode 6 | Normal if you started from a strong retriever ([`CONCEPTS.md`](CONCEPTS.md)) |
| Cost climbs after a mode-3 fix | HyDE and multi-query add a call per query. Expected — report it |
| The fix helped but cost doubled | That is a result. Report it against the ≤2× rule |
| Correctness went down | **Report it.** That is a full-marks Lab 5 |

## The sentence to leave with

> ### Diagnose before you fix. Predict before you measure.
