# Lab 5 report — Diagnose, Fix, Prove

*Process grading: the reference solution measured **−0.050 correctness** and
earned full marks, because it diagnosed before it fixed, predicted before it
measured, and explained the negative result. A −0.05 you can explain scores
above a +0.12 you cannot. State your delta plainly, whatever its sign.
Full story: [`CONCEPTS.md`](CONCEPTS.md).*

## 1. Part A — classify every failure

### A1 failure tally

| mode | name | n |
|---|---|---|
| 1 | missing content | |
| 2 | chunk boundary | |
| 3 | embedding mismatch | |
| 4 | ranking | |
| 5 | reranker | |
| 6 | generation | |
| 7 | presentation | |
| | **total** | |

Pareto summary (`--pareto` output):

```
failure mode          n    share   cumulative
```

Top two modes:  and   —   of   failures (  %)

### A2 human review — every `needs_human_check`

| qid | boundary? Y/N | evidence (what you saw in the chunks) | final mode |
|---|---|---|---|
| | | | |

### A3 Pareto answer

Two modes accounting for most failures: mode  ( ) and mode  ( ).

Together they are  of   failures (  %).

Why this concentration makes sense for this pipeline:

## 2. Part B — rank by expected value

### B1 ranking table

| cluster | n | fix | est. recovery | cost Δ | latency Δ | effort |
|---|---|---|---|---|---|---|
| | | | | | | |

### B2 chosen cluster

Cluster picked: mode  ( )

Fix to implement:

One-sentence justification (why this cluster, not a bigger one):

### B3 pre-registered prediction — written before Part C

> "I expect this to recover N =  of the M =  failures in this cluster."

## 3. Part C — the fix

### C1 fix description

- Mode targeted:
- Exact change (file + what):
- Where the change lives (function/line):
- Cost delta expected: ≤ 2× baseline? Y/N because:
- Archived-document trap (Q29–Q31) relevant? Y/N — if yes, that is metadata
  filtering, not retrieval tuning:

## 4. Part D — prove it

### D1 before/after — same questions, every Lab 4 metric

| metric | v1 | v2 | Δ |
|---|---|---|---|
| correctness | | | |
| faithfulness | | | |
| citation validity | | | |
| refusal recall | | | |
| refusal precision | | | |
| nDCG@10 | | | |
| recall@5 | | | |
| cost per query | | | |
| p95 latency | | | |

### D2 regression check — report anything that got worse, prominently

- refusal precision: v1 =  v2 =  — better retrieval often means fewer
  refusals, which means confident answers to unanswerable questions
- cost / p95: v1 =  v2 = 
- kinds that were already passing:
- other regressions:

### D3 re-classification of the remaining failures

- before, top modes were:  
- after, top modes were:  
- shift matches prediction? Y/N because:
  (mode 3 → mode 6 movement = previously masked problem revealed = progress)

### D4 next fix

Next fix I would make, and what I expect it to be worth:

## 5. Summary

- Prediction: recover N =  of M = 
- Actual: recovered  of M ; delta correctness = 
- Verdict: better / worse / mixed — one sentence why:

## 6. The fix that did not work

Fix number (from your Part B/C order):  

What it was supposed to recover, and what it actually did — the number:

## 7. Cost of the fix vs 2× baseline

| | value |
|---|---|
| Lab 4 baseline cost per query | |
| After-fix cost per query | |
| ratio (must be ≤ 2×) | |
