# Lab 5 Report — RAG v2: Diagnose, Fix, Prove

**Student:** Ajay Choudhary · **ID:** P20260002 · **Date:** 2026-10-03 · Module 1 (9%)

---

## 0. The baseline moved before the lab started

Lab 4's generator (`nemotron-3-super-120b-a12b`) returned HTTP 410 — end-of-life
2026-10-03T09:00Z, hours before this session (the same death `SMALL` died on
09-01). The verified replacement is `nemotron-3-nano-omni-30b-a3b-reasoning`;
`EMBED` and the `LARGE` judge are unchanged, so retrieval is bit-identical and
the instrument is the same. I re-ran the unmodified Lab 4 pipeline as arm
**v1** and use *that* as the baseline; `lab4-original` below is a reference
column only. Zero throttle waits fired in any arm.

## Part A — Classify every failure

**The shipped classifier put all 17 failures in mode 6** — the handout's own
mis-classification symptom. It asks the gold-context question before asking
whether the gold document reached the generator. I reordered it around one
check — *was the material already in front of the generator?* — with three
signals: `can_full` (every gold chunk: the capability ceiling), `can_window`
(5 chunks from gold docs only: is a five-slot window *enough*?), `span_ok` (the
gold numbers/words survive into the window: free, deterministic).

**The correction that reframed the lab.** A span-only classifier gave 8 mode-4 /
8 mode-6. The `can_full` probe overturned six of the eight 4s — Q04, Q20, Q21,
Q26, Q35 fail *even handed every gold chunk*. **The span check tells you where
material is missing; only a probe tells you whether its absence caused the
failure.**

### Tally (17 failures of 45) and Pareto

| mode | n | ids |
|---|---|---|
| 6 generation | 12 | Q04, Q05, Q06, Q07, Q10, Q11, Q20, Q21, Q22, Q26, Q29, Q35 |
| 4 ranking | 4 | Q19, Q24, Q32, Q34 |
| 3 embedding mismatch | 1 | Q37 |
| 1 / 2 / 5 / 7 | 0 | — |

```
generation            12   70.6%   70.6%  █████████████████████
ranking                4   23.5%   94.1%  ███████
embedding_mismatch     1    5.9%  100.0%  ██
```

**12 of 17 fail even with every gold chunk** — a capability ceiling no retriever
can lift. Mode 5 is structurally impossible (Lab 3 never recorded a rerank
sweep; no second stage exists to err) and mode 7 is zero (citation validity was
already 1.000). Evidence per case: `reports/lab5_diagnosis.json`,
`reports/lab5_evidence.txt`. One hand label (Q19, 2→4: the missing chunk is
well formed at rank 8, so window *size* binds, not chunking) overrides the
script; sixteen agree.

Two cases no script can decide. **Q29 is not the archived-document trap:** every
"missing" word comes from the gold answer's own parenthetical — grader
annotation. It answered 45 days correctly, then contaminated it with the
*current* motor-insurance deadline (faithfulness 0). The archived doc was never
retrieved here, and Lab 3 measured the archived filter at 1.000→1.000 on
Q29–Q31: it does nothing. **Q37's 31% span coverage is a measurement artefact**
(the gold is a PARTIAL REFUSE, mostly grader instruction). By hand: `exclusions`
never reached the top 30 — retrieval, not refusal policy — and self-retrieval
confirms mode 3.

## Part B — Rank by expected value

