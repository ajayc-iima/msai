# Lab 1 — Runsheet

**Follow this top to bottom.** Every step says *why* it exists, *what* to do,
and how you know you are finished.

| | |
|---|---|
| [`README.md`](README.md) | **the brief** — problem, targets, rubric (read first) |
| [`CONCEPTS.md`](CONCEPTS.md) | **the reference** — concept → code → theory |
| [`report.md`](report.md) | **the form** — fill by hand as you go |
| this file | **the actions** — follow it during the lab |

**Individual.** Pick one track and ignore the other: Track N =
[`lab1.ipynb`](lab1.ipynb) (numbered *your turn* cells), Track S =
`extract.py` driven by `run_eval.py`.

---

## The lab in one line

> Turn 240 messy insurance tickets into validated structured records —
> reliably, and without going broke.

---

## Pre-flight — before you sit down

- [ ] `pip install -r requirements.txt`; `GEMINI_API_KEY` in `.env`
- [ ] `python check_setup.py` → **Done when:** last line reads
      `Environment is ready.`
- [ ] `python labs/lab1/pydantic_primer.py` → **Done when:** prints
      `8/8 passing`. Every exercise maps to a TODO in `extract.py`; skipping
      it is not an option
- [ ] Read 5 dev tickets:

```bash
python -c "
import json,random
rows=[json.loads(l) for l in open('data/eval/extraction_dev.jsonl')]
for r in random.sample(rows,5):
    print('='*70); print(r['expected']); print('-'*70); print(r['input'])
"
```

      → **Done when:** you have written down three things that will make this
      hard (you will be asked in the first ten minutes)

- [ ] Read `data/README.md` — *Annotation guidelines* + *Known limitations*
      → **Done when:** you can state the `urgency` 1/2 rule and the
      `complaint` boundary
- [ ] [`CONCEPTS.md`](CONCEPTS.md) open in a second pane

---

## What you may call from `aip/`

| You need | It lives in | Signature |
|---|---|---|
| Chat + structured output + repair loop | `aip.llm` | `chat`, `structured(prompt, schema=..., system=..., tier=...)`, `StructuredOutputError` |
| Cost ceiling + ledger | `aip.llm` (or `aip`) | `Budget(limit_usd=..., label=...)` |
| PII patterns | `aip.guards` | `PII_PATTERNS` |
| Eval harness | `aip.evals` | `load_cases`, `run_eval`, `compare`, `field_accuracy` |

**Rule of thumb.** `aip/` is the toolkit — you may read it, not change it.
`labs/lab1/extract.py` is the system you are building.

---

## `extract.py` scaffolding — your TODOs

| Step | What | Done when |
|---|---|---|
| **B1a–B1j** | schema: `evidence` order · `category` Literal + description · `urgency` 1–5 + scale description · `sentiment` / `product` / `language` Literals · `evidence` ≤200 · `policy_number` pattern + null rule · `contains_pii` description · `field_validator` | every `TODO B1*` replaced; descriptions read as instructions to the model |
| **B2** | `SYSTEM_PROMPT` — stable instructions first, volatile data last | prompt is shorter than your first instinct |
| **B3** | wire `aip.llm.structured` into `extract_b` | dev run completes |
| **B4** | catch `StructuredOutputError` → `needs_human_review=True` | `extract_b` never raises |
| **C1** | `extract_deterministic()` + `apply_business_rules()` | `policy_number` / `contains_pii` / `escalate` computed in code |
| **C2** | `TicketRecordC` — delete the fields you now compute | model sees only judgement fields |
| **C3** | two-policy-number rule, written in a comment | rule stated; generalisation question answered |

---

# 0 · Setup — 10 min

Open Track N (`jupyter lab labs/lab1/lab1.ipynb`) or Track S
(`labs/lab1/extract.py`).

> **Done when:** pre-flight checklist above is fully checked.

---

# 1 · Part A — v0, the naive way — 30 min

**Why.** Your job is not to fix v0. It is to characterise how it fails, so
Parts B and C are solutions to problems you have actually seen.

