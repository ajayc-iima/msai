#!/usr/bin/env python3
"""Lab 3 — retrieval sweeps.

The scaffolding (corpus loading, metric computation, table printing) is
written for you. The four sweeps below the banner are yours — same contract
as labs/lab1/extract.py and labs/lab2/variants.py: complete the TODOs, keep
the function names, run the CLI.

    python labs/lab3/search.py --baseline
    python labs/lab3/search.py --sweep chunking
    python labs/lab3/search.py --sweep retrieval
    python labs/lab3/search.py --sweep rerank
    python labs/lab3/search.py --sweep index

Lab brief (targets, timetable, checkpoints): labs/lab3/README.md.
Keep labs/lab3/CONCEPTS.md open. Track N users: the same TODOs appear in
labs/lab3/lab3.ipynb as *your turn* cells.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from aip import cost  # noqa: E402
from aip.chunking import STRATEGIES, Chunk  # noqa: E402
from aip.evals import retrieval_metrics  # noqa: E402
from aip.retrieval import (  # noqa: E402
    Bm25Retriever,
    ChromaRetriever,
    CrossEncoderReranker,
    DenseRetriever,
    HybridRetriever,
    LLMReranker,
    Retriever,
)

CORPUS_DIR = ROOT / "data/corpus"
GOLDEN = ROOT / "data/eval/rag_golden.jsonl"
SWEEPS_JSON = ROOT / "reports/lab3_sweeps.json"

# Columns every table prints. hit_rate@5 is on the list so you can SEE it
# saturate (0.93-0.98 for every retriever) — the trap of this lab.
COLS = ("hit_rate@1", "hit_rate@5", "recall@5", "mrr", "ndcg@10", "latency_p95_ms")

# Chunker kwargs the provided builders expect (overlap must be < size).
STRATEGY_KW = {"sliding": {"overlap": 150}, "recursive": {"overlap": 100}}


# ---------------------------------------------------------------------------
# scaffolding (provided)
# ---------------------------------------------------------------------------
def load_corpus() -> dict[str, str]:
    return {p.stem: p.read_text(encoding="utf-8") for p in sorted(CORPUS_DIR.glob("*.md"))}


def load_questions(include_unanswerable: bool = False) -> list[dict]:
    rows = [json.loads(l) for l in GOLDEN.open(encoding="utf-8")]
    if include_unanswerable:
        return rows
    # THREE questions (Q36, Q38, Q39) have no relevant document, so recall and
    # nDCG are undefined for them -- you cannot rank correctly against an empty
    # relevant set. Dropping them leaves n = 42.
    #
    # Do not confuse that with the FIVE questions of kind 'unanswerable'
    # (Q36-Q40): two of those do keep relevant documents, because part of what
    # they ask is supported. All five are measured properly in Lab 4, as
    # refusal precision and recall.
    #
    # Excluding the three is correct -- but say so in your report rather than
    # letting an unexplained n = 42 pass for a stated 45.
    return [r for r in rows if r["relevant_docs"]]


def build_chunks(corpus: dict[str, str], strategy: str = "sliding",
                 size: int = 800, **kw) -> list[Chunk]:
    fn = STRATEGIES[strategy]
    out: list[Chunk] = []
    for doc_id, text in corpus.items():
        try:
            out.extend(fn(text, doc_id, size=size, **kw))
        except TypeError:                       # chunker without that kwarg
            out.extend(fn(text, doc_id, size=size))
    return out


def evaluate(retriever: Retriever, questions: list[dict], k: int = 10,
             reranker=None, final_k: int = 5) -> dict:
    """Run every question, return aggregate metrics + per-kind breakdown."""
    agg: dict[str, list[float]] = defaultdict(list)
    by_kind: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    latencies: list[float] = []
    per_q: dict[str, float] = {}
    per_q_mrr: dict[str, float] = {}

    for q in questions:
        t0 = time.perf_counter()
        hits = retriever.search(q["question"], k=k)
        if reranker is not None:
            hits = reranker.rerank(q["question"], hits, k=final_k)
        latencies.append((time.perf_counter() - t0) * 1000)

        # A document counts as retrieved at rank r if any of its chunks does.
        seen, ranked = set(), []
        for h in hits:
            if h.doc_id not in seen:
                seen.add(h.doc_id)
                ranked.append(h.doc_id)

        m = retrieval_metrics(ranked, q["relevant_docs"], ks=(1, 3, 5, 10))
        per_q[q["id"]] = m["hit_rate@5"]
        per_q_mrr[q["id"]] = m["mrr"]
        for key, val in m.items():
            agg[key].append(val)
            by_kind[q["kind"]][key].append(val)

    out = {k2: statistics.fmean(v) for k2, v in agg.items()}
    out["latency_p50_ms"] = statistics.median(latencies)
    out["latency_p95_ms"] = sorted(latencies)[int(0.95 * (len(latencies) - 1))]
    out["_by_kind"] = {kind: {k2: statistics.fmean(v) for k2, v in d.items()}
                       for kind, d in by_kind.items()}
    out["_per_question"] = per_q            # hit_rate@5 -- saturated, see kind_table
    out["_per_question_mrr"] = per_q_mrr    # use this one for Part B
    out["_kind_n"] = {kind: len(d["mrr"]) for kind, d in by_kind.items()}
    return out


def table(rows: dict[str, dict], cols: tuple[str, ...] = COLS) -> str:
    name_w = max(len(n) for n in rows) + 2
    head = f"{'config':<{name_w}}" + "".join(f"{c:>15}" for c in cols)
    lines = [head, "-" * len(head)]
    for name, m in rows.items():
        lines.append(f"{name:<{name_w}}" + "".join(f"{m.get(c, 0):>15.4f}" for c in cols))
    return "\n".join(lines)


def kind_table(metrics: dict, col: str = "hit_rate@5") -> str:
    """Break a result down by question kind.

    NOTE the default column. `hit_rate@5` is saturated on this corpus -- every
    retriever scores 0.93-0.98 -- so this table will look flat and tell you
    nothing. Pass col='mrr' or col='ndcg@10' for Part B. The default is left
    saturated on purpose.
    """
    bk, counts = metrics["_by_kind"], metrics.get("_kind_n", {})
    w = max(len(k) for k in bk) + 2
    lines = [f"{'kind':<{w}}{col:>12}{'n':>6}", "-" * (w + 18)]
    for kind, m in sorted(bk.items()):
        lines.append(f"{kind:<{w}}{m.get(col, 0):>12.4f}{counts.get(kind, 0):>6}")
    return "\n".join(lines)


def record(sweep: str, payload: dict) -> None:
    """Merge this sweep's results into reports/lab3_sweeps.json (deliverable 3)."""
    SWEEPS_JSON.parent.mkdir(parents=True, exist_ok=True)
    data: dict = {}
    if SWEEPS_JSON.exists():
        try:
            data = json.loads(SWEEPS_JSON.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}
    data[sweep] = payload
    data["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    SWEEPS_JSON.write_text(
        json.dumps(data, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    print(f"[saved] {sweep} -> {SWEEPS_JSON}")


def snippet(text: str, n: int = 120) -> str:
    return " ".join(text.split())[:n]


def time_search(retriever: Retriever, questions: list[dict], k: int = 10,
                repeats: int = 2) -> tuple[float, float]:
    """Warm once, then time every question `repeats` times. Returns (p50, p95) ms."""
    retriever.search(questions[0]["question"], k=k)
    lat: list[float] = []
    for _ in range(repeats):
        for q in questions:
            t0 = time.perf_counter()
            retriever.search(q["question"], k=k)
            lat.append((time.perf_counter() - t0) * 1000)
    lat.sort()
    return statistics.median(lat), lat[int(0.95 * (len(lat) - 1))]


def hit_at_1(retriever, questions: list[dict], where: dict | None = None
             ) -> tuple[float, dict[str, float]]:
    """Document-level hit_rate@1 for a small question set.

    ChromaRetriever.search accepts `where=...`. If you are running Part D
    without chromadb, wrap your dense retriever so search() also accepts a
    `where` dict and filters on chunk.meta — same idea, different backend.
    """
    per: dict[str, float] = {}
    for q in questions:
        if where is None:
            hits = retriever.search(q["question"], k=5)
        else:
            hits = retriever.search(q["question"], k=5, where=where)
        seen, ranked = set(), []
        for h in hits:
            if h.doc_id not in seen:
                seen.add(h.doc_id)
                ranked.append(h.doc_id)
        per[q["id"]] = float(bool(ranked) and ranked[0] in set(q["relevant_docs"]))
    return statistics.fmean(per.values()), per


def strip_heading_prefix(chunks: list[Chunk]) -> list[Chunk]:
    """A3 helper: drop the '[heading > path]\\n' line. Do NOT edit aip/chunking.py
    (other labs depend on it) — strip here instead.
    """
    out: list[Chunk] = []
    for c in chunks:
        text = c.text
        if text.startswith("[") and "\n" in text:
            text = text.split("\n", 1)[1]
        out.append(Chunk(text, c.doc_id, c.chunk_id, dict(c.meta)))
    return out


def index_and_eval(chunks: list[Chunk], questions: list[dict],
                   reranker=None, k: int = 10, final_k: int = 5
                   ) -> tuple[DenseRetriever, dict]:
    """Embed chunks (cached after first time), evaluate, return (retriever, metrics).

    Also stamps m['n_chunks'] and m['index_s'] (seconds to build the index).
    Report both next to quality — a config that is 1 point better and takes
    4x as long to build is a real trade-off.
    """
    t0 = time.perf_counter()
    r = DenseRetriever(chunks, show_progress=False)
    m = evaluate(r, questions, k=k, reranker=reranker, final_k=final_k)
    m["index_s"] = time.perf_counter() - t0
    m["n_chunks"] = float(len(chunks))
    return r, m


def best_chunk_cfg() -> tuple[str, int, dict]:
    """Winner from your Part A sweep if recorded; else the reference markdown-400.

    Parts B/C/D should freeze the chunker (greedy sweep) and vary only their
    own axis. Re-read the winner from reports/lab3_sweeps.json so each
    `--sweep` can run standalone.
    """
    try:
        data = json.loads(SWEEPS_JSON.read_text(encoding="utf-8"))
        w = data.get("chunking", {}).get("winner") or {}
        if w.get("strategy"):
            return str(w["strategy"]), int(w.get("size", 800)), dict(w.get("kw") or {})
    except (OSError, json.JSONDecodeError):
        pass
    return "markdown", 400, {}


def has_chroma() -> bool:
    try:
        import chromadb  # noqa: F401
        return True
    except ImportError:
        return False


def has_cross_encoder() -> bool:
    try:
        import sentence_transformers  # noqa: F401
        return True
    except ImportError:
        return False


# ---------------------------------------------------------------------------
# sweeps (yours)
# ---------------------------------------------------------------------------
def sweep_baseline() -> None:
    """Provided. Run this FIRST and write the numbers into report.md §0."""
    corpus, questions = load_corpus(), load_questions()
    chunks = build_chunks(corpus, "sliding", 800, overlap=150)
    print(f"corpus: {len(corpus)} docs -> {len(chunks)} chunks "
          f"(mean {statistics.fmean(len(c) for c in chunks):.0f} chars)")
    r = DenseRetriever(chunks)
    m = evaluate(r, questions)
    print(table({"baseline sliding-800 dense": m}))
    print()
    print(kind_table(m))
    print("\nWrite these numbers down before you change anything.")
    record("baseline", {"config": "sliding-800 dense", "n_docs": len(corpus),
                        "n_chunks": len(chunks), "metrics": m})


def sweep_chunking() -> None:
    """TODO A1-A4 — the biggest single lever. See README Part A.

    A1  All four strategies at size=800. Use index_and_eval(); report
        nDCG@10, recall@5, hit_rate@1, MRR, chunk count, index build seconds.
        Strategies: fixed, sliding, recursive, markdown.
        Checkpoint: markdown-800 should beat fixed-800 by a clear margin.
        If all four are within a point, you have a bug (rebuilding while
        reading a cached index), not a finding.

    A2  Take the A1 winner (by nDCG@10) and sweep size in {400, 800, 1600}.
        The curve is NOT monotonic. Explain the shape in report.md A2
        (dilution vs incomplete rules — see CONCEPTS.md).

    A3  markdown WITH and WITHOUT the '[heading > path]' prefix.
        Use strip_heading_prefix() on the chunks — do not modify
        aip/chunking.py. Report the delta on nDCG@10, hit_rate@1, hit_rate@5.
        Reference measured +0.054 nDCG@10 and +0.143 hit_rate@1; hit_rate@5
        may FALL while hit_rate@1 RISES — work out which one improved.

    A4  One golden question where chunking is clearly the failure.
        Print the chunk that should have matched and the chunks that did.
        Hint: pick the qid whose per-question MRR swings most across the
        four @800 strategies (metrics['_per_question_mrr']).

    When done:
        record("chunking", {
            "a1": ..., "a2": ..., "a3": ..., "a4": ...,
            "winner": {"strategy": ..., "size": ..., "kw": ...},
        })
    so later sweeps can freeze your winner via best_chunk_cfg().
    """
    raise NotImplementedError("TODO A1-A4: implement the chunking sweep")


def sweep_retrieval() -> None:
    """TODO B1-B5 — dense vs BM25 vs hybrid. See README Part B.

    Freeze the Part A winner (best_chunk_cfg()) before you start.

    B1  dense / bm25 / hybrid on that chunking. Print table(...).

    B2  THE IMPORTANT PART. Break down BY QUESTION KIND using MRR:
            print(kind_table(m, col="mrr"))
        and pull Q44 / Q41 from metrics['_per_question_mrr'].

        USE MRR, NOT hit_rate@5. Every retriever scores 0.93-0.98 on
        hit_rate@5 — saturated, shows nothing. kind_table() and
        metrics['_per_question'] both default to it on purpose; noticing
        that trap is part of the lab.

        Explain Q44 (exact identifier AUR-HI-SIL-2026) and Q41 (paraphrase
        of "grace period", zero lexical overlap) in two sentences each.

    B3  RRF k in {10, 30, 60, 100} — HybridRetriever(..., rrf_k=k).
        Expect a small spread. Flatness is the finding; chasing 0.008 at
        n=42 is fitting to noise.

    B4  Unequal fusion weights — HybridRetriever(..., weights=[2.0, 1.0]).
        Does anything beat 1:1? Be honest about noise at n=42.

    B5  Report dense vs hybrid WHICHEVER WAY IT LANDS. Count questions where
        dense beat BM25 among those they differ (compare
        metrics['_per_question_mrr']). Do not suppress a loss.

    When done: record("retrieval", {"chunking": ..., "b1": ..., "b3": ...,
                                    "b4": ..., "b5": ...}).
    """
    raise NotImplementedError("TODO B1-B5: implement the retrieval sweep")


def sweep_rerank() -> None:
    """TODO C1-C4 — retrieve wide, rerank narrow. See README Part C.

    Baseline for deltas: evaluate(dense, questions, k=30) — no reranker.

    C1  CrossEncoderReranker. evaluate(..., k=30, reranker=rr, final_k=5).
        Report Δ nDCG@5, hit_rate@1, recall@5, added p95 latency.
        First run downloads ~90 MB. If sentence-transformers/torch will not
        install (Windows ARM64), skip C1, say so in the report, and lean on C2.

    C2  LLMReranker — quality, latency, AND cost. This is the first config
        that costs money per query:
            b0 = cost.global_budget().as_dict()
            m = evaluate(...)
            spend = cost.global_budget().as_dict()["cost_usd"] - b0["cost_usd"]
            usd_per_1k = spend / len(questions) * 1000
        Tip: LLMReranker makes 30 calls IN SERIES per question (tens of
        seconds). Parallelise if you must; note what serialisation means
        for your C3 answer either way. If the free tier is rate-limited,
        wait and retry, or use tier MAIN and report the higher $/1k.

    C3  Decision table: no-rerank / cross-encoder / llm on
        nDCG@5, hit_rate@1, p95 ms, $/1k queries.
        TWO different deployment answers:
          (a) interactive agent-facing search box
          (b) overnight batch job
        They should not be the same. If they are, explain why.

    C4  Find a query where reranking made things WORSE, using
        metrics['_per_question_mrr'] before vs after. Was the relevant doc
        in the k=30 pool? Diagnose the failure mode.

    When done: record("rerank", {...}).
    """
    raise NotImplementedError("TODO C1-C4: implement the rerank sweep")


def sweep_index() -> None:
    """TODO D1-D3 — index choice and the metadata trap. See README Part D.

    Set status metadata first (needed for D3 either way):
        for c in chunks:
            c.meta["status"] = "archived" if "ARCHIVED" in c.doc_id else "current"

    D1  ChromaRetriever vs DenseRetriever — quality gap and latency on your
        best config. Needs `pip install chromadb`. On some Windows ARM64
        hosts the package has no wheel — skip D1/D2, note it in the report,
        and still do D3 (you can filter an exact dense index on meta the
        same way; the lesson does not depend on HNSW).

    D2  Scale with inline ballast — random unit vectors of the right
        dimension (np.random.default_rng(0), normalise rows). Ballast goes
        in the INDEX only; no golden answers, so exclude it from quality
        reporting. Time exact NumPy vs HNSW at ~160, ~4k, ~40k chunks.
        Find the crossover and explain the mechanism (at small n, HNSW is
        SLOWER: graph traversal + Python overhead vs one BLAS matmul).
        time_search() is provided.

    D3  THE TRAP. Q29/Q30/Q31 have a correct answer in claims-timelines and
        a wrong one in claims-timelines-2024-ARCHIVED.
        Report hit_rate@1 on those three before and after:
            before, per_b = hit_at_1(retriever, trap_qs)
            after,  per_a = hit_at_1(retriever, trap_qs, where={"status": "current"})
        Then answer in the report: this fix required NO change to the
        retriever. What does that tell you about where to look first when
        retrieval quality is poor?

    When done: record("index", {"d1": ..., "d2": ..., "d3": ...}).
    """
    raise NotImplementedError("TODO D1-D3: implement the index sweep")


SWEEPS = {
    "chunking": sweep_chunking,
    "retrieval": sweep_retrieval,
    "rerank": sweep_rerank,
    "index": sweep_index,
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline", action="store_true")
    ap.add_argument("--sweep", choices=list(SWEEPS))
    args = ap.parse_args()
    if args.baseline or not args.sweep:
        sweep_baseline()
    if args.sweep:
        SWEEPS[args.sweep]()


if __name__ == "__main__":
    main()
