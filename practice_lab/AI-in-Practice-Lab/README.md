# AI in Practice — Lab course

Five labs that build one system, stage by stage: **extract → experiment →
retrieve → ground → diagnose**. You start by turning messy insurance support
tickets into validated structured records (Lab 1), build the experiment
harness that tells you which configuration to ship (Lab 2), build the search
layer later labs sit on (Lab 3), generate cited, refuse-when-unknown answers
over that search (Lab 4), and learn to diagnose and fix a RAG system with
evidence instead of vibes (Lab 5). Every lab ships the same four docs:
**README** (the brief: problem, targets, rubric), **RUNSHEET** (the actions,
step by step), **CONCEPTS** (theory → code), and **report.md** (yours to
fill, by hand).

## Labs

| Lab | One line | Brief |
|---|---|---|
| 1 · The Reliable Extractor | 240 messy tickets → validated structured records, 100% validity, cost-aware | [labs/lab1/README.md](labs/lab1/README.md) |
| 2 · The Prompt Lab | Build the experiment harness, run the grid, recommend on quality × cost × latency | [labs/lab2/README.md](labs/lab2/README.md) |
| 3 · Semantic Search That Actually Works | Chunking, retrieval and reranking sweeps — justify the configuration against cost and latency | [labs/lab3/README.md](labs/lab3/README.md) |
| 4 · RAG v1: Grounded Answers with Citations | Every claim cited, honest refusal when the sources do not contain the answer | [labs/lab4/README.md](labs/lab4/README.md) |
| 5 · RAG v2: Diagnose, Fix, Prove | Classify every failure to a stage, fix the biggest cluster, prove the fix with before/after | [labs/lab5/README.md](labs/lab5/README.md) |

## Setup

```bash
python -m venv .venv
# Windows PowerShell:  .\.venv\Scripts\python -m pip install -r requirements.txt
# macOS / Linux:      ./.venv/bin/python -m pip install -r requirements.txt
```

Get a free key at **aistudio.google.com/apikey**, copy `.env` next to this
README, and put the key after `GEMINI_API_KEY=` (no quotes, no spaces).

```bash
python check_setup.py     # ready when the last line reads: Environment is ready.
```

Lab-specific pre-flight (the pydantic primer, the ticket read, the annotation
guidelines) lives in each lab's README and RUNSHEET — start at
[labs/lab1/README.md](labs/lab1/README.md).

## Choose ONE track per lab

Pick one and ignore the other for the whole lab.

- **Track N — Notebook.** `labs/labN/labN.ipynb` is the whole lab top to
  bottom. Run cells in order, edit the *your turn* cells, then copy your
  work into the graded file (`extract.py`, `variants.py`, `search.py`, …)
  and fill `report.md` **by hand** — never regenerate the report.
- **Track S — Scripts.** Ignore the notebook. Edit only the graded file and
  drive everything with the lab's runner (`run_eval.py`, `grid.py`, …).

## Layout

| Path | What it is |
|---|---|
| `aip/` | The shared library: `llm.py` (chat, structured output, repair loop, cache, cost ledger), `evals.py` (the harness), plus chunking, retrieval, guards, tracing. Read it; do not edit it. |
| `labs/` | One directory per lab: its README / RUNSHEET / CONCEPTS / report, the graded file, and the Track N notebook. |
| `data/` | All fixtures — tickets, eval splits, corpus, attack suite. Guidelines and known limitations: [data/README.md](data/README.md). |
| `reports/` | Saved harness outputs (`--save reports/...`) — deliverables. |

## Environment variables (.env)

| Variable | Default | Meaning |
|---|---|---|
| `AIP_PROFILE` | `gemini` | Provider profile (see `PROFILES` in `aip/config.py`) |
| `GEMINI_API_KEY` | — | The key for the chosen profile |
| `AIP_BUDGET_USD` | `2.0` | Hard spend ceiling; trips `BudgetExceeded` |
| `AIP_CACHE` | `1` | Identical requests are free and instant (sqlite) |
| `AIP_OFFLINE` | `0` | `1` = replay cache only; a cache miss raises instead of spending |
| `AIP_TEMPERATURE` | `0.0` | Deterministic by default |

Every run reports calls, tokens, cost, and p50/p95 latency. Cost is a
first-class metric in every lab — report the triple (quality × cost ×
latency), never quality alone.
