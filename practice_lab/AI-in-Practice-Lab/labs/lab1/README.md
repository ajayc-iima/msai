# Lab 1 — The Reliable Extractor
**3 hours · Individual**

> **Docs:** [README](README.md) (this brief) · [RUNSHEET](RUNSHEET.md) (the actions) · [CONCEPTS](CONCEPTS.md) (theory → code) · [report.md](report.md) (yours to fill)
> Track N: [`lab1.ipynb`](lab1.ipynb) · Track S: `extract.py`

---

## The problem

Aurora Health Insurance receives about 10,000 support messages a day across
email, WhatsApp, and an in-app form. Right now a team of agents reads each one
and types a category and an urgency into a routing tool. It takes about
40 seconds per ticket.

You have been asked to replace the typing.

You are given 240 real-shaped tickets: forwarded email chains with quoted
history, WhatsApp messages, HTML fragments from a web form, Hinglish
code-mixing, typos, shouting, and signature blocks containing phone numbers.
Some have no policy number. Some have two.

**Build a system that turns each ticket into a validated structured record.**

### Targets on the 120-item test split

| Metric | Target | Notes |
|---|---|---|
| Schema validity | **100%** | Non-negotiable |
| Field accuracy | ≥ 0.90 | |
| Record accuracy (all 8 fields correct) | ≥ 0.55 | Brutal by construction |
| Total cost, full 120-item run | ≤ $0.15 | |
| p95 latency per ticket | ≤ 4,000 ms | |
| Unhandled exceptions | 0 | |

**Why record accuracy looks so low.** Eight fields must *all* be right. Four
of them (`policy_number`, `contains_pii`, `product`, `language`) reach 1.000
once you do Part C, so record accuracy is driven almost entirely by the three
judgement fields. Field accuracy is the engineering metric; record accuracy is
the one the business feels, and the gap between them is the whole point.

Before you start, read `data/README.md` — the **annotation guidelines** the
labels were produced from. A label you cannot derive from a written rule is a
label nobody can hit. Pay attention to the `urgency` scale and the
`complaint` boundary; that is where most of the errors will be. The *Known
limitations* section at the end is worth five minutes too.

The validity target is the interesting one. 100% validity does **not** mean
the model is always right. It means your system always emits something
well-formed — possibly a record flagged for human review, but never a crash
and never a malformed payload. Validity ≠ correctness:
[CONCEPTS.md](CONCEPTS.md).

---

## Timetable

| Time | Part | What you do |
|---|---|---|
| 0:00–0:10 | Setup | `python check_setup.py`, and a show of hands on the primer |
| 0:10–0:45 | **A** | Build v0 the naive way. Watch it break. Record how |
| 0:45–1:30 | **B** | Schema + validation + repair loop |
| 1:30–2:00 | **C** | Move the deterministic fields out of the model |
| 2:00–2:35 | **D** | Run on test, measure the triple, error analysis |
| 2:35–3:00 | Show & tell | 4 minutes each: your table and your worst failure |

**During the lab, work from [RUNSHEET.md](RUNSHEET.md)** — it has the exact
commands, checkpoints, and the troubleshooting table. This README is the
brief; the RUNSHEET is the procedure.

---

## Before the lab — about an hour

### 1 · Your environment works — 5 min

```bash
python check_setup.py
```

You are ready when the last line reads `Environment is ready.`

### 2 · Pydantic — 30 min, and this one is not optional

```bash
python labs/lab1/pydantic_primer.py
```

Eight exercises covering the exact surface this lab uses — `BaseModel`,
`Field` constraints, `Literal`, optional fields, `field_validator`,
`ValidationError`, and the three `model_*` methods. Nothing else.
**You are ready when it prints `8/8 passing`.** Skipping the file is not an
option — every exercise maps onto a TODO in `extract.py`.

### 3 · Read five tickets — 10 min

Pull five random rows from `data/eval/extraction_dev.jsonl` and read the
`input` against the `expected` label. **Write down three things you notice
that will make this hard.** You will be asked for them in the first ten
minutes.

### 4 · Read the annotation guidelines — 15 min

`data/README.md`, the *Annotation guidelines* section, plus the *Known
limitations* at the end — two fields were rewritten after the first version's
labels turned out to be unachievable.

---

## Parts in brief

**A — v0, the naive way (30 min).** Run `v0_naive.py --n 40` and characterise
how it fails — do not fix it. Fill the failure table in `report.md` from both
halves of the output. **Checkpoint:** the arc is 0/40 parsed → 40/40 parsed
after a one-line fix → still ~0/40 clean. `markdown_fence` at 40/40 is
expected behaviour, not a broken key. That gap is why Part B exists.
RUNSHEET §2.

**B — Schema, validation, repair (45 min).** Complete TODOs B1–B4 in
`extract.py`: design the schema (`Literal` category, constrained urgency,
`AUR-\d{7}` policy pattern, evidence field), write the system prompt, wire up
`aip.llm.structured`, and never crash — catch `StructuredOutputError` into
`needs_human_review=True`. Evaluate on dev. **Checkpoint:** validity 1.00 and
field accuracy ≥ 0.85. Validity below 1.00 means your exception handling is
wrong, not your prompt. RUNSHEET §3.

