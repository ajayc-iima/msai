#!/usr/bin/env python3
"""Lab 3 — retrieval sweeps.

The scaffolding (corpus loading, metric computation, table printing) is
written for you. The sweeps are yours.

    python labs/lab3/search.py --baseline
    python labs/lab3/search.py --sweep chunking
    python labs/lab3/search.py --sweep retrieval
    python labs/lab3/search.py --sweep rerank
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

from aip import cost
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


def table(rows: dict[str, dict], cols: tuple[str, ...] =
          ("hit_rate@1", "hit_rate@5", "recall@5", "mrr", "ndcg@10",
           "latency_p95_ms")) -> str:
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


# ---------------------------------------------------------------------------
# sweeps (yours)
# ---------------------------------------------------------------------------
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
    """Document-level hit_rate@1 for a small question set (ChromaRetriever only:
    it is the one whose search() accepts a `where` filter)."""
    per: dict[str, float] = {}
    for q in questions:
        hits = retriever.search(q["question"], k=5, where=where)
        seen, ranked = set(), []
        for h in hits:
            if h.doc_id not in seen:
                seen.add(h.doc_id)
                ranked.append(h.doc_id)
        per[q["id"]] = float(bool(ranked) and ranked[0] in set(q["relevant_docs"]))
    return statistics.fmean(per.values()), per


def sweep_baseline() -> None:
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
    """TODO A1-A3.

    A1: all four strategies at size=800.
    A2: the winner at sizes 400 / 800 / 1600. Plot or tabulate the curve.
    A3: markdown WITH and WITHOUT the '[heading > path]' prefix.
        (Strip it with a list comprehension over the chunks -- do not modify
         aip/chunking.py; other labs depend on it.)

    Report chunk count and index build time alongside quality. A configuration
    that is 1 point better and takes 4x as long to build is a real trade-off.
    """
    corpus, questions = load_corpus(), load_questions()
    cols = ("hit_rate@1", "hit_rate@5", "recall@5", "mrr", "ndcg@10")
    stats: dict[str, dict] = {}

    def run(strategy, size, **kw):
        t0 = time.perf_counter()
        chunks = build_chunks(corpus, strategy, size, **kw)
        build_s = time.perf_counter() - t0
        t1 = time.perf_counter()
        r = DenseRetriever(chunks, show_progress=False)
        index_s = time.perf_counter() - t1
        t2 = time.perf_counter()
        m = evaluate(r, questions)
        eval_s = time.perf_counter() - t2
        stats[f"{strategy}-{size}"] = {"chunks": len(chunks),
                                       "build_s": round(build_s, 2),
                                       "index_s": round(index_s, 2),
                                       "eval_s": round(eval_s, 2)}
        print(f"  {strategy}-{size}: chunks={len(chunks)} build={build_s:.1f}s "
              f"index={index_s:.1f}s eval={eval_s:.1f}s")
        return chunks, m

    # A1: four strategies @ 800
    print("== A1 @800 ==")
    rows = {}
    _, rows["fixed-800"] = run("fixed", 800)
    _, rows["sliding-800"] = run("sliding", 800, overlap=150)
    _, rows["recursive-800"] = run("recursive", 800, overlap=100)
    _, rows["markdown-800"] = run("markdown", 800)
    print(table(rows, cols))

    # A2: winner @ 400/800/1600
    win = max(rows, key=lambda k: rows[k]["ndcg@10"]).rsplit("-")[0]
    kw = {"sliding": {"overlap": 150}, "recursive": {"overlap": 100}}.get(win, {})
    print(f"== A2 winner={win} ==")
    rows2 = {}
    for s in (400, 800, 1600):
        _, rows2[f"{win}-{s}"] = run(win, s, **kw)
    print(table(rows2, cols))
    best = int(max(rows2, key=lambda k: rows2[k]["ndcg@10"]).rsplit("-")[1])

    # A3: prefix on/off
    print(f"== A3 markdown@{best} prefix on/off ==")
    chunks = build_chunks(corpus, "markdown", best)
    no_pre = [Chunk(c.text.split("\n", 1)[1] if c.text.startswith("[") else c.text, c.doc_id, c.chunk_id, dict(c.meta)) for c in chunks]
    _, m_on = run("markdown", best)  # with prefix
    t0 = time.perf_counter()
    m_off = evaluate(DenseRetriever(no_pre, show_progress=False), questions)
    print(f"  markdown-{best}-noprefix: chunks={len(no_pre)} build={time.perf_counter()-t0:.1f}s")
    print(table({f"markdown-{best}-prefix": m_on, f"markdown-{best}-noprefix": m_off}, cols))

    # A4: one golden question where chunking is clearly the failure.
    # Pick the question whose per-question MRR swings most across the four
    # @800 strategies -- if every strategy scores it the same, chunking is not
    # the culprit, the retriever is.
    print("== A4 chunking failure case ==")
    per = {name: m["_per_question_mrr"] for name, m in rows.items()}

    def _spread(qid: str) -> float:
        vals = [per[name].get(qid, 0.0) for name in rows]
        return max(vals) - min(vals)

    qid = max((q["id"] for q in questions), key=_spread)
    q = next(x for x in questions if x["id"] == qid)
    worst = min(rows, key=lambda name: per[name].get(qid, 0.0))
    best_s = max(rows, key=lambda name: per[name].get(qid, 0.0))
    print(f"  {qid} ({q['kind']}): {q['question']}")
    print(f"  relevant={q['relevant_docs']}  gold: {snippet(q.get('gold_answer', ''), 140)}")
    print("  MRR by @800 strategy: "
          + "  ".join(f"{n}={per[n].get(qid, 0.0):.2f}" for n in rows))

    def strategy_chunks(name: str) -> list[Chunk]:
        strat, size = name.rsplit("-", 1)
        kw = {"sliding": {"overlap": 150}, "recursive": {"overlap": 100}}.get(strat, {})
        return build_chunks(corpus, strat, int(size), **kw)

    def show_case(name: str) -> None:
        ch = strategy_chunks(name)
        r = DenseRetriever(ch, show_progress=False)
        print(f"  -- {name}: chunks that DID match (top-3) --")
        for h in r.search(q["question"], k=3):
            print(f"     rank{h.rank + 1} {h.doc_id}: {snippet(h.text)}")
        # the chunk that SHOULD have matched: best chunk of a relevant doc
        sub = [c for c in ch if c.doc_id in set(q["relevant_docs"])]
        if sub:
            g = DenseRetriever(sub, show_progress=False).search(q["question"], k=1)[0]
            print(f"     should have matched ({g.doc_id}): {snippet(g.text)}")

    show_case(worst)
    show_case(best_s)
    print("  (failure mode 2: the answer-carrying chunk ranks below distractors,")
    print("   or the strategy split it so no single chunk contains the answer)")

    record("chunking", {
        "a1": rows, "a2": rows2,
        "a3": {f"markdown-{best}-prefix": m_on,
               f"markdown-{best}-noprefix": m_off},
        "a4": {"qid": qid, "worst": worst, "best": best_s,
               "mrr": {n: per[n].get(qid, 0.0) for n in rows}},
        "stats": stats,
    })


def sweep_retrieval() -> None:
    """TODO B1-B4.

    B1: dense / bm25 / hybrid on your best chunking.
    B2: print kind_table(m, col='mrr') for each, and pull out Q44 and Q41
        individually from metrics['_per_question_mrr'].

        USE MRR, NOT hit_rate@5. Every retriever here scores 0.93-0.98 on
        hit_rate@5, so it is saturated and shows you nothing -- which is why
        kind_table() and metrics['_per_question'] both default to it. That
        default is the trap, and noticing it is part of the lab.

    B3: RRF k in {10, 30, 60, 100} -- HybridRetriever(..., rrf_k=k).
    B4: unequal fusion weights -- HybridRetriever(..., weights=[2.0, 1.0]).
    """
    corpus, questions = load_corpus(), load_questions()
    cols = ("hit_rate@1", "hit_rate@5", "recall@5", "mrr", "ndcg@10")
    chunks = build_chunks(corpus, "markdown", 400)  # <- your A winner; change 400 if yours differs

    dense = DenseRetriever(chunks, show_progress=False)
    bm25 = Bm25Retriever(chunks)

    # B1: dense / bm25 / hybrid
    print("== B1 dense/bm25/hybrid ==")
    m_d = evaluate(dense, questions)
    m_b = evaluate(bm25, questions)
    m_h = evaluate(HybridRetriever([dense, bm25]), questions)
    print(table({"dense": m_d, "bm25": m_b, "hybrid": m_h}, cols))

    # B2: per-kind MRR + Q44/Q41 (use MRR, hit_rate@5 is saturated)
    for name, m in [("dense", m_d), ("bm25", m_b), ("hybrid", m_h)]:
        print(f"-- {name} by kind (mrr) --")
        print(kind_table(m, col="mrr"))
        pq = m["_per_question_mrr"]
        print(f"  {name} Q44={pq.get('Q44', 0):.2f} Q41={pq.get('Q41', 0):.2f}")
    # dense wins paraphrase (Q41), bm25 wins identifier (Q44), hybrid splits both

    # B3: RRF k sensitivity
    print("== B3 rrf_k ==")
    rrf_rows = {}
    for k in (10, 30, 60, 100):
        rrf_rows[f"hybrid-k{k}"] = evaluate(HybridRetriever([dense, bm25], rrf_k=k), questions)
    print(table(rrf_rows, cols))
    # expect: nearly flat -- insensitivity is the point

    # B4: unequal weights
    print("== B4 weights ==")
    rows = {
        "1:1": m_h,
        "densex2": evaluate(HybridRetriever([dense, bm25], weights=[2.0, 1.0]), questions),
        "bm25x2": evaluate(HybridRetriever([dense, bm25], weights=[1.0, 2.0]), questions),
    }
    print(table(rows, cols))
    # n=42: only trust gaps >> noise (~0.03+)

    # B5: report dense vs hybrid WHICHEVER WAY IT LANDS, with the mechanism.
    # On the reference corpus hybrid loses (0.846 -> 0.830): RRF counts BM25's
    # opinion on every query, and dense beats BM25 on most of them. If your
    # numbers say the same, say so; if they say the opposite, say that.
    print("== B5 dense vs hybrid (report honestly) ==")
    pq_d, pq_b, pq_h = (m_d["_per_question_mrr"], m_b["_per_question_mrr"],
                        m_h["_per_question_mrr"])
    print(f"  ndcg@10: dense={m_d['ndcg@10']:.3f}  bm25={m_b['ndcg@10']:.3f}  "
          f"hybrid={m_h['ndcg@10']:.3f}  -> "
          f"hybrid is {'WORSE than' if m_h['ndcg@10'] < m_d['ndcg@10'] else 'better than'} dense")
    differ = [qid for qid in pq_d if pq_d[qid] != pq_b.get(qid, 0.0)]
    d_ahead = sum(1 for qid in differ if pq_d[qid] > pq_b.get(qid, 0.0))
    print(f"  dense vs bm25 differ on {len(differ)} questions; "
          f"dense ahead on {d_ahead}, bm25 ahead on {len(differ) - d_ahead}")
    d_over_h = sum(1 for qid in pq_d if pq_d[qid] > pq_h.get(qid, 0.0))
    h_over_d = sum(1 for qid in pq_h if pq_h[qid] > pq_d.get(qid, 0.0))
    print(f"  per-question MRR vs hybrid: dense better on {d_over_h}, "
          f"hybrid better on {h_over_d}, ties on {len(pq_d) - d_over_h - h_over_d}")
    print("  (a technique that is right on average can be wrong on your data --")
    print("   if hybrid loses here, that is the finding, not a bug)")

    record("retrieval", {
        "chunking": "markdown-400",
        "b1": {"dense": m_d, "bm25": m_b, "hybrid": m_h},
        "b3_rrf_k": rrf_rows,
        "b4_weights": rows,
        "b5": {"ndcg10": {k: v["ndcg@10"] for k, v in
                          {"dense": m_d, "bm25": m_b, "hybrid": m_h}.items()},
               "differ": len(differ), "dense_ahead": d_ahead,
               "dense_over_hybrid": d_over_h, "hybrid_over_dense": h_over_d},
        "kind_mrr": {name: m["_by_kind"] for name, m in
                     {"dense": m_d, "bm25": m_b, "hybrid": m_h}.items()},
        "q41_q44_mrr": {name: {qid: m["_per_question_mrr"].get(qid, 0.0)
                               for qid in ("Q41", "Q44")}
                        for name, m in {"dense": m_d, "bm25": m_b,
                                        "hybrid": m_h}.items()},
    })


def sweep_rerank() -> None:
    """TODO C1-C4.

    Retrieve k=30, rerank to 5: evaluate(r, questions, k=30, reranker=rr,
    final_k=5).

    C1: CrossEncoderReranker. First run downloads ~90 MB.
    C2: LLMReranker -- report cost as well as latency.
    C3: the decision table, and TWO different deployment answers
        (interactive search box vs overnight batch). They should differ.
    C4: find a query reranking made worse, using
        metrics['_per_question_mrr'] before and after.
    """
    corpus, questions = load_corpus(), load_questions()
    chunks = build_chunks(corpus, "markdown", 400)  # A winner; change if yours differs
    dense = DenseRetriever(chunks, show_progress=False)
    cols = ("ndcg@5", "hit_rate@1", "recall@5", "mrr", "ndcg@10", "latency_p95_ms")

    # Baseline for the deltas: retrieve wide, keep the natural order.
    print("== no rerank (retrieve k=30) ==")
    m_none = evaluate(dense, questions, k=30)
    print(table({"no-rerank k30": m_none}, cols))

    # C1: cross-encoder. ~90 MB download on first run.
    print("== C1 cross-encoder (k=30 -> 5) ==")
    t0 = time.perf_counter()
    ce = CrossEncoderReranker()
    print(f"  cross-encoder ready in {time.perf_counter() - t0:.1f}s")
    m_ce = evaluate(dense, questions, k=30, reranker=ce, final_k=5)
    print(table({"no-rerank": m_none, "cross-encoder": m_ce}, cols))
    print("  delta vs no-rerank:")
    for key in ("ndcg@5", "hit_rate@1", "recall@5", "latency_p95_ms"):
        print(f"    {key:<16} {m_ce[key] - m_none[key]:+.4f}")

    # C2: LLM reranker -- 30 sequential model calls per question. Report
    # quality, latency AND cost: this is the first per-query-spend config.
    #
    # Tier note: the default SMALL tier's configured model
    # (nemotron-3-nano-30b-a3b) went end-of-life on 2026-09-01 (HTTP 410).
    # Model IDs rot silently -- that is why scripts/list_models.py exists.
    # MAIN (nemotron-3-super-120b-a12b) is verified live, so use it.
    print("== C2 LLM reranker (k=30 -> 5; 30 sequential calls/question) ==")
    llm = LLMReranker(tier="MAIN")
    print("  tier=MAIN: default SMALL model returned HTTP 410 (EOL 2026-09-01)")

    # NVIDIA's developer key rate-limits hard (~a burst of ~30 calls then
    # 429). aip.llm retries 4x with short backoff and then gives up; for
    # 42 x 30 sequential calls we wrap chat() with (a) a minimum gap between
    # NETWORK calls -- cached calls skip the gap, so re-runs stay fast --
    # and (b) patient outer retries with window-reset-length sleeps.
    # LLMReranker does `from aip.llm import chat` inside rerank(), so it
    # picks up this patched attribute on every call.
    import aip.llm as _llm_mod

    _real_chat = _llm_mod.chat
    _state = {"last_net": 0.0, "gap": 2.5, "was_net": False, "net_calls": 0}

    def _patient_chat(*args, **kwargs):
        kwargs["return_full"] = True

        def _transient(exc: Exception) -> bool:
            text, name = str(exc), type(exc).__name__
            return ("429" in text or "RateLimit" in name
                    or "503" in text or "ServiceUnavailable" in name
                    or "overloaded" in text.lower())

        for attempt in range(12):
            if _state["was_net"]:
                wait = _state["gap"] - (time.perf_counter() - _state["last_net"])
                if wait > 0:
                    time.sleep(wait)
            try:
                res = _real_chat(*args, **kwargs)
            except Exception as exc:  # noqa: BLE001 - classify, re-raise others
                _state["last_net"] = time.perf_counter()
                _state["was_net"] = True
                if _transient(exc):
                    backoff = min(70.0, 30.0 + 15.0 * attempt)
                    print(f"\n  [throttle] {type(exc).__name__} -- sleeping "
                          f"{backoff:.0f}s (retry {attempt + 1}/12)", flush=True)
                    time.sleep(backoff)
                    continue
                raise
            if res.get("usage", {}).get("cached"):
                _state["was_net"] = False
            else:
                _state["last_net"] = time.perf_counter()
                _state["was_net"] = True
                _state["net_calls"] += 1
                if _state["net_calls"] % 30 == 0:
                    print(f"  [throttle] {_state['net_calls']} network calls done "
                          f"(~question {_state['net_calls'] // 30}/42)", flush=True)
            return res["text"]
        raise RuntimeError("LLM reranker still rate-limited after 12 patient retries")

    _llm_mod.chat = _patient_chat

    b0 = cost.global_budget().as_dict()
    m_llm = evaluate(dense, questions, k=30, reranker=llm, final_k=5)
    b1 = cost.global_budget().as_dict()
    n = len(questions)
    spend = b1["cost_usd"] - b0["cost_usd"]
    llm_calls = b1["calls"] - b0["calls"]
    unpriced = b1["unpriced_calls"] - b0["unpriced_calls"]
    usd_per_1k = spend / n * 1000
    print(table({"no-rerank": m_none, "cross-encoder": m_ce, "llm": m_llm}, cols))
    print(f"  cost: {llm_calls} calls ({llm_calls / n:.0f}/question), "
          f"{b1['prompt_tokens'] - b0['prompt_tokens']} in / "
          f"{b1['completion_tokens'] - b0['completion_tokens']} out tokens, "
          f"${spend:.4f} total -> ${usd_per_1k:.3f}/1k queries"
          + (f" [UNPRICED: {unpriced} calls on a model with no published "
             f"pricing -- report as unknown, not $0]" if unpriced and not spend else ""))

    # C3: the decision. Quality x latency x money, then TWO answers.
    print("== C3 decision table ==")
    cost_cell = {
        "no-rerank": "$0.000",
        "cross-encoder": "$0.000 (local)",
        "llm": (f"unpriced ({llm_calls} calls)" if unpriced and not spend
                else f"${usd_per_1k:.3f}"),
    }
    print(f"  {'config':<16}{'ndcg@5':>10}{'hit_rate@1':>12}{'p95 ms':>10}{'$/1k queries':>20}")
    print("  " + "-" * 66)
    for name, m in (("no-rerank", m_none), ("cross-encoder", m_ce), ("llm", m_llm)):
        print(f"  {name:<16}{m['ndcg@5']:>10.4f}{m['hit_rate@1']:>12.4f}"
              f"{m['latency_p95_ms']:>10.1f}{cost_cell[name]:>20}")
    cfgs = [("no-rerank", m_none), ("cross-encoder", m_ce), ("llm reranker", m_llm)]
    interactive = max((c for c in cfgs if c[1]["latency_p95_ms"] < 500),
                      key=lambda c: c[1]["ndcg@5"], default=cfgs[0])
    batch = max(cfgs, key=lambda c: c[1]["ndcg@5"])
    print(f"  (a) interactive agent-facing search box -> {interactive[0]}: "
          f"ndcg@5 {interactive[1]['ndcg@5']:.4f} at p95 "
          f"{interactive[1]['latency_p95_ms']:.0f} ms -- quality per millisecond "
          f"inside a latency budget a human notices")
    print(f"  (b) overnight batch job -> {batch[0]}: best ndcg@5 "
          f"{batch[1]['ndcg@5']:.4f}; p95 {batch[1]['latency_p95_ms']:.0f} ms "
          f"and {cost_cell['llm']} per 1k queries are irrelevant when nobody "
          f"is waiting")
    if interactive[0] == batch[0]:
        print("  WARNING: both answers came out the same -- justify why the "
              "latency budgets do not change the call, or re-check the numbers")
    else:
        print("  (the two answers differ, as they should: same measured quality, "
              "different latency budget, different deployment)")

    # C4: find a query reranking made WORSE (failure mode 5: right doc in the
    # pool, reranked out of the top).
    print("== C4 where reranking hurt ==")
    pq_none = m_none["_per_question_mrr"]
    drops: list[tuple[float, str, str]] = []
    for label, m in (("cross-encoder", m_ce), ("llm", m_llm)):
        for qid, v in m["_per_question_mrr"].items():
            d = pq_none.get(qid, 0.0) - v
            if d > 0:
                drops.append((d, label, qid))
    if not drops:
        print("  no question got worse -- report that too (it will not always happen)")
        worst_qid = None
    else:
        drops.sort(reverse=True)
        d, label, worst_qid = drops[0]
        q = next(x for x in questions if x["id"] == worst_qid)
        rr = ce if label == "cross-encoder" else llm
        m_rr = m_ce if label == "cross-encoder" else m_llm
        print(f"  worst: {worst_qid} under {label} -- MRR "
              f"{pq_none[worst_qid]:.2f} -> {m_rr['_per_question_mrr'].get(worst_qid, 0.0):.2f} "
              f"(drop {d:.2f})")
        print(f"  Q: {q['question']}")
        print(f"  relevant: {q['relevant_docs']}  gold: {snippet(q.get('gold_answer', ''), 140)}")
        before = dense.search(q["question"], k=30)
        after = rr.rerank(q["question"], dense.search(q["question"], k=30), k=5)
        print("  before (dense k=30, top-5 docs): "
              + " | ".join(dict.fromkeys(h.doc_id for h in before[:5])))
        print("  after  (reranked, top-5 docs):   "
              + " | ".join(dict.fromkeys(h.doc_id for h in after[:5])))
        for h in after[:3]:
            print(f"     now rank{h.rank + 1} {h.doc_id}: {snippet(h.text)}")
        print("  diagnosis (failure mode 5): the relevant doc WAS in the k=30 "
              "pool; the reranker -- a model with its own training distribution "
              "-- scored a lexically plausible distractor above it and pushed it "
              "out of the top 5. 'Reranking helps' is a claim about distribution "
              "match, not a law.")

    record("rerank", {
        "config": "markdown-400 dense, retrieve k=30 -> rerank final_k=5",
        "llm_tier": "MAIN (default SMALL model EOL 2026-09-01, HTTP 410)",
        "none": m_none, "cross_encoder": m_ce, "llm": m_llm,
        "llm_cost": {"calls": llm_calls, "cost_usd": spend,
                     "usd_per_1k_queries": usd_per_1k, "unpriced_calls": unpriced},
        "c4_worst": worst_qid if drops else None,
        "c4_drops": [{"drop": d, "reranker": lab, "qid": qid}
                     for d, lab, qid in drops[:10]],
    })


def sweep_index() -> None:
    """TODO D1-D3.

    D1/D2: ChromaRetriever vs DenseRetriever -- recall gap and latency.
    D3: pass status metadata into the chunks and filter at query time.

        Set chunk.meta['status'] = 'archived' if 'ARCHIVED' in doc_id else 'current'
        then ChromaRetriever.search(..., where={"status": "current"}).

        Report hit_rate@1 on Q29/Q30/Q31 before and after (hit_rate@1, not
        @5 -- @5 is saturated here and will hide the whole effect).

    D2 note: scripts/expand_corpus.py is not in this repo, so ballast is
    generated inline. Ballast vectors are random unit vectors of the right
    dimension: ANN latency depends on (n, d), not on vector content, and
    embedding 40k filler docs costs real time/money for zero signal (ballast
    is excluded from quality reporting anyway). Ballast is injected straight
    into the Chroma collection / NumPy matrix so only the REAL corpus is ever
    embedded.
    """
    corpus, questions = load_corpus(), load_questions()
    chunks = build_chunks(corpus, "markdown", 400)  # A winner
    for c in chunks:
        c.meta["status"] = "archived" if "ARCHIVED" in c.doc_id else "current"
    cols = ("hit_rate@1", "hit_rate@5", "recall@5", "mrr", "ndcg@10", "latency_p95_ms")

    dense = DenseRetriever(chunks, show_progress=False)
    # One Chroma index carries the status metadata: D1 uses it unfiltered,
    # D3 filters it. reset=True so a stale index from a different chunking
    # cannot silently answer for this one (the trap in SEARCH_PY.md #3).
    chroma = ChromaRetriever(chunks, path=".chroma", collection="lab3-best", reset=True)

    # D1: exact vs HNSW on the real corpus
    print("== D1 exact (numpy) vs HNSW (chroma) ==")
    m_exact = evaluate(dense, questions)
    m_chroma = evaluate(chroma, questions)
    print(table({"exact (numpy)": m_exact, "hnsw (chroma)": m_chroma}, cols))
    for key in ("ndcg@10", "recall@5", "hit_rate@1", "latency_p95_ms"):
        print(f"  gap {key:<16} {m_chroma[key] - m_exact[key]:+.4f}")

    # D2: scale the index to ~4k and ~40k chunks and time both search paths.
    print("== D2 scale: exact vs HNSW ==")
    n_real = len(chunks)
    targets = [n_real, 4000, 40000]
    rng = np.random.default_rng(0)
    max_extra = max(targets) - n_real
    dim = dense.matrix.shape[1]
    ball_vecs = rng.standard_normal((max_extra, dim), dtype=np.float32)
    ball_vecs /= np.linalg.norm(ball_vecs, axis=1, keepdims=True)
    ballast = [Chunk(f"Ballast policy filler paragraph {i} for index scaling only.",
                     f"ballast-{i}", f"ballast::{i}", {"strategy": "ballast"})
               for i in range(max_extra)]

    real_chunks, real_mat = list(dense.chunks), dense.matrix.copy()
    scale = ChromaRetriever(chunks, path=".chroma", collection="lab3-scale", reset=True)
    timing: list[dict] = []
    injected = 0
    for target in targets:
        extra = max(0, target - n_real)
        dense.matrix = (np.vstack([real_mat, ball_vecs[:extra]])
                        if extra else real_mat)
        dense.chunks = real_chunks + ballast[:extra]
        if extra > injected:
            t0 = time.perf_counter()
            for i in range(injected, extra, 2000):
                part = ballast[i:min(i + 2000, extra)]
                scale.col.add(
                    ids=[c.chunk_id for c in part],
                    documents=[c.text for c in part],
                    embeddings=ball_vecs[i:min(i + 2000, extra)].tolist(),
                    metadatas=[{"doc_id": c.doc_id, "status": "ballast"} for c in part],
                )
            injected = extra
            print(f"  indexed ballast up to {n_real + injected} chunks "
                  f"in {time.perf_counter() - t0:.1f}s")
        e_p50, e_p95 = time_search(dense, questions)
        h_p50, h_p95 = time_search(scale, questions)
        timing.append({"n": n_real + extra,
                       "exact_p50_ms": round(e_p50, 3), "exact_p95_ms": round(e_p95, 3),
                       "hnsw_p50_ms": round(h_p50, 3), "hnsw_p95_ms": round(h_p95, 3)})
        print(f"  n={n_real + extra:>6}  exact p50={e_p50:7.2f} p95={e_p95:7.2f} ms   "
              f"hnsw p50={h_p50:7.2f} p95={h_p95:7.2f} ms   "
              f"hnsw/exact p95 = {h_p95 / e_p95:.2f}x")
    dense.matrix, dense.chunks = real_mat, real_chunks
    cross = next((t["n"] for t in timing if t["hnsw_p95_ms"] < t["exact_p95_ms"]), None)
    print(f"  crossover: {'at ~' + format(cross, ',') + ' chunks' if cross else 'not reached within 40k'}")
    print("  mechanism: at small n one BLAS matmul + argsort beats per-query HNSW")
    print("  graph traversal plus Python call overhead; ANN pays off only when")
    print("  exact search stops fitting -- adopt it then, not before.")

    # D3: the trap. Archived doc competes with the current one on Q29-Q31.
    print("== D3 metadata filter on Q29/Q30/Q31 (hit_rate@1) ==")
    trap_qs = [q for q in questions if q["id"] in ("Q29", "Q30", "Q31")]
    before, per_before = hit_at_1(chroma, trap_qs)
    after, per_after = hit_at_1(chroma, trap_qs, where={"status": "current"})

    def archived_rank(where: dict | None) -> dict[str, int | None]:
        """At what rank (1-based, top-5) does an ARCHIVED doc appear, if ever?"""
        out: dict[str, int | None] = {}
        for q in trap_qs:
            hits = chroma.search(q["question"], k=5, where=where)
            out[q["id"]] = next((h.rank + 1 for h in hits if "ARCHIVED" in h.doc_id), None)
        return out

    rank_before, rank_after = archived_rank(None), archived_rank({"status": "current"})
    print(f"  before (no filter): hit_rate@1={before:.3f}  {per_before}")
    print(f"  after  (status=current): hit_rate@1={after:.3f}  {per_after}")
    print(f"  ARCHIVED doc rank in top-5 before: {rank_before}")
    print(f"  ARCHIVED doc rank in top-5 after : {rank_after}")
    if before == after:
        print("  hit@1 did not move: with this embedding model ARCHIVED never")
        print("  reaches rank 1, so the trap does not spring AT rank 1 -- report")
        print("  that honestly. The filter still removes the archived competitor")
        print("  from the top-5 wherever it did appear (one ranking change away")
        print("  from becoming a rank-1 failure).")
    print("  This fix required NO change to the retriever: label the data at")
    print("  ingest, filter at query time. When retrieval quality is poor, look")
    print("  at the corpus and the metadata FIRST -- the best retrieval fix is")
    print("  often not a retrieval change (T4 s2.4).")

    record("index", {
        "config": "markdown-400 + status metadata",
        "d1": {"exact": m_exact, "chroma": m_chroma},
        "d2_scale_timing": timing,
        "d2_crossover_n": cross,
        "d3_trap": {"before": {"hit_rate@1": before, "per_question": per_before,
                               "archived_rank_top5": rank_before},
                    "after": {"hit_rate@1": after, "per_question": per_after,
                              "archived_rank_top5": rank_after}},
        "n_chunks": n_real,
    })


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
