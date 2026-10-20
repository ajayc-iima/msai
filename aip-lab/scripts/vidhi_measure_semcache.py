#!/usr/bin/env python3
# ruff: noqa: BLE001 - intentional guarded fallbacks
"""Measure the semantic-cache threshold honestly (Lab 7 Part B1).

For each available embedder, computes cosine similarity for:
  * the 5 committed danger pairs (must NEVER collide), and
  * a set of genuine paraphrases (should hit the cache).

Writes evaluation/semcache_thresholds.json. Exit non-zero when no
embedder could be measured. The finding this script exists to check:
is there a cosine threshold that separates dangers from paraphrases?

Known result (2026-10-15): bge-small-en-v1.5 danger max (0.9713) exceeds
paraphrase min (~0.94) -- no pure threshold is safe, the field-guard
carries safety. nemotron-3-embed-1b separates this sample, proving the
threshold is embedder-dependent and must not be trusted alone.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PARAPHRASES = [
    (
        "What was rural MPCE in HCES 2023-24?",
        [
            "Tell me the rural monthly per-capita expenditure for HCES 2023-24.",
            "HCES 2023-24 rural MPCE figure?",
            "Rural average MPCE, 2023-24 round, without imputation.",
        ],
    ),
    (
        "What was all-India LFPR for age 15+ in usual status in PLFS 2025?",
        [
            "PLFS 2025 usual-status LFPR for 15+ at all-India level?",
            "All-India labour force participation, 15 years and above, PLFS 2025.",
        ],
    ),
    (
        "Will unemployment fall in 2027?",
        ["Do you expect joblessness to decline by 2027?"],
    ),
]


def cos(a, b) -> float:
    import numpy as np

    return float(np.asarray(a, dtype=float) @ np.asarray(b, dtype=float))


def measure_bge() -> dict | None:
    try:
        from sentence_transformers import SentenceTransformer

        m = SentenceTransformer("BAAI/bge-small-en-v1.5")
    except Exception as exc:
        return {"embedder": "bge-small-en-v1.5", "skipped": str(exc)}
    return {
        "embedder": "bge-small-en-v1.5 (local, 384-dim)",
        "pairs": _measure(lambda t: m.encode(t, normalize_embeddings=True)),
    }


def measure_nvidia() -> dict | None:
    import os

    if not (os.getenv("NVIDIA_API_KEY") or os.getenv("NVIDIA_NIM_API_KEY")):
        return {"embedder": "nemotron-3-embed-1b", "skipped": "no NVIDIA key"}
    try:
        sys.path.insert(0, str(ROOT))
        from aip.embed import embed_batch

        vecs = {}

        def emb(t: str):
            if t not in vecs:
                vecs[t] = embed_batch(
                    [t],
                    model="nvidia_nim/nvidia/nemotron-3-embed-1b",
                    input_type="query",
                )[0]
            return vecs[t]

        return {
            "embedder": "nemotron-3-embed-1b (NIM, 2048-dim, input_type=query)",
            "pairs": _measure(emb),
        }
    except Exception as exc:
        return {"embedder": "nemotron-3-embed-1b", "skipped": str(exc)[:300]}


def _measure(emb) -> dict:
    danger = [
        json.loads(l)
        for l in (ROOT / "evaluation" / "danger_pairs.jsonl").open(encoding="utf-8")
        if l.strip()
    ]
    d_sims = []
    for d in danger:
        s = cos(emb(d["question_a"]), emb(d["question_b"]))
        d_sims.append({"pair_id": d["pair_id"], "cosine": round(s, 4)})
    p_sims = []
    for base, paras in PARAPHRASES:
        vb = emb(base)
        for p in paras:
            p_sims.append(
                {"paraphrase_of": base[:50], "cosine": round(cos(vb, emb(p)), 4)}
            )
    dmax = max(d["cosine"] for d in d_sims)
    pmin = min(p["cosine"] for p in p_sims)
    return {
        "danger": d_sims,
        "paraphrases": p_sims,
        "danger_max": dmax,
        "paraphrase_min": pmin,
        "separable": pmin > dmax,
        "verdict": (
            f"a threshold in ({dmax}, {pmin}] separates this sample"
            if pmin > dmax
            else "NO threshold separates dangers from paraphrases; "
            "the field-guard must carry safety"
        ),
    }


def main() -> int:
    out = {"bge": measure_bge(), "nvidia": measure_nvidia()}
    n_measured = sum(1 for v in out.values() if v and "pairs" in v)
    dest = ROOT / "evaluation" / "semcache_thresholds.json"
    dest.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2)[:2000])
    print(f"\nwrote {dest} ({n_measured} embedders measured)")
    return 0 if n_measured else 1


if __name__ == "__main__":
    sys.exit(main())
