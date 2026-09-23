# Lab 2 — Concepts
### The reference — keep this open while you work

> [README](README.md) (the brief) · [RUNSHEET](RUNSHEET.md) (the actions) · this file (theory → code) · [report.md](report.md)

| Concept | In the code |
|---|---|
| Stochasticity; single runs lie | your Part D comparisons |
| Few-shot as retrieval; leakage | `variants.py::few_shot_block` (A1–A4) |
| Cascade routing | `variants.py::cascade` |
| Temperature-0 cache bug | `aip/cache.py` keying; your C trigger |
| Disagreement = variance, not bias | your signal check |
| Confidence intervals | `stats.py::wilson_interval`, printed by `grid.py` |
| McNemar paired test | `stats.py::paired_test`, auto in `grid.py` |
| quality × cost × latency; dominance | `grid.py` compare + dominated block |
| Calibration numbers | the reference test-split run |

---

## Stochasticity, and why single runs lie

**What it is.** A language model call is a stochastic function: the same
prompt can produce different outputs across runs. Any two accuracy numbers
you print are *estimates* drawn from that distribution, each with its own
wobble.

**In the code.** Every variant goes through the same `run_eval()` in
`aip/evals.py`, which reports record accuracy, field accuracy, cost and
latency per configuration — and `grid.py` wraps each record accuracy in a
Wilson interval and a paired test.

**Measured in the reference.** Configuration A scores **0.88** on 60 cases,
configuration B scores **0.91**. Three points! Ship B?

**The trap.** At n = 60 the 95% CI half-width near p = 0.90 is about
**±0.076** (see the intervals section below). 0.88 and 0.91 sit inside each
other's intervals; re-run both and B can come out *lower*. Shipping B on
those 3 points is a decision made on nothing — and people do it constantly,
in real companies, with real money. The skill this lab teaches is telling
**a result** from **a wobble**. "No significant difference" is a finding: it
tells you to choose on cost.

---

## Few-shot examples as retrieval — and the leakage trap

**What it is.** Few-shot prompting is retrieval in disguise: you select up to
6 examples from a corpus (the dev set) that you believe are informative for
the query at hand. Selection quality *is* the method — a boring ticket teaches
the model nothing it did not already know. Examples cost prompt tokens on
every single call, forever, so they must earn their keep.

**In the code.** `variants.py`: `FEW_SHOT_IDS` (TODO A1), `few_shot_block()`
(TODO A2) renders each example into the exact output format, concatenated
onto `SYSTEM_PROMPT`. Measured by `grid.py --variants zero_shot few_shot`.

**Measured in the reference.** Few-shot moved field accuracy **0.928 → 0.931**
and moved record accuracy *down*, paired **p = 1.00**. The zero-shot prompt
already carries the labelling rules inside the Pydantic field `description`s —
exactly where the rules belong — so the examples had nothing left to teach.
When few-shot *does* buy a large delta (say 20 points), that is not a win: it
means your zero-shot prompt was under-specified, and the honest fix is to
improve it rather than bank the inflated number.

**The trap (A4).** You picked your 6 examples **from the dev set** and you
measure **on the dev set**. The model has effectively seen the answers; the
comparison is contaminated before it starts. Name the problem, pick a
defensible fix (hold the examples out of the measurement set, pick them from
outside dev, re-measure on a clean slice — more than one works), and state in
your report which number is the honest one. An unhandled A4 is an
experimental-discipline failure, regardless of what the table says.

---

## Cascade routing, the temperature-0 cache bug, and what disagreement detects

**What it is.** Most tickets are easy; a few are hard. A cascade calls the
cheap SMALL model first and escalates to MAIN only on a trigger you choose —
so you pay large-model prices on the hard minority instead of on everything.

**In the code.** `variants.py::cascade()` (TODO C). The diagram:

```
   SMALL model
       │
       ├── validates AND evidence non-empty ──▶ accept
       │
       └── otherwise ──▶ MAIN ──▶ accept, or flag for review
```

Set `rec["_path"] = "small" | "large"`; `grid.py` reads it and prints the
escalation rate. Triggers, weak to strong: validation failed · evidence field
empty or too short · second SMALL sample disagrees on category.

### The silent bug — full story

The obvious way to detect disagreement is to draw the same prompt twice and
compare. **Two identical requests at temperature 0 are the same request.**
The response cache (`aip/cache.py`, keyed on messages + temperature + format)
serves the second call from the first. The answers are byte-identical.
Disagreement is never detected. The escalation rate is **0%**. Your cascade
reports the small model's accuracy at the small model's price while
appearing to work — **nothing errors**, and the only symptom anywhere in the
output is `escalated = 0.00`.

The fix: draw the second sample at **temperature > 0**, which changes both
the sampling and the cache key.

### Then check whether the trigger carries any signal

Self-consistency (two samples, compare) detects **variance** — a model that
is unsure and answers differently on different draws. What you often have is
**bias**: a model that is *consistently* wrong. Measure agreement when the
answer is **correct** versus when it is **wrong**.

