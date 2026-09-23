# Lab 2 — Runsheet

**Follow this top to bottom.** Every step says *why* it exists, *what* to do,
and how you know you are finished.

| | |
|---|---|
| [`README.md`](README.md) | **the brief** — problem, targets, rubric (read first) |
| [`CONCEPTS.md`](CONCEPTS.md) | **the reference** — concept → code → theory |
| [`report.md`](report.md) | **the form** — fill by hand as you go |
| this file | **the actions** — follow it during the lab |

**Individual.** Pick one track and ignore the other: Track N =
[`lab2.ipynb`](lab2.ipynb) (numbered *your turn* cells), Track S = `variants.py`
driven by `grid.py`.

---

## The lab in one line

> Build the experiment harness, run the grid, and produce a recommendation
> defensible on quality × cost × latency — with statistics behind every claim.

---

## Before you sit down

- [ ] Lab 1 finished — `labs/lab1/extract.py` imports without error
- [ ] `GEMINI_API_KEY` in `.env`; `python check_setup.py` ready
- [ ] [`README.md`](README.md) read; [`CONCEPTS.md`](CONCEPTS.md) open in a
      second pane
- [ ] `aip/evals.py` read **in full** — it is the instrument
- [ ] `python labs/lab2/stats.py` run, output understood
- [ ] You know: **there is no accuracy target**, and **negative results are
      required**

---

## What you may call from `aip/`

| You need | It lives in | Signature |
|---|---|---|
| Harness: cases, runner, report, compare | `aip.evals` | `load_cases`, `run_eval`, `compare`, `field_accuracy` |
| Structured output + repair loop | `aip.llm` | `structured(prompt, schema=..., system=..., tier=...)` |
| Lab 1 extractor pieces (imported by `variants.py`) | `labs.lab1.extract` | `SYSTEM_PROMPT`, `TicketRecordC`, `extract_deterministic`, `apply_business_rules` |
| CIs and the paired test | `labs.lab2.stats` | `wilson_interval`, `paired_test` |

**Rule of thumb.** `aip/` is the toolkit — you may read it, not change it.
`labs/lab2/variants.py` is the system you are building.

---

## `variants.py` scaffolding — read, do not rewrite

| Helper | What it does |
|---|---|
| `FEW_SHOT_IDS` / `load_examples(ids)` | TODO A1 — your six chosen dev tickets |
| `few_shot_block(ids)` | TODO A2 — render examples into the prompt (exact output format) |
| `zero_shot(ticket, tier)` | the baseline: Lab 1 Part C, no examples |
| `few_shot` / `few_shot_reasoned` | zero-shot + examples; + `reasoning` field first |
| `cascade(ticket)` | TODO C — SMALL first, escalate on your trigger; set `rec["_path"]` |
| `_call_main(ticket, det)` | the escalation path — given to you |
| `VARIANTS` | the seven configurations `grid.py` runs |

---

# 0 · Setup — 10 min

Open Track N (`jupyter lab labs/lab2/lab2.ipynb`) or Track S
(`labs/lab2/variants.py` + `grid.py`).

Run the environment cells. Sanity-check the baseline first:

```bash
python labs/lab2/grid.py --variants zero_shot --split dev --n 10
```

> **Done when:** a 10-case zero-shot run completes, you have seen the summary
> block (metrics, cost, p50/p95), and `stats.py` output makes sense.

---

# 1 · Part A — few-shot selection — 40 min

**Why.** Examples can teach what prose cannot — but they cost tokens on every
call, forever. You need to know whether they earn it, honestly measured.

### TODOs A1–A4

| Step | What | Done when |
|---|---|---|
| **A1** | pick 6 dev tickets by hand, one-line justification each | every row answers "what does this teach that prose cannot?" |
| **A2** | `few_shot_block()` renders them in the exact output format | block concatenates onto `SYSTEM_PROMPT`, no format mismatch |
| **A3** | run zero-shot vs few-shot on dev | comparison table exists |
| **A4** | name and fix the leakage | the fix and the honest number are written down |

**1.1 — A1.** Fill `FEW_SHOT_IDS`. Pick **edges, not averages**: the
billing/complaint boundary, a ticket with no policy number, a Hinglish one, a
satisfied-but-urgent one, one whose policy number sits only in a quoted reply,
one you got wrong in Lab 1.

**1.2 — A2.** Implement `few_shot_block()`. The example output must be
byte-identical to the format you ask the model for.

**1.3 — A3.** Run:

