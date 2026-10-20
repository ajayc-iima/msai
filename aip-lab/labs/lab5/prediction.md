# Lab 5 — Part B: ranking and pre-registered prediction

Two sections, both dated. **B1–B4 is superseded and kept as history. B5 is the
operative prediction.** No v2 arm had been run when either was written; what
changed between them is the *diagnosis*, not a result.

---

# B1–B4 (superseded — written from an incomplete classifier)

**Written 2026-10-03 with the span check as the only retrieval-side signal.**

### Tally as I first had it

| mode | | n |
|---|---|---|
| 4 | ranking | 8 |
| 6 | generation | 8 |
| 3 | embedding mismatch | 1 |
| | **total** | **17** |

Two modes at 8 each, so the decision was supposed to be "which fix reaches the
failures". My pick was **#1, a cross-encoder reranker (retrieve 30 → rerank 5)**,
on the reasoning that only one of the eight mode-4 failures had its material
inside rank 8, so "raise `final_k`" was nearly worthless and a reranker was the
only candidate that could reach material at ranks 7–27 without breaching the
≤2× cost rule. I recorded a table of seven candidates with expected recoveries,
cost deltas and effort, and pre-registered "3–5 of the 8 mode-4 failures
recovered, +0.03 to +0.06 normalised correctness".

### Why it was wrong

The span check answers **where** material is missing. It does not answer
**whether its absence caused the failure**. Those are different questions, and
on this data they have different answers.

I added a third probe — rerun the generator with the pipeline's own geometry
(5 chunks, size 400) but a retriever forbidden from returning non-gold
documents — and compared it against Lab 4's E2 gold-context probe (every chunk
of every gold document at size 800). In **12 of 17** failures the generator
produces the wrong answer *even when handed every gold chunk of every gold
document*. For those twelve, retrieval was never the binding constraint and no
retrieval fix could have touched them. My pick would have been the exact error
the handout warns about: fixing retrieval after a tally that says generation.

I also found the converse case, which is the reason the third probe exists at
all. On **Q34** the span check looks *fine* (80% of content words present), yet
filling all five slots with the best gold-document chunks still fails, while
more gold material succeeds. The generator is perfectly capable; the window is
simply too small. Read naively, that is a generation failure. It is a context
budget.

---

# B5 — the operative ranking and prediction

**Re-registered 2026-10-03, after the diagnosis was corrected, before any v2 arm
was run.**

### The tally the corrected classifier produces

| mode | | n | ids |
|---|---|---|---|
| 1 | missing content | 0 | |
| 2 | chunk boundary | 0 | |
| 3 | embedding mismatch | 1 | Q37 |
| 4 | ranking | 4 | Q19, Q24, Q32, Q34 |
| 5 | reranker | 0 | — |
| 6 | generation | 12 | Q04, Q05, Q06, Q07, Q10, Q11, Q20, Q21, Q22, Q26, Q29, Q35 |
| 7 | presentation | 0 | — |
| | **total** | **17** | |

```
failure mode          n    share   cumulative
generation            12   70.6%   70.6%  █████████████████████
ranking                4   23.5%   94.1%  ███████
embedding_mismatch     1    5.9%  100.0%  ██
```

Two modes account for 16 of 17. Two zeroes are structural, not luck:

- **mode 5 is impossible here.** Lab 3's rerank sweep was never recorded
  (`reports/lab3_sweeps.json` has no `rerank` key), so `build_retriever()` has
  no second stage. There is no reranker to get wrong.
- **mode 7 is zero** because citation validity was already 1.000 in Lab 4. The
  validate-and-repair path is holding.

The single most important number in this lab is the **12**. It is a capability
ceiling: for 70% of our failures, a *perfect* retriever would still produce the
wrong answer. That reframes the whole backlog — retrieval quality is not where
this system is losing.

### The two clusters as mechanisms

**Mode 6 — generation (n=12).** Two sub-shapes, both visible in the answers:

- *Under-answering* (Q04, Q05, Q06, Q07, Q10, Q11, Q20, Q21, Q22, Q26, Q35):
  the headline is right and a qualifier is dropped. Q07 is the extreme — 100%
  of gold content words and every gold number in the window, and the output
  still garbles the table into "up to a maximum of 10 of 100%". The prompt's
  rule 5 says "Be concise. Two or three sentences unless the question needs
  more", and most of these gold answers are two sentences by construction.
- *Over-refusal* (Q19): refuses a question whose deciding numbers were
  delivered at ranks 1–3. The only `correctness=0` in the set.

