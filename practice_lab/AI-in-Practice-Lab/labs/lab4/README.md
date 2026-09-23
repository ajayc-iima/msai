# Lab 4 — RAG v1: Grounded Answers with Citations
**3 hours · Pairs · Prepared by T4**

> **Docs:** [README](README.md) (this brief) · [RUNSHEET](RUNSHEET.md) (the actions) · [CONCEPTS](CONCEPTS.md) (theory → code) · [report.md](report.md) (yours to fill)
> Track N: [`lab4.ipynb`](lab4.ipynb) (numbered *your turn* cells) · Track S: `rag.py` + `evaluate.py`

---

## The one-sentence version

**An answer without a source is a liability in a regulated business — and before you may report a number produced by an LLM judge, you have to earn the right to use it.**

---

## The problem

Lab 3 gave you a retriever that puts the right document in the top 5 about 85%
of the time. Agents still have to read the passages and work out the answer.

Now generate the answer. But an insurance helpdesk cannot ship a system that
sometimes invents a claim deadline, so the answer comes with two hard
constraints:

1. **Every factual sentence carries a citation** to a source you supplied, and
   the citation index is validated in code.
2. **When the sources do not contain the answer, the system says so** — in an
   exact, machine-detectable form — rather than guessing.

Constraint 2 is where systems like this usually fail, and it is why 5 of the 45
golden questions are unanswerable.

### Targets on the 45-question golden set

| Metric | Target | Reference solution |
|---|---|---|
| Citation validity (every `[n]` refers to a real source) | **1.00** | 1.000 |
| Faithfulness (no claim unsupported by context) | ≥ 0.90 | 0.933 |
| Answer correctness (LLM-judged, calibrated) | ≥ 0.75 | 0.825 |
| Refusal recall (of 5 unanswerable, how many declined) | ≥ 4/5 | 5/5 |
| Refusal precision (of your declines, how many were right) | ≥ 0.70 | 0.714 |
| Repair rate | reported | 0.089 |
| Cost per query | ≤ $0.01 | $0.0095 |
| p95 end-to-end latency | ≤ 6,000 ms | 4,259 ms |

**Both refusal numbers are extremely noisy and you must say so.** There are
only 5 unanswerable questions; the reference solution declined 7 in total. One
case moves precision by 0.12 and recall by 0.20. Report the raw counts
alongside the ratios (`3/5`, not `0.60`) and claim no difference below about
0.15. And report **both** — a system that refuses everything scores recall
1.00. Full mechanics: [CONCEPTS.md](CONCEPTS.md).

---

## Timetable

| Time | Part | What you do |
|---|---|---|
| 0:00–0:20 | **A** | The generation prompt and the output contract |
| 0:20–0:50 | **B** | Citation enforcement in code |
| 0:50–1:20 | **C** | Refusal: the escape hatch, and measuring both directions |
| 1:20–2:05 | **D** | The judge: rubric, calibration, and earning the right to use it |
| 2:05–2:40 | **E** | Full evaluation + the gold-context decomposition |
| 2:40–3:00 | Show & tell | Your numbers, and one answer that is confidently wrong |

**During the lab, work from [RUNSHEET.md](RUNSHEET.md)** — it has the exact
commands, numbered TODOs, checkpoints, and the troubleshooting table. This
README is the brief; the RUNSHEET is the procedure.

---

## Why this lab exists

Lab 3's retriever found the passage. The moment you generate text from it, two
threads run through this lab. The first is the citation/refusal contract above.
The second, more important one: you are about to measure quality with a model,
and that instrument needs calibrating like any other. This module's own harness
once read faithfulness as **0.667** when the true value was **0.933** — a
truncated judge verdict, scored as zero, with nothing erroring. The full war
story and the rule it produced are in [CONCEPTS.md](CONCEPTS.md).

**Where it sits.** The failures you produce today are Lab 5's backlog — bring
them. The pipeline you build here is what Lab 6 adds tools to and Lab 7 ships.

---

## What you will build

- An **answer prompt** with a source-only rule, an exact refusal string, and a
  policy for contradictory sources
- **Citation validation in code** — target 1.00, because it is a code guarantee
  and not a model behaviour
- **Refusal**, measured in both directions, including one question that needs a
  *partial* answer
- **Two single-criterion judges** — faithfulness and correctness — each with a
  **Cohen's κ against your own hand labels**
- The **gold-context decomposition**: the single most useful experiment in RAG
  debugging, and the one that tells you how to spend Lab 5

---

## How to approach it

**The step people underestimate is judge calibration (D2), and it is required.**
Twenty hand labels against each rubric, done *before* you look at what the judge
said. Budget the full 45 minutes for Part D. You may not report a judge number
in this lab without its κ, and κ is 25% of the rubric.

Do the hand labelling as a pair, independently, then compare. Where the two of
you disagree is almost always where your rubric is implicit — and that is the
same thing the judge is struggling with.

**Run E2 even if you are short of time.** It is one extra evaluation run and it
decides what you do for the whole of next week.

Hints worth carrying into the work (the operational ones live as checkpoints in
the RUNSHEET):

- **Numbering the sources is what makes one class of hallucination provable.**
  `[7]` with five sources is a mechanical error — no judge, no cost.