```bash
python labs/lab2/grid.py --variants zero_shot few_shot --split dev
```

**1.4 — A4. THE TRAP.** Your 6 examples came out of the dev set, and you are
measuring on the dev set. Name that problem, pick a defensible fix (there is
more than one), and record which number you will report as honest.

> **Checkpoint — leakage.** If you leave A4 unfixed, every few-shot number in
> your report is contaminated. `report.md` §2 must state the problem, the fix,
> and the resulting number.

> **Checkpoint — expect ~nothing.** Few-shot may buy you nothing; the
> reference moved field accuracy 0.928 → 0.931 with p = 1.00. If few-shot
> buys you 20 points, your zero-shot prompt was under-specified — fix that
> instead of banking the delta. Full story:
> [CONCEPTS.md](CONCEPTS.md).

> **Done when:** `report.md` §2 has the six-example table, the A4 answer, and
> the zero vs few-shot delta with b/c/p.

---

# 2 · Part B — run the grid — 40 min

**Why.** One configuration is an anecdote; seven on one harness is a dataset.

**2.1** Run everything and save:

```bash
python labs/lab2/grid.py --all --split dev --save reports/lab2_grid.json
```

**2.2** Build the table — one row per configuration, columns:

```
record_accuracy | field_accuracy | schema_valid | repair_rate |
cost_usd | cost_per_1k_tickets | p50_ms | p95_ms
```

**2.3** Answer, in `report.md` §1:

1. Which axis moved the numbers most — prompt, or model tier?
2. What did the reasoning field cost in output tokens, and what did it buy?
   Express it as accuracy points per rupee.
3. Is there a configuration that is worse than another on **every** axis?
   Say so explicitly — dominated configurations are a real finding, and the
   harness prints them.

> **Done when:** `reports/lab2_grid.json` exists, the table has all seven
> rows, the three questions are answered, and the cost of the best
> configuration is stated per 1k tickets and per year at 10k/day.

---

# 3 · Part C — the cascade — 30 min

**Why.** Most tickets are easy; paying MAIN prices on all of them to handle
the hard 10% is wasteful. Cheap first, escalate when you have reason to doubt.

**The shape:**

```
   SMALL model
       │
       ├── validates AND evidence is non-empty ──▶ accept
       │
       └── otherwise ──▶ MAIN model ──▶ accept, or flag for review
```

**3.1** Implement the trigger in `cascade()` (TODO C). Options, weakest to
strongest: validation failed · evidence field empty or too short · second
SMALL sample at **temperature > 0** disagrees on category.

**3.2** Run it:

```bash
python labs/lab2/grid.py --variants zero_shot cascade --split dev --save reports/lab2_grid.json
```

**3.3** Report the three numbers in `report.md` §3: escalation rate,
blended cost (vs both pure configurations), blended accuracy (vs both).

> **Checkpoint — the silent cache bug.** Two identical requests at
> temperature 0 hit the response cache; the answers are byte-identical,
> disagreement is never detected, and `escalated = 0.00` while everything
> *appears* to work. Nothing errors. Your second sample must be at
> temperature > 0. Full story: [CONCEPTS.md](CONCEPTS.md).

> **Checkpoint — the signal check.** Compute how often your two samples agree
> when the answer is right vs when it is wrong. The reference measured 94%
> vs 83% — catching 2 of 12 errors, a cascade worth almost nothing.
> Disagreement detects variance; a consistently wrong model has bias.
> Report both rates; a cascade you did not interrogate is not full marks.

> **Done when:** escalation rate is **non-zero**, the three blended numbers
> are in `report.md` §3, and the signal check (agreement correct vs wrong)
> has been computed and interpreted.

---

# 4 · Part D — is your difference real? — 20 min

**Why.** The intellectual core of the lab: telling *a result* from *a wobble*.

**4.1 — Confidence intervals.** The normal approximation:

```
CI ≈ p ± 1.96 · sqrt( p(1-p) / n )
```

At n = 60, p = 0.90 the half-width is about **±0.076** — so 0.88 and 0.91
overlap almost completely. Run the better version (Wilson):

```bash
python labs/lab2/stats.py
```

`wilson_interval(successes, n)` is what `grid.py` already prints per
configuration. Paste both intervals into `report.md` §4.

**4.2 — Paired test.** Same 60 items, both systems. Count only disagreements:

- b = A right, B wrong
- c = B right, A wrong

`paired_test(a_correct, b_correct)` in `stats.py` runs exact McNemar on
(b, c). `grid.py` prints paired comparisons automatically when you pass two
or more `--variants`.

