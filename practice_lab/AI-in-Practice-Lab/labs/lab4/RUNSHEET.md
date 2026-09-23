# Lab 4 — Runsheet

**Follow this top to bottom.** Every step says *why* it exists, *what* to do,
*how* to do it, and how you know you are finished.

| | |
|---|---|
| [`README.md`](README.md) | **the brief** — problem, targets, rubric (read first) |
| [`CONCEPTS.md`](CONCEPTS.md) | **the reference** — concept → code → theory |
| [`report.md`](report.md) | **the form** — fill by hand as you go |
| this file | **the actions** — follow it during the lab |

**Pairs.** Swap driver at each part.

**Pick one track and ignore the other:** Track N = [`lab4.ipynb`](lab4.ipynb)
(numbered *your turn* cells), Track S = `rag.py` + `evaluate.py`.

---

## The lab in one line

> Lab 3 found the right passage. Now write the answer — with a citation on
> every claim, and an honest refusal when the sources do not contain one.

---

## Before you sit down

- [ ] Lab 3 finished; you know your winning retrieval configuration
- [ ] `make check` clean
- [ ] [`README.md`](README.md) read; T4 §6 (generation, citation, refusal) and
      T3 §4 (LLM-as-judge) skimmed
- [ ] [`CONCEPTS.md`](CONCEPTS.md) open in a second pane

---

## What you may call from `aip/`

| You need | It lives in | Signature |
|---|---|---|
| Number the sources so citations are checkable | `aip.retrieval` | `format_context(hits, max_chars=8000) -> str` |
| Check `[n]` indices in an answer | `aip.guards` | `enforce_citations(answer, n_sources) -> (bool, list[int])` |
| A reference answer prompt (read **after** you write yours) | `aip.rag` | `ANSWER_SYSTEM` |
| A complete reference pipeline | `aip.rag` | `RagPipeline` |
| One judge call, JSON verdict | `aip.evals` | `llm_judge(prompt, tier="LARGE", max_tokens=2048) -> dict` |
| Starting rubrics — deliberately improvable | `aip.evals` | `JUDGE_RUBRIC_FAITHFULNESS`, `JUDGE_RUBRIC_CORRECTNESS` |
| Cohen's κ against your hand labels | `aip.evals` | `judge_agreement(judge, human) -> dict` |
| Structured generation with repair | `aip.llm` | `structured(prompt, schema=..., system=..., tier=...)` |
| Cost ceiling for a run | `aip.cost` | `Budget(limit_usd=..., label=...)` |

**Rule of thumb for the whole module.** `aip/` is the toolkit: provider
plumbing, metrics, guards. `labs/` is the system you are building. You may read
anything in `aip/`; you may not change it — Labs 5–7 depend on it.

Two details that matter:

- **`llm_judge` defaults to `tier="LARGE"` on purpose** — a *different and
  stronger* tier than the system under test, because self-preference bias is
  real (T3 §4.1).
- **It returns `parse_error`** when the verdict will not parse. That is missing
  data. Do not score it 0.

---

## `rag.py` and `evaluate.py` — what is provided, every TODO

Both files are yours. Knowing which side of the `aip/` line a thing lives on is
most of the battle.

### `rag.py` — the pipeline

| Piece | Status | Notes |
|---|---|---|
| `Answer` dataclass | provided | read its fields first — they tell you what the lab expects you to produce |
| `REFUSAL` | provided | exact string; downstream detects refusal by matching it — a paraphrase is a bug |
| `ANSWER_SYSTEM` | **TODO A** | write before opening `aip/rag.py::ANSWER_SYSTEM`, then diff (§1) |
| `validate_answer(text, n_sources, finish_reason=None) -> dict` | **TODO B2** | the three checks are in §2 |
| `answer_question(question, retriever, *, k=12, ...)` | **TODO B3** | retrieve → (rerank) → generate → validate → maybe repair; the repair choice lives here (§2) |
| `answer_with_gold_context(question, gold_docs, ...)` | **TODO E2** | same generator, gold documents as context, no retrieval (§5) |

### `evaluate.py` — the harness

