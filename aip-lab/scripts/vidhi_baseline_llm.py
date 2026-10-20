#!/usr/bin/env python3
# ruff: noqa: BLE001 - intentional guarded fallbacks
"""Unconstrained-LLM baseline on the valued golden queries.

Same questions, no firewall: a direct LLM answer. Scores strict numeric
equality against the official table values. This is the honest control
group for 'why not just ask an LLM' -- same items, same extraction.

Limit: numeric-only; it does not score caveats/warnings (that would need
human judgment). Run: python scripts/vidhi_baseline_llm.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    from aip.llm import generate as chat
except ImportError:
    def chat(p, **kw):
        return ""


def first_number(text: str) -> float | None:
    for m in re.finditer(r"[\d,]+(?:\.\d+)?", text):
        try:
            v = float(m.group(0).replace(",", ""))
        except ValueError:
            continue
        if 1900 <= v <= 2100 and v.is_integer():
            continue
        return v
    return None


def main() -> int:
    gold = [
        json.loads(l)
        for l in (ROOT / "evaluation" / "vidhi_golden.jsonl").open(encoding="utf-8")
        if l.strip() and l and json.loads(l).get("expected_value") is not None
    ]
    results = []
    for g in gold:
        try:
            ans = chat(
                "Answer with just the number, no explanation. "
                "Question: " + g["question"],
                max_tokens=60,
                temperature=0.0,
            )
        except Exception as exc:
            results.append({"qid": g["qid"], "error": str(exc)[:120], "match": False})
            continue
        got = first_number(ans)
        match = got is not None and abs(got - float(g["expected_value"])) <= 1e-9
        results.append(
            {
                "qid": g["qid"],
                "expected": g["expected_value"],
                "got": got,
                "raw": ans[:160],
                "match": match,
            }
        )
        print(
            f"{g['qid']}: exp={g['expected_value']} got={got} "
            f"{'MATCH' if match else 'MISS'}"
        )
    n_match = sum(1 for r in results if r["match"])
    print(
        f"\nbaseline numeric match: {n_match}/{len(results)} "
        f"= {n_match / max(len(results), 1):.3f} (firewall: {len(results)}/{len(results)} = 1.000)"
    )
    (ROOT / "evaluation" / "llm_baseline.json").write_text(
        json.dumps(results, indent=2), encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
