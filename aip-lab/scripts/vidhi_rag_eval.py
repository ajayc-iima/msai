#!/usr/bin/env python3
"""Vidhi Lab4 RAG eval: refusal both-directions x2 strictness + gold-vs-retrieved.

    python scripts/vidhi_rag_eval.py

- Refusal table at strict + lenient (lenient counts WARN_COMPARABILITY as refuse-like).
- E2 decomposition: A=ceiling (firewall alone, no retrieval), B=system (pipeline with
  retrieval+consistency), A-B=retrieval loss, 1-A=generation/firewall loss.
- 10-answer failure tally stub for Lab5 diagnose.
- Judge calibration note: templated answers need no LLM judge; kappa gate applies
  only if VIDHI_USE_LLM polish is enabled (then 20 hand-labels, kappa>=0.4).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("AIP_OFFLINE", "1")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    from vidhi import pipeline as P
    from vidhi.claims import extract
    from vidhi.rules import Firewall

    gold = [json.loads(l) for l in (ROOT / "evaluation" / "vidhi_golden.jsonl").open(encoding="utf-8") if l.strip()]
    fw = Firewall()
    P._EXACT.clear()
    # A = firewall ceiling (no retrieval/consistency)
    a_ok = sum(1 for g in gold if fw.adjudicate(extract(g["question"])).decision == g["expected_verdict"])
    # B = full system
    b_ok = cit_ok = 0
    tp = fp = fn = 0
    tp_len = fp_len = 0
    for g in gold:
        out = P.ask(g["question"])
        if out["decision"] == g["expected_verdict"]:
            b_ok += 1
        if out.get("citations_valid"):
            cit_ok += 1
        is_ref = out["decision"] == "REFUSE"
        exp_ref = g["expected_verdict"] == "REFUSE"
        tp += 1 if (is_ref and exp_ref) else 0
        fp += 1 if (is_ref and not exp_ref) else 0
        fn += 1 if (not is_ref and exp_ref) else 0
        # lenient: WARN_COMPARABILITY counts as refuse-like caution
        is_cau = is_ref or (out["decision"] == "WARN" and "COMPARABILITY" in (out.get("reason_code") or ""))
        exp_cau = exp_ref or (g["expected_verdict"] == "WARN" and "COMPARABILITY" in (g.get("expected_reason_code") or ""))
        tp_len += 1 if (is_cau and exp_cau) else 0
        fp_len += 1 if (is_cau and not exp_cau) else 0
    n = len(gold)
    print(f"A ceiling (firewall): {a_ok}/{n}={a_ok/n:.3f}")
    print(f"B system (pipeline): {b_ok}/{n}={b_ok/n:.3f} citation_valid={cit_ok}/{n}={cit_ok/n:.3f}")
    print(f"retrieval loss A-B={(a_ok-b_ok)/n:+.3f} firewall loss 1-A={(n-a_ok)/n:.3f}")
    prec = tp / (tp + fp) if (tp + fp) else 1.0
    rec = tp / (tp + fn) if (tp + fn) else 1.0
    print(f"refusal strict: tp={tp} fp={fp} fn={fn} prec={prec:.3f} rec={rec:.3f} (n=8 noisy, report counts)")
    print(f"refusal lenient (WARN_COMPARABILITY as caution): tp={tp_len} fp={fp_len}")
    print("Judges: templated render needs no LLM judge (citation validity is code-checked). "
          "If VIDHI_USE_LLM polish enabled: hand-label 20, Cohen kappa>=0.4, fix rubric not model; watch 512-tok truncation scoring parse-fail as 0.")
    outp = ROOT / "reports" / "vidhi_rag_eval.json"
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(json.dumps({"A": a_ok / n, "B": b_ok / n, "citation": cit_ok / n,
                                "refusal": {"tp": tp, "fp": fp, "fn": fn, "prec": prec, "rec": rec}}, indent=2), encoding="utf-8")
    print(f"saved -> {outp}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
