# PowerShell Reproduction Script for Rajya Sabha QA Pipeline
\Continue = 'Stop'

# 1. Corpus (2019-2025 default)
python -m src.build_corpus

# 2. Evaluation queries
python -m src.make_queries --gold-b 100 --seed 7

# 3. Indexes
python -m src.retrieval build
python -m src.retrieval sweep --out data/index/bm25_config.json
python -m src.retrieval dense --mode head --index-dir data/index --out data/runs/
python -m src.retrieval dense --mode chunked --index-dir data/index --out data/runs/

# 4. Retrieval runs + fusion + evaluation
python -m src.retrieval search --system bm25
python -m src.retrieval search --system dense_head
python -m src.retrieval search --system dense_chunked
python -m src.retrieval search --system oracle
python -m src.retrieval fuse --runs data/runs/bm25.jsonl data/runs/dense_head.jsonl data/runs/dense_chunked.jsonl --out data/runs/hybrid.jsonl
python -m src.retrieval rerank --fused data/runs/hybrid.jsonl --queries data/queries.jsonl --out data/runs/hybrid_rerank.jsonl --limit 50
python -m src.make_gold_b_probes
python -m src.evaluate retrieval --systems bm25,dense_head,dense_chunked,hybrid,hybrid_rerank,oracle --gold A
python -m src.evaluate retrieval --systems bm25,dense_head,dense_chunked,hybrid,hybrid_rerank,oracle --gold B --queries data/gold_b_queries.jsonl
python -m src.evaluate retrieval --gold-b-eval --queries data/gold_b_queries.jsonl

# 5. Answer generation & evaluation
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

# 6. Plots
python -m src.plots
Write-Host 'Reproduction complete! Open notebooks/capstone.ipynb and Run All.'
