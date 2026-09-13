#!/usr/bin/env bash
set -euo pipefail
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 1. Corpus — 2019-2025 only (--since 2019 default; raw parquet auto-removed after filter).
#    Pre-existing data/corpus.jsonl can be trimmed in place instead:
#      python -m src.build_corpus --refilter --since 2019
python -m src.build_corpus

# 2. Evaluation queries: Gold A (auto) + Gold B (manual annotation, ~2h, 2 sittings)
python -m src.make_queries --gold-b 100 --seed 7

# 3. Indexes: tuned BM25, then dense (head-only and chunked variants)
python -m src.retrieval build
python -m src.retrieval sweep --out data/index/bm25_config.json
python -m src.retrieval dense --mode head --index-dir data/index --out data/runs/
python -m src.retrieval dense --mode chunked --index-dir data/index --out data/runs/

# 4. Retrieval runs per system + hybrid fusion, scored on Gold A and Gold B
python -m src.retrieval search --system bm25
python -m src.retrieval search --system dense_head
python -m src.retrieval search --system dense_chunked
python -m src.retrieval search --system oracle
python -m src.retrieval fuse --runs data/runs/bm25.jsonl data/runs/dense_head.jsonl data/runs/dense_chunked.jsonl --out data/runs/hybrid.jsonl
python -m src.retrieval rerank --fused data/runs/hybrid.jsonl --queries data/queries.jsonl --out data/runs/hybrid_rerank.jsonl --limit 50
python -m src.make_gold_b_probes    # 200 blinded candidates for Gold B judging
python -m src.evaluate retrieval --systems bm25,dense_head,dense_chunked,hybrid,hybrid_rerank,oracle --gold A
python -m src.evaluate retrieval --systems bm25,dense_head,dense_chunked,hybrid,hybrid_rerank,oracle --gold B --queries data/gold_b_queries.jsonl
python -m src.evaluate retrieval --gold-b-eval --queries data/gold_b_queries.jsonl

# 5. Answer-generation runs (Exp-2, policy A–D + extractive); --no-llm replays cached
#    LLM responses so no API key is needed for the replay
python -m src.answer --system bm25 --policy A --no-llm --limit 200
python -m src.answer --system bm25 --policy B --no-llm --limit 200
python -m src.answer --system bm25 --policy C --no-llm --limit 200
python -m src.answer --system bm25 --policy D --no-llm --limit 200
python -m src.answer --system bm25 --policy extractive --limit 200
python -m src.evaluate answers --system bm25 --policy A
python -m src.evaluate answers --system bm25 --policy B
python -m src.evaluate answers --system bm25 --policy C
python -m src.evaluate answers --system bm25 --policy D
python -m src.evaluate answers --system bm25 --policy extractive

# 6. Plots + report
python -m src.plots
echo "Manual: python -m uvicorn src.app:app --reload   |   notebooks/capstone.ipynb -> Restart and Run All"