#!/usr/bin/env python3
"""Lab 5 -- run one arm of the pipeline over the 45 golden questions.

    python labs/lab5/run_eval.py --variant v1  --save reports/lab5_v1.json
    python labs/lab5/run_eval.py --variant v2a --save reports/lab5_v2a.json
    python labs/lab5/run_eval.py --variant v2b --save reports/lab5_v2b.json

Same questions, same judges (LARGE tier, unchanged from Lab 4), same
validation contract as labs/lab4/evaluate.py -- so a difference in the numbers
is a difference in the pipeline, not in the measuring instrument.

Saves incrementally: a run that dies at Q30 resumes at Q31.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from aip import cost as cost_mod
from aip.evals import retrieval_metrics
from labs.lab3.search import load_questions
from labs.lab4.evaluate import (  # judges, imported unchanged from Lab 4
    _safe_judge,
    build_retriever,
    judge_correctness,
    judge_faithfulness,
)
from labs.lab5 import pipeline


def stage1_metrics(questions: list[dict], retriever, k: int = 10) -> dict:
    """Dense stage-1 metrics. Identical across arms by construction -- printed
    every run to PROVE the arms share a stage 1, not to claim an improvement."""
    agg: dict[str, list[float]] = {}
    for q in questions:
        if not q["relevant_docs"]:
            continue
        hits = retriever.search(q["question"], k=k)
        ranked = list(dict.fromkeys(h.doc_id for h in hits))
        for key, val in retrieval_metrics(ranked, q["relevant_docs"],
                                          ks=(1, 3, 5, 10)).items():
            agg.setdefault(key, []).append(val)
    return {k: statistics.fmean(v) for k, v in sorted(agg.items())}


def run(variant: str, questions: list[dict], retriever, save: str,
        limit: int = 0) -> list[dict]:
    path = ROOT / save
    rows: list[dict] = []
    done: set[str] = set()
    if path.exists():
        try:
            rows = json.loads(path.read_text(encoding="utf-8"))
            done = {r["id"] for r in rows}
            print(f"resuming: {len(done)} rows already in {save}", flush=True)
        except Exception:  # noqa: BLE001 - corrupt partial -> start clean
            rows, done = [], set()

    todo = [q for q in questions if q["id"] not in done]
    if limit:
        todo = todo[:limit]
    pipeline.activate(variant)

    b0 = cost_mod.global_budget().as_dict()
    lat: list[float] = []
    for i, q in enumerate(todo, 1):
        t0 = time.perf_counter()
        try:
            a = pipeline.answer(q["question"], retriever, variant=variant)
            dt = (time.perf_counter() - t0) * 1000
            lat.append(dt)
            from aip.retrieval import format_context
            ctx = format_context(a.hits)
            row = {
                "id": q["id"], "kind": q["kind"],
                "unanswerable": (not q["relevant_docs"]
                                 or q["kind"] == "unanswerable"),
                "answer": a.text, "refused": a.refused,
                "citations_valid": a.citations_valid,
                "invalid_citations": a.invalid_citations,
                "repaired": a.repaired,
                "n_citations": a.n_citations,
                "answer_chars": len(a.text),
                "faithfulness": _safe_judge(judge_faithfulness, a.text, ctx),
                "correctness": _safe_judge(
                    judge_correctness, q["question"], a.text, q["gold_answer"]),
                "retrieved": [h.doc_id for h in a.hits],
                "relevant": q["relevant_docs"],
                "gen_latency_ms": round(dt, 1),
            }
        except Exception as exc:  # noqa: BLE001 - one dead question != dead run
            print(f"  {q['id']} ERROR {type(exc).__name__}: {exc}", flush=True)
            row = {
                "id": q["id"], "kind": q["kind"],
                "unanswerable": (not q["relevant_docs"]
                                 or q["kind"] == "unanswerable"),
                "answer": f"[run failed: {type(exc).__name__}]",
                "refused": False, "citations_valid": False,
                "invalid_citations": [], "repaired": False, "n_citations": 0,
                "answer_chars": 0,
                "faithfulness": None, "correctness": None,
                "retrieved": [], "relevant": q["relevant_docs"],
                "gen_latency_ms": None, "error": str(exc)[:200],
            }
        rows.append(row)
        print(f"  {q['id']} {i}/{len(todo)}  corr={row['correctness']} "
              f"faith={row['faithfulness']} {row['gen_latency_ms']}ms", flush=True)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(rows, indent=2, ensure_ascii=False),
                        encoding="utf-8")
    b1 = cost_mod.global_budget().as_dict()

    meta = {
        "variant": variant,
        "pipeline": {
            **pipeline.VARIANTS[variant],
            # Read the prompt off the system actually sent, not off the flag.
            # When these two disagreed, v2a silently ran v1's prompt and every
            # number came back identical -- the flag would have said
            # "completeness: true" and the run would have been a no-op.
            "system": ("lab4 ANSWER_SYSTEM (imported, unmodified)"
                       if pipeline.SYSTEMS[variant] is pipeline.ANSWER_SYSTEM
                       else "lab5 ANSWER_SYSTEM_V2 (completeness clause)"),
        },
        "stage1": stage1_metrics(questions, retriever),
        "cost": {
            "calls": b1["calls"] - b0["calls"],
            "prompt_tokens": b1["prompt_tokens"] - b0["prompt_tokens"],
            "completion_tokens": b1["completion_tokens"] - b0["completion_tokens"],
            "cost_usd": round(b1["cost_usd"] - b0["cost_usd"], 6),
            "unpriced_calls": b1["unpriced_calls"] - b0["unpriced_calls"],
        },
        "gen_latency_ms": {
            "p50": round(statistics.median(lat), 1) if lat else None,
            "p95": round(sorted(lat)[int(0.95 * (len(lat) - 1))], 1) if lat else None,
        },
        "throttle_waits": pipeline._PATIENT["waits"],
    }
    path.with_suffix(".meta.json").write_text(
        json.dumps(meta, indent=2), encoding="utf-8")
    return rows


def summarise(rows: list[dict], meta: dict) -> None:
    ans = [r for r in rows if not r["unanswerable"]]
    una = [r for r in rows if r["unanswerable"]]
    refusals = [r for r in rows if r["refused"]]

    def mean(vals):
        vals = [v for v in vals if v is not None]
        return statistics.fmean(vals) if vals else None

    corr = mean([r["correctness"] for r in ans])
    faith = mean([r["faithfulness"] for r in rows])
    cov, ndoc = [], []
    for r in rows:
        rel = set(r["relevant"])
        got = list(dict.fromkeys(r["retrieved"]))
        ndoc.append(len(got))
        if rel:
            cov.append(len(rel & set(got)) / len(rel))
    c = meta["cost"]
    n = len(rows) or 1
    print(f"\n=== {meta['variant']} ===")
    print(f"n = {len(rows)}  ({len(ans)} answerable, {len(una)} unanswerable)")
    print(f"correctness (0-2)   {corr:.3f}  normalised {corr / 2:.3f}"
          if corr is not None else "correctness n/a")
    print(f"faithfulness        {faith:.3f}   (excluded judge parse failures: "
          f"{sum(1 for r in rows if r['faithfulness'] is None)})")
    print(f"citation validity   "
          f"{statistics.fmean(r['citations_valid'] for r in rows):.3f}   (target 1.000)")
    print(f"repair rate         {statistics.fmean(r['repaired'] for r in rows):.3f}")
    rec = (sum(1 for r in una if r["refused"]) / len(una)) if una else 0.0
    prec = (sum(1 for r in refusals if r["unanswerable"]) / len(refusals)) if refusals else 1.0
    print(f"refusal recall      {rec:.3f}   ({sum(1 for r in una if r['refused'])}/{len(una)})")
    print(f"refusal precision   {prec:.3f}   ({len(refusals)} refusals total)")
    print(f"gold-doc coverage   {statistics.fmean(cov):.3f}   "
          f"mean distinct docs in window {statistics.fmean(ndoc):.2f}")
    s1 = meta["stage1"]
    print(f"stage-1 ndcg@10     {s1['ndcg@10']:.3f}   recall@5 {s1['recall@5']:.3f}   "
          f"mrr {s1['mrr']:.3f}")
    print(f"cost                {c['calls']} calls ({c['calls'] / n:.2f}/q), "
          f"{(c['prompt_tokens'] + c['completion_tokens']) / n:.0f} tokens/q "
          f"({c['prompt_tokens'] / n:.0f} in / {c['completion_tokens'] / n:.0f} out), "
          f"${c['cost_usd']:.4f}"
          + (f" + {c['unpriced_calls']} UNPRICED calls" if c["unpriced_calls"] else ""))
    lat = meta["gen_latency_ms"]
    print(f"gen latency         p50 {lat['p50']} ms / p95 {lat['p95']} ms")

    print("\nby question kind (mean correctness / 2):")
    for kind in sorted({r["kind"] for r in ans}):
        sub = [r for r in ans if r["kind"] == kind]
        m = mean([r["correctness"] for r in sub])
        if m is not None:
            print(f"  {kind:<16} {m / 2:.3f}  n={len(sub)}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", required=True, choices=list(pipeline.VARIANTS))
    ap.add_argument("--save", required=True)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    pipeline.harden_transport()
    questions = load_questions(include_unanswerable=True)
    retriever = build_retriever()
    rows = run(args.variant, questions, retriever, args.save, args.limit)
    meta = json.loads((ROOT / args.save).with_suffix(".meta.json")
                      .read_text(encoding="utf-8"))
    summarise(rows, meta)
    print(f"\nsaved -> {ROOT / args.save}")


if __name__ == "__main__":
    main()