**4.3** State for your chosen comparison: **b, c, p, conclusion**.

> **Done when:** `report.md` §4 has both Wilson intervals, an overlap answer,
> and a paired-test row with b, c, p and a verdict. "No significant
> difference" is a perfectly good result — then you choose on cost.

---

# 5 · Part E — error analysis and the recommendation — 25 min

**Why.** An average tells you *how much* is wrong, never *what* is wrong.

**5.1.** Take your best configuration. **Read 20 failures.** Cluster them;
name the top three with counts (`report.md` §5 E1).

**5.2.** For your worst field, build the confusion matrix (rows = gold, cols =
predicted). There is a specific systematic confusion in this dataset that the
aggregate hides — find it (`report.md` §5 E2).

**5.3.** Write the recommendation — one paragraph, four ingredients:
configuration · three numbers (quality × cost × latency) · annual cost at
10,000 tickets/day · one condition that would change your mind (`report.md`
§5 E3).

**5.4.** Fill `report.md` §6 with **at least one negative result**.

> **Calibration (two lines).** Reference test split: `SMALL` zero-shot 0.930
> field / $0.080 / 2,276 ms p95; `MAIN` zero-shot 0.942 / $0.382 / 6,720 ms —
> 4.8× cost and 3× latency for a difference at **p = 0.71**. Full story:
> [CONCEPTS.md](CONCEPTS.md). Your grid may land differently; say so plainly
> whichever way it lands.

> **Done when:** E1 clusters with counts, E2 matrix with the named confusion,
> E3 recommendation with all four ingredients, §6 has a negative result.

---

# 6 · Submit — 10 min

- [ ] `variants.py` complete — `few_shot_block` and `cascade` implemented,
      no remaining `NotImplementedError`
- [ ] `reports/lab2_grid.json` saved from the full grid run
- [ ] [`report.md`](report.md) filled **by hand** (never regenerate):
  - [ ] §1 all seven configurations + three questions + cost of the winner
  - [ ] §2 six examples, A4 leakage + fix, delta with b/c/p
  - [ ] §3 escalation rate (non-zero), blended cost, blended accuracy, signal check
  - [ ] §4 Wilson intervals + McNemar row(s) with b, c, p
  - [ ] §5 clusters, confusion matrix, recommendation paragraph
  - [ ] §6 at least one negative result

---

## Deliverables checklist

- [ ] `labs/lab2/variants.py` — configurations including the cascade
- [ ] `labs/lab2/report.md` — ≤ 3 pages
- [ ] `reports/lab2_grid.json`

---

## The traps

1. **Temperature-0 cache bug.** Second sample at T=0 is a cache hit;
   disagreement never fires; `escalated = 0.00` and everything looks fine.
   Draw the second sample at temperature > 0.
2. **A4 leakage.** Examples from dev, measured on dev. Name it, fix it,
   report the honest number.
3. **No accuracy target / negative results required.** You are graded on the
   decision and the evidence. At least one negative result must appear in
   `report.md` §6.
4. **Claiming beyond the CI.** If the intervals overlap and the paired test
   says p ≥ 0.05, you may not claim a difference. Choose on cost instead.
5. **Accuracy alone.** Every claim carries the triple: quality × cost ×
   latency.
6. **Editing `aip/` or regenerating `report.md`.** The report is filled by
   hand; `aip/` is shared across labs.

---

## If something goes wrong

| Symptom | Cause |
|---|---|
| `escalated = 0.00` but the cascade "works" | Cache bug — second sample at temperature 0. Use T > 0 |
| `NotImplementedError: TODO A2` / `TODO C` | `few_shot_block()` or `cascade()` still stubbed — fill them |
| `every case failed. First error: ...` in `grid.py` | Unimplemented TODO or a raise inside the variant; also check Lab 1 `extract.py` imports |
| `ImportError` from `labs.lab1.extract` | Lab 1 incomplete or syntax-broken — fix Lab 1 first |
| Cost printed as `UNPRICED` | NVIDIA (or another provider) publishes no per-token price — compare on tokens, not dollars |
| `reports/lab2_grid.json` missing after Part B | You ran without `--save reports/lab2_grid.json` — re-run the full grid |
| Intervals overlap, partner says "B is better" | Misread — overlapping CIs mean you cannot conclude; run the paired test and report b/c/p |
| Few-shot gained 20 points | Almost certainly under-specified zero-shot (or unfixed A4) — not a win |