**1.1** Run:

```bash
python labs/lab1/v0_naive.py --n 40
```

**1.2** Fill the failure table in `report.md` from **both** halves of the
output — Part 1 (why bare `json.loads()` refused) and Part 2 (defects hiding
inside the recovered JSON):

| Failure mode | Count in 40 | Example ticket id |
|---|---|---|
| Not valid JSON at all | | |
| JSON wrapped in a markdown fence | | |
| Extra prose before or after the JSON | | |
| Valid JSON, missing a required field | | |
| Valid JSON, category outside the allowed set | | |
| Urgency as a string instead of an int | | |
| Policy number invented (not present in the text) | | |
| Unhandled exception | | |

> **Checkpoint — the arc.** On the current SMALL model, `markdown_fence`
> lands close to **40/40 in Part 1** — that is correct behaviour, not a
> broken key. Part 2 then shows `urgency_is_string` and
> `category_out_of_set` at a similar rate. You are done when you can state:
> **0/40 parsed → 40/40 parsed after a one-line fix → still ~0/40 clean.**

> **Done when:** `report.md` Part A table has counts and an example ticket id
> per row, and the arc sentence is written.

---

# 2 · Part B — schema, validation, repair — 45 min

**Why.** The schema is the contract; the repair loop is what makes 100%
validity achievable without pretending the model is always right.

**2.1** Complete the TODOs B1–B4 listed above in `extract.py`. Design
notes that matter:

- `category` is a `Literal`; `urgency` an `int` constrained 1–5 with a
  description that *defines the scale* (anchor 1, 3, 5; state the 1/2 lookup
  rule and the 4/5 tense rule from `data/README.md`).
- `policy_number` is `str | None` with the `AUR-\d{7}` pattern; null when
  none appears in the LIVE message; never invent one.
- Decide whether `evidence` goes before or after `category` — and leave a
  one-line comment saying why.
- Most instructions belong in field `description`s, not the system prompt.

**2.2** Evaluate on dev:

```bash
python labs/lab1/run_eval.py --split dev --variant b
```

> **Checkpoint.** Validity **1.00**, field accuracy **≥ 0.85** on the full
> dev split. If validity is below 1.00 your exception handling (B4) is
> wrong, not your prompt.

> **Done when:** the dev summary shows validity 1.00 and field accuracy
> ≥ 0.85, and the per-field table has been read (worst field named).

---

# 3 · Part C — move work out of the model — 30 min

**Why.** Regex, PII patterns and a business rule are deterministic, free,
auditable and unit-testable. Asking a model for them is paying for variance
you do not want.

