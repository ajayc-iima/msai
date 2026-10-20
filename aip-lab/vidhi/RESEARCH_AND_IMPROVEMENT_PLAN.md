# Refuse to Hallucinate — Research Review & Improvement Plan

> **Implementation status (Oct 2026):** Priority 1 is **implemented and verified**
> (abstention confusion matrix, figure attestation + store-binding, measured
> multilingual Safety-A P/R, plus Unicode normalization). Full test suite:
> **108 passed**. See "Part 2" for what remains (P2/P3).
> (*Updated 2026-10-20: the raw-PDF expansion grew the store from 173 to
> 1708 verified rows — PLFS Highlights battery, TUS 2024 tables battery,
> HCES Statement 10 legs — suite is now **123 passed** (state-vocabulary
> and slice-completion guarantees added), and
> `scripts/coverage_probe.py` proves all 1708 rows answerable with exact
> figures.*)
>
> **2026-10-20 line-by-line audit:** every `vidhi/` file was re-read and
> hardened — wrong-granularity PASS eliminated (an unspecified dimension is
> now satisfied only by an aggregate row), the WARN_NO_DATA coverage note
> never substitutes another state, Safety-A false positives on legitimate
> methodology/Hinglish phrasings were fixed (red-team grown to n=28, still
> P/R/F1 1.000 with 0 FP / 0 FN), out-of-corpus PLFS rounds are pinned and
> WARN instead of silently serving 2025 data (the calendar round "2024" and
> the traditional 2017-18…2023-24 annuals have since been curated by the
> raw-PDF expansion; "2024-25", "2016-17" etc. genuinely have no rows and
> still WARN), "what is … <round>" is
> treated as a value question, cache/MCP responses are truthful, and dead
> code was removed. All green: 110 tests, eval 100/100, demo 6/6. Details in
> `EVALUATION_REPORT.md` (revision log).

**Context:** Vidhi Guardian (the ConfAI 2026 poster project) is a deterministic
validity firewall for Indian official survey statistics. Its core claim is
*"refuse to hallucinate"* — it adjudicates a claim with versioned rules
**before** generation and refuses/warns when the claim is not defensible.

This document (1) reviews the 2024–2026 literature on hallucination refusal,
and (2) maps the findings to concrete, prioritized changes to the Vidhi
codebase and its measured results. All arXiv IDs / URLs should be re-verified
before citing in a camera-ready paper.

---

## Part 1 — Research, step by step

### 1.1 Hallucination is a *systems* problem, not a prompt problem

Two 2025 surveys (ACM TOIS *Survey on Hallucination in LLMs*; MDPI *From
Illusion to Insight*) converge on the same conclusion: **no single technique
eliminates hallucination**; the SOTA is a **hybrid** — retrieval grounding +
reasoning/self-consistency + training-time adaptation + post-hoc filters.
Vidhi is precisely such a hybrid (retrieval + deterministic rules + post-hoc
consistency check). The surveys also flag the two failure modes most relevant
to Vidhi: (a) RAG *introduces* hallucination when retrieval is noisy/outdated,
and (b) attribution is fragile.

### 1.2 Abstention is a first-class capability (the poster's thesis)

- **Know Your Limits (Wen et al., TACL 2025)** — the canonical survey. It
  frames abstention from three angles: the **query** (ambiguous/unanswerable),
  the **model** (insufficient confidence), and **human values** (safety/privacy).
  It defines abstention as a *spectrum* (uncertainty → refusal), and warns that
  naive calibration conflates "is this answerable" with "how confident am I" —
  exactly the distinction Vidhi draws with `WARN_NO_DATA` vs `R_LOW_EXTRACTION_CONF`.
- **Abstain-QA / AUCM (COLING 2025)** — a confusion matrix for
  answerable-vs-unanswerable. Even GPT-4 / Mixtral fail to abstain reliably.
  → *Vidhi should report this matrix on its own golden set.*
- **Reinforced Hesitation (arXiv 2511.11500)** — shows **prompts cannot override
  training that rewards "any answer over no answer"**. Models almost never
  abstain under penalty warnings. This is the strongest published support for
  Vidhi's core design decision: **don't ask a model to refuse — make refusal
  a deterministic rule.**
