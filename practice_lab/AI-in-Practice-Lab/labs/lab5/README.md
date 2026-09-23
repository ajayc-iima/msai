# Lab 5 — RAG v2: Diagnose, Fix, Prove
**3 hours · Pairs · Prepared by T4 §5**

> Docs: [`README.md`](README.md) — this brief (problem, targets, rubric) ·
> [`RUNSHEET.md`](RUNSHEET.md) — procedure, code TODOs, troubleshooting ·
> [`CONCEPTS.md`](CONCEPTS.md) — theory and the full reference run; keep open ·
> [`report.md`](report.md) — yours to fill ·
> Track N: [`lab5.ipynb`](lab5.ipynb) — numbered *your turn* cells

**In one line.** The difference between engineers who improve systems and
engineers who thrash is diagnosis before treatment — and this is the only lab
in the module where the reference solution's fix made things *worse* and still
scores full marks.

**Two tracks.** Track N is the notebook above; Track S is the script
`labs/lab5/diagnose.py`. Pick one and ignore the other for the whole lab. You
submit `diagnose.py` + `report.md` either way.

---

## The problem

Your Lab 4 system gets roughly a quarter of the questions wrong.

The instinct at this point is to try things: bigger model, more chunks, a
different embedding. That is how teams spend six weeks and gain two points.

This lab teaches the alternative. **Every wrong answer has exactly one stage
that failed. Find it, count how often each stage is at fault, fix the biggest
cluster, and prove the fix with a before/after table.**

You are graded on the *process*, not the final score. A team that raises
correctness by 4 points and can show exactly which failure mode they eliminated
scores higher than a team that raises it by 12 points and cannot say why.

**Where it sits.** It reads `reports/lab4.json` and cannot start without it.
The pipeline you leave here is what Lab 7 ships.

### Targets

| Requirement | Target |
|---|---|
| Failure classification | every Lab 4 failure classified into the 7 modes, with evidence |
| A prediction | stated **before** implementing: which cluster, how many recoveries |
| A measured before/after | on every Lab 4 metric, not just the one you targeted |
| Regression check | anything that got worse is reported, prominently |
| Cost discipline | your fix costs ≤ 2× the Lab 4 baseline per query |

**There is no improvement target, and that is deliberate.** The reference
solution diagnosed the dominant cluster, chose a well-motivated fix, predicted
4–6 recoveries — and measured **−0.050 correctness**. The fix made the system
worse, and that is a complete, full-marks Lab 5. What is graded is whether you
diagnosed before you fixed, predicted before you measured, and reported what
happened rather than what you hoped. Full story: [`CONCEPTS.md`](CONCEPTS.md).

---

## Timetable

| Time | Part | What you do |
|---|---|---|
| 0:00–0:50 | **A** | Classify every failure. This is most of the lab |
| 0:50–1:10 | **B** | Rank the clusters by expected value |
| 1:10–2:20 | **C** | Fix the top cluster. Then the second, if time |
| 2:20–2:45 | **D** | Prove it: before/after, regression check, cost |
| 2:45–3:00 | Show & tell | Your Pareto chart and your one fix |

---

## What you will build

- A **classification of every Lab 4 failure** into the seven modes, with
  evidence for each
- A **Pareto chart** showing that two modes account for most of them
- A **ranking by expected value** — recovery weighed against cost, latency and
  effort — and a one-sentence justification for your pick
- A **prediction**, written down before you implement
- One **fix**, measured, with a full before-and-after table and a genuine
  regression check

---

## How to approach it

**Part A is most of the lab — fifty minutes, and it is not optional.**
`diagnose.py` automates six of the seven checks; the one it cannot decide is
mode 2, chunk boundaries, because that needs someone to look at where the cut
fell and judge whether the two halves are separately retrievable.

**Write the prediction down before you touch any code.** Not in your head, in
the report. It is the difference between an experiment and a story told
afterwards.

**One fix at a time, measured each time.** If you apply three and the number
moves, you have learned nothing you can carry to the next system — and a fix
that helped may be hiding one that hurt.

---

## Part A — Classify every failure (50 min)

Run `python labs/lab5/diagnose.py --input reports/lab4.json`. It decides six
of the seven modes; you judge mode 2 by opening the chunks around the gold
answer. Deliver the tally (**A1**), the human review of every
`needs_human_check` (**A2**), and the Pareto chart with the two dominant modes
named (**A3**). A concentrated tally is normal; a flat one means
mis-classification — full tree and measured distribution:
[`CONCEPTS.md`](CONCEPTS.md).

**Full procedure: [`RUNSHEET.md`](RUNSHEET.md) step 1.**

---

## Part B — Rank by expected value (20 min)

Fill the ranking table — cluster, n, fix, estimated recovery, cost delta,
latency delta, effort. Pick one cluster and justify the pick in one sentence.
Then write the prediction down, before you implement: *"I expect this to
recover N of the M failures in this cluster."* Being wrong is informative;
not predicting is penalised.

