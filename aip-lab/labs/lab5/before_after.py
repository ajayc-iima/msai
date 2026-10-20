#!/usr/bin/env python3
"""Lab 5, Part D -- build the before/after table from the arm runs.

    python labs/lab5/before_after.py

Reads reports/lab4.json (the original Lab 4 run) plus every
reports/lab5_<arm>.json, computes the same metric set for each, and writes
reports/lab5_before_after.json.

Every Lab 4 metric appears, not only the one that was targeted, and anything
that got worse is flagged in `regressions` rather than left for the reader to
notice.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from labs.lab5.pipeline import VARIANTS  # noqa: F401 - for the arm table

# metric key -> (higher_is_better, human label)
DIRECTION = {
    "correctness_norm": (True, "correctness (normalised 0-1)"),
    "correctness_raw": (True, "correctness (raw 0-2)"),
    "faithfulness": (True, "faithfulness"),
    "citation_validity": (True, "citation validity"),
    "refusal_recall": (True, "refusal recall"),
    "refusal_precision": (True, "refusal precision"),
    "repair_rate": (None, "repair rate"),
    "gold_doc_coverage": (True, "gold-doc coverage in window"),
    "distinct_docs": (None, "distinct docs in window"),
    "answer_chars": (None, "mean answer chars"),
    "ndcg@10": (True, "nDCG@10 (stage 1)"),
    "recall@5": (True, "recall@5 (stage 1)"),
    "mrr": (True, "MRR (stage 1)"),
    "hit_rate@1": (True, "hit_rate@1 (stage 1)"),
    "calls_per_query": (False, "model calls / query"),
    "tokens_per_query": (False, "tokens / query"),
    "prompt_tokens_per_query": (False, "prompt tokens / query"),
    "completion_tokens_per_query": (False, "completion tokens / query"),
    "latency_p50_ms": (False, "generation p50 (ms)"),
    "latency_p95_ms": (False, "generation p95 (ms)"),
}


def _mean(vals):
    vals = [v for v in vals if v is not None]
    return statistics.fmean(vals) if vals else None


def metrics(rows: list[dict], meta: dict | None) -> dict:
    ans = [r for r in rows if not r["unanswerable"]]
    una = [r for r in rows if r["unanswerable"]]
    refusals = [r for r in rows if r["refused"]]

    corr = _mean([r.get("correctness") for r in ans])
    cov, ndoc, chars = [], [], []
    has_chars = False
    for r in rows:
        got = list(dict.fromkeys(r.get("retrieved") or []))
        ndoc.append(len(got))
        if r.get("answer_chars") is not None:
            has_chars = True
            chars.append(r["answer_chars"])
        rel = set(r.get("relevant") or [])
        if rel:
            cov.append(len(rel & set(got)) / len(rel))

    m: dict = {
        "n": len(rows),
        "n_answerable": len(ans),
        "n_unanswerable": len(una),
        "n_failures": sum(1 for r in ans if (r.get("correctness") or 0) < 2),
        "correctness_raw": corr,
        "correctness_norm": None if corr is None else corr / 2,
        "faithfulness": _mean([r.get("faithfulness") for r in rows]),
        "faithfulness_parse_failures": sum(1 for r in rows
                                           if r.get("faithfulness") is None),
        "citation_validity": statistics.fmean(bool(r["citations_valid"])
                                              for r in rows),
        "repair_rate": statistics.fmean(bool(r["repaired"]) for r in rows),
        "refusal_recall": (sum(1 for r in una if r["refused"]) / len(una)) if una else 0.0,
        "refusal_precision": ((sum(1 for r in refusals if r["unanswerable"])
                               / len(refusals)) if refusals else 1.0),
        "n_refusals": len(refusals),
        "gold_doc_coverage": statistics.fmean(cov) if cov else None,
        "distinct_docs": statistics.fmean(ndoc) if ndoc else None,
        "answer_chars": statistics.fmean(chars) if has_chars else None,
    }
    if meta:
        s1 = meta.get("stage1", {})
        for key in ("ndcg@10", "recall@5", "mrr", "hit_rate@1"):
            m[key] = s1.get(key)
        c = meta.get("cost", {})
        n = len(rows) or 1
        m["calls_per_query"] = c.get("calls", 0) / n
        m["tokens_per_query"] = ((c.get("prompt_tokens", 0)
                                  + c.get("completion_tokens", 0)) / n)
        m["prompt_tokens_per_query"] = c.get("prompt_tokens", 0) / n
        m["completion_tokens_per_query"] = c.get("completion_tokens", 0) / n
        m["cost_usd"] = c.get("cost_usd")
        m["unpriced_calls"] = c.get("unpriced_calls")
        lat = meta.get("gen_latency_ms", {})
        m["latency_p50_ms"] = lat.get("p50")
        m["latency_p95_ms"] = lat.get("p95")
        m["variant"] = meta.get("variant")
        m["pipeline"] = meta.get("pipeline")
    else:
        m["variant"] = "lab4 (as run 2026-09-22)"
        m["note"] = ("no .meta.json: cost and latency were not recorded per arm "
                     "in the Lab 4 run, only in its log")
    return m


def by_kind(rows: list[dict]) -> dict:
    ans = [r for r in rows if not r["unanswerable"]]
    out = {}
    for kind in sorted({r["kind"] for r in ans}):
        m = _mean([r.get("correctness") for r in ans if r["kind"] == kind])
        out[kind] = {"normalised": None if m is None else m / 2,
                     "n": sum(1 for r in ans if r["kind"] == kind)}
    return out


def transitions(base: list[dict], new: list[dict]) -> dict:
    b = {r["id"]: r for r in base}
    gained, lost, same = [], [], []
    for r in new:
        o = b.get(r["id"])
        if not o:
            continue
        bc = (o.get("correctness") if o.get("correctness") is not None else -1)
        nc = (r.get("correctness") if r.get("correctness") is not None else -1)
        if nc > bc:
            gained.append({"id": r["id"], "kind": r["kind"], "from": bc, "to": nc})
        elif nc < bc:
            lost.append({"id": r["id"], "kind": r["kind"], "from": bc, "to": nc,
                         "answer": r["answer"][:300]})
        else:
            same.append(r["id"])
    return {"gained": gained, "lost": lost, "unchanged": same}


def fmt(v) -> str:
    if v is None:
        return "n/a"
    if isinstance(v, float):
        return f"{v:.3f}"
    return str(v)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", nargs="*",
                    default=["lab5_v1", "lab5_v2a", "lab5_v2b"])
    ap.add_argument("--baseline", default="lab5_v1")
    ap.add_argument("--out", default="reports/lab5_before_after.json")
    args = ap.parse_args()

    arms: dict[str, dict] = {}
    lab4 = json.loads((ROOT / "reports/lab4.json").read_text(encoding="utf-8"))
    arms["lab4-original"] = {"metrics": metrics(lab4, None),
                             "by_kind": by_kind(lab4),
                             "rows": lab4}
    for name in args.arms:
        p = ROOT / "reports" / f"{name}.json"
        if not p.exists():
            print(f"[skip] {name}: no run yet")
            continue
        rows = json.loads(p.read_text(encoding="utf-8"))
        mp = (ROOT / "reports" / f"{name}.meta.json")
        meta = json.loads(mp.read_text(encoding="utf-8")) if mp.exists() else None
        # A partially-resumed run is worse than no run: it would compare 6 rows
        # against 45 and report the difference as a result.
        if meta and len(rows) < len(lab4):
            print(f"[skip] {name}: only {len(rows)}/{len(lab4)} questions done")
            continue
        arms[name] = {"metrics": metrics(rows, meta), "by_kind": by_kind(rows),
                      "rows": rows}

    base = args.baseline if args.baseline in arms else "lab4-original"
    out: dict = {"baseline": base, "arms": {}, "before_after": {},
                 "regressions": [], "transitions": {}}

    for name, a in arms.items():
        out["arms"][name] = {"metrics": a["metrics"], "by_kind": a["by_kind"]}

    # The original Lab 4 run is a REFERENCE COLUMN, not a comparison target: it
    # ran on a generator model that has since gone end-of-life, so a delta
    # against it measures the model migration as much as anything we did. It is
    # reported so the drift is visible, never used as the baseline.
    for name, a in arms.items():
        if name == base or name == "lab4-original":
            continue
        bm, am = arms[base]["metrics"], a["metrics"]
        table = {}
        for key, (higher, label) in DIRECTION.items():
            bv, av = bm.get(key), am.get(key)
            delta = None if (bv is None or av is None) else av - bv
            table[key] = {"label": label, "baseline": bv, "arm": av,
                          "delta": delta, "higher_is_better": higher}
        out["before_after"][f"{base} -> {name}"] = table
        out["transitions"][f"{base} -> {name}"] = transitions(arms[base]["rows"],
                                                             a["rows"])
        for key, row in table.items():
            d = row["delta"]
            if d is None or row["higher_is_better"] is None or d == 0:
                continue
            worse = (d < 0) if row["higher_is_better"] else (d > 0)
            if worse:
                out["regressions"].append({"comparison": f"{base} -> {name}",
                                           "metric": key, "label": row["label"],
                                           "baseline": row["baseline"],
                                           "arm": row["arm"], "delta": d})

    p = ROOT / args.out
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

    names = list(arms)
    print(f"\nD1 -- before/after, every Lab 4 metric (baseline = {base})\n")
    w = max(len(DIRECTION[k][1]) for k in DIRECTION) + 1
    hdr = f"{'metric':<{w}}" + "".join(f"{n:>16}" for n in names)
    print(hdr)
    print("-" * len(hdr))
    for key in DIRECTION:
        label = DIRECTION[key][1]
        print(f"{label:<{w}}" + "".join(f"{fmt(arms[n]['metrics'].get(key)):>16}"
                                        for n in names))
    print()
    for name in out["before_after"]:
        gained = out["transitions"][name]["gained"]
        lost = out["transitions"][name]["lost"]
        print(f"{name}: {len(gained)} gained, {len(lost)} lost")
        for g in gained:
            print(f"    + {g['id']:<5} {g['kind']:<14} {g['from']} -> {g['to']}")
        for g in lost:
            print(f"    - {g['id']:<5} {g['kind']:<14} {g['from']} -> {g['to']}")
    if out["regressions"]:
        print("\nD2 -- REGRESSIONS (anything that got worse):")
        for r in out["regressions"]:
            print(f"    {r['comparison']:<28} {r['label']:<32} "
                  f"{r['baseline']} -> {r['arm']}  ({r['delta']:+.3f})")
    else:
        print("\nD2 -- no metric moved in the wrong direction.")
    print(f"\nsaved -> {p}")


if __name__ == "__main__":
    main()