| Piece | Status | Notes |
|---|---|---|
| `build_retriever()` | **TODO** | your Lab 3 winning configuration; the placeholder throws away Lab 3 (§0) |
| `judge_faithfulness(answer_text, context) -> int \| None` | **TODO D1** | returns 0 or 1; `None` = judge parse failure, exclude it (§4) |
| `judge_correctness(question, candidate, reference) -> int \| None` | **TODO D1** | returns 0, 1 or 2; handle refusal deterministically first (§4) |

**Handle refusal in `judge_correctness` explicitly:** if the reference says the
right behaviour is to refuse, a refusal scores full marks and a confident answer
scores zero. A rubric silent on that punishes correct behaviour.

### Provided runners

| Command | What it does |
|---|---|
| `--full --save reports/lab4.json` | every metric; **Lab 5 reads this file** |
| `--gold-context` | the E2 decomposition |
| `--calibrate` | writes the hand-labelling sheet for D2 |
| `--kappa` | computes κ once you have labelled it |

---

# 0 · Setup — 10 min

Open `labs/lab4/rag.py`, `labs/lab4/evaluate.py`, and a scratch file.

**Put your Lab 3 configuration into `build_retriever()`** in `evaluate.py`. The
placeholder there is not your answer — using it throws away Lab 3. Read
`reports/lab3_sweeps.json` (or your lab3 `report.md`) for the winning strategy,
size, and retriever type.

> **Done when:** `build_retriever()` reflects your own chunking, retriever and
> `final_k`.

---

# 1 · Part A — the answer prompt — 20 min

**Why.** The output contract is what makes everything downstream checkable.

### `ANSWER_SYSTEM` — TODO A

| Step | What | Done when |
|---|---|---|
| A | Six required elements, written **before** reading the reference | Your prompt works, and every difference vs `aip/rag.py::ANSWER_SYSTEM` is noted in `report.md` |

**1.1** Write `ANSWER_SYSTEM` **yourself, before opening `aip/rag.py`.** Six
required elements (T4 §6.1):

1. Answer **only** from the numbered sources; forbid general knowledge
2. Cite by index — `[1]`, `[2][5]`
3. Never cite a number that was not supplied
4. An exact refusal string, given verbatim
5. What to do when sources disagree — surface it, never pick silently
6. Length discipline — two or three sentences unless more is needed

It MUST contain the exact `REFUSAL` string from `rag.py`.

**1.2** *Then* read `aip/rag.py::ANSWER_SYSTEM` and note every difference.

> Rule 6 is not cosmetic. Output tokens dominate latency and cost (T1 §2.2).

> **Done when:** `report.md` Part A has your prompt, all six elements ticked,
> and the diff from the reference written down.

---

# 2 · Part B — citation enforcement — 30 min

**Why.** A citation the model invented is indistinguishable from a real one —
unless you number the sources. Then `[7]` with five sources is a *provable*
error found by three lines of regex.

### `validate_answer` / `answer_question` — TODO B2, B3

| Step | What | Done when |
|---|---|---|
| B2 | Three checks in `validate_answer` | Validator wired into the return path |
| B3 | Repair strategy chosen and defended | The function never returns `citations_valid=False` with `refused=False` |
| B4 | Citation validity across all 45 | `report.md` B4 filled; value = 1.00 |

**2.1** Read `aip.retrieval.format_context`. Understand why numbering makes
hallucination detectable.

**2.2 — `B2`.** Implement `validate_answer()`. It must check:

| Check | Why |
|---|---|
| every `[n]` is in range | a citation you never supplied is a *provable* hallucination |
| non-empty, and `finish_reason != "length"` | a truncated answer looks fine and is silently incomplete (T1 failure 4) |
| at least one citation, unless it is a refusal | an uncited claim is unauditable |

`aip.guards.enforce_citations` does the index check; the rest is yours. A
refusal needs no citation; truncation and out-of-range indices fail even on a
refusal.

**2.3 — `B3`.** Decide what happens on failure — retry with a corrective
message (the scaffold shows the shape: `_generate(..., correction=...)`), strip
the bad citation, or fall back to refusal — and **defend it in a comment.**
There is no single right answer. There is one wrong one: silently returning an
answer with a bogus citation.

**2.4 — `B4`.** Report citation validity across all 45.

> **Checkpoint. The target is 1.00 and it is achievable**, because this is a
> **code guarantee, not a model behaviour.** If yours is below 1.00, your
> validator is not wired into the return path.

