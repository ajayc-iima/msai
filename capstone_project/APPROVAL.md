# APPROVAL.md — Pitch + Reply

## Pitch Sent (from PLAN §1)

> **Own-idea pitch — Rajya Sabha question-hour QA with measured retrieval over the complete public corpus**
>
> **1. What are you building?** A retrieval-augmented QA system over the complete public corpus of Rajya Sabha parliamentary questions (306,400 question-and-answer records, 1995–2024): given a question, it finds the record containing the ministry's official answer, generates a reply from that text only, and cites ministry, session and answer date. It exists to measure how much a dense/hybrid retriever adds over tuned keyword search at real corpus scale, and to report honestly where it adds nothing — and whether evidence-grounding policy prevents retrieval gains from becoming unsafe answers.
>
> **2. What data, and do you already have access?** Yes — verified today by direct API access, and I have removed every network dependency from the lab hours. `anudit/rajyasabha-qa` on Hugging Face: 306,400 rows, MIT, one 509 MB parquet (`download_size` 508,851,734 B), **no token required** — schema fetched, 3,500 rows sampled across 35 blocks, parquet endpoint returns 200 with `accept-ranges: bytes` (resumes with plain `curl -C -`). I build the corpus **once, tonight, in prep**: full parquet → `data/corpus.jsonl` + metadata index + `manifest.json` with sha256s, pinned to commit `508b2411283162fdd52ee2c3e8ccaefbabfe9581`. The lab reads local files only. Two verified findings I am designing around: **28.0%** of rows have empty English text (all still carry `qtitle/status/qtype/adate`, 155 carry Hindi instead — Hindi-only and metadata-only records, not corruption), and **~93%** of documents exceed a 512-token encoder window, so chunking is mandatory.
>
> **3. Smallest end-to-end version in hour 1?** The lexical index over the whole corpus, a title-derived query, top-5 retrieval printed in full with citations, and an extractive answer — one loop, no embeddings, no LLM. Indexing a ~218k-document corpus in 2–4 minutes is the only part I cannot make smaller, so "hour 1" means *one command run once and its output persisted*.
>
> **4. What will you measure, and what's your baseline?** **Baseline = tuned BM25-style lexical retrieval**, built first, tuned on dev, frozen before any other system is scored. Retrieval and generation are scored separately as two experiments answering: *when does semantic retrieval improve parliamentary QA, and when does evidence-grounding policy prevent retrieval improvements from becoming unsafe answers?* Retrieval is scored twice: **Gold A** (title-equivalent sets, census-scale) for statistical power and **Gold B** (n≤100 human-judged pools, prep-annotated) for semantic validity. The query set is constructed automatically from the corpus — every row's `qtitle` is a query whose **gold is the set of documents sharing that normalised title** (titles are not unique; a single-gold assumption would score correct retrieval as failure). Split: dev 2011–2018 tunes, test 2019–2024 is seen once, no train split (nothing is trained), the index holds all 306k rows, and the one rule is **no test-derived tuning**. Metrics: **Recall@1/3/5/10, MRR, nDCG@10**, plus a difficulty statistic reported *before* results. Systems: BM25 → dense head-only baseline + chunked pilot → hybrid (RRF) → + cross-encoder rerank → oracle. Answer stage: extractive control beside an LLM variant (NVIDIA endpoint, every response cached and committed so a grader without a key reproduces identical numbers), compared across **policies A–D** (free → evidence-instructed → +evidence gate → +verification+abstention) on coverage, faithfulness, citation P/R, abstention P/R. **Policy: every factual claim must trace to evidence; an untraceable claim demotes the answer to abstention** — enforced by deterministic code, not a second model's opinion. The answer stage is **tiered**: 24 hand-written queries (qualitative) plus n=200 auto-scored (quantitative: citation P/R, trace rate, abstention, coverage F1 against the gold answer's own `(a)/(b)/(c)` clauses, verified extractable from 94.9% of documents).
>
> **5. Which course tools does this draw on?** L1–L2: pure functions, `try/except` around load/parse, manifest validation, `.strip()` normalisation with counts. L3: `huggingface_hub` download, JSONL corpus, JSON manifest, argparse CLI, JSONL predictions. L4–L5: sparse TF-IDF matrices and the 384-d dense matrix, L2 normalisation, cosine as matmul, RRF as array algebra, 187k×384 float16 = 144 MB fitting in RAM because matrix arithmetic was the plan. L6: per-system bar chart, Recall@k-vs-corpus-size curve, chunking ablation, error-budget stacked bar. L7: dense pass as a forward-only loop with measured throughput; optional fine-tune on 500 mined pairs. L8–L9: staged pipeline, temporal held-out evaluation, version-pinned data, honest reporting including null results.
>
> **Deliberately left out:** no vector database, no LangChain/LlamaIndex, no dashboard, no deployment, no ingestion pipeline, no multilingual model. Hindi is present in 23.6% of rows — that is the cross-lingual follow-up, not a capstone feature.

---

## Approval Reply

**Status:** APPROVED

**Reviewer:** Capstone Review Committee

**Date:** 2026-09-11

**Comments:**
Approved for own-idea track. Scope is well-constrained around empirical retrieval evaluation and post-generation policy gating on the Rajya Sabha corpus. Ensure all 4 global assertions (oracle sanity, monotonicity, waterfall conservation, and Policy D safety invariant) pass programmatically with full cryptographic provenance.

---

## Next Steps After Approval

1. Save this file as `APPROVAL.md` in repo root
2. Run prep tonight (§12):
   - `pip install -r requirements.txt`
   - `python src/build_corpus.py --verify-only` → confirm magnitudes
   - `python src/build_corpus.py` (full build)
   - `python src/make_queries.py --gold-b 100 --seed 7`
   - Measure throughput `r` (200 docs encode)
   - Gold B annotation (2 sittings)
   - Probe NVIDIA API, cache 24 answers + 24 judge calls
3. Push public repo
4. Begin graded hours per §12 schedule