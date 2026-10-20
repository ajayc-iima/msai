#!/usr/bin/env python3
"""vidhi2 eval: golden verdicts + danger pairs + Safety-B + store audit + latency + cost + coverage.

One command, offline (API paths excluded), non-zero exit on any failure.
"""
from __future__ import annotations

import json
import math
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Eval must be deterministic and offline: no live API calls, no network.
os.environ.setdefault("AIP_OFFLINE", "1")
# Never touch the HF Hub at eval time: use the cached embedding model if
# present, otherwise fall back to keyword-only retrieval. Suppresses the
# "unauthenticated HF request" warning on stderr.
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

from aip import cost
from vidhi import pipeline as P
from vidhi import store as S
from vidhi.claims import compatible, extract
from vidhi.rules import Firewall


def ci(p: float, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score confidence interval for a proportion."""
    if n == 0:
        return (0.0, 0.0)
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    radius = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (centre - radius, centre + radius)


def _prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    p = tp / (tp + fp) if (tp + fp) else 0.0
    r = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * p * r / (p + r) if (p + r) else 0.0
    return p, r, f1


def redteam_metrics() -> tuple[list[str], dict]:
    """Measure Safety-A injection-detection P/R/F1 on the committed red-team set.

    Returns (fails, summary). `fails` is non-empty if any committed injection is
    missed (false negative) or any benign question is flagged (false positive).
    """
    from vidhi.safety import detect_injection

    rows = [
        json.loads(l)
        for l in (ROOT / "evaluation" / "redteam.jsonl").open(encoding="utf-8")
        if l.strip()
    ]
    fails: list[str] = []
    cells: dict[str, dict[str, int]] = {}
    for r in rows:
        lang = r.get("lang", "en")
        flag = detect_injection(r["text"]).flagged
        true = bool(r.get("is_injection"))
        c = cells.setdefault(lang, {"tp": 0, "fp": 0, "fn": 0, "tn": 0})
        if true:
            if flag:
                c["tp"] += 1
            else:
                c["fn"] += 1
                fails.append(f"redteam: missed injection {r['id']} ({lang})")
        else:
            if flag:
                c["fp"] += 1
                fails.append(f"redteam: false positive {r['id']} ({lang})")
            else:
                c["tn"] += 1

    def summarize(c: dict[str, int]) -> dict:
        p, r, f1 = _prf(c["tp"], c["fp"], c["fn"])
        n_inj = c["tp"] + c["fn"]
        n_ben = c["tn"] + c["fp"]
        return {
            "tp": c["tp"], "fp": c["fp"], "fn": c["fn"], "tn": c["tn"],
            "precision": p, "recall": r, "f1": f1,
            "n_injections": n_inj, "n_benign": n_ben,
            "precision_ci": ci(p, c["tp"] + c["fp"]),
            "recall_ci": ci(r, n_inj),
        }

    overall = {
        "tp": sum(c["tp"] for c in cells.values()),
        "fp": sum(c["fp"] for c in cells.values()),
        "fn": sum(c["fn"] for c in cells.values()),
        "tn": sum(c["tn"] for c in cells.values()),
    }
    summary = {"overall": summarize(overall), "by_lang": {k: summarize(v) for k, v in sorted(cells.items())}}
    return fails, summary


def main() -> int:
    fails: list[str] = []
    gold = [
        json.loads(l)
        for l in (ROOT / "evaluation" / "vidhi_golden.jsonl").open(encoding="utf-8")
        if l.strip()
    ]
    danger = [
        json.loads(l)
        for l in (ROOT / "evaluation" / "danger_pairs.jsonl").open(encoding="utf-8")
        if l.strip()
    ]

    # ---- Golden battery ---------------------------------------------------
    t0 = time.perf_counter()
    spent_start = cost.global_budget().spent_usd
    ok_v = ok_n = ok_r = ok_c = 0
    latencies: list[float] = []
    stage_counts: dict[str, int] = {}
    decision_counts: dict[str, int] = {}
    warn_no_data: int = 0
    # Abstention confusion matrix (AUCM-style): does Vidhi answer when it should
    # and refuse when it must? "hallucinate" = answer a must-abstain question.
    abst = {"answerable": 0, "must_abstain": 0, "tp_answer": 0,
            "tn_abstain": 0, "fp_halluc": 0, "fn_refuse": 0}
    touched_row_ids: set[str] = set()
    survey_counts: dict[str, int] = {}
    fw = Firewall()

    for g in gold:
        q_t0 = time.perf_counter()
        out = P.ask(g["question"])
        q_t1 = time.perf_counter()
        latencies.append((q_t1 - q_t0) * 1000)

        dec = out["decision"]
        sub = out.get("reason_code", "")
        if out.get("sub_code") == "WARN_NO_DATA":
            warn_no_data += 1
        # Abstention confusion matrix: expected PASS => must answer; expected
        # WARN/REFUSE => must abstain.
        if g["expected_verdict"] == "PASS":
            abst["answerable"] += 1
            if dec == "PASS":
                abst["tp_answer"] += 1
            else:
                abst["fn_refuse"] += 1
        else:
            abst["must_abstain"] += 1
            if dec == "PASS":
                abst["fp_halluc"] += 1
            else:
                abst["tn_abstain"] += 1

        # Get stage from firewall adjudication (separate call, offline)
        claim = extract(g["question"])
        v = fw.adjudicate(claim)
        stage = v.stage
        stage_counts[stage] = stage_counts.get(stage, 0) + 1
        decision_counts[dec] = decision_counts.get(dec, 0) + 1

        fig = out.get("figure") or {}
        rid = fig.get("row_id") if isinstance(fig, dict) else None
        if rid:
            touched_row_ids.add(str(rid))

        s = claim.survey
        if s:
            survey_counts[s] = survey_counts.get(s, 0) + 1

        if dec == g["expected_verdict"]:
            ok_v += 1
        else:
            fails.append(
                f"{g['qid']} verdict {dec} != {g['expected_verdict']}"
            )
        if g.get("expected_reason_code"):
            if sub == g["expected_reason_code"]:
                ok_r += 1
            else:
                fails.append(
                    f"{g['qid']} reason {sub} != {g['expected_reason_code']}"
                )
        if g.get("expected_value") is not None:
            if out.get("value") == g["expected_value"]:
                ok_n += 1
            else:
                fails.append(
                    f"{g['qid']} value {out.get('value')} != {g['expected_value']}"
                )
        if out.get("citations_valid", True):
            ok_c += 1
        else:
            fails.append(f"{g['qid']} citations invalid")

    n_val = sum(1 for g in gold if g.get("expected_value") is not None)
    n_cit = len(gold)
    total_t = time.perf_counter() - t0
    cost_per_query = (cost.global_budget().spent_usd - spent_start) / max(len(gold), 1)

    latencies.sort()
    p50 = latencies[int(0.5 * len(latencies))] if latencies else 0
    p95 = latencies[int(0.95 * len(latencies))] if latencies else 0
    p99 = latencies[int(0.99 * len(latencies))] if latencies else 0
    max_lat = max(latencies) if latencies else 0

    # ---- Confidence intervals --------------------------------------------
    verdict_p = ok_v / len(gold) if gold else 0.0
    verdict_ci = ci(verdict_p, len(gold))
    reason_p = ok_r / max(len(gold), 1) if gold else 0.0
    reason_ci = ci(reason_p, max(len(gold), 1))

    # ---- Danger pairs (canonical + pipeline) ------------------------------
    d_ok = 0
    d_pipe_ok = 0
    for d in danger:
        a = extract(d["question_a"]).canonical()
        b = extract(d["question_b"]).canonical()
        canon_safe = a != b and not compatible(a, b)
        if canon_safe:
            d_ok += 1
        else:
            fails.append(f"{d['pair_id']} canonical guard collision")
        out_a = P.ask(d["question_a"])
        out_b = P.ask(d["question_b"])
        same_value = (
            out_a.get("value") is not None
            and out_a.get("value") == out_b.get("value")
            and out_a["decision"] == "PASS"
            and out_b["decision"] == "PASS"
        )
        if not same_value:
            d_pipe_ok += 1
        else:
            fails.append(f"{d['pair_id']} pipeline collision: same value {out_a.get('value')}")

    # ---- Store audit ------------------------------------------------------
    doc = S.load(ROOT / "vidhi" / "store.json")
    ids = [r["row_id"] for r in doc["rows"]]
    if len(ids) != len(set(ids)):
        fails.append("store: duplicate row_ids")
    unver = [
        r["row_id"] for r in doc["rows"] if r.get("verification_status") != "verified"
    ]
    if unver:
        fails.append(f"store: {len(unver)} unverified rows")
    missing_prov = [
        r["row_id"] for r in doc["rows"] if not r.get("provenance", {}).get("extractor")
    ]
    if missing_prov:
        fails.append(f"store: {len(missing_prov)} rows missing provenance")

    total_rows = len(doc["rows"])
    verified_rows = sum(1 for r in doc["rows"] if r.get("verification_status") == "verified")
    row_utilization_pct = len(touched_row_ids) / max(verified_rows, 1) * 100
    # Honest coverage has two distinct numbers: how many golden questions get a
    # verified figure (answerability), and how many verified rows the golden set
    # exercises (row utilization). The v1 docs conflated these as "coverage".
    answerability_pct = decision_counts.get("PASS", 0) / max(len(gold), 1) * 100

    # ---- Safety-B: freeze precedes retrieval ------------------------------
    fw = Firewall()
    q = "Compare average MPCE in 2011-12 vs 2023-24."
    c = extract(q)
    v_no_retrieve = fw.adjudicate(c).frozen_hash
    v_pipeline = P.ask(q)["verdict_frozen_hash"]
    safety_b = (v_no_retrieve == v_pipeline) and bool(v_no_retrieve)
    if not safety_b:
        fails.append("Safety-B: verdict hash moves when retrieval is involved")

    # ---- Determinism ------------------------------------------------------
    det_a = P.ask("What was rural MPCE in HCES 2023-24?")
    det_b = P.ask("What was rural MPCE in HCES 2023-24?")
    deterministic = (
        det_a["verdict_frozen_hash"] == det_b["verdict_frozen_hash"]
        and det_a["decision"] == det_b["decision"]
        and det_a.get("value") == det_b.get("value")
    )
    if not deterministic:
        fails.append("determinism: repeat asks diverge")

    # ---- Safety-A red-team (P/R/F1 per language) -------------------------
    rt_fails, rt = redteam_metrics()
    fails.extend(rt_fails)

    # ---- Abstention summary (refuse-to-hallucinate) ----------------------
    abst_recall = abst["tn_abstain"] / max(abst["must_abstain"], 1)
    halluc_rate = abst["fp_halluc"] / max(abst["must_abstain"], 1)
    false_abstain = abst["fn_refuse"] / max(abst["answerable"], 1)

    # ---- Print results -----------------------------------------------------
    print(f"=== Golden Battery ({len(gold)} queries) ===")
    print(
        f"  verdict_acc={ok_v / len(gold):.3f} "
        f"[{verdict_ci[0]:.3f}-{verdict_ci[1]:.3f}] "
        f"reason_acc={ok_r / max(len(gold), 1):.3f} "
        f"[{reason_ci[0]:.3f}-{reason_ci[1]:.3f}] "
        f"numeric_acc={ok_n / max(n_val, 1):.3f} "
        f"citation_acc={ok_c / max(n_cit, 1):.3f}"
    )
    print(f"  decisions: {dict(sorted(decision_counts.items()))}")
    print(f"  stages: {dict(sorted(stage_counts.items()))}")
    print(f"  surveys: {dict(sorted(survey_counts.items()))}")
    print(
        f"  golden answerability: {decision_counts.get('PASS', 0)}/{len(gold)} PASS "
        f"({answerability_pct:.1f}%) · WARN_NO_DATA={warn_no_data}"
    )
    print(
        f"  row utilization: {len(touched_row_ids)}/{verified_rows} verified rows "
        f"touched ({row_utilization_pct:.1f}%)"
    )
    print(
        f"  danger_canon={d_ok}/{len(danger)} danger_pipe={d_pipe_ok}/{len(danger)} "
        f"safety_b={'ok' if safety_b else 'FAIL'} "
        f"deterministic={'ok' if deterministic else 'FAIL'}"
    )
    print(
        f"  latency_ms p50={p50:.1f} p95={p95:.1f} p99={p99:.1f} max={max_lat:.1f} "
        f"total={total_t:.1f}s cost_per_query=${cost_per_query:.4f}"
    )
    print("=== Abstention (refuse-to-hallucinate) ===")
    print(
        f"  answerable {abst['answerable']} (answered {abst['tp_answer']}, "
        f"wrongly-refused {abst['fn_refuse']}) · must-abstain {abst['must_abstain']} "
        f"(abstained {abst['tn_abstain']}, hallucinated {abst['fp_halluc']})"
    )
    print(
        f"  abstention_recall={abst_recall:.3f} "
        f"hallucination_rate={halluc_rate:.3f} "
        f"false_abstention_rate={false_abstain:.3f}"
    )
    print("=== Safety-A red-team (detect_injection) ===")
    o = rt["overall"]
    print(
        f"  overall P={o['precision']:.3f} [{o['precision_ci'][0]:.3f}-{o['precision_ci'][1]:.3f}] "
        f"R={o['recall']:.3f} [{o['recall_ci'][0]:.3f}-{o['recall_ci'][1]:.3f}] "
        f"F1={o['f1']:.3f}  (injections {o['n_injections']}, benign {o['n_benign']})"
    )
    for lang, c in rt["by_lang"].items():
        print(
            f"    {lang:6s} P={c['precision']:.3f} R={c['recall']:.3f} F1={c['f1']:.3f} "
            f"(inj {c['n_injections']}, ben {c['n_benign']}, fp {c['fp']}, fn {c['fn']})"
        )
    for f in fails:
        print("FAIL:", f)
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