> **Done when:** validity = 1.00 in `report.md`, and the repair choice is
> written down with its defense.

---

# 3 · Part C — refusal, both directions — 30 min

**Why.** A system that never refuses invents deadlines. A system that always
refuses is useless. You must measure both.

### Refusal — TODO C1–C4

| Step | What | Done when |
|---|---|---|
| C1 | Run Q36–Q40, count refusals | Raw `x/5` in `report.md` C1 |
| C2 | Q37 partial answer | First-attempt behaviour + what you changed, written down |
| C3 | Wrongful refusals on the 40 answerable | Both rates, with raw counts |
| C4 | Tighten the dial, re-run, report both directions | Product recommendation with cost-of-error reasoning |

**3.1 — `C1`.** Run Q36–Q40, the five unanswerable ones. Count refusals.

**3.2 — `C2`. Q37 is the interesting one.** *"Does Aurora cover treatment in
Singapore, and up to what limit?"* The corpus confirms a Platinum international
benefit exists, but the addendum describing it is missing.

The right behaviour is a **partial** answer: state what is supported, refuse
the rest. **Most systems do not do this on the first attempt.** Make yours, and
say what you changed.

**3.3 — `C3`.** Run all 40 answerable questions and count wrongful refusals:

```
refusal recall    = refused_and_should_have / should_have_refused
refusal precision = refused_and_should_have / total_refused
```

**3.4 — `C4`.** Make the refusal instruction stricter, re-run, report how both
numbers moved. Then state, **as a product decision with a reason**, where you
would set it for an insurance helpdesk. *"Higher precision"* is not a reason; a
claim about the relative cost of the two error types is.

> ⚠️ **Both refusal numbers are extremely noisy, and you must say so.** Five
> unanswerable questions; the reference declined seven in total. **One case
> moves precision by 0.12 and recall by 0.20.** Report raw counts beside the
> ratios and claim no difference below ~0.15. T3 §2.1 in miniature. Full
> mechanics: [CONCEPTS.md](CONCEPTS.md).
>
> And report **both**. A system that refuses everything scores recall 1.00.
> Reporting only one is the classic way to make a bad system look good, and it
> costs marks.

> **Done when:** `report.md` C has the two-setting table with raw counts, the
> Q37 note, and the defended product recommendation.

---

# 4 · Part D — the judge — 45 min

**Why.** You are about to measure quality with a model. Before you may quote
its numbers, you have to show it agrees with you.

### Judges — TODO D1–D3

| Step | What | Done when |
|---|---|---|
| D1 | Two separate single-criterion rubrics, improved | Both copied into `evaluate.py`; refusals handled deterministically |
| D2 | Hand-label 20 answers per rubric → κ | κ ≥ 0.4 for **both**, or the rubric is fixed and re-run |
| D3 | Self-preference note | Direction stated (or judge moved to a different tier) |

**4.1 — `D1`.** Write **two separate single-criterion** rubrics (T3 §4.2):
**faithfulness** (is every claim supported by the context?) and **correctness**
(does it match the gold answer substantively?).

> Never one judge weighing several things. A single number from a
> multi-criterion judge cannot be recovered into its parts.

`aip.evals` has templates. They are **deliberately improvable**. Improve them
in `judge_faithfulness` / `judge_correctness`, and keep `None` on
`parse_error` — never 0.

**4.2 — `D2`. Calibration. This is required.**

```bash
python labs/lab4/evaluate.py --calibrate     # writes the sheet
python labs/lab4/evaluate.py --kappa         # after you have labelled
```

Hand-label **20** answers against each rubric **before** looking at the judge.
Then compute Cohen's κ.

> **Report κ. If κ < 0.4, fix the rubric and re-run.** You may not report a
> judge number in this lab without its κ. The fix is almost always **the
> rubric**, not the model — read your disagreements and you will find your own
> labelling rule was implicit. The κ mechanics are in
> [CONCEPTS.md](CONCEPTS.md).

**4.3 — `D3`.** If your judge is the same model that generated the answer, say
so and state the **direction** of the bias (T3 §4.1). Use a different tier or
profile if you can.