**Full procedure: [`RUNSHEET.md`](RUNSHEET.md) step 2.**

---

## Part C — Implement the fix (70 min)

Three rules: **one fix at a time, measured each time**; **record the failures
too**; **fix what the diagnosis says, not what you reach for by reflex**. Your
fix must cost ≤ 2× the Lab 4 baseline per query. The fix catalogue by mode —
with the `aip/` module to reach for each — lives in the runsheet.

**Full procedure and catalogue: [`RUNSHEET.md`](RUNSHEET.md) step 3.**

---

## Part D — Prove it (25 min)

Before/after on the same questions with **every** Lab 4 metric (**D1**); a
regression check that reports anything worse prominently (**D2**); re
-classification of the remaining failures — did the distribution shift as you
predicted (**D3**); and the next fix you would make, and what you expect it to
be worth (**D4**).

**Full procedure: [`RUNSHEET.md`](RUNSHEET.md) step 4.**

---

## Hints

- **A tally spread evenly across all seven modes means you mis-classified.**
  A heavily concentrated tally is normal and is not a mistake.
- **Your distribution will not match the reference's, and should not.** Its 93%
  mode-6 concentration is a consequence of starting from Lab 3's *winning*
  retriever. If you ended Lab 3 somewhere else, your backlog is different —
  and that is exactly why you classify rather than copy. Measured numbers:
  [`CONCEPTS.md`](CONCEPTS.md).
- **The mode-6 test is the one people invert.** Gold context *fixing* the
  answer means **retrieval** was at fault. Full explanation:
  [`CONCEPTS.md`](CONCEPTS.md); you will meet it as the Part A checkpoint in
  [`RUNSHEET.md`](RUNSHEET.md).
- **When your fix and your tally disagree, stop.** Either the tally wins or the
  tally was wrong; resolving that is the work — [`RUNSHEET.md`](RUNSHEET.md)
  step 3.
- **If Q29–Q31 are still failing, the fix is metadata filtering and it is
  free.** If you already did it in Lab 3, say so —
  [`RUNSHEET.md`](RUNSHEET.md) step 3.
- **Check refusal precision in your regression check.** Better retrieval often
  makes a system refuse *less*, which means it starts answering questions it
  should decline — [`RUNSHEET.md`](RUNSHEET.md) step 4.

---

## Deliverables

1. `labs/lab5/diagnose.py` with your completed classification, and your fix
2. `report.md` — at most three pages:
   - the failure tally and the Pareto chart
   - your Part B ranking table and the justification for your pick
   - your prediction, and what actually happened
   - the D1 before/after table
   - the D2 regression check, including anything that got worse
   - the D3 re-classification
   - **the fix that did not work**, with its number
3. `reports/lab5_before_after.json`

---

## What separates a good report from an adequate one

- An adequate report has a tally. A good one has a tally **with evidence per
  case** and a named judgement on every `needs_human_check`.
- An adequate report shows the metric it targeted. A good one shows **every Lab
  4 metric**, with whatever got worse reported prominently rather than in a
  footnote.
- A good report **re-classifies the remaining failures** and notices when
  failures have moved downstream — that is not a new problem, it is a
  previously masked one becoming visible, and saying so is the mark of someone
  who understands their own pipeline.

---

## Rubric (9% of Module 1)

| Criterion | Weight | Full marks means |
|---|---|---|
| Diagnostic rigour | 35% | Every failure classified with evidence; mode-6 test done correctly |
| Prioritisation | 15% | Ranking by expected value, not by what seemed interesting |
| Fix quality | 20% | Implemented cleanly, measured, one variable at a time |
| Proof | 20% | Before/after complete; regression check genuine; nothing hidden |
| Honesty | 10% | Prediction stated up front; negative results reported |

---

## Stretch

1. **Automate mode 2.** Detect chunk-boundary failures by checking whether the
   gold answer span is split across chunks. Report your detector's precision
   against your hand labels from A2.
2. **Contextual retrieval** end to end, with the ingest cost measured.
3. **Multi-hop decomposition** for Q19–Q28. Measure on that subset only.
4. **Adaptive retrieval.** Route by query type: identifier → BM25, paraphrase →
   HyDE + dense, comparison → multi-query. Does routing beat one good pipeline?
5. **Ablation.** Remove each component of your final pipeline one at a time and
   report what each is actually worth. Some of them will be worth nothing.

---

## Questions we will discuss

1. Your prediction versus what happened. If you were wrong, was your model of
   the system wrong, or was the fix a bad implementation of a good idea?
2. The reference relaxed the answer-length rule and correctness *and* refusal
   precision both fell. What is the mechanism connecting those two?
3. You ranked clusters by expected value. Did the largest cluster win? If it
   did not, what beat it?
4. Which of the seven modes is the only one with no retrieval or generation fix
   at all — and what would you actually do about a system whose failures were
   mostly that?