- **Design so that errors become checkable in code, then check them there**,
  rather than asking a model whether it lied.
- **A parse failure is missing data, not a failing answer.** If your harness
  scores it zero, every number it has ever given you is biased downward.

The map from theory session to today's work is in
[CONCEPTS.md](CONCEPTS.md).

---

## Parts in brief

**A — The generation prompt (20 min).** Write `ANSWER_SYSTEM` yourself before
opening `aip/rag.py`, against the six required elements (T4 §6.1), then diff
yours against the reference. Deliverable: your prompt + the differences noted.
RUNSHEET §1.

**B — Citation enforcement (30 min).** Number the sources, implement
`validate_answer()` (range, truncation, ≥1 citation), pick a repair strategy
for validation failures and defend it, then report citation validity across all
45 — target 1.00. Deliverable: the validator + your defended failure path.
RUNSHEET §2.

**C — Refusal, both directions (30 min).** Run the 5 unanswerable questions,
make Q37 answer partially, measure wrongful refusals on the 40 answerable, move
the strictness dial and report both numbers at both settings. Deliverable: the
two-direction table + a product recommendation with cost-of-error reasoning.
RUNSHEET §3.

**D — The judge (45 min).** Two separate single-criterion rubrics, hand-label
20 answers against each *before* reading the judge, compute κ for both —
κ ≥ 0.4 or fix the rubric and re-run — and state the self-preference direction.
Deliverable: both κ values in `report.md`. RUNSHEET §4.

**E — Full evaluation (35 min).** `--full --save reports/lab4.json`, then the
gold-context decomposition (A, B, A−B, 1−A), then read 10 wrong answers and tag
each with one of the seven failure modes. Deliverable: the metrics table, the
decomposition, the E3 tally = your Lab 5 backlog. RUNSHEET §5.

---

## Choose ONE track

Pick one and ignore the other for the whole lab.

**Track N — Notebook.** [`lab4.ipynb`](lab4.ipynb) is the whole lab as one file.
Run cells in order; edit *your turn* cells there. Submit by finishing `rag.py`
and `evaluate.py` and filling [`report.md`](report.md) by hand.

```bash
jupyter lab labs/lab4/lab4.ipynb
```

**Track S — Scripts.** Ignore the notebook. Edit only `rag.py` and
`evaluate.py`. The same TODOs appear as docstrings; the RUNSHEET maps them.

Either way you submit `rag.py`, `evaluate.py`, `reports/lab4.json`, and
[`report.md`](report.md).

---

## Deliverables

1. `labs/lab4/rag.py`, `labs/lab4/evaluate.py`
2. [`report.md`](report.md) — at most three pages:
   - your `ANSWER_SYSTEM`, with the differences from the reference noted
   - citation validity, and what you do on failure
   - the refusal precision/recall table at two strictness settings, with raw
     counts and your product recommendation
   - judge κ for both rubrics, and how you fixed the rubric if you had to
   - the E2 decomposition table with A, B, and the two attributed losses
   - the E3 failure-mode tally
3. `reports/lab4.json`

---

## What separates a good report from an adequate one

- An adequate report gives faithfulness and correctness. A good one gives them
  **with κ**, and says what it changed when κ was too low.
- An adequate refusal section gives precision. A good one gives **both rates at
  two settings**, and a product recommendation grounded in the relative cost of
  the two error types — not in "precision matters more".
- The **decomposition** is the highest-value table in the report. A and B, the
  two attributed losses, and one sentence saying where Lab 5 will go.

---

## Rubric (9% of Module 1)

| Criterion | Weight | Full marks means |
|---|---|---|
| Grounding | 20% | Citation validity 1.00, enforced in code not by prompt |
| Refusal | 20% | Both directions measured; Q37 partial handled; product recommendation defended |
| Judge rigour | 25% | κ reported for both rubrics, ≥ 0.4, self-preference addressed |
| Decomposition | 20% | E2 done correctly and the conclusion drawn |
| Engineering | 15% | Runs on the full set within budget; traces usable in Lab 5 |

---

## Stretch

1. **Streaming.** Stream the answer token-by-token. Measure TTFT vs total.
   Then explain the problem streaming creates for citation validation, and
   solve it.
2. **Answer-level confidence.** Combine top retrieval score, number of sources
   cited, and self-consistency across 3 samples into a single confidence score.
   Does it predict correctness? Show the correlation, not a claim.
3. **Two-model agreement.** Generate with two providers; disagreement flags for
   review. What is the false-alarm rate?
4. **Conversational RAG.** Add history and a query-rewriting step that resolves
   "what about on Gold?" against the previous turn. Measure the rewriter's
   accuracy separately.

---

## Questions we will discuss

1. Your decomposition probably says generation is the larger loss. Did you
   expect that? What would you have worked on if you had not measured it?
2. Refusal precision and recall trade against each other. For an insurance
   helpdesk, what is the exchange rate — how many unnecessary refusals is one
   invented claim deadline worth?
3. Your judge and your generator may be the same model family. Which direction
   does that bias your numbers, and by roughly how much would you guess?
4. Citation validity is 1.00 and faithfulness is 0.93. A sentence can carry a
   valid citation and still not be supported by it. What would it take to close
   that gap mechanically?
