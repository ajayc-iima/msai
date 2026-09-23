# Lab 5 — Concepts
### Keep this open while you work

> Docs: [`README.md`](README.md) — the brief · [`RUNSHEET.md`](RUNSHEET.md) —
> the procedure · [`report.md`](report.md) — yours to fill

| Concept | In the code | In the theory |
|---|---|---|
| The seven failure modes | `diagnose.py` | T4 §5 |
| The diagnostic tree | `diagnose.py` | T4 §5 |
| The gold-context test | mode-6 check | T4 §5, Lab 4 E2 |
| Error analysis as a method | Part A | T3 §5.1 |
| Pareto prioritisation | `--pareto` | T3 §5.4 |
| Expected-value ranking | your Part B table | T3 §5.4 |
| Pre-registered prediction | your Part B | — |
| One variable at a time | Part C rule 1 | T3 §5.2 |
| Regression checks | your D2 | T3 §5.3 |
| Ablation | Stretch 5 | T3 §5.4 |

---

## Where this comes from in the theory

| Theory | What it claimed | Where you meet it today |
|---|---|---|
| **T4 §5** — the seven failure modes | Exactly one stage usually failed; here is the tree | Part A. The whole lab is built on this table |
| **T4 §5 #6** — the gold-context test | The single most useful experiment in RAG debugging | The mode-6 branch. Note which way round it reads |
| **T4 §2.2–2.3** — chunking | Boundaries, overlap, small-to-big | The mode 2 fix menu |
| **T4 §4.3, §4.5** — hybrid, HyDE, multi-query | Query-side transforms for lexical mismatch | The mode 3 fix menu — and each adds a call per query |
| **T4 §4.4** — rerank narrow | Two-stage retrieval | The mode 4 and 5 fix menus |
| **T3 §5.1** — error analysis | The step actually worth your time | Part A. Fifty minutes of reading failures, deliberately |
| **T3 §5.2** — change one thing | One variable or nothing transferable | Part C rule 1 |
| **T3 §5.3** — regression checks | Measure everything; report what got worse | Part D2 |
| **T3 §5.4** — Pareto, expected value, ablation | Fix the head of the distribution; weigh cost; strip to find worth | Parts A3, B, Stretch 5 |
| **T3 §1.1** — no number, no claim | | Part D. Including the numbers that went the wrong way |

---

## The seven failure modes

**What it is.** When a RAG system gives a wrong answer, *"RAG is bad"* is not a
diagnosis. Exactly one stage usually failed, and each has a different test and a
different fix.

| # | Stage | Confirmed by | Fixed by |
|---|---|---|---|
| 1 | Missing content | grep the corpus | **Nothing in retrieval.** Fix the data |
| 2 | Chunk boundary | Read the chunks around the gold answer | Larger chunks, overlap, markdown-aware, small-to-big |
| 3 | Embedding mismatch | Search the gold chunk's own text — if *that* retrieves it, the query is the problem | Hybrid, HyDE, contextual retrieval |
| 4 | Ranking | Compare hit_rate@30 with hit_rate@5 | Rerank; raise `final_k` |
| 5 | Reranker error | Log pre- and post-rerank ids | Different reranker; keep stage-1 top-1 unconditionally |
| 6 | Generation | **Run the generator on gold context** | Prompt, tier, fewer distractors, decomposition |
| 7 | Presentation | Answer right, citation wrong | Output contract; validate before returning |

**In the code.** `diagnose.py` automates six of the seven.

**In the theory.** T4 §5.

---

## The diagnostic tree, and the one test people invert

```
                    wrong answer
                         │
        ┌────────────────┴────────────────┐
   is the answer in the corpus at all?
        │ no                              │ yes
        ▼                                 ▼
   FAILURE 1                    does gold context fix it?
   (data problem)                        │
                          ┌──────────────┴──────────────┐
                       yes │                            │ no
                           ▼                            ▼
                  retrieval problem                 FAILURE 6
                           │                       (generation)
              ┌────────────┴────────────┐
       is it in the top 30?
              │ no                      │ yes
              ▼                         ▼
       FAILURE 2 or 3            FAILURE 4 or 5
```

**Read the mode-6 branch twice.** Gold context **fixing** the answer means
retrieval was at fault — the generator was fine and never got the material.
Still wrong with gold context means the generator cannot do the job even with
perfect input. People get this backwards, and a whole lab's work goes to the
wrong stage.

**Mode 2 is the one that is not automated.** "Did the answer get cut in half?"
needs someone to look at where the cut fell and judge whether the two halves are
separately retrievable. That is a judgement about meaning, not a string
operation.

**A flat tally across all seven modes means you mis-classified.** A heavily
concentrated one is normal — and yours will not match the reference's, because
the distribution is a property of *your* pipeline, not of RAG. The reference's
measured numbers are in the process story below.

---

## The process story: predicted +, measured −0.050

