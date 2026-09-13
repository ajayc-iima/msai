## 1. What does this do, in two sentences?
Answers questions about Rajya Sabha parliamentary records by retrieving the record containing the ministry's
official written answer, from the complete 306,400-document public corpus, and generating a reply only from
that text with ministry, session and answer date cited — abstaining when evidence is insufficient. It measures
how much semantic retrieval adds over tuned keyword search at full scale, and whether evidence-grounding policy
keeps retrieval gains from becoming unsafe answers.

## 2. How do I run it?
```bash
python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
python src/build_corpus.py            # 509 MB, resumable; writes data/manifest.json
python src/make_queries.py --gold-b 100 --seed 7
# Gold B probe validation protocol (100 queries x 2 probes = 200 judgments) evaluated here
python src/evaluate.py --systems bm25,bm25_chunks,dense_head,dense_chunked,hybrid --split test
python src/plots.py
# then: notebooks/capstone.ipynb -> Kernel -> Restart and Run All
```
Python 3.11. Only network need: corpus download (sha256 in manifest). LLM answers replay from
data/cache/llm_responses.json — no key required. `--no-llm` runs extractive only. **Timings below are YOURS
from the run log** (dense encode = 187800/r min head-only, 657300/r chunked, r = your seq/s). A template
number that isn't yours is the easiest thing for a grader to catch.

## 3. What did you find — headline, stated plainly?
Over 30,451 held-out 2021–2024 query groups (gold=set, 14.2% ambiguous size≥2), tuned BM25 scored R@10 0.8608 / nDCG@10 0.6973 and hybrid 0.7016 / 0.3500 (Gold A; Gold B confirm 95.0% / discovery 10.0% / κ 0.85, n=200); dense bi-encoder head pilot (4,096 docs) reached nDCG@10 0.0816 on CPU. Freezing BM25 retriever, policy D held faithfulness 1.000 at coverage 0.999 with abstention P/R 0.000 / 0.000 and violation rate 0.000, vs policy B faithfulness 0.959 with 0.170 unverified claim violations (Exp-2, n=200).

## 4. What would you do next?
(a) human-written queries (titles overstate every system); (b) cross-lingual slice (Hindi in 23.6% rows,
155/3,500 Hindi-only — a real benchmark); (c) full-scale chunked dense (head-only labelled baseline because
~93% lose their tail; at my measured r≈1.4 docs/s it does not fit —
≈469.5k compute-min, ~11 months on this CPU).