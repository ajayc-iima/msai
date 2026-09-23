# Lab 2 — The Prompt Lab: Build the Harness, Then Let It Choose
**3 hours · Individual**

> **Docs:** [README](README.md) (this brief) · [RUNSHEET](RUNSHEET.md) (the actions) · [CONCEPTS](CONCEPTS.md) (theory → code) · [report.md](report.md) (yours to fill)
> Track N: [`lab2.ipynb`](lab2.ipynb) · Track S: `variants.py` + `grid.py`

---

## The one-sentence version

**In Lab 1 you built something that works. In Lab 2 you find out whether it is
the best version of itself — and you build the measuring instrument that can
answer that question honestly.**

---

## The problem

You finished Lab 1 with a working extractor and an opinion about why it works.

Your opinion is not evidence.

There are at least twelve reasonable configurations of that extractor, and you
have tried one. Somebody is going to ask which one to deploy, and "this one
felt good" is not an answer they can act on.

**Build an experiment harness, run the grid, and produce a recommendation
defensible on quality × cost × latency.**

### The grid

| Axis | Levels |
|---|---|
| Prompt strategy | zero-shot · few-shot (6 examples) · few-shot + reasoning field |
| Model tier | `SMALL` · `MAIN` |
| Routing | single call · small→large cascade on validation failure or low agreement |

That is 3 × 2 + cascade = at least 7 runs. On 60 dev cases with caching, this
costs a few cents and about ten minutes.

### Targets

| Requirement | Target |
|---|---|
| A defensible recommendation | with the table that supports it |
| Cascade escalation rate | reported, with blended cost — and **non-zero**, see Part C |
| Statistical honesty | no claim of a difference smaller than your confidence interval |
| Every configuration in the grid | run on dev, reported on one table |
| Cost of the best configuration | reported per 1,000 tickets and per year at 10k/day |

---

## Why this lab exists

You have an opinion about your Lab 1 extractor. You have no evidence for it.
Lab 2 is about being able to answer "which version should we deploy, and what
will it cost?" with a table.

**The trap this lab is built to spring.** Language models are stochastic:
configuration A scores 0.88 and B scores 0.91 on 60 cases, and the difference
is well inside the noise — shipping B on those 3 points is a decision made on
nothing. This lab teaches you to tell *a result* from *a wobble*. The full
88-vs-91 story: [CONCEPTS.md](CONCEPTS.md).

**What you will build, in four pictures.**

1. **A grid of choices** — prompt style × model tier × routing, seven
   configurations, all on the same 60 tickets.
2. **Three measurements, not one** — quality × cost × latency, never quality
   alone. The harness measures all three for free.
3. **A significance check on every comparison** — if the test says "no
   significant difference", that is a result: choose on cost.
4. **A recommendation someone could act on** — one paragraph, a
   configuration, the three numbers, the annual cost, and one thing that would
   change your mind.

**How to approach it.** Work one part at a time from
[RUNSHEET.md](RUNSHEET.md). Write the baseline down before you change
anything. Run every configuration through the same harness so the only
difference between table rows is the thing you intended to differ. And treat
a negative result as a finding — the graded artefact is the decision and the
evidence, not a particular number.

---

## Timetable

| Time | Part | What you do |
|---|---|---|
| 0:00–0:10 | Setup | Read `aip/evals.py`. All of it |
| 0:10–0:50 | **A** | Few-shot selection — and why choosing examples is a retrieval problem |
| 0:50–1:30 | **B** | Run the grid. Build the comparison table |
| 1:30–2:00 | **C** | The cascade |
| 2:00–2:20 | **D** | Is your difference real? Confidence intervals and paired tests |
| 2:20–2:45 | **E** | Error analysis and the recommendation |
| 2:45–3:00 | Show & tell | Your table, your recommendation, your negative result |

**During the lab, work from [RUNSHEET.md](RUNSHEET.md)** — exact commands,
checkpoints, done-whens, and the troubleshooting table. This README is the
brief; the RUNSHEET is the procedure.