| # | cluster (n) | fix | est. recovery | cost Δ | verdict |
|---|---|---|---|---|---|
| 1 | 6 (12) | completeness clause for the brevity rule | 4–7 | +25–40% completion tokens, +0 calls | **PICK — only candidate touching 12/17; the dropped-qualifier shape is what rule 5 invites** |
| 2 | 4 (4) | cross-encoder rerank, 30→5 | 2–3 | ~0 tokens, +0.6 s local | second, measured separately |
| 3 | 4 (4) | `final_k` 5→10 | 1 (only Q19's rank-8 material is reachable) | +60–80% prompt | rejected — three failures sit at rank 18 |
| 4 | 6 (12) | larger tier | 2–5 | +2–4 s latency | rejected — the forced migration already changed the generator once; a second change would make the delta uninterpretable |

"Raise `final_k`" is the reflex fix for cluster 4 and nearly worthless here.
A larger tier is the honest runner-up and the first thing to try next.

> **Prediction (pre-registered).** v2a recovers 4–7 of the 12 (most likely Q05,
> Q06, Q07, Q22, Q24), correctness +0.05–+0.09, +0 calls/query — **and refusal
> precision falls**, since covering-every-part looks, on an unanswerable
> question, like an instruction to answer it. v2b recovers 2–3 of the 4 (Q19
> likely; rank-18 cases unlikely).

## Part C — The fix, one variable at a time

- **v1**: Lab 4 verbatim — `ANSWER_SYSTEM` *imported*, not re-typed (a re-typed
  prompt is a silent second variable). Baseline.
- **v2a**: v1 with rule 5 ("two or three sentences") replaced by COMPLETENESS
  BEFORE BREVITY. Same retrieval, validation, refusal string. Targets mode 6.
- **v2b**: v2a + cross-encoder rerank (MiniLM, local ~90 MB) over dense k=30 →
  5. Targets mode 4 without inflating context. v1→v2a and v2a→v2b each isolate
  one change. (A first v2a run silently reused v1's prompt and every number
  came back identical; the harness now asserts the sent prompt per arm.)

## Part D — Prove it

### D0. The migration, as its own number

lab4-original → v1: correctness 0.787→0.762 (−0.025), faithfulness
0.795→0.756 (−0.039), refusal precision 0.833→1.000 (+0.167). Everything below
is v1→v2 with the generator held fixed.

### D1. Before/after, same 45 questions, every Lab 4 metric

| Metric | v1 | v2a | Δ | v2b | Δ |
|---|---|---|---|---|---|
| correctness (norm.) | 0.762 | 0.762 | **+0.000** | 0.775 | **+0.012** |
| faithfulness | 0.756 | 0.711 | −0.044 | 0.756 | +0.000 |
| citation validity | 1.000 | 1.000 | 0 | 1.000 | 0 |
| refusal recall | 1.000 | 0.800 | −0.200 | 0.800 | −0.200 |
| refusal precision | 1.000 | 1.000 | 0 | 1.000 | 0 |
| gold-doc coverage | 0.907 | 0.907 | 0 | 0.881 | −0.026 |
| calls / query | 3.02 | 2.96 | −0.07 | 2.98 | −0.04 |
| tokens / query | 3519 | 3733 | +6.1% ✓ | 3513 | −0.2% ✓ |
| gen p50 / p95 (ms) | 6351 / 26878 | 11720 / 34290 | — | 8381 / 36020 | — |

Latency is provider variance, not the pipeline (v2b p50 < v2a p50 despite an
extra stage; the reranker is ~0.6 s local). No arm added a model call — the ≤2×
cost rule holds with headroom.

**Prediction vs. what happened.** v2a recovered 3 of 12 (Q07, Q08, Q24) plus
Q29 partially — just under the predicted 4–7 — and correctness moved **+0.000**.
The fix recovered the under-answering cases it targeted and lost the same
number by the symmetric mechanism. v2b recovered Q21 (not the predicted
Q19) plus Q43; the rank-18 cases did not move, as predicted. The predicted
refusal-precision fall did not happen (1.000 held); instead **refusal recall
fell to 0.800** — right direction, wrong column.

### D2. What got worse, prominently

v2a gained 4, lost 5; v2b gained 5, lost 5:

| arm | gained | lost |
|---|---|---|
| v2a | Q07, Q08, Q24 (qualifiers volunteered), Q29 (0→1) | Q01, Q30, Q31 (2→1: surfaces archived/current disagreements the gold omits), Q25 (2→1: bare "₹60,000" scores below the shown computation), **Q37 (1→0: confident answer to an unanswerable question)** |
| v2b | +Q21, +Q43 | Q12 (2→1: dropped the governing-act qualifier), **Q26 (1→0: reranker evicted the 24-month list; model asserts "30-day")**, **Q39 (2→0: refusal → "No, the policy does not cover a dog's bills [2]")** |

Three mechanisms: (1) completeness answers the unanswerable (Q37, Q39 —
recall −0.200 in both arms); (2) completeness volunteers disagreements the gold
omits (Q01, Q30, Q31); (3) **the reranker promotes fluent distractors** —
coverage *falls* 0.907→0.881, Q26 is the receipt.

### D3. Re-classification of the remaining failures (v2b: 18 failures)

| mode | n | shift vs v1-based tally |
|---|---|---|
| 6 generation | 12 | Q07, Q08, Q24, Q21 out (recovered); Q01, Q12, Q30 in (sufficient window, misused); Q26 in (commits to the distractor) |
| 5 reranker | 2 | **new — Q19, Q41: the needed chunk sat in the dense top-30 pool and the cross-encoder dropped it** (rank-8 rule clause; rank-6 consequence clause, replaced by waiting-period lookalikes) |
| 4 ranking | 2 | Q24 recovered, Q19→5; Q32, Q34 unmoved at rank 18, as predicted |
| 3 / 1 | 1 / 1 | Q37 unchanged; **Q39 is new mode 1**: its gold is a REFUSE with no relevant docs, so answering at all is the failure — correctly reported as nothing-to-retrieve |

Failures moved downstream exactly as theory describes: fixing retrieval revealed
the next weakest stage, and the new stage is one the fix itself built — the
first mode-5 instances in the lab are the reranker's own drops.

### The fix that did not work, with its number

**Completeness clause: +0.000 correctness (1.525→1.525).** 3 of 12 recovered, 5
lost. Cross-encoder: +0.012, recovering Q21 while creating Q26. Neither is
recommended for adoption as-is.

### D4. Next fix

A larger generation tier: 12 failures are generator-side ceilings and the prompt
trades under-answering for over-answering ~1:1. Expected +0.05–0.10 if the
ceiling is capacity, not contract. Second: a refusal guardrail (answer only
from ≥1 gold-doc chunk) for the −0.200 recall loss.
