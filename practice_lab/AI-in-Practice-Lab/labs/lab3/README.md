# Lab 3 — Semantic Search That Actually Works
**3 hours · Pairs**

> **Docs:** [README](README.md) (this brief) · [RUNSHEET](RUNSHEET.md) (the actions, step by step) · [CONCEPTS](CONCEPTS.md) (theory → code reference) · [report.md](report.md) (yours to fill)
> Track N: [`lab3.ipynb`](lab3.ipynb) · Track S: `search.py`

---

## The one-sentence version

**Everything you build in Labs 4–7 is capped by what retrieval finds — and this is the lab where you discover that published best practice is a prior, not a result.**

---

## The problem

Aurora's support agents currently find policy information by using Ctrl-F on a
PDF. It does not work: they type *"how long do I have to file"* and the document
says *"submitted within 30 days of discharge"*, so Ctrl-F finds nothing.

You are building the search layer that Labs 4–7 will sit on top of.

You get: 30 documents (`data/corpus/`) and 45 labelled questions with
document-level relevance judgements (`data/eval/rag_golden.jsonl`).

16 of the documents are Aurora Health policy documents. The other 14 are
distractors: motor claim timelines, travel exclusions, a group corporate plan
comparison, a life-insurance grace period, a senior-citizen product, an app
guide. They are there because they compete lexically with the real answers, and
a corpus without distractors makes every retrieval method look equally good.

**Find the retrieval configuration that maximises nDCG@10, and justify it
against cost and latency.**

### The search space

| Axis | Levels |
|---|---|
| Chunking | fixed · sliding · recursive · markdown-aware |
| Chunk size | 400 · 800 · 1600 characters |
| Retrieval | dense · BM25 · hybrid (RRF) |
| Reranking | none · cross-encoder · LLM reranker |
| Index | exact NumPy · Chroma HNSW |

That is far too many combinations to run exhaustively in three hours, and
noticing that is part of the lab. **Do not grid-search blindly.** Sweep one axis
at a time, fix the winner, move on. Say in your report what that greedy
procedure could miss.

---

## Why this lab exists

Common course wisdom says hybrid retrieval is *"the strongest single change
most RAG systems can make"*. On this corpus, hybrid **loses**. The cross-encoder
reranker **lowers** quality. The approximate index is **slower** than exact
search.

None of those are mistakes in the theory. They are the theory meeting a
particular corpus, and learning to report what your data says rather than what
you were told to expect is the transferable skill in this lab.

**Where it sits.** Labs 4, 5 and 7 all sit on the retriever you choose today.
Choosing badly is recoverable; choosing without measuring is not, because you
will not know which stage to blame when Lab 4's answers are wrong.

The full argument for each of those contradictions is in
[CONCEPTS.md](CONCEPTS.md).

---

## What you will build

- A **chunking sweep** across four strategies and three sizes, with the shape of
  the size curve explained rather than just reported
- A **retrieval comparison** — dense, BM25, hybrid — broken down **by question
  kind**, not just in aggregate
- A **reranking decision** with two different answers: one for an interactive
  search box, one for an overnight batch job
- A **metadata filter** that fixes three trap questions without touching the
  retriever at all
- A recommended configuration with all of its numbers

---

## How to approach it

**Do not grid-search.** Four chunkers × three sizes × three retrievers × three
rerankers × two indexes is 216 combinations and does not fit in three hours.
Sweep one axis, fix the winner, move on — and then say in your report what that
greedy procedure could miss.

**Write down the baseline before you change anything.** You will run
`--baseline` in the first fifteen minutes; that number is what every later
claim is relative to.

**Pick your metric before you run.** `hit_rate@5` is saturated on this corpus —
every retriever scores 0.93 to 0.98 — so it reports *nothing* while looking
exactly like "no difference". Use nDCG@10, recall@5, hit_rate@1 and MRR.
The full saturation story is in [CONCEPTS.md](CONCEPTS.md); the RUNSHEET
checkpoints remind you at each step.

---

## Targets on the golden set (n = 42 after exclusions)

| Metric | Target | BM25 baseline | Reference solution |
|---|---|---|---|
| nDCG@10 | ≥ 0.80 | 0.701 | 0.853 |
| recall@5 | ≥ 0.85 | 0.790 | 0.903 |
| hit_rate@1 | ≥ 0.65 | 0.524 | 0.786 |
| MRR on the `paraphrase` subset | ≥ 0.75 | 0.500 | 0.900 |
| Retrieval latency p95 | ≤ 400 ms (excluding first-time embedding) | 0.3 ms | 1.0 ms |
| Cost to build the index | reported, once | $0 | $0.008 |

Both extra columns are measured, not estimated. The reference configuration is
markdown-aware chunking at 400 characters with exact dense retrieval.

**Do not use `hit_rate@5` as the headline.** Every retriever scores 0.93–0.98
on it; dense vs BM25 looks like 0.976 vs 0.929 — "no interesting difference" —
while on MRR the same comparison is 0.872 vs 0.693. Full mechanics:
[CONCEPTS.md](CONCEPTS.md).

**3 of the 45 questions have no relevant document at all** (Q36, Q38, Q39).
**Exclude those three from retrieval metrics** — you cannot compute recall
against an empty relevant set — which leaves **n = 42**. Say in your report that
you excluded them and why. Five questions in total are of kind `unanswerable`;
the other two do have relevant documents. All five belong to Lab 4, where
refusal is measured properly.

---

## Timetable