---

## Before you start

- [ ] Lab 1 is finished. Lab 2 imports your `extract.py` — a broken Lab 1 is a
      broken Lab 2.
- [ ] Read `aip/evals.py`. **All of it.** It is the instrument; you are
      responsible for knowing what it measures.
- [ ] Run `python labs/lab2/stats.py` and understand its output.

## Choose ONE track

Pick one and ignore the other for the whole lab.

**Track N — Notebook.** [`lab2.ipynb`](lab2.ipynb) is the whole lab as one file,
top to bottom. Run the cells in order and edit the *your turn* cells there.
When you submit, copy your few-shot block and cascade into
`variants.py` and fill [`report.md`](report.md) by hand — never regenerate the
report.

```bash
jupyter lab labs/lab2/lab2.ipynb    # use .venv's jupyter so the kernel matches
```

**Track S — Scripts.** Ignore the notebook. Edit only `variants.py` and drive
everything with `grid.py` (commands in the RUNSHEET).

## Layout

| Path | What it is |
|---|---|
| `aip/evals.py` | The instrument. Read all of it before Part A. |
| `labs/lab2/` | The lab. `grid.py` (harness), `variants.py` (**the graded file**), `stats.py` (CIs + paired test), `report.md` (yours to fill), `lab2.ipynb` (Track N). |
| `reports/lab2_grid.json` | Your saved grid output. |

---

## Parts in brief

**A — Few-shot selection (40 min).** Pick 6 edge-case dev tickets by hand,
justify each in one line, render them into the prompt in the exact output
format, run zero-shot vs few-shot. **A4 is the question that matters:** your
examples came out of dev and you are measuring on dev — name that leakage and
fix it. Expect few-shot to buy you close to nothing; the full
"prepare-to-be-annoyed" story is in [CONCEPTS.md](CONCEPTS.md). RUNSHEET §2.

**B — Run the grid (40 min).** One command runs all seven configurations and
saves `reports/lab2_grid.json`. Build the one-table comparison, then answer
the three report questions: which axis moved the numbers, what the reasoning
field cost per accuracy point, and whether any configuration is dominated.
RUNSHEET §3.

**C — The cascade (30 min).** Implement `cascade()` in `variants.py`: SMALL
first, escalate to MAIN on a trigger you choose. Watch for the temperature-0
response-cache bug — the silent failure where disagreement is never detected
and `escalated = 0.00` ([CONCEPTS.md](CONCEPTS.md), RUNSHEET §4). Then run
the signal check: agreement-when-correct vs agreement-when-wrong. Report
escalation rate, blended cost, blended accuracy.

**D — Is your difference real? (20 min).** 0.88 vs 0.91 on 60 cases proves
nothing. Compute Wilson CIs (`wilson_interval()`), then run the paired
McNemar test (`paired_test()`) on the items where the systems disagree, and
report b, c, p. "No significant difference" is a good result — choose on
cost. RUNSHEET §5.

**E — Error analysis and recommendation (25 min).** Read 20 failures of your
best configuration, cluster them, build the confusion matrix for your worst
field, then write the one-paragraph recommendation: configuration, three
numbers, annual cost at 10k/day, change-my-mind condition. Two-line
calibration pointer: the reference measured SMALL 0.930 field / $0.080 vs
MAIN 0.942 / $0.382 — 4.8× cost for a difference at p = 0.71. Full numbers in
[CONCEPTS.md](CONCEPTS.md). RUNSHEET §6.

---

## Deliverables

1. `variants.py` — your configurations, including the cascade
2. [`report.md`](report.md) — at most three pages:
   - the grid table
   - the few-shot selection justification, and your answer to A4
   - the cascade numbers (escalation rate, blended cost, blended accuracy)
   - the paired-test result with b, c, and p
   - three error clusters, and the confusion matrix from E2
   - the recommendation paragraph
   - **at least one negative result**
