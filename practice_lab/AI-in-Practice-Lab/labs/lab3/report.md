# Lab 3 report — Semantic Search

*n = 42 (excluded Q36, Q38, Q39 — no relevant document; recall/nDCG undefined).
Say this explicitly in §0. Five questions of kind `unanswerable` are Lab 4;
two of those still have relevant_docs and belong here.*

## 0. Baseline (sliding-800 dense) — write before you change anything

| metric | value |
|---|---|
| nDCG@10 | |
| recall@5 | |
| hit_rate@1 | |
| mrr | |
| chunks | |
| latency p95 ms | |

## 1. Part A — chunking

### A1 @ size=800

| strategy | nDCG@10 | recall@5 | hit_rate@1 | mrr | chunks | build s |
|---|---|---|---|---|---|---|
| fixed | | | | | | |
| sliding | | | | | | |
| recursive | | | | | | |
| markdown | | | | | | |

### A2 size curve (winner strategy)

| size | nDCG@10 | recall@5 | hit_rate@1 | chunks |
|---|---|---|---|---|
| 400 | | | | |
| 800 | | | | |
| 1600 | | | | |

Shape and why (dilution vs incomplete rules):

### A3 heading-path prefix on/off

| variant | nDCG@10 | hit_rate@1 | hit_rate@5 |
|---|---|---|---|
| prefix | | | |
| no prefix | | | |

Delta and interpretation:

### A4 chunking failure case

- Question id / kind:
- Relevant docs / gold snippet:
- Chunk that should have matched:
- Chunks that did:
- Diagnosis:

## 2. Part B — dense / BM25 / hybrid

### B1 overall (best chunking)

| config | nDCG@10 | recall@5 | hit_rate@1 | mrr | hit_rate@5 (saturated) |
|---|---|---|---|---|---|
| dense | | | | | |
| bm25 | | | | | |
| hybrid | | | | | |

### B2 by kind — **MRR**, not hit_rate@5

| kind | dense | bm25 | hybrid | n |
|---|---|---|---|---|
| | | | | |

Q44 (identifier) MRR: dense / bm25 / hybrid —

Q41 (paraphrase) MRR: dense / bm25 / hybrid —

Mechanism (two sentences):

### B3 RRF k

| k | nDCG@10 |
|---|---|
| 10 | |
| 30 | |
| 60 | |
| 100 | |

### B4 weights

| weights | nDCG@10 |
|---|---|
| 1:1 | |
| dense×2 | |
| bm25×2 | |

Exceeds noise at n=42? Y/N — why:

### B5 dense vs hybrid (report whichever way it lands)

nDCG@10: dense= hybrid= → hybrid is better / worse / tied.

Questions where dense beat BM25 among those they differ: / 

## 3. Part C — reranking

### C3 decision table

| Config | nDCG@5 | hit_rate@1 | p95 ms | $/1k queries |
|---|---|---|---|---|
| no-rerank | | | | $0 |
| cross-encoder | | | | $0 (local) |
| llm | | | | |

**(a) Interactive agent-facing search box →** config:  because:

**(b) Overnight batch job →** config:  because:

### C4 where reranking made things worse

- Question id:
- MRR before → after:
- Was the relevant doc in the k=30 pool? Y/N
- Diagnosis (failure mode 5):

## 4. Part D — index and metadata

### D1 exact vs HNSW (quality gap)

| config | nDCG@10 | recall@5 | p95 ms |
|---|---|---|---|
| exact | | | |
| hnsw | | | |

### D2 scale timings

| n chunks | exact p50/p95 ms | hnsw p50/p95 ms | hnsw/exact |
|---|---|---|---|
| ~160 | | | |
| ~4k | | | |
| ~40k | | | |

Crossover:  Mechanism:

### D3 metadata filter (Q29/Q30/Q31, hit_rate@1)

| filter | hit_rate@1 | per-question |
|---|---|---|
| none | | |
| status=current | | |

What this tells you about where to look first when retrieval is poor:

## 5. Final recommendation

Configuration:  (chunking · size · retriever · reranker · index)

| metric | value | target | met? |
|---|---|---|---|
| nDCG@10 | | ≥ 0.80 | |
| recall@5 | | ≥ 0.85 | |
| hit_rate@1 | | ≥ 0.65 | |
| paraphrase MRR | | ≥ 0.75 | |
| p95 latency | | ≤ 400 ms | |
| index build cost | | reported | |

Greedy-sweep limitation (what you could have missed):

## 6. One thing that surprised you