- **R-Tuning (Zhang et al., 2024)** and DPO-for-abstention — fine-tune models
  to say "I don't know" on refusal-aware data. Relevant only to Vidhi's
  *optional* LLM translator, never the judge.

**Takeaway for Vidhi:** refusal must stay deterministic (rules), and the
*quality of refusal* must be **measured** (see §2, Priority 1A).

### 1.3 Grounding & attribution are the weak point of generative answers

- **FACTS Grounding (arXiv 2501.03200)** — long-form grounding benchmark with an
  "eligibility filter" (a non-answer is disqualified before factuality is judged).
  Top models score well below 1.0. → Vidhi's byte-identity-of-numbers gate is the
  right bar; "fluent but ungrounded" is exactly what it excludes.
- **GaRAGe (ACL Findings 2025)** — models **deflect only ~31%** of the time when
  grounding is insufficient, and over-summarise instead of grounding strictly.
  → Vidhi's `WARN_NO_DATA` (never guess) is the behavior models *fail* to do;
  measuring Vidhi's deflection rate is a defensible result.
- **Correctness is not Faithfulness (ICTIR 2025)** — up to **57% of citations are
  post-rationalized** (the model cites a source it didn't actually rely on).
  → Vidhi avoids this *by construction* (citations = verified rows), but should
  *say so* with a metric.

### 1.4 Deterministic verification is the strongest "refusal" mechanism

This is Vidhi's differentiator, and the literature now has direct analogues:

- **VerityGate (arXiv 2610.00833)** — a **four-gate deterministic checker**
  between a structured backend and an LLM narrator: (G1) evidence existence,
  (G2) entity allowlisting, (G3) **number binding** (exact string match of
  numbers), (G4) claim-type → evidence-type rules. It hashes the evidence graph
  (SHA-256) so verification is auditable. LLMs fail these deterministic gates
  **47.9%–80.3%** of the time before repair. → *This is essentially Vidhi's
  Numeric stage + provenance, plus the missing F1 figure-attestation hash.*
- **ATLAS (arXiv 2510.25890)** — constraint-guided generation that emits
  **machine-checkable certificates** a third party can re-check without trusting
  the LLM. → Vidhi's frozen hash + manifest should be extended so the *figure*
  is independently verifiable (F1).
- **CaMeL / FIDES (via MLSecOps L0–L3)** — the L3 "deterministic policy /
  information-flow control" layer treats untrusted data as *values, never
  instructions*, enforced outside the model. → This is exactly Vidhi's
  freeze-before-retrieval; it should be stated as a formal **data
  non-interference property** and tested.

### 1.5 Injection & trust boundaries (Safety-A / Safety-B)

- **OWASP LLM01:2025** — "there are no fool-proof preventions"; mitigation =
  constrain behavior, **validate output formats with deterministic code**,
  input/output filtering, segregate untrusted content, and *adversarial testing*.
- **Instruction Hierarchy (Wallace et al., 2024) / GuardRAG / InstructDetector
  (EMNLP Findings 2025)** — retrieved text must be lower-privilege than user
  intent. Instruction-detection via hidden-state probes hits 99.6% in-domain.
  The 2025 "invisible-font prompt in academic papers" (Nikkei) case shows
  attacks now use **Unicode/hidden-text** carriers — which regex cannot see.
- → Vidhi already ships the trust boundary (freeze + verified-only). Gaps:
  (a) Safety-A is regex-only and misses **normalized/hidden-text** injection;
  (b) its P/R is **unmeasured**.

### 1.6 Uncertainty, calibration & conformal abstention

- **Semantic Entropy (Farquhar et al., Nature 2024)** and **SEPs (ICML 2024)** —
  detect confabulations from meaning-level uncertainty; the key metric is
  **AURAC** (accuracy under rejection). Cheap probes (SEPs) make it CPU-feasible.
- **Conformal abstention (arXiv 2502.06884)** — replaces static thresholds with
  calibrated thresholds giving coverage guarantees; RL-learned thresholds
  improve AUROC for hallucination detection by ~22%.
- → Applies only to Vidhi's *optional* LLM translator/polish (the judge is
  deterministic and has no "uncertainty"). The fixed `0.60` confidence floor
  should become a **calibrated threshold** (the spec already plans this).