3. `reports/lab2_grid.json`

---

## Rubric (9% of Module 1)

| Criterion | Weight | Full marks means |
|---|---|---|
| Harness quality | 20% | Runs the grid reproducibly; caching works; results are stable across re-runs |
| Experimental discipline | 25% | One variable at a time; dev/test respected; A4 handled honestly |
| Statistical honesty | 20% | CIs computed; paired test run; no claim beyond the evidence |
| Cascade | 15% | Implemented, and the three numbers reported and interpreted |
| Recommendation | 20% | Specific, quantified, falsifiable, and includes a change-my-mind condition |

**The thing that surprises people: there is no accuracy target.** None. You
are graded on the quality of your decision and the evidence behind it. When
the reference solution ran this grid, the honest answer was *"none of the
clever configurations beat the cheap baseline by a statistically detectable
margin, so ship the cheap one."* Reaching that conclusion, with the paired
tests to support it, is full marks. Inventing an improvement is not. Your
report must contain **at least one negative result** — that is not a penalty
box, it is the point.

---

## What separates a good report from an adequate one

- An adequate report names a winner. A good one gives the full table and
  says "no significant difference, therefore choose on cost", with b, c and p
  to back it.
- An adequate report implements the cascade. A good one reports the
  escalation rate *and* the signal check — agreement when correct vs when
  wrong — and admits when the trigger detects nothing.
- An adequate report handles A4 with a sentence. A good one names the
  leakage, states the fix, and reports which number is the honest one.
- An adequate report prints a cost. A good one notices `UNPRICED` on NVIDIA
  and compares on tokens instead of accepting a silent `$0.00`.

---

## Stretch

1. **Self-consistency.** Sample n=5 at T=0.7, majority vote. Plot accuracy
   against disagreement rate. Does disagreement predict error better than the
   model's own stated confidence? (It does. Show by how much.)
2. **Prompt-length ablation.** Delete one instruction at a time from your
   system prompt and re-run. Which instructions are load-bearing? Most are not.
3. **Cross-provider.** Run your best configuration on a second provider profile
   (`AIP_PROFILE=nvidia`, which is verified, or `ollama` for fully local).
   Report the portability gap. Two things you will hit, both instructive:
   NVIDIA is roughly **7-10x slower** on this task, so use `--n 20`; and it
   publishes **no per-token prices**, so the harness reports `UNPRICED` and
   gives you tokens instead of dollars. Compare on tokens — cost is
   proportional to them — and say in your report why a cost meter that printed
   `$0.00` there would have been worse than one that refuses to guess.

---

## A note on providers

Everything in this lab is calibrated on **Gemini** — use it if you can.

`AIP_PROFILE=nvidia` works and is fully verified, with two differences you must
know about:

- It is roughly **7–10× slower**. Use `--n 20` rather than the full 60, or start
  the grid and go read `aip/evals.py` while it runs.
- NVIDIA **publishes no per-token prices**, so the harness prints `UNPRICED`
  and gives you **token counts** instead of dollars. Compare variants on
  tokens — cost is proportional to them, so the ranking is unchanged.

That second point is worth pausing on. The harness *could* have printed `$0.00`
and looked tidy. It refuses to, because a cost meter that silently reports zero
for a paid API is exactly the class of bug this module exists to teach you to
hate.

---

## Questions we will discuss

1. Your paired test said "no significant difference" on every comparison. Is
   that a failed lab, or the correct conclusion at n = 60? What would it take
   to detect a real 3-point difference?
2. Few-shot moved your accuracy by (almost) nothing. Where else in this
   course might an "improvement" be a symptom of an under-specified baseline
   rather than a win?
3. The cascade's disagreement trigger detected variance, not bias. Name one
   production decision where self-consistency would have told you the system
   was safe while it was consistently wrong.
4. The harness refused to print `$0.00` for an unpriced provider. What other
   zeros in dashboards and reports might be lies of the same kind?