**Mode 4 — ranking / context budget (n=4).** Q19, Q24, Q32, Q34 all share one
signature: the generator succeeds with all gold material, fails with five
gold-only chunks, and the material it needs sits at dense rank 8–18. The window
is five chunks because Lab 4 chose `final_k=5`.

### Ranking by expected value

Cost is tokens/query, because every model on this provider is unpriced and the
"≤ 2× per query" rule is only checkable against something measurable. All
candidates keep **model calls/query unchanged** — no extra generation call.

| # | Cluster | n | Fix | Est. recovery | Cost Δ tokens/query | Latency Δ | Effort |
|---|---|---|---|---|---|---|---|
| 1 | 6 | 12 | **completeness clause replacing the brevity rule** | **4–7** | +0 prompt, +25–40% completion | ~0 | trivial |
| 2 | 4 | 4 | **cross-encoder rerank, retrieve 30 → 5** | **2–3** | ~0 | +0.6 s | low (one 90 MB local model) |
| 3 | 4 | 4 | raise `final_k` 5 → 10 | 1 (Q19 only; Q24/Q32/Q34 need rank 18) | +60–80% prompt | 0 | trivial |
| 4 | 6 | 12 | larger generation tier (`nemotron-3-ultra-550b`) | 2–5 | ~0 | +2–4 s | trivial |
| 5 | 6 | 12 | multi-hop decomposition for Q19–Q28 | 0–2 | +1 call/query | +2× | high |
| 6 | 4 | 4 | small-to-big (parent-section expansion) | 1–2 | +30% prompt | 0 | medium |
| 7 | 3 | 1 | hybrid BM25 + dense | 0–1 | 0 | +2 ms | low |
| 8 | 6 | 12 | reorder so the best chunk is last | 0–1 | 0 | 0 | trivial |

**Pick #1, the completeness clause.** One sentence: it is the only candidate
that can touch 12 of the 17 failures, it costs zero additional model calls, and
the failure mode it targets — a correct first clause followed by a dropped
qualifier — is the shape the current rule 5 actively invites.

**Second, #2, the cross-encoder reranker**, measured separately on top. It
targets the four mode-4 failures without inflating the context, which matters
because #3 (raise `final_k`) cannot reach three of those four anyway — their
material is at rank 18, beyond any window anyone would ship.

Row 4 is the honest runner-up and I am not measuring it, for a reason I will
state rather than hide: the model I am obliged to run *is already a forced
change*. Lab 4's `MAIN` model returned HTTP 410 (end-of-life) on 2026-10-03, so
the v1 baseline runs on a different generator than the original Lab 4 numbers
do. Adding a deliberate second model change on top would make the v2-vs-v1
delta uninterpretable. It is the first thing to try next.

### The prediction

> **Fix 1 (v2a = completeness clause).** I expect it to recover **4–7 of the 12**
> mode-6 failures. Most likely the under-answering cases where a qualifier sits
> in the window and is simply not volunteered (Q05, Q06, Q07, Q22, Q24).
> Least likely the ones where the model garbles or invents (Q07's table
> misreading, Q29's distractor contamination, Q20's four-document assembly).
>
> I expect **normalised correctness +0.05 to +0.09**, **+0 calls/query**,
> **+25–40% completion tokens**, and **no change to prompt tokens** beyond the
> longer contract.
>
> I expect **refusal precision to fall**, and I want to be explicit that this is
> a prediction rather than an accident: the reference solution saw the same
> thing when it relaxed the answer-length rule, and the mechanism is the same
> one. A rule telling the model to cover every part of the question looks, on a
> question that cannot be answered, like an instruction to answer it. Lab 4 sits
> at 0.833 with six refusals, so there is one bad refusal of headroom to lose.
> If refusal precision falls and correctness rises, that is a trade, not a
> failure, and the number to report is both.
>
> **Fix 2 (v2b = v2a + cross-encoder rerank).** I expect it to recover **2–3 of
> the 4** mode-4 failures (Q19 at rank 8 is the likely one; Q24, Q32 and Q34 sit
> at rank 18 and I do not expect a MiniLM cross-encoder to out-rank a dense
> retriever that far). I expect **gold-doc coverage in the window to rise** even
> where correctness does not, and **p50 generation latency +0.5–0.7 s**.
>
> The prediction I am least sure about is the size of the correctness gain from
> fix 1, in both directions: the same mechanism that makes the model volunteer a
> qualifier also makes it volunteer a qualifier on a question it should have
> declined. That is exactly what the refusal-precision number is for.
