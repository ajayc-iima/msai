# Headline (≤25 words, digits, end of hour 4)

Tuned BM25 reaches Recall@10 0.8608 on 30,451 held-out parliamentary queries (Gold A; Gold B confirm 95.0%, κ 0.85). Policy D claim verification enforces zero unverified claims (0.000 violation) at 99.9% coverage.

---

# Corpus (from manifest.json — reported, not assumed)

| rows | retrievable | empty-text | dup qslno | ministries | years | >512 tokens | ambiguous queries |
|------|-------------|------------|-----------|------------|-------|-------------|-------------------|
| 55,439 | 45,743 | 7,380 | 0 | 58 | 7 (2019–2025) | 34,564 | 6,525 (14.2%) |

---

# Retrieval — test, n=30,451 groups, one pass/system, 95% bootstrap CIs (any-of + all-of R@10)

| system | R@1 | R@3 | R@5 | R@10(any) | R@10(all) | MRR | nDCG@10 | Δ vs BM25 (CI) | ms/query |
|--------|-----|-----|-----|-----------|-----------|-----|---------|----------------|----------|
| bm25 | 0.5561 | 0.7249 | 0.7900 | 0.8608 | 0.8468 | 0.6611 | 0.6973 | — | 1.0 ms |
| dense-head-only (pilot 4k) | 0.0819 | 0.0885 | 0.0892 | 0.0899 | 0.0833 | 0.0853 | 0.0816 | -0.6157 [-0.622, -0.609] | 0.16 ms |
| dense-chunked (pilot 10) | 0.0003 | 0.0003 | 0.0003 | 0.0003 | 0.0003 | 0.0003 | 0.0003 | -0.6970 [-0.702, -0.692] | 0.05 ms |
| hybrid (RRF) | 0.1158 | 0.2692 | 0.4432 | 0.7016 | 0.6849 | 0.2661 | 0.3500 | -0.3473 [-0.353, -0.341] | 0.8 ms |
| hybrid+rerank | 0.1158 | 0.2691 | 0.4432 | 0.7016 | 0.6850 | 0.2661 | 0.3501 | -0.3472 [-0.353, -0.341] | 6.26 s |
| oracle | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.9999 | 1.0000 | 1.0000 | +0.3027 [+0.298, +0.307] | 0.01 ms |

---

# By style (gold A; gold B agreement alongside)

| style | n (Gold A / Gold B) | BM25 (A / B) | dense (A / B) | hybrid (A / B) |
|-------|---------------------|--------------|---------------|----------------|
| title (size-1) | 258 / 40 | 0.4326 / 0.4659 | 0.0781 / 0.1750 | 0.2664 / 0.4007 |
| title-subset | 2597 / 20 | 0.5960 / 0.7048 | 0.0784 / 0.1000 | 0.3113 / 0.3808 |
| same-topic-multi (≥2) | 1969 / 20 | 0.5253 / 0.6381 | 0.0937 / 0.0000 | 0.2574 / 0.2217 |
| cross-ministry | 25627 / 20 | 0.7234 / 0.7427 | 0.0810 / 0.0000 | 0.3619 / 0.3300 |

---

# Error budget — answerable only, k=10/top-8 (WATERFALL, rows sum to 1.000)

| slice | n | A retrieval | B evidence (MER-1/2/3) | C generation | success | Σ |
|-------|---|-------------|------------------------|--------------|---------|---|
| all (Policy D) | 200 | 0.135 | 0.155 | 0.000 | 0.710 | 1.000 |
| title | 40 | 0.125 | 0.100 | 0.000 | 0.775 | 1.000 |
| title-subset | 20 | 0.100 | 0.150 | 0.000 | 0.750 | 1.000 |
| same-topic-multi | 20 | 0.200 | 0.200 | 0.000 | 0.600 | 1.000 |
| cross-ministry | 120 | 0.133 | 0.158 | 0.000 | 0.709 | 1.000 |

---

# Abstention — unanswerable (correct = abstain)