**3.1** Implement `extract_deterministic()` and `apply_business_rules()`
(TODO C1): `policy_number` by regex, `contains_pii` from `PII_PATTERNS`
(Aurora's own `support@` / `grievance@` addresses do NOT count),
`escalate = urgency >= 4 or "ombudsman" in ticket.lower()`.

**3.2** Build `TicketRecordC` (TODO C2) — delete those fields from the
schema the model sees.

**3.3 — the trap (C3).** Some tickets contain **two** policy-number-shaped
strings: one in the live body, one in a quoted reply below `>` lines. They
are not always the same number. Decide a rule, write it down in a comment
right there, implement it — then ask whether it generalises or whether you
fitted it to the data.

**3.4** Compare against B:

```bash
python labs/lab1/run_eval.py --split dev --variant c --compare b
```

> **Checkpoint.** Cost falls **~25–35%**. Accuracy holds — it does not rise,
> and that is the finding: those fields were already near 1.00 in Part B, so
> there were no points to win. What Part C buys is fields *guaranteed and
> auditable* rather than *usually right*, at lower cost. Say that in your
> report. `policy_number` / `contains_pii` / `escalate` should read 1.000 in
> the per-field table.

> **Done when:** the B-vs-C compare table shows the cost drop, deterministic
> fields at 1.000, and your two-policy-number rule is written in the code
> and the report.

---

# 4 · Part D — measure and analyse — 35 min

**Why.** The triple is what the business feels; the clusters are where the
next points are; the economics is whether any of it is worth deploying.

**4.1 — D1. Run the test split, once:**

```bash
python labs/lab1/run_eval.py --split test --variant c --save reports/lab1_test.json
```

> **Warning — once means once.** The harness will remind you. Do not iterate
> against test; if the number is worse than dev, report it anyway.

**4.2 — D2.** Report the **triple**: quality × cost × latency. Not one of
them.

**4.3 — D3.** Per-field breakdown and the `category` confusion matrix (the
harness prints both). Expect `urgency` and `sentiment` worst; deterministic
fields at 1.00. Check whether `urgency` errors are off-by-one at a boundary
(they will be).

**4.4 — D4.** Open 15 failures and cluster them. Name your top three
clusters and the fix each needs — naming them correctly is the skill.

**4.5 — D5. The economics.** cost/ticket × 10,000 tickets/day vs 40 s of
agent time at ₹300/hour. State the break-even accuracy. Show the arithmetic
in `report.md`.

> **Done when:** `reports/lab1_test.json` exists, `report.md` has the triple,
> the v0/B/C comparison table, the per-field table, the confusion matrix,
> three clusters with fixes, and the D5 break-even arithmetic.

---

# 5 · Submit — 10 min

- [ ] `extract.py` complete — no remaining `NotImplementedError`; imports
      cleanly
- [ ] `reports/lab1_test.json` saved from the single test run
- [ ] [`report.md`](report.md) filled **by hand** (never regenerate):
  - [ ] Part A failure table + the arc sentence
  - [ ] variant comparison v0/B/C (quality, cost, p95, per-field)
  - [ ] `category` confusion matrix
  - [ ] top three error clusters + proposed fixes
  - [ ] D5 economic argument with arithmetic
  - [ ] one thing you tried that did not work
- [ ] Track N only: notebook runs top-to-bottom, and your schema/functions
      are copied into `extract.py`

---

## Deliverables checklist

- [ ] `labs/lab1/extract.py`
- [ ] `labs/lab1/report.md` — ≤ 2 pages
- [ ] `reports/lab1_test.json`

---

## The traps

1. **Validity ≠ correctness.** 100% valid can still be wrong — the record
   may be flagged `needs_human_review` or confidently mislabelled. Full
   argument: [CONCEPTS.md](CONCEPTS.md).
2. **Validity < 1.00 after Part B** is an exception-handling bug (B4), not a
   prompt problem.
3. **`markdown_fence` at 40/40 in Part A is expected.** Do not "fix" v0 and
   do not blame the key.
4. **Running test twice.** Iterate on dev; test is run once and reported
   as-is, including when it disappoints.
5. **Two policy numbers.** Pick a rule (live body wins; quoted `>` lines are
   stale), write it down, and question whether it generalises.
6. **Accuracy without cost.** Report the triple — quality × cost × latency —
   everywhere it is asked for.

---

## If something goes wrong

| Symptom | Cause |
|---|---|
| Primer prints fewer than `8/8 passing` | TODOs in `pydantic_primer.py` unfinished — every exercise maps to an `extract.py` TODO |
| Validity < 1.00 on dev | B4 exception handling wrong, not the prompt — catch `StructuredOutputError`, return `needs_human_review=True` |
| `markdown_fence` 40/40 in v0 output | Expected — the exhibit, not a bug. Read Part 2 of the output next |
| `NotImplementedError` from `extract_b` / `extract_c` | TODOs B3/B4/C1/C2 still stubbed |
| Cost meter shows $0.00 / no spend | All responses served from the cache (`AIP_CACHE=1`) — fine for re-runs; a fresh run must record spend |
| `BudgetExceeded` mid-run | Raise `--budget` deliberately, or find why calls cost more than expected (repairs are not free) |
| Test split number worse than dev | Report it — dev/test gap is part of the finding, not a reason to re-run test |