**C — Move work out of the model (30 min).** Regex, PII patterns and a
business rule take `policy_number`, `contains_pii` and `escalate` away from
the model entirely — shorter prompt, three fields at 100%, lower cost.
Handle the two-policy-number trap (live body vs quoted reply) with a written
rule. **Checkpoint:** cost falls ~25–35% while accuracy holds — the finding
is *guaranteed and auditable*, not *usually right*. RUNSHEET §4.

**D — Measure and analyse (35 min).** Run the test split **once**, report the
triple (quality × cost × latency), read the per-field breakdown and
confusion matrix, cluster 15 failures into your top three, and do the D5
economics: cost/ticket × 10,000/day vs 40 s of agent time at ₹300/hour, with
break-even accuracy. RUNSHEET §5.

---

## Choose ONE track

Pick one and ignore the other for the whole lab.

**Track N — Notebook.** [`lab1.ipynb`](lab1.ipynb) is the whole lab as one file,
top to bottom. Run the cells in order and edit the *your turn* cells there.
When you submit, copy your schema and functions into `extract.py` and fill
[`report.md`](report.md) by hand — never regenerate the report.

```bash
jupyter lab labs/lab1/lab1.ipynb    # use .venv's jupyter so the kernel matches
```

**Track S — Scripts.** Ignore the notebook. Edit only `extract.py` and drive
everything with `run_eval.py` (commands in the RUNSHEET).

## Layout

| Path | What it is |
|---|---|
| `aip/` | The shared library. `aip/llm.py` is the heart: chat, structured output, repair loop, cache, cost ledger. Read it. |
| `labs/lab1/` | The lab. `v0_naive.py` (Part A), `extract.py` (**the graded file**), `run_eval.py` (the harness), `pydantic_primer.py`, `report.md` (yours to fill), `lab1.ipynb` (Track N). |
| `data/eval/` | `extraction_dev.jsonl` (iterate here) · `extraction_test.jsonl` (run once) · `extraction_blind.jsonl` (stretch). |
| `data/corpus/`, `data/tickets/`, `data/attacks/` | Reference material for the lab and later modules. |

---

## Deliverables

Push to your repo under `labs/lab1/`:

1. `extract.py` — your working extractor
2. `report.md` — at most two pages: the Part A failure table, the variant
   comparison (v0/B/C) with quality, cost, p95, per-field accuracy and the
   `category` confusion matrix, top three error clusters with proposed fixes,
   the D5 economic argument, and **one thing you tried that did not work**.
3. `reports/lab1_test.json` — the raw harness output

---

## Rubric

| Criterion | Weight | Full marks means |
|---|---|---|
| Correctness | 25% | Meets the accuracy and validity targets on test |
| Reliability engineering | 20% | Zero crashes; repair loop works; failures degrade to review, not exceptions |
| Boundary design | 20% | Deterministic fields moved out of the model, with the reasoning stated |
| Measurement | 20% | All three axes reported; test split run exactly once; dev/test gap acknowledged |
| Analysis | 15% | Error clusters are specific and real; economic argument holds up |

**A negative result, honestly reported, scores full marks in the Analysis
row.** Fabricated or unreproducible numbers score zero for the lab.

---

## What separates a good report from an adequate one

- An adequate report prints validity 1.00. A good one says what validity
  does **not** buy — 100% valid can still be wrong — and points at
  `needs_human_review`.
- An adequate report moves three fields to 1.000 in Part C. A good one
  explains the two-policy-number rule it chose and whether that rule
  generalises or fits the data.
- An adequate report shows a field accuracy of 0.90. A good one also shows
  the record accuracy the business feels, and names the three judgement
  fields that drive the gap.
- An adequate report runs test once and pastes numbers. A good one reports
  the triple, the clusters, the break-even arithmetic, and one thing that did
  not work.

---

## Stretch (if you finish early)

1. **Cascade.** Route to a larger model only when validation fails or the
   evidence field is empty. Report the blended cost and the escalation rate.
2. **Batch.** Extract 10 tickets in one call. Measure the cost saving and the
   accuracy cost.
3. **Self-consistency on `urgency`.** Sample 3 times at temperature 0.7, take
   the median. Does disagreement predict error?
4. **Run the blind set** (`data/eval/extraction_blind.jsonl`) and submit your
   predictions.

---

## Questions we will discuss

1. Validity hit 1.00 and the record was still wrong. What exactly is the
   100% target buying the business, and what is it not buying?
2. Part C made three fields perfect without the model seeing them. Which
   other fields in later labs are candidates for the same move, and how do
   you tell a deterministic field from a judgement field?
3. Your labels come from a generator, so inter-annotator agreement is 1.00.
   Real queues sit near 0.60–0.75. How much of your reported accuracy would
   survive that gap?
4. The annotation guidelines were rewritten after unachievable labels were
   found. Describe a label rule in your own life (course, work, sports) that
   two reasonable people would apply differently — and what written rule
   would fix it.
