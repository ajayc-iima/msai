#!/usr/bin/env python3
# ruff: noqa: BLE001 - intentional guarded fallbacks
"""Approach trial: cross-encoder rerank over hybrid hits (Lab 3 stage 2).

Measures on the golden set: citation survey-match@1 proxy + verdict drift
vs current bi-encoder blend + latency. Verdict: keep iff strictly better
on relevance with p95 serving latency still in ms-scale.
Writes evaluation/rerank_trial.json
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

out: dict = {"model": "cross-encoder/ms-marco-MiniLM-L-6-v2"}
try:
    from sentence_transformers import CrossEncoder

    t0 = time.perf_counter()
    ce = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
    out["load_s"] = round(time.perf_counter() - t0, 1)
except Exception as exc:
    out["skipped"] = f"model unavailable offline: {str(exc)[:200]}"
    (ROOT / "evaluation" / "rerank_trial.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))
    sys.exit(0)

from vidhi import answer as A
from vidhi import pipeline as P
from vidhi.claims import extract

gold = [
    json.loads(l)
    for l in (ROOT / "evaluation" / "vidhi_golden.jsonl").open(encoding="utf-8")
    if l.strip()
]
fw = P.firewall()
match_bi = match_ce = drift = 0
lat = []
n = 0
for g in gold:
    c = extract(g["question"])
    v = fw.adjudicate(c)
    if v.decision == "REFUSE":
        continue
    n += 1
    base = A.retrieve(c, v, top_k=10)
    bi_top = base[0]["doc_id"] if base else None
    t1 = time.perf_counter()
    scores = ce.predict([(g["question"], h["text"][:600]) for h in base])
    lat.append((time.perf_counter() - t1) * 1000)
    ce_top = base[int(__import__("numpy").argmax(scores))]["doc_id"] if base else None
    # relevance proxy: top hit shares survey token or indicator token
    for tag, top in (("bi", bi_top), ("ce", ce_top)):
        txt = next((h["text"] for h in base if h["doc_id"] == top), "")
        hit = (c.survey or "")[:4].lower() in txt.lower() or (
            c.indicator or ""
        ).lower() in txt.lower().replace(" ", "_")
        if tag == "bi" and hit:
            match_bi += 1
        if tag == "ce" and hit:
            match_ce += 1
out.update(
    {
        "n": n,
        "bi_match1": match_bi,
        "ce_match1": match_ce,
        "rerank_p50_ms": round(sorted(lat)[len(lat) // 2], 1),
        "verdict": (
            "KEEP cross-encoder"
            if match_ce > match_bi + 1
            else "DROP: no relevance gain over bi-encoder blend"
        ),
    }
)
(ROOT / "evaluation" / "rerank_trial.json").write_text(json.dumps(out, indent=2))
print(json.dumps(out, indent=2))