| Time | Part | What you do |
|---|---|---|
| 0:00–0:15 | Setup | Build the index, run the provided baseline |
| 0:15–0:55 | **A** | Chunking sweep. The biggest single lever |
| 0:55–1:35 | **B** | Dense vs BM25 vs hybrid — and the per-question-type breakdown |
| 1:35–2:10 | **C** | Reranking, and whether it earns its latency |
| 2:10–2:35 | **D** | ANN vs exact; metadata filtering |
| 2:35–3:00 | Show & tell | Your configuration and the one surprising result |

**During the lab, work from [RUNSHEET.md](RUNSHEET.md)** — it has the exact
commands, numbered TODOs, checkpoints, and the troubleshooting table. This
README is the brief; the RUNSHEET is the procedure.

---

## Parts in brief

**A — Chunking (40 min).** Four strategies at size 800, then the winner at
400/800/1600, then markdown heading-prefix on/off, then one failure case.
Commands and numbered steps: RUNSHEET §2.

**B — Dense vs BM25 vs hybrid (40 min).** Freeze the A winner. Break down
**by question kind using MRR**. Watch Q44 (identifier) and Q41 (paraphrase).
Tune RRF `k`. Report dense vs hybrid **whichever way it lands**. RUNSHEET §3.

**C — Reranking (35 min).** Cross-encoder and LLM reranker, retrieve k=30 → 5.
Build the decision table and give **two different** answers (interactive vs
batch). Find a query where reranking made things worse. RUNSHEET §4.

**D — Index and metadata (25 min).** Exact vs HNSW (skip-with-note without
`chromadb`), scale with ballast to find the crossover, then the archived-doc
trap on Q29–Q31 — a fix that needs **no retriever change**. RUNSHEET §5.

---

## Choose ONE track

Pick one and ignore the other for the whole lab.

**Track N — Notebook.** [`lab3.ipynb`](lab3.ipynb) is the whole lab as one file.
Run cells in order; edit *your turn* cells there. Submit by finishing
`search.py` and filling [`report.md`](report.md) by hand.

```bash
jupyter lab labs/lab3/lab3.ipynb
```

**Track S — Scripts.** Ignore the notebook. Edit only `search.py`. The same
TODOs appear as docstrings; the RUNSHEET maps them.

---

## Setup (15 min)

```bash
python labs/lab3/search.py --baseline
```

This chunks the corpus with sliding windows, embeds it, and reports the
baseline. It takes 1–3 minutes the first time (embedding) and is instant after
that (cache). Write down the baseline numbers before you change anything.

**Dependencies:**

```bash
pip install -r requirements.txt
# Part D only (HNSW + metadata filter):
pip install chromadb
```

> On some Windows ARM64 hosts `chromadb` has no prebuilt wheel. If install
> fails, complete Parts A–C, skip D, and note that in your report.

---

## What separates a good report from an adequate one

- An adequate report gives the winning configuration. A good one gives the
  **per-kind breakdown** and explains the mechanism on Q44 and Q41 in two
  sentences each.
- An adequate report reports hybrid. A good one reports hybrid **honestly
  whichever way it lands**, with the count of questions where dense beat BM25.
- The C3 answer should be **two different deployments with two different
  answers**. If they are the same, that needs explaining.

---

## Deliverables

1. `search.py` — your completed sweeps
2. [`report.md`](report.md) — at most three pages:
   - the chunking table and the size curve, with the dilution explanation
   - the retrieval table **broken down by question kind**, with the Q44/Q41 analysis
   - the reranking decision table and your two different deployment answers
   - the metadata-filter before/after on Q29–Q31
   - your final recommended configuration, with all its numbers
   - one thing that surprised you
   - that you excluded Q36/Q38/Q39 (n = 42) and why
3. `reports/lab3_sweeps.json`

---

## Rubric

| Criterion | Weight | Full marks means |
|---|---|---|
| Retrieval quality | 20% | Meets the nDCG@10 / recall@5 / hit_rate@1 targets, including on `paraphrase` |
| Sweep discipline | 20% | One axis at a time; the greedy-search limitation acknowledged |
| Diagnostic depth | 25% | The per-kind breakdown uses a non-saturated metric and is correctly interpreted; Q44/Q41 mechanism explained; the hybrid result reported honestly whichever way it lands |
| Cost/latency reasoning | 20% | The two different deployment answers in C3 are both defended |
| Metadata insight | 15% | D3 works, and its implication is stated |

---

## Stretch

1. **Contextual retrieval.** One small-model call per chunk at ingest to prepend
   a situating sentence. Costs ~$0.02 for this corpus. Verify or refute a
   retrieval-quality gain on this corpus.
2. **HyDE.** Generate a hypothetical answer, embed that, retrieve. Measure on
   the `paraphrase` subset specifically, where it should help most.
3. **Small-to-big.** Embed 300-character chunks, return the parent section.
4. **Query classification.** Route identifier-shaped queries to BM25 and
   natural-language queries to dense. Does routing beat fusion?

---

## Questions we will discuss

1. Hybrid lost here and wins in most published results. What is different about
   this corpus? What would have to change for it to win?
2. The metadata filter fixed three questions for free and changed nothing about
   the retriever. Where else in your pipeline is there a data fix hiding behind
   a modelling problem?
3. Your greedy sweep fixed the chunker before choosing the retriever. Name a
   pair of axes in this lab that you suspect interact.
4. The LLM reranker is the best configuration measured and unusable
   interactively. If someone parallelised it to 1.5 seconds, would you deploy
   it? What else would you need to know?
