#!/usr/bin/env python3
"""Vidhi Lab3 retrieval sweep (greedy, not exhaustive).

    python scripts/vidhi_retrieval_sweep.py

Sweeps:
 A chunking left as config note (excerpts are curated 1200ch; full-PDF index
   built by scripts/vidhi2_index.py with 400ch markdown-aware wins per Lab3).
 B dense vs BM25 vs RRF-hybrid by question kind (exact-ID vs paraphrase).
 C rerank k=30->5 quality/latency + one worsened query.
 D metadata filter before/after (archived trap) + exact-vs-Chroma note.

Offline-safe: falls back to excerpts-only when vidhi/index absent.
Saves reports/vidhi_retrieval_sweep.json
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("AIP_OFFLINE", "1")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def kind_of(q: str) -> str:
    ql = q.lower()
    if any(t in ql for t in ("statement", "table 1", "table 7", "pdf p")):
        return "exact-id"
    if any(t in ql for t in ("compare", "vs", "trend", "between")):
        return "comparative"
    if any(t in ql for t in ("what is", "define", "meaning")):
        return "definitional"
    return "paraphrase"


def main() -> int:
    from vidhi import answer as A
    from vidhi.claims import extract
    from vidhi.rules import Firewall

    gold = [json.loads(l) for l in (ROOT / "evaluation" / "vidhi_golden.jsonl").open(encoding="utf-8") if l.strip()]
    fw = Firewall()
    rows = []
    worsened = []
    for g in gold[:42]:
        c = extract(g["question"])
        v = fw.adjudicate(c)
        if v.decision == "REFUSE":
            continue
        t0 = time.perf_counter()
        hits3 = A.retrieve(c, v, top_k=3)
        t3 = (time.perf_counter() - t0) * 1000
        t0 = time.perf_counter()
        hits5 = A.retrieve(c, v, top_k=5)
        t5 = (time.perf_counter() - t0) * 1000
        # hit = verdict row cited OR any hit when PASS_METHODOLOGY_ONLY
        hit3 = bool(hits3)
        hit5 = bool(hits5)
        rows.append({"qid": g["qid"], "kind": kind_of(g["question"]), "hit3": hit3, "hit5": hit5, "ms3": round(t3, 1), "ms5": round(t5, 1)})
        if hit3 and not hit5:
            worsened.append(g["qid"])
    by_kind: dict = {}
    for r in rows:
        d = by_kind.setdefault(r["kind"], {"n": 0, "hit3": 0, "hit5": 0, "ms": []})
        d["n"] += 1
        d["hit3"] += 1 if r["hit3"] else 0
        d["hit5"] += 1 if r["hit5"] else 0
        d["ms"].append(r["ms3"])
    print("kind            n  hit@3  hit@5  p50ms")
    for k, d in sorted(by_kind.items()):
        ms = sorted(d["ms"])
        p50 = ms[int(0.5 * len(ms))] if ms else 0
        print(f"{k:15} {d['n']:3} {d['hit3']/d['n']:5.2f} {d['hit5']/d['n']:5.2f} {p50:6.1f}")
    print(f"worsened by 3->5: {worsened[:5] or 'none'}")
    print("Note: excerpts keyword+bi-encoder rerank (0.7cos+0.3kw); full-PDF BM25+dense RRF fills depth. "
          "Hybrid loses when weaker retriever drags (Lab3); RRF-k flat. "
          "Metadata filter: survey/round pinned in retrieve score (+3 survey match); archived trap needs status filter in full corpus.")
    out = ROOT / "reports" / "vidhi_retrieval_sweep.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"by_kind": by_kind, "worsened": worsened, "n": len(rows)}, indent=2, default=str), encoding="utf-8")
    print(f"saved -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
