# Lab 1 — Concepts
### The reference — keep this open while you work

> [README](README.md) (the brief) · [RUNSHEET](RUNSHEET.md) (the actions) · this file (theory → code) · [report.md](report.md)

| Concept | In the code |
|---|---|
| Schema as contract; validity vs correctness | `extract.py::TicketRecord`, harness `schema_valid` |
| `Literal` vs free text | `CATEGORIES`, `sentiment`, `product`, `language` |
| Repair loop | `aip/llm.py::structured` (StructuredExtractor) |
| Deterministic vs model fields | `extract_deterministic`, `apply_business_rules`, `TicketRecordC` |
| PII patterns | `aip/guards.py::PII_PATTERNS` |
| The evidence field | `extract.py::evidence` (≤ 200 chars) |
| quality × cost × latency | `run_eval.py` summary + `Budget` |
| Annotation guidelines as the label contract | `data/README.md` |
| Record vs field accuracy | `aip/evals.py::field_accuracy` |

---

## Validity is not correctness

**What it is.** *Schema validity* means every output was a well-formed
record the contract allows: right types, values inside constraints, no
missing keys, no crash. *Correctness* means the values are right against the
gold labels. The harness scores them separately — `schema_valid` and
`field_accuracy` / `record_accuracy` in `run_eval.py`.

**In the code.** Validity is your 100% non-negotiable target and it is
enforced by the Pydantic contract plus the catch-all in `extract_b` /
`extract_c`: on `StructuredOutputError`, return a record with
`needs_human_review=True` rather than raising. The record is valid; it is
merely not trusted.

**The trap.** **100% valid can still be wrong.** A confidently mislabelled
`urgency` is perfectly valid. Validity buys the business a pipeline that
never wedges — no malformed payload ever reaches the routing tool, and
failures degrade to a human queue instead of an exception. It buys nothing
about whether the routing decision is right. That is what field and record
accuracy are for, and it is why `needs_human_review` exists: the system's
honest answer to "I cannot derive this label from the rules" is a flag, not
a guess.

---

## The Pydantic schema is the contract

**What it is.** Everything the model is allowed to say, and nothing else.
Field `description`s ship to the model as part of the JSON Schema, which
makes them the highest-leverage place for an instruction — they sit next to
the thing they govern.

**In the code.** `extract.py::TicketRecord` (TODOs B1a–B1j):

| Design choice | Why it is in the schema |
|---|---|
| `category: Literal[...]` | The model cannot emit `billingg` or a seventh category. The type system rejects it |
| `urgency: int` with `ge=1, le=5` | Out-of-scale values never reach your metrics |
| `description` that **defines the scale** | Anchors 1/3/5, the 1/2 lookup rule, the 4/5 tense rule — instructions where the model reads them |
| `policy_number: str \| None` + `field_validator` | Format `AUR-\d{7}` enforced in code; empty string / `"null"` coerced to `None` |
| `evidence: str` `max_length=200` | Forces a span quote; a model that must show its evidence cannot silently freewheel |
| field **order** | Pydantic preserves declaration order; order conditions generation |

**The trap.** Two failure modes pull in opposite directions. **Free text** for
a six-value field invites drift and typos you will score as wrong.
Over-narrowing a `Literal` without reading `data/README.md` invites a schema
that cannot express a legal gold label. The guidelines are the source of the
scale; the schema is its executable form. A `description` that says "urgency
1–5" teaches nothing; one that states the 1/2 boundary teaches the boundary.

---

## The repair loop

**What it is.** Structured output is enforced in four layers: JSON mode on
the request → tolerant parsing (strip fences, find the braces — the salvage
`v0_naive.py` only *diagnoses*) → Pydantic validation → a **repair round**:
feed the `ValidationError` back to the model and ask again. After
`max_repairs` (default 2) failures, raise `StructuredOutputError`.

**In the code.** `aip/llm.py::structured` → `StructuredExtractor.run()` —
JSON mode, `extract_json`, `model_validate`, repair loop. Your TODO B3 wires
it in; TODO B4 catches the final `StructuredOutputError` and degrades to
`needs_human_review=True`. **Repairs are not free**: every attempt is cached
and counted against the budget (`repair_rate` in later labs).

**The trap.** Two misconceptions. (1) The repair loop does **not** make the
model *right* — it makes it *well-formed*. A repair can fix a truncated JSON
object; it cannot fix a misunderstanding of the complaint boundary. (2) A
crash inside your extractor is not a model failure, it is your contract's
failure: if `extract_b` raises, you miss the validity target outright.
"Never crash" is a code property, not a prompt property.

---

## Deterministic fields out of the model

**What it is.** Some outputs are functions of the input text with no
judgement in them. Compute those in code: regex, pattern tables, business
rules. Leave the model only the fields that genuinely need interpretation.

**In the code.**