### 1.7 Constrained decoding → schema-locked translation

- **JSONSchemaBench (arXiv 2501.10868) / automata-based decoding / SEM-CTRL** —
  constrain the decoder so the model can **only** emit schema-valid output.
  → Vidhi's LLM translator should use constrained decoding (outlines/xgrammar)
  so a claim can never be malformed — the "closed-set translator" (L0) in the
  spec.

### 1.8 Research → Vidhi, in one line

The literature **validates Vidhi's architecture** (deterministic rules +
grounded verified data + freeze-before-retrieval is exactly the L3/VerityGate
pattern the field is converging on), and it shows the next steps are: **measure
the refusal quality, bind the number to the verdict, harden injection detection,
and calibrate the confidence gate** — not "add a bigger model."

---

## Part 2 — Improvement plan (mapped to code)

> **Status:** ✅ P1A, P1B, P1C, P2A are implemented and verified (108 tests green).
> ⬜ P2B, P2C, P3A–P3C remain.

Each item lists: files, the change, and the new **measured result** it produces.
Priorities are ordered by (value to the demo/paper) × (risk/effort).

### Priority 1 — high value, demo-ready, low risk

**P1A. Measure refusal quality (abstention recall + confusion matrix).**
- *Files:* `vidhi/eval.py`.
- *Change:* classify each golden by "answerable" (expected `PASS`) vs
  "must-abstain" (expected `WARN_NO_DATA` / `REFUSE`), then report:
  - **abstention recall** = must-abstain questions actually abstained ÷ all
    must-abstain (Vidhi should be 1.000 by construction);
  - **hallucination rate** = answerable questions abstained + must-abstain
    questions answered (should be 0);
  - a 2×2 AUCM-style table printed in the eval output.
- *Result:* replaces the weak "WARN_NO_DATA=16" with **"deflection 1.000 on 24
  must-abstain goldens; hallucination rate 0.000"** — a headline result that
  directly backs "refuse to hallucinate" and is *measured*, unlike the
  (anecdotal) StatsDoc comparison.

**P1B. Figure attestation — bind the number to the frozen verdict (fixes F1).**
- *Files:* `vidhi/rules.py` (add `Verdict.attestation`), `vidhi/answer.py`
  (populate it post-retrieval), `vidhi/pipeline.py` (emit it), `demo.html`
  (show it).
- *Change:* after retrieval,
  `attestation = sha256(frozen_hash ⊕ row_id ⊕ value ⊕ unit ⊕ pdf_sha256 ⊕ page)`,
  exposed in the response. A tampered store now fails the client's verify path.
- *Result:* closes the integrity seam the paper audit flagged (F1); the demo
  gains a second verifiable hash ("figure attestation"), mirroring VerityGate's
  SHA-256 number binding.

**P1C. Measure Safety-A precision/recall (incl. multilingual) with CIs.**
- *Files:* new `evaluation/redteam_measured.jsonl` (committed attacks + benign
  controls), `vidhi/safety.py` (no change needed), a new `vidhi/redteam.py` or a
  block in `eval.py`.
- *Change:* run `detect_injection` over the committed set; report P/R/F1 + Wilson
  CIs, separately for English / Hindi / Hinglish and for the 6+3 signal classes.
- *Result:* replaces the unmeasured "regex baseline" with a **measured**
  number (e.g., "P=…, R=…, F1=…, n=…" per language), with an explicit false-negative
  caveat — the honesty bar the paper already commits to.

### Priority 2 — medium value, moderate effort

**P2A. Unicode / hidden-text normalization in Safety-A.**
- *Files:* `vidhi/safety.py`.
- *Change:* NFKC-normalize + strip zero-width / invisible codepoints before the
  regex scan, so invisible-font and confusable-homoglyph injections are caught.
  Add cases to the red-team set (P1C).

