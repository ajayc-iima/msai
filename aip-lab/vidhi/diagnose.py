#!/usr/bin/env python3
"""Vidhi Lab5 diagnose: classify every golden failure into exactly one mode.

    python -m vidhi.diagnose
    python -m vidhi.diagnose --save reports/vidhi_diagnosis.json

Modes (Vidhi-adapted 7):
 1 missing_content      WARN_NO_DATA, 0 verified rows for survey+indicator
 2 metadata_block       WARN_METADATA_* (unsupported disagg/unknown)
 3 comparability_block  WARN/REFUSE comparability (HCES break, revamp, status mix)
 4 numeric_mismatch     WARN_NUMERIC_MISMATCH (true user-figure error)
 5 consistency_fp       firewall PASS but pipeline WARN (retrieval/consistency)
 6 scope_refuse         REFUSE_* (forecast/causal/political/microdata/safety)
 7 presentation         PASS verdict but citations invalid
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter
from pathlib import Path

os.environ.setdefault("AIP_OFFLINE", "1")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

MODES = {
    1: "missing_content",
    2: "metadata_block",
    3: "comparability_block",
    4: "numeric_mismatch",
    5: "consistency_fp",
    6: "scope_refuse",
    7: "presentation",
}


def classify(g: dict, out: dict, fw_verdict) -> tuple[int, str]:
    dec, reason = out.get("decision"), out.get("reason_code", "")
    fw_dec = fw_verdict.decision if fw_verdict is not None else None
    # 7: right verdict, wrong citations
    if dec == g["expected_verdict"] and not out.get("citations_valid", True):
        return 7, f"correct {dec} but invalid citations {out.get('invalid_citations')}"
    if dec == g["expected_verdict"]:
        return 0, "no failure"
    # 5: firewall PASS but pipeline WARN -> consistency/retrieval FP
    if fw_dec == "PASS" and dec == "WARN" and reason == "R_NUMERIC_MISMATCH":
        return 5, "firewall PASS downgraded by consistency; check activity/round attribution"
    if reason in ("R_COMPARABILITY_HCES_METHOD", "R_COMPARABILITY_PLFS_REVAMP",
                  "R_COMPARABILITY_EUS_PLFS", "R_COMPARABILITY_STATUS_MIX",
                  "R_FORECAST", "R_CAUSAL", "R_POLITICAL", "R_MICRODATA",
                  "R_PROMPT_INJECTION", "R_SCOPE_OUT"):
        if dec == "REFUSE":
            return 6, f"scope/safety refuse {reason}"
        return 3, f"comparability block {reason}"
    if reason and reason.startswith("R_METADATA"):
        return 2, f"metadata block {reason}"
    if reason == "R_NO_CURATED_ROW":
        return 1, "no verified row for slice; coverage limit not logic"
    if reason == "R_NUMERIC_MISMATCH":
        return 4, "user figure disagrees with official table"
    if reason == "R_LOW_EXTRACTION_CONF":
        return 2, "low extraction confidence; translator limit"
    return 6, f"unclassified {dec}/{reason}"


def pareto(tally: Counter) -> str:
    total = sum(tally.values()) or 1
    lines = ["failure mode            n  share  cumul"]
    cum = 0
    for mode, n in tally.most_common():
        cum += n
        bar = "#" * round(24 * n / total)
        lines.append(f"{MODES.get(mode, str(mode)):22} {n:3} {n/total:5.1%} {cum/total:5.1%} {bar}")
    return "\n".join(lines)


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--save", default="reports/vidhi_diagnosis.json")
    args = ap.parse_args()

    from vidhi import pipeline as P
    from vidhi.claims import extract
    from vidhi.rules import Firewall

    gold = [json.loads(l) for l in (ROOT / "evaluation" / "vidhi_golden.jsonl").open(encoding="utf-8") if l.strip()]
    fw = Firewall()
    tally: Counter = Counter()
    recs = []
    P._EXACT.clear()
    for g in gold:
        # fresh firewall verdict (no retrieval) vs pipeline (with retrieval)
        c = extract(g["question"])
        try:
            fv = fw.adjudicate(c)
        except Exception:
            fv = None
        out = P.ask(g["question"])
        if out.get("decision") == g["expected_verdict"] and out.get("reason_code") == g.get("expected_reason_code"):
            continue
        mode, ev = classify(g, out, fv)
        if mode == 0:
            continue
        tally[mode] += 1
        recs.append({"qid": g["qid"], "question": g["question"], "expected": f"{g['expected_verdict']}/{g.get('expected_reason_code')}",
                     "got": f"{out.get('decision')}/{out.get('reason_code')}",
                     "fw": f"{fv.decision}/{fv.reason_code}" if fv else "err",
                     "mode": mode, "mode_name": MODES[mode], "evidence": ev})
        print(f"  {g['qid']:<5} {MODES[mode]:22} {ev}")

    print(f"\n{len(recs)} failures / {len(gold)}")
    print(pareto(tally) if tally else "(no failures)")
    # EV ranking: n x recovery likelihood (heuristic) vs effort
    print("\nEV rank (n x p_recover / effort):")
    effort = {1: "M (add rows+parsers)", 2: "S (taxonomy)", 3: "S (YAML quotes)",
              4: "S (already correct)", 5: "S (consistency guard)", 6: "S (scope correct)", 7: "S (render)"}
    for mode, n in tally.most_common():
        print(f"  mode {mode} {MODES[mode]}: n={n} effort={effort.get(mode)}")
    if args.save:
        p = ROOT / args.save
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"n": len(gold), "failures": recs, "tally": {MODES[m]: tally[m] for m in tally}}, indent=2), encoding="utf-8")
        print(f"\nsaved -> {p}")
    return 0 if not tally else 1


if __name__ == "__main__":
    sys.exit(main())