**There is no improvement target — and that is deliberate.**

When the reference solution ran this lab it:

1. **Diagnosed correctly.** 13 of 14 failures were mode 6 (generation) and one
   was mode 4 — a 93% concentration, starting from Lab 3's *winning* retrieval
   configuration. Its gold-context decomposition agreed independently:
   generation-attributable loss 0.107 against retrieval-attributable loss 0.071.
2. **Chose a well-motivated fix** for that cluster.
3. **Predicted, before implementing,** that it would recover 4–6 of the 13
   failures.
4. **Measured −0.050 correctness.** The fix made the system worse. The
   prediction was wrong in *direction*, not just magnitude.

**That is a complete, full-marks Lab 5.** What is graded is whether you
diagnosed before you fixed, predicted before you measured, and reported what
happened rather than what you hoped. A pair reporting −0.05 with a clear
account of why scores above a pair reporting +0.12 they cannot explain.

**Why a negative result still scores.** Without a pre-registered prediction,
any outcome can be narrated as the one you expected. With one, a wrong
prediction is data about your model of the system — the most useful kind of
wrong. Write it in the report, not in your head.

**Your backlog is yours.** The 93% mode-6 concentration is a consequence of the
reference's starting point. If you ended Lab 3 somewhere else, your
distribution will differ — and that is exactly why you classify rather than
guess.

---

## Pareto prioritisation

**What it is.** The observation, general to defect data, that failures are not
spread evenly: a small number of causes account for most of them. Sort your
clusters by count, plot them descending, and read where the curve flattens.

**In the code.** `diagnose.py --pareto`.

**In the theory.** T3 §5.4.

**Why it is the right first move.** It converts "we have 14 failures" into "two
modes account for 13 of them", and it tells you that fixing anything outside the
head of the distribution cannot move your headline number much — however
interesting that fix is.

**The trap.** Pareto ranks by **count**. It does not know that the biggest
cluster might have the most expensive fix. It is where you start, not where you
decide. That is the next section.

---

## Expected-value ranking

**What it is.** The decision rule that turns a Pareto chart into a plan. For
each cluster:

| Cluster | n | Fix | Est. recovery | Cost Δ | Latency Δ | Effort |
|---|---|---|---|---|---|---|

Then pick, and justify the pick in one sentence.

**In the theory.** T3 §5.4.

**Why the largest cluster does not automatically win.** A cluster of 9 whose fix
adds a model call per query — HyDE and multi-query both do — can lose to a
cluster of 6 with a free fix like metadata filtering. Lab 5's cost discipline is
explicit: your fix must cost **≤ 2× the Lab 4 baseline per query**, so an
expensive fix has to earn that price in recoveries.

**How to estimate recovery honestly.** Read a sample of the cluster and ask, per
case, whether the proposed fix would actually have helped. Six of nine is a
better estimate than "most of them", and it is the number your prediction gets
compared against.

**This is the same triple as everywhere else** — quality against cost against
latency — applied to a backlog instead of a configuration.

---

## Pre-registered prediction

**What it is.** Writing down, before you implement, how many failures you expect
to recover.

**Why.** It turns the fix into an **experiment**. Afterwards you know not just
what happened but whether your model of the system was right. Without it, any
outcome can be narrated as the one you expected.

**Being wrong is not penalised. Not predicting is.** The reference predicted
4–6 of 13 recoveries and measured **−0.050** — wrong in *direction*, not merely
magnitude, and that is the most useful kind of wrong. Full account: the process
story above.

**Write it in the report, not in your head.**

---

## Regression checks

**What it is.** After a change, measure **every** metric — not only the one you
targeted — and report whatever got worse, prominently.

**In the theory.** T3 §5.3.

**The three the handout names:**

- **Refusal precision.** Better retrieval often makes a system refuse *less*,
  which means it starts confidently answering questions it should decline. This
  is the improvement quietly buying itself a new problem.
- **Cost and p95.** HyDE and multi-query each add a call per query.
- **The question kinds that were already passing.**

**Re-classify the survivors.** If failures moved from mode 3 to mode 6, that is
not a new problem — a question failing at retrieval never got the chance to fail
at generation, so fixing retrieval **reveals** the next weakest stage. Say so;
it is progress, and it tells you where the next fix goes.

---

## Ablation

**What it is.** Remove one component of a working pipeline at a time and
re-measure. What the number drops by is what that component was actually worth.

**In the theory.** T3 §5.4. In the lab it is stretch goal 5.

**Why it matters more than it sounds.** Pipelines accumulate. A reranker added
in week two, a query rewriter in week four, an extra retrieval pass in week six —
each justified when added, none re-checked since. Ablation is the only way to
find out that two of them are now worth nothing, and it is how you make a system
cheaper without making it worse.

**The relationship to this lab.** A fix that "worked" and an ablation that shows
it contributes nothing are the same measurement taken at different times.
