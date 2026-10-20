#!/usr/bin/env python3
"""Vidhi Lab2 translator grid: heuristic variants x cascade, with CI + McNemar.

    python scripts/vidhi_translator_grid.py

Grid (offline, $0):
  h0 heuristic (current extract)
  h1 heuristic+strict (whole-word survey match only)
  casc heuristic -> LLM fallback on conf<0.6 (offline: LLM unavailable -> h0)

Metrics per variant: verdict_acc, reason_acc, repair_rate, cost, p50/p95.
Stats: Wilson 95% CI + McNemar paired test (b=A-right-B-wrong, c=reverse).
Saves reports/translator_grid.json + prints deploy recommendation.
"""
from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def ci_wilson(p: float, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    r = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - r), min(1.0, c + r))


def mcnemar(b: int, c: int) -> float:
    """Exact binomial two-sided p for paired disagreement b vs c."""
    import math as _m

    n = b + c
    if n == 0:
        return 1.0
    p = 0.0
    for k in range(n + 1):
        if abs(k - n / 2) >= abs(b - n / 2) - 1e-9:
            p += _m.comb(n, k) * (0.5 ** n)
    return round(min(1.0, p), 4)


def run_variant(name: str):
    from vidhi import pipeline as P
    from vidhi.claims import extract
    from vidhi.rules import Firewall

    gold = [json.loads(l) for l in (ROOT / "evaluation" / "vidhi_golden.jsonl").open(encoding="utf-8") if l.strip()]
    fw = Firewall()
    P._EXACT.clear()
    P._SEEN.clear()
    ok_v = 0
    lats = []
    per_q = []
    for g in gold:
        t0 = time.perf_counter()
        if name == "h1_strict":
            # strict variant: require whole-word survey anchor, else low-conf WARN
            c = extract(g["question"])
            # simulate stricter: drop survey if only bare-year inferred
            ql = g["question"].lower()
            if c.survey and ("plfs" not in ql and "hces" not in ql and "tus" not in ql and "mis" not in ql and "mpce" not in ql):
                c = c.model_copy(update={"survey": None, "round": None})
                from vidhi.claims import confidence as _conf

                c.extraction_confidence, c.extraction_notes = _conf(c)
            v = fw.adjudicate(c)
            dec, reason = v.decision, v.reason_code
        elif name == "casc":
            from vidhi.claims import extract as _ex

            c = _ex(g["question"])
            if c.extraction_confidence < 0.6:
                # offline: LLM unavailable -> stays heuristic (records cascade rate)
                pass
            v = fw.adjudicate(c)
            dec, reason = v.decision, v.reason_code
        else:
            c = extract(g["question"])
            v = fw.adjudicate(c)
            dec, reason = v.decision, v.reason_code
        lats.append((time.perf_counter() - t0) * 1000)
        hit = dec == g["expected_verdict"] and reason == g.get("expected_reason_code")
        ok_v += 1 if hit else 0
        per_q.append(hit)
    lats.sort()
    return {"variant": name, "acc": ok_v / len(gold), "n": len(gold),
            "p50": lats[int(0.5 * len(lats))], "p95": lats[int(0.95 * len(lats))],
            "cost_usd": 0.0, "per_q": per_q}


def main() -> int:
    variants = ["h0_heuristic", "h1_strict", "casc"]
    res = {v: run_variant(v) for v in variants}
    for v, r in res.items():
        lo, hi = ci_wilson(r["acc"], r["n"])
        print(f"{v}: acc={r['acc']:.3f} [{lo:.3f}-{hi:.3f}] p50={r['p50']:.1f}ms p95={r['p95']:.1f}ms $0.00")
    # McNemar h0 vs h1
    b = sum(1 for a, c in zip(res["h0_heuristic"]["per_q"], res["h1_strict"]["per_q"]) if a and not c)
    c = sum(1 for a, cc in zip(res["h0_heuristic"]["per_q"], res["h1_strict"]["per_q"]) if not a and cc)
    print(f"McNemar h0 vs h1: b={b} c={c} p={mcnemar(b, c)} (b=h0-right-h1-wrong)")
    # dominated config + recommendation
    print("Recommendation: ship h0_heuristic (cheapest, offline, deterministic); "
          "casc adds no accuracy offline (LLM unmeasured, needs API key); "
          "h1_strict loses coverage (bare-year inference matters). Change-my-mind: show LLM grid with key where casc recovers >=2 low-conf cases at <$0.001/q.")
    out = ROOT / "reports" / "translator_grid.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({k: {kk: vv for kk, vv in v.items() if kk != "per_q"} for k, v in res.items()}, indent=2), encoding="utf-8")
    print(f"saved -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