**Measured in the reference: 94% agreement when correct against 83% when
wrong** — the trigger fired on only **2 of 12 errors**. The cascade was worth
almost nothing. Reporting that, with the numbers, is full marks; a cascade
you did not interrogate is not. The same logic returns in the stretch
self-consistency task: disagreement predicts error far better than the
model's own stated confidence — but only after you have measured it.

---

## Confidence intervals

**What it is.** A point estimate (accuracy = 0.90) is a guess about the
underlying rate. A confidence interval says how far that guess could plausibly
wobble. The normal approximation:

```
CI ≈ p ± 1.96 · sqrt( p(1-p) / n )
```

**Worked example.** At n = 60 and p = 0.90:
`1.96 · sqrt(0.9 · 0.1 / 60) ≈ 0.076`, so the interval is roughly
**[0.824, 0.976]** — a ±0.076 half-width. Scores of 0.88 and 0.91 both sit
inside it; their intervals overlap almost completely. **You cannot conclude B
is better from those numbers alone.**

**In the code.** `stats.py::wilson_interval(successes, n)` — the Wilson score
interval, preferred over the normal approximation because it stays inside
[0, 1] and remains sane at small n and extreme p, both of which describe your
60-case dev set. `grid.py` prints a Wilson CI for every configuration.

**The trap.** Overlapping intervals mean *not enough evidence*, not *equal*.
And a narrow-looking interval on the wrong metric (or with n miscounted) is
worse than an honest wide one. Never claim a difference smaller than your
interval.

---

## McNemar's paired test

**What it is.** Two systems, the **same** items. Ignore every item where they
agree; count only the disagreements:

```
b = cases where A is right and B is wrong
c = cases where B is right and A is wrong
```

Under the null hypothesis each discordant pair is a fair coin, so the exact
two-sided binomial on (b, c) gives the p-value. If b ≈ c, neither system is
better; if one dominates the other on the discordant set, you have evidence.

**In the code.** `stats.py::paired_test(a_correct, b_correct)` returns b, c,
the discordant count, and p. `grid.py` prints paired comparisons against the
first `--variant` automatically whenever you pass two or more.

**Measured in the reference.** The few-shot comparison came back with
**p = 1.00**; SMALL vs MAIN zero-shot on test came back **p = 0.71**. Both
are "no significant difference" — and both are usable conclusions.

**Why pairing wins.** The dominant source of variance here is **item
difficulty**: some of the 60 tickets are just harder than others, for every
system. An unpaired comparison of overall percentages makes you fight that
noise. Pairing on the same items **cancels it out completely**, so it
routinely detects differences at n = 60 that an unpaired test cannot. This is
the most portable statistical idea in the course.

**The trap.** Pairing does not create power out of nothing: if the systems
agree on 58 of 60 items, b + c = 2 and nothing will reach p < 0.05. Report
that honestly — it means choose on cost.

---

## quality × cost × latency, and dominated configurations

**What it is.** Never report quality alone. Every configuration is a point in
a three-dimensional space:

```
        quality  ×  cost  ×  latency
```

A configuration that is 1% more accurate, 5× more expensive and 3× slower is
usually a bad trade. You cannot see the trade-off unless you measure all
three — which is the entire point of running everything through one harness.

**A dominated configuration** is one that is worse than another
configuration on **every** axis: strictly lower quality, strictly higher
cost, strictly higher latency. There is never a reason to pick it, and
naming it explicitly is a real, useful finding.

**In the code.** `grid.py` prints cost / 1k tickets / year at 10k/day, p50
and p95 latency, and a final `Dominated configurations` block computed over
quality AND cost (or total tokens when any provider is unpriced — otherwise
comparing zeros would declare everything dominated).

**The trap.** Cost alone is not even honest cost: when a provider publishes
no per-token prices the meter must print `UNPRICED` and fall back to tokens,
because a cost meter that silently reports `$0.00` for a paid API is the
exact class of bug this module teaches you to hate. And on any single axis,
"best" is meaningless until you say what you traded away.

---

## Calibration numbers — what the reference actually measured

**What it is.** Before you interpret your own grid, know where the reference
solution landed on the **test** split, so you can tell a landing from a bug.

**Measured in the reference (test split):**

| Configuration | field accuracy | cost | p95 latency |
|---|---|---|---|
| `SMALL` zero-shot | **0.930** | **$0.080** | 2,276 ms |
| `MAIN` zero-shot | **0.942** | **$0.382** | 6,720 ms |

**MAIN is 4.8× the cost and 3× the latency** for +0.012 field accuracy — a
difference the paired test **could not distinguish from noise (p = 0.71)**.

**The trap.** The tempting narrative is "bigger model, better number". The
honest conclusion is the other one: *"the expensive configuration is not
detectably better, therefore ship the cheap one."* That sentence, backed by
b/c/p, is a complete and correct recommendation — and full marks. Your grid
may land differently; if it does, report it the same way: whichever way it
lands, with the test attached.