| Field | Where it moves | Mechanism |
|---|---|---|
| `policy_number` | `extract_deterministic()` | `POLICY_RE = \bAUR-\d{7}\b`, live body only |
| `contains_pii` | `extract_deterministic()` | `PII_PATTERNS` from `aip/guards.py`, minus Aurora's own addresses |
| `escalate` | `apply_business_rules()` | `urgency >= 4 or "ombudsman" in ticket.lower()` |

`TicketRecordC` (TODO C2) is the reduced schema the model sees in Part C.

**Measured effect (Part C checkpoint).** Cost falls **~25–35%** (shorter
prompt, fewer output tokens); those three fields hit **1.000**; overall
accuracy *holds rather than rises* — because they were already near 1.00 in
Part B, there were no points to win. What you bought is fields **guaranteed
and auditable** instead of **usually right**, at lower cost. A compliance
officer can read `apply_business_rules`; nobody can read a prompt.

**The trap — two policy numbers.** Some tickets contain two
policy-number-shaped strings: one in the live message, one in a quoted reply
(`>` lines) from an earlier thread — and they are not always the same
number. The gold rule: **only from the live message**; a ticket whose only
policy-shaped string is inside a quoted reply is labelled `null`. Decide
your rule, write it in a comment, implement it — then ask whether it
generalises or whether you fitted it to this dataset. Fitting a rule to the
dev split and calling it a solution is the same sin as Lab 2's A4, one lab
earlier.

---

## Record accuracy vs field accuracy — why 0.55 is brutal by construction

**What it is.** Both come from the same per-field comparison in
`aip/evals.py::field_accuracy`:

```
field_accuracy  = (fields correct) / (fields scored)
record_accuracy = 1 if EVERY field is correct, else 0
```

Record accuracy is the **conjunction** over 8 fields. Even with every field
at 95% independent accuracy, record accuracy would be `0.95^8 ≈ 0.66`; drag
three judgement fields down to ~0.80 and the product collapses.

**Measured in the target table.** Field ≥ 0.90, record ≥ 0.55. After Part C,
four fields (`policy_number`, `contains_pii`, `product`, `language`) sit at
1.000 — so record accuracy is driven almost entirely by the three judgement
fields (`category`, `urgency`, `sentiment`) plus whatever `escalate` and
`language` do on the edge.

**The trap.** The two numbers answer different questions. Field accuracy is
the **engineering** metric — it moves when you change the prompt, and it is
sensitive enough to track progress. Record accuracy is the **business**
metric — one wrong field still sends the record to a human, so the gap
between 0.90 and 0.55 is not a rounding artefact, it is the fraction of
tickets your system still cannot touch. Reporting only field accuracy
flatters the system; reporting only record accuracy hides which field to fix
next. Report both.

---

## Annotation guidelines are the label contract

**What it is.** `data/README.md` (*Annotation guidelines*) is the written
ruleset the gold labels were produced from — the same artefact a real
project publishes as its annotation guide.

**Where it lives.** `data/README.md`: the `category` table with the
complaint boundary, the full `urgency` 1–5 scale with the 1/2 lookup rule
and the 4/5 tense rule, `sentiment`'s neutral/frustrated prior-failure rule,
`product` must-be-named, `policy_number` live-message-only, `contains_pii`'s
deliberately narrow definition, `language` code-mixing, and `escalate` as a
code rule.

**The principle.** *A label the annotator cannot derive from a written rule
is a label nobody can hit.* Your field `description`s are downstream of this
document: if the guideline cannot state the rule, the schema cannot encode
it, and the model cannot follow it. The reference solution scored ~0.55 on
`urgency` against an unpublished scale and ~0.85 once the table existed —
**with no change to the model.**

**The trap.** Reading five example tickets and inferring the rules is not
the same as reading the rules — you will silently disagree with the gold
labels and call it model error. The complaint boundary alone accounts for
roughly a third of errors any system makes here.

---

## Known label limitations — pointer, not summary

**Read `data/README.md` → *Known limitations* yourself.** Three things worth
carrying into every later lab:

1. **Labels are exact by construction** (text generated *from* the label),
   so inter-annotator agreement here is 1.00 while real queues sit at
   0.60–0.75. Your 0.95 on this benchmark is not a 0.95 production
   expectation — part of the shortfall will be the labels, not the system.
2. **Two label bugs were found by running a correct solution against them**
   (invented policy numbers; `contains_pii` flags contradicting the finished
   text — 14% of "no PII" labels sat on text containing an email). The fix
   states the general rule: **derive the label from the finished artefact,
   never from the process that built it.** Write a regression test per label
   rule first.
3. **The urgency scale was unlearnable until it was written down** — 0.55 →
   0.85 from documentation alone. If your annotators cannot state the rule,
   your labels are noise wearing a number.

Do not copy these into `report.md`; cite the document and use them when you
interpret your own numbers.
