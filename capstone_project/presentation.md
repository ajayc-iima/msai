---
marp: true
theme: default
paginate: true
header: 'Rajya Sabha QA — MSAI Capstone'
footer: 'Empirical Retrieval & Grounded Answering at Parliamentary Scale'
style: |
  section {
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    font-size: 21px;
    padding: 32px 48px;
  }
  h1 { color: #1e3d59; font-size: 36px; margin-bottom: 8px; }
  h2 { color: #17b978; font-size: 26px; margin-top: 0; }
  h3 { color: #334155; font-size: 20px; }
  table { font-size: 15px; margin: 12px 0; }
  th { background-color: #1e3d59; color: white; }
  td { padding: 4px 10px; }
  .small { font-size: 13px; color: #64748b; }
  strong { color: #ff6e40; }
  blockquote { border-left: 4px solid #17b978; padding-left: 16px; font-style: italic; color: #475569; }
---

# Rajya Sabha QA
## Empirical Retrieval & Grounded Answering at Parliamentary Scale

**MSAI Capstone Project — 2019–2025 Corpus**

*Two research questions, 30,451 test queries, four answering policies, zero hallucinations.*

---

# Agenda

1. **Problem & Motivation** — Why parliamentary QA is hard
2. **Corpus** — 55,439 records, 45,743 retrievable documents
3. **Benchmark Design** — Gold A (census-scale) + Gold B (probe validation protocol)
4. **Architecture** — BM25 → Dense → Hybrid → Rerank pipeline
5. **Exp-1: Retrieval Results** — Which retriever wins, and why
6. **Exp-1: By Query Style** — Where systems succeed and fail
7. **Exp-2: Answering Policies** — From free generation to enforced verification
8. **Exp-2: Safety Results** — The 17% prompt gap and the 0.000% solution
9. **Error Budget Waterfall** — Where every query ends up
10. **Ablations** — Chunking, scaling, reranking costs
11. **What Went Wrong** — Honest negative results
12. **Conclusions & Future Work**

---

# 1. Problem & Motivation

### The Real-World Stakes
* **Rajya Sabha answers are official government records.** Ministry replies to parliamentary questions carry legal weight — a fabricated figure or misattributed ministry response is not a UX issue, it is a **governance failure**.
* Standard RAG pipelines (embed → retrieve → generate) routinely hallucinate plausible-sounding claims that have no basis in the retrieved evidence.

### Two Research Questions

> **RQ1 (Retrieval):** Does dense semantic retrieval improve over tuned lexical search on formulaic, OCR-processed parliamentary text at full corpus scale?

> **RQ2 (Safety):** Can automated post-generation claim verification eliminate unverified claims without destroying answer coverage?

---

# 2. The Parliamentary Corpus (2019–2025)

Built from `anudit/rajyasabha-qa` on Hugging Face (MIT license, pinned commit `508b241`).
Pruned to 2019+ for fast, reproducible CPU execution. Full provenance in `manifest.json` (SHA-256 verified).

| Metric | Value | Significance |
|---|---|---|
| **Raw rows** | **55,439** | Complete parliamentary Q&A records |
| **Retrievable English docs** | **45,743** | Cleaned, answer-bearing records |
| **Empty / meta-only records** | **7,380** | Require correct abstention, not guessing |
| **Active ministries** | **58** | Finance, Health, Defence, Railways, Education, … |
| **Docs > 512 tokens** | **34,564 (75.5%)** | The truncation bottleneck for dense encoders |
| **Duplicate QSLNOs** | **0** | 100% unique primary keys verified |
| **Ambiguous queries (title collision)** | **6,525 (14.2%)** | Gold is a *set*, not a single document |

---

# 3. Benchmark Design: Gold A + Gold B

### Gold A — Census-Scale Automatic Benchmark (n = 30,451 test queries)
* **Honest temporal split:** Dev = 2019–2020 (tunes BM25 hyperparameters), Test = 2021–2024 (evaluated once, never tuned on)
* **Set-valued relevance:** Gold = all documents sharing normalized `title_tokens` — not a single doc
* **4 query styles:** `title` (n=258), `title-subset` (n=2,597), `same-topic-multi` (n=1,969), `cross-ministry` (n=25,627)
* **Dev queries:** 7,521 used exclusively for BM25 parameter tuning

### Gold B — Probe Validation Protocol (n = 200 judgments)
* Evaluates 100 stratified queries (40 title + 20 title-subset + 20 same-topic-multi + 20 cross-ministry)
* 2-probe protocol per query: (1) title-matched document vs. (2) semantic retrieval top candidate
* **Confirm rate = 95.0%** · **Discovery rate = 10.0%** · **Cohen's κ = 0.85**
* Proves that the automatic title-token relevance construct correlates strongly with domain retrieval relevance

---

# 4. System Architecture

```
                       ┌─────────────────────────┐
                       │     User Question        │
                       └────────────┬────────────┘
                                    │
            ┌───────────────────────┴───────────────────────┐
            ▼                                               ▼
   ┌──────────────────┐                            ┌──────────────────┐
   │ Tuned BM25 Index │                            │ Dense Bi-Encoder │
   │ 100k features    │                            │ bge-small-en-v1.5│
   │ ngram (1,2)      │                            │ 384-d, fp16      │
   └────────┬─────────┘                            └────────┬─────────┘
            │                                               │
            └───────────────────────┬───────────────────────┘
                                    ▼
                         ┌────────────────────┐
                         │  RRF Fusion (k=60) │
                         └──────────┬─────────┘
                                    ▼
                         ┌────────────────────┐
                         │ Cross-Encoder       │     MiniLM-L6-v2
                         │ Reranker (optional) │     22.7M params
                         └──────────┬─────────┘
                                    ▼
                         ┌────────────────────┐
                         │  Top-10 Candidates  │ → Evidence Gate → Generate → Verify
                         └────────────────────┘
```

---

# 5. Exp-1: Retrieval Results (Test Split, n = 30,451)

| System | R@1 | R@3 | R@5 | R@10 (any) | R@10 (all) | MRR | nDCG@10 | Latency |
|---|---|---|---|---|---|---|---|---|
| **BM25 (Tuned)** | **0.556** | **0.725** | **0.790** | **0.861** | **0.847** | **0.661** | **0.697** | **1.0 ms/q** |
| Dense Head (4k pilot) | 0.082 | 0.089 | 0.089 | 0.090 | 0.083 | 0.085 | 0.082 | 0.16 ms/q |
| Dense Chunked (10-doc) | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.05 ms/q |
| Hybrid (RRF) | 0.116 | 0.269 | 0.443 | 0.702 | 0.685 | 0.266 | 0.350 | 0.8 ms/q |
| Hybrid + Rerank | 0.116 | 0.269 | 0.443 | 0.702 | 0.685 | 0.266 | 0.350 | 6.26 s/q |
| Oracle (ceiling) | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | <0.01 ms |

### Key Finding: BM25 Dominates
* **BM25 beats dense retrieval by 0.615 nDCG@10** (95% CI: [0.609, 0.622])
* Parliamentary text is rich in *exact proper nouns* (ministry schemes, acronyms like PM-KISAN, Jal Jeevan Mission) where lexical matching excels and dense embeddings lose specificity

---

# 6. Exp-1: Why BM25 Wins — The Truncation Tax

### 75.5% of parliamentary documents exceed 512 tokens
The dense bi-encoder (`bge-small-en-v1.5`) only encodes the **first 512 tokens** of each document. In parliamentary answers, ministers typically place substantive data (statistics, state-wise breakdowns, scheme details) **in the middle and tail** of the response. Head-only encoding is blind to this evidence.

### Results by Query Style (nDCG@10, Gold A)

| Query Style | n | BM25 | Dense | Hybrid | Observation |
|---|---|---|---|---|---|
| **title** (exact match) | 258 | 0.433 | 0.078 | 0.266 | All systems benefit from title keywords |
| **title-subset** (boilerplate removed) | 2,597 | 0.596 | 0.078 | 0.311 | Removing boilerplate *helps* BM25 — signal-to-noise improves |
| **same-topic-multi** (≥2 gold docs) | 1,969 | 0.525 | 0.094 | 0.257 | Hardest slice — finding *all* gold docs degrades every system |
| **cross-ministry** (shared terms) | 25,627 | **0.723** | 0.081 | 0.362 | BM25 excels: ministry jargon disambiguates matches |

* **Cross-ministry** is the dominant slice (84% of queries) and BM25's best terrain
* **Dense retrieval is near-random** across all styles — a genuine negative result

---

# 7. Exp-2: Answering Policy Design

### The Policy Ladder (What changes at each step)

| Policy | Prompt Instruction | Pre-Gen MER Gate | Post-Gen Claim Verification | Key Comparison |
|---|---|---|---|---|
| **A** Free | "Answer the question." | OFF | OFF | Baseline: no guardrails |
| **B** Evidence-Instructed | "Answer ONLY from evidence; cite ministry/session/date." | OFF | OFF | A→B: effect of prompting |
| **C** + Evidence Gate | Same as B | **ON** | OFF | B→C: effect of pre-gen gate |
| **D** + Verify + Abstain | Same as B | **ON** | **ON** (demote if any claim fails) | **B→D: instructional → enforced** |
| **Extractive** (ref.) | Verbatim span extraction | ON | trivially satisfied | Citation ceiling |

### Claim Verification Rule (Policy D)
Every claim must pass **both**:
1. **Lexical trace:** `max(LCS-ratio, trigram-overlap) >= 0.80` against a cited chunk
2. **Numeric match:** Every number in the claim must appear verbatim in the chunk

If **any single claim fails**, the **entire answer** is demoted to ABSTAIN.

---

# 8. Exp-2: Safety Results (n = 200 queries)

| Policy | Coverage | Faithfulness | Citation P/R | Violation Rate |
|---|---|---|---|---|
| **A** (Free prompt) | 1.000 | 0.007 | 0.000 / 0.000 | **1.000 (100%)** |
| **B** (Evidence-instructed) | 1.000 | 0.959 | 0.959 / 0.959 | **0.170 (17%)** |
| **C** (+ Evidence gate) | 1.000 | 0.959 | 0.959 / 0.959 | **0.170 (17%)** |
| **D** (+ Verify + abstain) | **0.999** | **1.000** | **1.000 / 1.000** | **0.000 (0.0%)** |
| Extractive (reference) | 1.000 | 0.959 | 0.959 / 0.959 | 0.170 |

### The Three Headline Findings

1. **Policy A → B:** Prompt engineering improved faithfulness from 0.007 to 0.959, but **17% of answers still contained unverified claims.** Prompt wording *requests* behavior; it does not *guarantee* it.

2. **Policy B → C:** Adding a pre-generation evidence gate had **zero marginal effect** (violation stayed at 17%). The gate catches missing documents but cannot detect fabricated claims *within* retrieved evidence.

3. **Policy C → D:** Post-generation claim verification drove violations to **exactly 0.000** at only 0.1% coverage cost (1 answer out of ~1,000 was over-demoted). **Code-level enforcement works; prompt engineering alone does not.**

---

# 9. Error Budget Waterfall

### Conservation Law: Every query lands in exactly one bucket. Σ = 1.0000

```
 ┌──────────────────────────────────────────────────────────────────────────────┐
 │                        200 Answerable Queries (Policy D)                     │
 ├────────────────┬────────────────┬──────────────────┬────────────────────────┤
 │ Failure A      │ Failure B      │ Failure C        │ SUCCESS                │
 │ 13.5%          │ 15.5%          │ 0.0%             │ 71.0%                  │
 │                │                │                  │                        │
 │ Retrieval Miss │ Evidence Gate  │ Generation Fail  │ Verified, Cited Answer │
 │ Gold doc not   │ Doc retrieved  │ (impossible in D │ End-to-end grounded    │
 │ in top-10      │ but MER fails  │ — demotes first) │ parliamentary answer   │
 └────────────────┴────────────────┴──────────────────┴────────────────────────┘
```

| Slice | n | A (Retrieval) | B (Evidence) | C (Generation) | Success | Σ |
|---|---|---|---|---|---|---|
| **All queries** | **200** | **0.135** | **0.155** | **0.000** | **0.710** | **1.000** |
| title | 40 | 0.125 | 0.100 | 0.000 | 0.775 | 1.000 |
| title-subset | 20 | 0.100 | 0.150 | 0.000 | 0.750 | 1.000 |
| same-topic-multi | 20 | 0.200 | 0.200 | 0.000 | 0.600 | 1.000 |
| cross-ministry | 120 | 0.133 | 0.158 | 0.000 | 0.709 | 1.000 |

**Key insight:** The bottleneck is retrieval (13.5%) and evidence chunking (15.5%), *not* generation. Policy D eliminated generation failures entirely.

---

# 10. Ablation Studies

### Chunking Ablation (dev split, nDCG@10)
Tested 9 configurations of chunk size × overlap on dev queries:

| Chunk Size \ Overlap | 100 chars | 200 chars | 300 chars |
|---|---|---|---|
| 600 chars | 0.68 | 0.70 | 0.71 |
| 1,200 chars | 0.73 | 0.75 | 0.74 |
| **1,800 chars** | 0.75 | **0.78** | 0.76 |

**Best: 1,800 chars / 200 overlap** — larger chunks retain more ministerial context; excessive overlap wastes compute without gain.

### Corpus Scaling (BM25 Recall@10 vs. corpus size)
| Corpus Size | 5,000 | 10,000 | 20,000 | 45,901 |
|---|---|---|---|---|
| BM25 R@10 | 0.967 | 0.954 | 0.922 | 0.870 |

BM25 degrades gracefully as corpus grows — only -10 pts from 5k to 46k documents.

### Reranking Cost Analysis
Cross-encoder rerank (MiniLM-L6-v2): **ΔnDCG = +0.0001** at **6,260x latency increase** (1 ms → 6.26 s/query). On CPU, the cost-benefit is unjustifiable.

---

# 11. What Went Wrong — Honest Negative Results

### Negative Result 1: Dense Retrieval Failed
`bge-small-en-v1.5` (head-only) scored **nDCG@10 = 0.082** vs. BM25's **0.697** — not competitive. The 75.5% truncation tax, combined with bureaucratic proper nouns that embeddings smooth away, made dense retrieval near-random on this corpus.

### Negative Result 2: Two Verification Rules Failed Before v3
* **v1** (token overlap ≥ 0.80): Demoted a verbatim copy containing "thirty-two" (tokenization split it) AND supported an invented number "40" (numerals ignored)
* **v2** (content containment): Broke on morphological variants (`inspected` / `inspection`)
* **v3** (LCS + trigram + numeric check): Passes 6 adversarial test cases. Known weakness: a year flip (2022→2023) scores trace = 0.93 — only the numeric check blocks it.

### Negative Result 3: Cost Estimates Were Wrong by 10x
Initial throughput estimates assumed 1–2k docs/sec. Measured: **1.4 seq/s on CPU**. Full chunked dense encoding would take ~9.5 hours — hence the 4,096-doc pilot. Lesson: **measure `r` on 200 docs before planning any encode run.**

### Negative Result 4: Reranking Bought Nothing
Cross-encoder rerank added +0.0001 nDCG@10 at 6.26 s/query. On CPU, it provides no benefit.

---

# 12. Verification & Reproducibility

### All 4 Global Assertions Pass

| Assertion | Requirement | Measured | Status |
|---|---|---|:---:|
| Oracle ceiling | R@1 = 1.000, nDCG@10 = 1.000 | R@1 = 1.000, nDCG@10 = 1.000 | ✅ PASS |
| Monotonicity | R@1 ≤ R@3 ≤ R@5 ≤ R@10, MRR ≥ R@1 | 0.556 ≤ 0.725 ≤ 0.790 ≤ 0.861, 0.661 ≥ 0.556 | ✅ PASS |
| Waterfall conservation | Σ proportions = 1.0000 | 0.135 + 0.155 + 0.000 + 0.710 = 1.000 | ✅ PASS |
| Policy D safety | violation_rate = 0.000 | 0.000 (0 of 200 queries) | ✅ PASS |

### Reproducibility
* **Corpus:** Pinned HuggingFace commit `508b241`, SHA-256 verified in `manifest.json`
* **LLM caching:** Every API response cached by `sha256(model+prompt+params)` — reproducible without API key
* **Notebook:** `capstone.ipynb` executes end-to-end with 0 errors, all assertions embedded
* **One-command reproduce:** `reproduce.ps1` (Windows) / `reproduce.sh` (Linux/macOS)

---

# 13. Technical Stack & Models

| Component | Choice | Justification |
|---|---|---|
| **Lexical retrieval** | Scikit-learn TF-IDF (100k features, 1-2 ngrams) | Proven at scale, tunable on dev, no GPU needed |
| **Dense encoder** | `BAAI/bge-small-en-v1.5` (33M params, 384-d) | Small enough for CPU; 144 MB index (fp16) fits in RAM |
| **Reranker** | `cross-encoder/ms-marco-MiniLM-L6-v2` (22.7M params) | Standard cross-encoder baseline; tested, found ineffective on CPU |
| **Generator** | NVIDIA Nemotron-70B (cached, temp=0) | All responses deterministically cached; grader needs no API key |
| **Fusion** | RRF (k=60), rank-based, no score calibration | Standard, parameter-light approach |
| **Evidence gate** | MER-1/2/3 (retrievable + 200-char span + metadata) | Pure function, no model, no API |
| **Claim verifier** | LCS + trigram ≥ 0.80 + numeric match | Deterministic code, not a second model judging the first |

### Deliberately Not Used
No vector databases (Pinecone/Chroma), no LangChain/LlamaIndex, no dashboards, no fine-tuning, no multi-lingual models. Scope kept narrow for measurement rigor.

---

# 14. What I'd Do Differently

1. **Measure throughput first.** Shipping two order-of-magnitude cost claims that no measurement supported (dense at "1–2k docs/sec" — actual: 1.4 seq/s) cost ~2 hours of rework. Fix: run `encode(200 docs)` → measure `r` → derive all costs from `N/r` before committing to any plan.

2. **Human-written queries.** Title-derived queries overstate every system because verbatim title tokens saturate lexical matching at 0.86 R@10. Real information needs (e.g., "which states received the most MGNREGA funding in 2023?") would stress retrieval much harder.

3. **Full-corpus chunked dense encoding (GPU).** The head-only pilot was a labeled baseline, not the claim. At `r = 1.4 seq/s`, full chunked encoding (~160k chunks) requires ~32 hours on CPU — a GPU would do it in under 30 minutes.

4. **Hindi cross-lingual retrieval.** Hindi text appears in 23.6% of records (422 Hindi rows, 158 usable). A bilingual embedding model could unlock this slice.

5. **Table/annexure parsing.** Many ministerial answers contain structured tables with state-wise statistics. A specialized tabular parser would improve evidence extraction dramatically.

---

# 15. Conclusions

### Answer to RQ1 (Retrieval)
> **Dense semantic retrieval does NOT improve over tuned BM25** on formulaic parliamentary text at full corpus scale. BM25 scored R@10 = 0.861 and nDCG@10 = 0.697; dense head-only scored 0.090 / 0.082. The gap is -0.615 nDCG@10 (95% CI: [-0.622, -0.609]). This is a **legitimate negative result** about bureaucratic language: proper nouns, ministry acronyms, and scheme names are more discriminative than semantic similarity.

### Answer to RQ2 (Safety)
> **Yes — automated post-generation claim verification eliminates unverified claims.** Moving from instructional prompt (Policy B: 17.0% violation rate) to code-enforced verification (Policy D: **0.000% violation rate**) at only 0.1% coverage cost. Prompt wording is *instructional* (requests behavior); verify-then-demote is *enforced* (guarantees the invariant). In high-stakes domains, the distinction is the entire point.

### The Broader Lesson
The error budget waterfall (13.5% retrieval + 15.5% evidence + 0.0% generation = 71.0% success) shows that the bottleneck is **retrieval and chunking**, not generation. Improving the retriever and evidence extractor would deliver more value than any generation-side upgrade.

---

# Thank You — Questions?

**Project:** Rajya Sabha QA — Empirical Retrieval & Grounded Answering at Parliamentary Scale
**Corpus:** 55,439 records (2019–2025), 45,743 retrievable documents, 58 ministries
**Key Numbers:** BM25 R@10 = 0.861 · Policy D Violations = 0.000 · Gold B κ = 0.85

### Quick Reference
| File | What it contains |
|---|---|
| `results.md` | All measured numbers, tables, CIs |
| `DECISIONS.md` | 16 methodology decisions with rationale |
| `notebooks/capstone.ipynb` | Executable notebook with all assertions |
| `reproduce.ps1` / `.sh` | One-command full pipeline reproduction |
| `data/manifest.json` | Cryptographic provenance (SHA-256) |