> **Checkpoint — the truncated-judge war story.** A judge capped too low once
> turned a true faithfulness of **0.933** into a reading of **0.667**. The full
> telling and the three signals that caught it are in
> [CONCEPTS.md](CONCEPTS.md). The rule it produced: **a parse failure is
> missing data, not a failing answer.**

> **Done when:** both rubrics are in `evaluate.py`, both κ values are in
> `report.md`, and the self-preference direction is stated.

---

# 5 · Part E — full evaluation and the decomposition — 35 min

### Evaluation — TODO E1–E3

| Step | What | Done when |
|---|---|---|
| E1 | `--full --save reports/lab4.json` | Every metric in the target table reported |
| E2 | `--gold-context` decomposition | A, B, A−B, 1−A in `report.md` E2 |
| E3 | Read 10 wrong answers, tag modes 1–7 | Tally in `report.md` E3 = your Lab 5 backlog |

**5.1 — `E1`.**

```bash
python labs/lab4/evaluate.py --full --save reports/lab4.json
```

Report every metric in the target table.

**5.2 — `E2`. The most useful experiment in RAG** (T4 §5, failure 6).

```bash
python labs/lab4/evaluate.py --gold-context
```

Requires `answer_with_gold_context` (TODO E2): **same generator, different
context** — the gold documents, with no retrieval. Change anything else and the
comparison is meaningless.

```
correctness with gold context      = A    ← the generation ceiling
correctness with retrieved context = B    ← your system
retrieval-attributable loss        = A − B
generation-attributable loss       = 1 − A
```

> **This decomposition tells you where to spend Lab 5.** If A is 0.95 and B is
> 0.72, work on retrieval. If A is 0.78, no retrieval improvement will save you.
> Full reasoning: [CONCEPTS.md](CONCEPTS.md).

**5.3 — `E3`.** Read **10 wrong answers**. Tag each with one of the seven
failure modes (T4 §5): 1 missing content, 2 chunk boundary, 3 embedding
mismatch, 4 ranking, 5 reranker, 6 generation, 7 presentation. **This is your
Lab 5 backlog — bring it with you.**

> **Done when:** `reports/lab4.json` exists. Lab 5 reads it.

---

## Deliverables checklist

- [ ] `labs/lab4/rag.py`, `labs/lab4/evaluate.py`
- [ ] `reports/lab4.json`
- [ ] `report.md` ≤ 3 pages:
  - [ ] your `ANSWER_SYSTEM` + differences from the reference
  - [ ] citation validity, and what you do on failure
  - [ ] refusal precision/recall **at two strictness settings**, with raw counts
  - [ ] **κ for both rubrics**, and how you fixed the rubric
  - [ ] the E2 decomposition: A, B, and both attributed losses
  - [ ] the E3 failure-mode tally

---

## The traps

1. **Judge truncation.** A reasoning judge spends most of its budget on
   invisible thinking. Cap it too low and the JSON truncates, fails to parse,
   and gets scored 0 — a silent downward bias. This cost the reference a
   faithfulness reading of 0.667 when the truth was 0.933. Full story:
   [CONCEPTS.md](CONCEPTS.md).
2. **Scoring a parse failure as 0.** It is missing data. Exclude it, or retry.
3. **Reporting one refusal number.** Refuse everything and recall is 1.00.
4. **Judging with the generator.** Self-preference is real. Different tier.
5. **Leaving `build_retriever()` as the placeholder.**

---

## If something goes wrong

| Symptom | Cause |
|---|---|
| `NotImplementedError` | One of the TODOs in `rag.py` / `evaluate.py` |
| Citation validity < 1.00 | The validator is not on the return path |
| Judge scores suspiciously low, or faithfulness much lower than correctness | Truncated judge verdicts. Check `finish_reason` and `parse_error` |
| κ below 0.4 | The rubric, not the model. Read your disagreements |
| `judge_agreement` raises | Your two lists differ in length — one label is missing |
| Refusal numbers swing wildly | n = 5. They are noisy. Report counts |
| `--gold-context` errors | Q36/Q38/Q39 have no gold docs; skip them |
| Cost above budget on `--full` | 45 questions × (generate + 2 judges). Check your tier |

---

## The sentence to leave with

> ### A parse failure is missing data, not a failing answer.