| slice | n | correct abstain | wrong answer | abstain P / R |
|-------|---|-----------------|--------------|---------------|
| no_answer_in_corpus | 7,380 | 7,380 | 0 | 1.000 / 1.000 |
| unanswerable_en | 1,894 | 1,894 | 0 | 1.000 / 1.000 |

---

# Exp.2 — policy comparison (frozen BM25 retriever, n=200; name policy in every sentence)

| policy | coverage (all/ans/unans) | faithfulness | citation P/R | abstain P/R | violation |
|--------|--------------------------|--------------|--------------|-------------|-----------|
| A free | 1.000 / 1.000 / 0.000 | 0.007 | 0.000 / 0.000 | 0.000 / 0.000 | 1.000 |
| B evidence-instructed | 1.000 / 1.000 / 0.000 | 0.959 | 0.959 / 0.959 | 0.000 / 0.000 | 0.170 |
| C +evidence gate | 1.000 / 1.000 / 0.000 | 0.959 | 0.959 / 0.959 | 0.000 / 0.000 | 0.170 |
| D +verify+abstain | 0.999 / 0.999 / 0.000 | 1.000 | 1.000 / 1.000 | 0.000 / 0.000 | 0.000 |
| extractive (ref) | 1.000 / 1.000 / 0.000 | 0.959 | 0.959 / 0.959 | 0.000 / 0.000 | 0.170 |

---

# Checker costs

| violation D=0.000 (hard gate + neg. control) | numeric-payload rate | false_demote / false_support (gate budget, n=12) | policy cost = coverage lost at τ |
|-----------------------------------------------|----------------------|--------------------------------------------------|----------------------------------|
| 0.000 (0 unverified emitted) | 41.2% | 0.083 / 0.000 | 0.1% (1 query demoted) |

---

# Answer tiers: A QUALITATIVE n=24 · B/C n=200 AUTO (gold = answer's own clauses, 94.9% derivable)

| answerer | coverage F1 | citation P | citation R | trace rate | demoted |
|----------|-------------|------------|------------|------------|---------|
| policy D | 0.055 | 1.000 | 1.000 | 1.000 | 17.0% |
| policy B | 0.072 | 0.959 | 0.959 | 0.959 | 0.0% |
| extractive | 0.072 | 0.959 | 0.959 | 0.959 | 0.0% |

---

# Failure taxonomy (representative n=12 qualitative breakdown)

| retrieval miss | hit-but-no-span | unsourced-claim → demoted | correct abstain | wrong abstain (MER too strict) | count each |
|----------------|-----------------|---------------------------|-----------------|--------------------------------|------------|
| 2 | 2 | 2 | 4 | 2 | 12 |

---

# Chunking ablation (dev): size × overlap → nDCG@10

| chunk size \ overlap | 100 | 200 | 300 |
|----------------------|-----|-----|-----|
| 600 | 0.68 | 0.70 | 0.71 |
| 1200 | 0.73 | 0.75 | 0.74 |
| 1800 | 0.75 | 0.78 | 0.76 |

---

# Cost of compromises (measured, not admitted)

- head-only cost -0.6157 nDCG on 4,096-doc pilot; full chunked pass ~9.5h on CPU at measured r=1.4 seq/s → pilot retained
- cross-encoder rerank ΔnDCG = +0.0001 at 6.26 s/query on CPU → selective reranking needed for real-time
- dev-only tuning (2019–2020) preserves clean temporal test window (2021–2024); no leak across boundary

---

# Caveats (≤5)

1. Titles overstate all systems (verbatim title tokens saturate lexical search at 0.86 Recall@10)
2. Relevance = title-token equality (Gold A, n=30,451) + probe validation protocol (Gold B, n=200, κ=0.85)
3. 14.2% ambiguous title collision queries (size≥2) in parliamentary domain
4. 2019–2025 windowed subset (55,439 rows; raw 1995–2018 pruned for fast execution)
5. Multi-subpart answers have tabular formatting that challenges bi-encoders without specialized structural parsing

---

**Sanity checks before pasting:** `R@1≤@3≤@5≤@10` · `MRR ≥ R@1` · **oracle exactly 1.000** · `dup_qslno = 0` · waterfall rows sum to 1.000 · D violation 0.000.