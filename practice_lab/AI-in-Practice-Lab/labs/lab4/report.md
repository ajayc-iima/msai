# Lab 4 report — Grounded Answers with Citations

*n = 45 (all golden questions, including the 5 unanswerable).
Both refusal numbers go here **with raw counts**; both κ values go here or in
§4 — a judged number without its κ does not count. Fill this by hand; never
regenerate it.*

## 0. Headline

| Metric | Value | Target | Met? |
|---|---|---|---|
| Citation validity | | 1.00 | |
| Faithfulness | | ≥ 0.90 | |
| Answer correctness | | ≥ 0.75 | |
| Refusal recall | | ≥ 4/5 | |
| Refusal precision | | ≥ 0.70 | |
| Repair rate | | reported | |
| Cost per query | | ≤ $0.01 | |
| p95 end-to-end latency ms | | ≤ 6,000 | |

Refusal raw counts (state them wherever the ratios appear):

- recall: refused correctly `/` 5 unanswerable =
- precision: refused correctly `/` total refused =

Judge calibration:

| Rubric | κ | ≥ 0.4? | Rubric fix you made |
|---|---|---|---|
| faithfulness | | | |
| correctness | | | |

---

## 1. Part A — the generation prompt

Six elements checklist (T4 §6.1):

| # | Element | Present? |
|---|---|---|
| 1 | Answer only from the numbered sources; general knowledge forbidden | |
| 2 | Cite by index — `[1]`, `[2][5]` | |
| 3 | Never cite a number that was not supplied | |
| 4 | Exact refusal string, verbatim | |
| 5 | Sources disagree → surface it, never pick silently | |
| 6 | Length discipline — two or three sentences unless more is needed | |

Your `ANSWER_SYSTEM` (paste it):

```

```

Differences from `aip/rag.py::ANSWER_SYSTEM` (rule order, refusal handling,
length, anything else you saw):

---

## 2. Part B — citation validation

### B2 — the tests

| Check | Implemented? | Notes |
|---|---|---|
| Every `[n]` in range 1..n_sources | | |
| Non-empty, and `finish_reason != "length"` | | |
| Non-refusal answer has ≥ 1 citation | | |

### B3 — repair strategy (pick one and defend it)

Choice: retry with corrective message / strip invalid citations / fall back to
refusal / other:

Defense (why this one — and what the rejected ones cost):

The combination you must never return (`citations_valid=False`,
`refused=False`) — how your code prevents it:

### B4 — citation validity over 45

| Metric | Value |
|---|---|
| Citation validity | |

What happens on failure (one sentence):

---

## 3. Part C — refusal, both directions

### C1/C3 — refusal table at two strictness settings

| Setting | Refused on 5 unanswerable (raw) | Refused on 40 answerable (raw) | Recall (raw) | Precision (raw) |
|---|---|---|---|---|
| default | /5 | /40 | | |
| strict | /5 | /40 | | |

Raw counts belong beside every ratio — one case moves precision by 0.12 and
recall by 0.20.

### C2 — Q37 partial answer

*"Does Aurora cover treatment in Singapore, and up to what limit?"*

- What your system did on the first attempt:
- What you changed:
- Final behaviour — what is stated vs refused:

### C4 — the dial, before → after

| Dial | Recall (raw) | Precision (raw) |
|---|---|---|
| before | /5 | / |
| after | /5 | / |

Product recommendation for an insurance helpdesk — where you would set it, and
why (cost of a wrong claim deadline vs cost of an unnecessary refusal; not
"precision matters"):

---

## 4. Part D — the judge

### D2 — calibration (hand-label BEFORE reading the judge's output)

| Rubric | n labelled | κ | ≥ 0.4? | What you fixed when κ was low |
|---|---|---|---|---|
| faithfulness | 20 | | | |
| correctness | 20 | | | |

Disagreements that revealed an implicit labelling rule of yours:

### D3 — self-preference

Judge tier/model vs generator tier/model:

Direction and rough size of the bias (or what you did to avoid it):

---

## 5. Part E — full evaluation

### E1 — metrics (from `--full --save reports/lab4.json`)

| Metric | Value | Target | Met? |
|---|---|---|---|
| Citation validity | | 1.00 | |
| Faithfulness | | ≥ 0.90 | |
| Answer correctness | | ≥ 0.75 | |
| Refusal recall (raw /5) | | ≥ 4/5 | |
| Refusal precision (raw /total refused) | | ≥ 0.70 | |
| Repair rate | | reported | |
| Judge parse failures excluded | | reported | |
| Cost per query | | ≤ $0.01 | |
| p95 end-to-end latency ms | | ≤ 6,000 | |

### E2 — gold-context decomposition

| Quantity | Value |
|---|---|
| A — correctness with gold context (generation ceiling) | |
| B — correctness with retrieved context (your system) | |
| A − B — retrieval-attributable loss | |
| 1 − A — generation-attributable loss | |

Whichever loss is larger is where Lab 5 goes. One sentence saying which, and
what you would have assumed without measuring:

### E3 — failure-mode tally (T4 §5, 10 wrong answers)

| Mode | Failure mode | Count | Example question ids |
|---|---|---|---|
| 1 | missing content | | |
| 2 | chunk boundary | | |
| 3 | embedding mismatch | | |
| 4 | ranking | | |
| 5 | reranker | | |
| 6 | generation | | |
| 7 | presentation | | |
| | **total tagged** | /10 | |

Lab 5 backlog, one line:

---

## 6. One thing that surprised you
