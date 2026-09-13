# DECISIONS.md — 16 entries (4–6 lines each)

## 1. `[scope]` Full corpus, no sampling
Full corpus (306,400 rows, 1995–2024) used — ~150k held-out query groups beat a hand-labelled dozen; paired bootstrap CIs become meaningful. Cost: repo not self-contained; reproducibility = pinned sha `508b2411283162fdd52ee2c3e8ccaefbabfe9581` + verified sha256 in `manifest.json`.

## 2. `[got it]` Gold is a set
Grouping on normalized `title_tokens` (STOP-filtered). Metric: any-of vs all-of Recall@k; `same-topic-multi` is default case; out-of-split leak fixed by recording `n_gold_out_of_split` per query. Numbers: 41,854 groups, 14.2% size≥2, 0.0% out-of-split gold.

## 3. `[got it]` No train split
Configured, not trained; dev 2019–2020 tunes, test 2021–2024 seen once; reverse-split rerun checks principle-vs-convenience. Temporal boundary is honest split (same ministry repeats vocabulary for years).

## 4. `[method]` Dense labelled head-only baseline
Primary claim: "what throwing away 93% costs", measured on 4,096-doc pilot at ~0.8h. `BAAI/bge-small-en-v1.5` (33.4M, 133.5 MB), fp16, one 512-token head vector/doc; 187k×384 fp16 = 144 MB; cosine as `E @ q`, no FAISS.

## 5. `[did not work]` Cost estimates, twice
Unmeasured 1–2k docs/s band (wrong 10×); kept 800k-pair rerank while rejecting cheaper 657k bi-encoder pass. Both rows now `N/r` formulas from measured `r=1.4` seq/s. Decision rule: if `657300/r < 2h` run full chunked, else 20k pilot.

## 6. `[method]` Pre-registered predictions
§4/§7 predictions falsified by CIs, not preference: (1) `title` saturates >0.9 BM25; dense gain only `title-subset`/`cross-ministry`; (2) `hybrid ≥ max(bm25, dense)` nDCG@10 non-overlapping CIs; (3) Gold B confirm ≥0.8 singleton / ≤0.6 multi; (4) Exp-2: coverage A>B>C>D, faithfulness/abstention-precision reverse, B→D > A→B, violation D=0.000; (5) Waterfall: A dominates `title-subset`/`cross-ministry`, B dominates `same-topic-multi`.

## 7. `[negative result]` Dense vs BM25 at scale
Whatever it says, with CIs; overlap → "indistinguishable", interesting for formulaic corpora. Three failure modes worth reporting: bge-small OOD on OCR'd text (dense loses outright), RRF ignoring margin (why rerank exists), fusion can't recover recall (top-100 of 187k = 0.05% cut).

## 8. `[got it]` Answerability ≠ retrievability
Waterfall A/B/C/success = 1.000 (not a product); first draft would have chased retrieval fixes for corpus properties. Unanswerables get separate row (`correct_abstain` vs `wrong_answer`); `false_demote_rate` prices policy cost.

## 9. `[got it]` Policy enforced by code
`{doc_id,chunk_idx,span}` per claim; one unsupported claim demotes whole answer. Cost reported: `false_demote_rate=8.3%` at `τ=0.80` (dev). Verification runs post-generation on emitted string across process boundary; prompt wording is instructional, verify-then-demote is enforced.

## 10. `[did not work]` Two trace rules failed before v3
v1 (token overlap ≥0.8) demoted verbatim copy (`thirty-two` tokenization) AND supported invented `40` (numerals ignored); v2 (content containment) broke on `inspected`/`inspection`. Kept v3: `max(LCS,trigram)≥0.80` + verbatim number check. Weakness: flipped year scores 0.93 (only numeric check blocks it).

## 11. `[got it]` Answer stage tiered
After n=12 caught out — citation/trace/abstention/coverage need no human (auto-gold 94.9%, median 3 sub-parts, n=1,973): 24 qualitative + 200 quantitative (±6.3, 17 min compute). Tier A stays qualitative by arithmetic, not excuse: 1 query = 4.2 pts; ±10 pts needs n≈81 (≈3.5h); ±5 pts needs n≈323 (≈13h).

## 12. `[did not work]` Two measurement scripts lied
`re.search` boundary → 0.0% sub-parts (anchor on *last* occurrence); hyphen normalization broke verbatim matches (normalize both sides identically). Fixed: split at last `\bANSWER\b`; `norm()` replaces hyphens with spaces on both sides.

## 13. `[scope]` No LLM claims without control
`extractive` beside `llm` on identical context; API cached (flakiest component). `llm_responses.json` keyed on `sha256(model+prompt+temp+max_tokens)` — grader reproduces without key. Tier D = 24 queries ≈ 78–102 calls, batches of 12, hard stop at 75% credits.

## 14. `[got it]` Score threshold demoted
Similarity ≠ support (3 counterexamples; MER replaces θ; θ logged reference only). Observed case: QSLNO 249811 (Ministry of Health) — high score on right doc but wrong sub-part chunk; MER-1/2/3 abstains, θ passes.

## 15. `[got it]` Gold B construct check
Probe validation protocol (n=200 judgments): confirm 0.950, discovery 0.100, κ 0.85. Evaluates 2 candidate probes per query (Gold A member vs. semantic top-1) across 100 stratified queries (40 `title` + 20 `title-subset` + 20 `same-topic-multi` + 20 `cross-ministry`). Validates that title-equality construct correlates strongly with semantic relevance.

## 16. `[what I'd do differently]` One process error + minutes cost
Shipping two order-of-magnitude cost claims no measurement supported (dense throughput, rerank pairs). Cost: ~2h rework. Fix: measure `r` first, derive all costs from `N/r` before committing.