**P2B. Calibrated confidence gate (replace fixed 0.60 floor).**
- *Files:* `vidhi/claims.py` (`confidence()`), `vidhi/rules.py` (`adjudicate()`),
  a small calibration set `evaluation/paraphrase_calib.jsonl`.
- *Change:* pick the threshold on a calibration set so the correct-field rate is
  ≥ 1−α (conformal-style), rather than hard-coding 0.60. Keep the deterministic
  fallback (never up/down-grade silently).

**P2C. Citation-faithfulness metric.**
- *Files:* `vidhi/eval.py`.
- *Change:* report "attribution faithfulness 1.000" by asserting every `[n]`
  citation resolves to a verified row/excerpt (already enforced; make it a
  named, reported metric).

### Priority 3 — larger / more speculative (post-demo)

**P3A. Constrained decoding for the LLM translator** (`vidhi/claims.py`
`extract_llm`) via outlines/xgrammar JSON-schema mode — a claim can never be
malformed; parse-failure → `WARN_LOW_CONFIDENCE` (never a guess).

**P3B. Claim-type → evidence-type gate** (`vidhi/consistency.py`) — a VerityGate
Gate-4 analog: a "comparative" claim must cite pair-level evidence, a
"definitional" claim a methodology excerpt, etc.

**P3C. R-Tuning-style fine-tuned translator** — train a small model (or distil a
MuRIL student) to extract claims *and* emit "unknown" on unanchored inputs; used
only behind the deterministic judge, never to move a verdict.

### Acceptance gates (new, all offline-reproducible)

1. `python vidhi/eval.py` additionally prints: abstention recall = 1.000,
   hallucination rate = 0.000, attribution faithfulness = 1.000, Safety-A
   P/R/F1 per language with CIs, and the figure-attestation self-check.
2. `python -m pytest tests/ -q` gains: figure-attestation tamper test
   (flip a store value → attestation mismatch), a Unicode-injection test, and a
   calibrated-gate test.
3. Demo: the verdict card shows both the frozen hash **and** the figure
   attestation; a "red-team" tab reports the measured Safety-A numbers.

### Paper implications

- Reframe the contribution as: *"refusal is a rule, not a model behavior"* —
  supported by Reinforced Hesitation (prompts can't enforce abstention) and
  VerityGate (models fail deterministic checks 48–80% of the time).
- Add the **abstention-confusion-matrix** as the headline honesty metric,
  replacing the vague "coverage is the limit" wording with a measured
  deflection rate and a 0.000 hallucination rate on the committed set.
- Keep every new number provenance-marked (measured `M` vs target `T`), per the
  existing discipline — no unmeasured number goes on the poster or in the paper.

---

## Sources (re-verify IDs before citing)

- Wen et al., *Know Your Limits: A Survey of Abstention in LLMs*, TACL 2025 —
  aclanthology.org/2025.tacl-1.26
- *Abstain-QA* + AUCM, COLING 2025 — aclanthology.org/2025.coling-main.627
- *Reinforced Hesitation*, arXiv 2511.11500
- Zhang et al., *R-Tuning* (refusal-aware instruction tuning), 2024
- *FACTS Grounding Leaderboard*, arXiv 2501.03200
- *GaRAGe*, ACL Findings 2025
- *Correctness is not Faithfulness in RAG Attributions*, ICTIR 2025
- *VerityGate*, arXiv 2610.00833
- *ATLAS*, arXiv 2510.25890
- Farquhar et al., *Detecting hallucinations using semantic entropy*, Nature 2024
- *Semantic Entropy Probes (SEPs)*, ICML 2024
- *Learning Conformal Abstention Policies*, arXiv 2502.06884
- *OWASP LLM01:2025 Prompt Injection*
- Wallace et al., *Instruction Hierarchy*, 2024; *GuardRAG*; *InstructDetector*,
  EMNLP Findings 2025
- *JSONSchemaBench*, arXiv 2501.10868; *SEM-CTRL*, arXiv 2503.01804
- *A Survey on Hallucination in LLMs*, ACM TOIS 2025; *From Illusion to Insight*,
  MDPI 2025
