"""src/evaluate.py — All evaluation: retrieval metrics (Exp-1) + answer metrics (Exp-2).

Merged from evaluate.py (retrieval metrics, bootstrap CIs, Gold B) and
score_parts.py (faithfulness, citation P/R, coverage F1, abstention, waterfall).
Import the shared retrieval metrics from src/retrieval.py for a clean flow:
    make_queries → retrieval search → answer → evaluate (this file).
"""
import argparse
import json
import re
from pathlib import Path
from typing import List, Dict, Any, Set, Tuple

import numpy as np
from scipy import stats
from tqdm import tqdm

from src.common import (load_jsonl, write_jsonl, ensure_dir, setup_logging,
                        bootstrap_ci, wilson_interval, cohens_kappa, extract_subparts)
from src.gating import claim_supported, verify_answer_claims


# ══ Retrieval metrics (Exp. 1) ══════════════════════════════════════════════

def recall_any(gold: Set, ranked: List, k: int) -> float:
    return 1.0 if gold & set(ranked[:k]) else 0.0

def recall_all(gold: Set, ranked: List, k: int) -> float:
    if not gold:
        return 1.0
    return len(gold & set(ranked[:k])) / len(gold)

def mrr(gold: Set, ranked: List) -> float:
    for i, doc_id in enumerate(ranked):
        if doc_id in gold:
            return 1.0 / (i + 1)
    return 0.0

def ndcg_at_k(gold: Set, ranked: List, k: int = 10) -> float:
    if not gold:
        return 1.0
    dcg = sum(1.0 / np.log2(i + 2) for i, doc_id in enumerate(ranked[:k]) if doc_id in gold)
    idcg = sum(1.0 / np.log2(i + 2) for i in range(min(len(gold), k)))
    return dcg / idcg if idcg > 0 else 0.0

def compute_metrics(gold: Set, ranked: List, ks: List[int] = [1, 3, 5, 10]) -> Dict[str, float]:
    ranked_ids = [item["doc_id"] for item in ranked]
    metrics = {}
    for k in ks:
        metrics[f"R@{k}_any"] = recall_any(gold, ranked_ids, k)
        metrics[f"R@{k}_all"] = recall_all(gold, ranked_ids, k)
    metrics["MRR"] = mrr(gold, ranked_ids)
    metrics["nDCG@10"] = ndcg_at_k(gold, ranked_ids, 10)
    return metrics

def evaluate_retrieval(run_path: Path, queries_path: Path, gold_type: str = "A",
                       ks: List[int] = [1, 3, 5, 10]) -> Dict[str, Any]:
    """Per-query + aggregate retrieval metrics for one system."""
    runs = load_jsonl(run_path)
    queries = [q for q in load_jsonl(queries_path) if q["split"] == "test" and q["retrievable"]]
    queries_by_id = {q["query_id"]: q for q in queries}

    gold_b_judgments = {}
    if gold_type == "B":
        jpath = Path("data/gold_b_judgments.jsonl")
        if jpath.exists():
            for j in load_jsonl(jpath):
                gold_b_judgments[(j["query_id"], j["qslno"])] = j["label"]

    per_query = []
    for run in runs:
        qid = run["query_id"]
        if qid not in queries_by_id:
            continue
        query = queries_by_id[qid]
        gold = set(query["gold"])
        if gold_type == "B" and gold_b_judgments:
            gold = {g for g in gold if gold_b_judgments.get((qid, g), 2) >= 1}
        metrics = compute_metrics(gold, run["ranked_list"], ks)
        metrics.update(query_id=qid, style=query.get("style", "unknown"),
                       n_gold=len(gold), n_gold_out_of_split=query.get("n_gold_out_of_split", 0))
        per_query.append(metrics)

    n = len(per_query)
    agg = {"n_queries": n}
    for k in ks:
        agg[f"R@{k}_any"] = float(np.mean([m[f"R@{k}_any"] for m in per_query]))
        agg[f"R@{k}_all"] = float(np.mean([m[f"R@{k}_all"] for m in per_query]))
    agg["MRR"] = float(np.mean([m["MRR"] for m in per_query]))
    agg["nDCG@10"] = float(np.mean([m["nDCG@10"] for m in per_query]))

    by_style = {}
    for style in set(m["style"] for m in per_query):
        sm = [m for m in per_query if m["style"] == style]
        keys = [k for k in sm[0].keys() if k not in ("query_id", "style", "n_gold", "n_gold_out_of_split", "n_gold_out")]
        by_style[style] = {"n": len(sm), **{k: float(np.mean([m[k] for m in sm])) for k in keys}}
    agg["by_style"] = by_style

    return {"aggregate": agg, "per_query": per_query}

def compare_systems(sys1_name, sys1_path, sys2_name, sys2_path, queries_path,
                    gold_type="A", n_bootstrap=1000) -> Dict[str, Any]:
    r1 = evaluate_retrieval(sys1_path, queries_path, gold_type)
    r2 = evaluate_retrieval(sys2_path, queries_path, gold_type)
    q1 = {m["query_id"]: m for m in r1["per_query"]}
    q2 = {m["query_id"]: m for m in r2["per_query"]}
    common = set(q1) & set(q2)
    comparisons = {}
    for metric in ["R@1_any", "R@3_any", "R@5_any", "R@10_any",
                   "R@1_all", "R@3_all", "R@5_all", "R@10_all", "MRR", "nDCG@10"]:
        s1 = [q1[i][metric] for i in common]
        s2 = [q2[i][metric] for i in common]
        mean_diff, lo, hi = bootstrap_ci(lambda x: np.mean(x), s1, s2, n_bootstrap)
        comparisons[metric] = {"sys1_mean": float(np.mean(s1)), "sys2_mean": float(np.mean(s2)),
                               "mean_diff": float(mean_diff), "ci_lo": float(lo), "ci_hi": float(hi),
                               "significant": bool(lo > 0 or hi < 0)}
    return {"sys1": sys1_name, "sys2": sys2_name, "n_queries": len(common),
            "comparisons": comparisons}

def evaluate_gold_b(judgments_path: Path, queries_path: Path) -> Dict[str, Any]:
    """Gold B construct validity: confirm/discovery rates + Cohen's kappa."""
    judgments = load_jsonl(judgments_path)
    queries_by_id = {q["query_id"]: q for q in load_jsonl(queries_path)}
    confirm_t = confirm_r = discovery_t = discovery_r = 0
    gold_labels, human_labels = [], []

    for j in judgments:
        query = queries_by_id.get(j["query_id"])
        if not query:
            continue
        gold = set(query["gold"])
        is_gold = j["qslno"] in gold
        is_rel = j["label"] >= 1
        if is_gold:
            confirm_t += 1
            confirm_r += int(is_rel)
        else:
            discovery_t += 1
            discovery_r += int(is_rel)
        gold_labels.append(int(is_gold))
        human_labels.append(int(is_rel))

    return {
        "n_judgments": len(judgments),
        "confirm_rate": confirm_r / confirm_t if confirm_t else 0.0,
        "confirm_n": confirm_t,
        "discovery_rate": discovery_r / discovery_t if discovery_t else 0.0,
        "discovery_n": discovery_t,
        "cohens_kappa": cohens_kappa(gold_labels, human_labels) if gold_labels else 0.0,
    }


# ══ Answer metrics (Exp. 2) ═════════════════════════════════════════════════

def load_coverage_gold(path: Path) -> Dict[str, List[str]]:
    return {r["query_id"]: r["gold_subparts"] for r in load_jsonl(path)}

def coverage_f1(pred_claims: List[str], gold_subparts: List[str], tau: float = 0.80) -> Tuple[float, float, float]:
    """(precision, recall, f1) between predicted claims and gold answer sub-parts."""
    if not gold_subparts:
        return 0.0, 0.0, 0.0
    recall = sum(1 for gp in gold_subparts
                 if claim_supported(gp, pred_claims, tau)[0]) / len(gold_subparts)
    matching = 0
    for claim in pred_claims:
        if any(claim_supported(claim, [gp], tau)[0] for gp in gold_subparts):
            matching += 1
    precision = matching / len(pred_claims) if pred_claims else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    return precision, recall, f1

def citation_precision_recall(pred: Dict, tau: float = 0.80) -> Tuple[float, float]:
    claims = pred.get("claims", [])
    citations = pred.get("citations", [])
    if not claims:
        return 0.0, 0.0
    supported_citations = 0
    for i, cite in enumerate(citations):
        if i < len(claims) and claim_supported(claims[i], [cite.get("span", "")], tau)[0]:
            supported_citations += 1
    claims_with_support = 0
    for i, claim in enumerate(claims):
        if i < len(citations) and claim_supported(claim, [citations[i].get("span", "")], tau)[0]:
            claims_with_support += 1
    return (supported_citations / len(citations) if citations else 0.0,
            claims_with_support / len(claims) if claims else 0.0)

def abstention_pr(preds: List[Dict], queries: List[Dict]) -> Dict[str, float]:
    unanswerable = {q["query_id"] for q in queries if not q["retrievable"] or q["style"] == "answer-unavailable"}
    answerable = {q["query_id"] for q in queries if q["retrievable"] and q["style"] != "answer-unavailable"}
    pred_abstain = {p["query_id"] for p in preds if p["abstained"]}
    tp = len(pred_abstain & unanswerable)
    fp = len(pred_abstain - unanswerable)
    fn = len(unanswerable - pred_abstain)
    emitted = sum(1 for p in preds if not p["abstained"])
    violated = sum(1 for p in preds if not p["abstained"] and not p.get("verification", {}).get("all_supported", True))
    coverage = len(answerable - pred_abstain) / len(answerable) if answerable else 0.0
    return {
        "abstention_precision": tp / (tp + fp) if (tp + fp) > 0 else 0.0,
        "abstention_recall": tp / (tp + fn) if (tp + fn) > 0 else 0.0,
        "coverage_answerable": coverage,
        "violation_rate": violated / emitted if emitted > 0 else 0.0,
        "n_unanswerable": len(unanswerable), "n_answerable": len(answerable),
        "n_emitted": emitted, "n_violated": violated,
    }

def classify_waterfall(query: Dict, pred: Dict, gold: Set, ranked: List[Dict], k: int = 10) -> str:
    """A (retrieval fail) | B (evidence fail) | C (generation fail) | success | unanswerable."""
    if not query["retrievable"] or query["style"] == "answer-unavailable":
        return "unanswerable"
    ranked_ids = [item["doc_id"] for item in ranked[:k]]
    if not (gold & set(ranked_ids)):
        return "A"
    if pred.get("gate_reason", "") != "MER_PASS":
        return "B"
    if pred["abstained"] or not pred.get("verification", {}).get("all_supported", True):
        return "C"
    return "success"

def compute_waterfall(preds, queries, runs, k: int = 10) -> Dict[str, Any]:
    queries_by_id = {q["query_id"]: q for q in queries}
    runs_by_id = {r["query_id"]: r for r in runs}
    buckets = {"A": 0, "B": 0, "C": 0, "success": 0, "unanswerable": 0}
    details = {bk: [] for bk in buckets}
    for pred in preds:
        query, run = queries_by_id.get(pred["query_id"]), runs_by_id.get(pred["query_id"])
        if not query or not run:
            continue
        bucket = classify_waterfall(query, pred, set(query["gold"]), run["ranked_list"], k)
        buckets[bucket] += 1
        details[bucket].append({"query_id": pred["query_id"], "style": query.get("style"),
                                "gate_reason": pred.get("gate_reason"),
                                "gold": list(query["gold"]),
                                "top_k": [item["doc_id"] for item in run["ranked_list"][:k]]})
    total = sum(buckets.values())
    assert total > 0, "No queries evaluated"
    proportions = {k: v / total for k, v in buckets.items()}
    assert abs(sum(proportions.values()) - 1.0) < 0.001, f"Waterfall sum = {sum(proportions.values())}"
    return {"counts": buckets, "proportions": proportions, "details": details, "total": total}

def evaluate_answers(pred_path: Path, queries_path: Path, runs_path: Path,
                     coverage_gold_path: Path = None, k: int = 10) -> Dict[str, Any]:
    """All Exp-2 metrics for one policy prediction file."""
    preds = load_jsonl(pred_path)
    queries = [q for q in load_jsonl(queries_path) if q["split"] == "test"]
    queries_by_id = {q["query_id"]: q for q in queries}
    runs_by_id = {r["query_id"]: r for r in load_jsonl(runs_path)}
    coverage_gold = load_coverage_gold(coverage_gold_path) if coverage_gold_path and coverage_gold_path.exists() else {}

    supported_c = total_c = 0
    supported_cites = total_cites = 0
    coverage_f1s = []

    for pred in preds:
        qid = pred["query_id"]
        if qid not in queries_by_id:
            continue
        claims = pred.get("claims", [])
        citations = pred.get("citations", [])
        total_c += len(claims)
        if not pred.get("abstained", False):
            for cr in pred.get("verification", {}).get("claims", []):
                supported_c += int(cr.get("supported", False))

        total_cites += len(citations)
        for i, cite in enumerate(citations):
            if i < len(claims) and claim_supported(claims[i], [cite.get("span", "")], 0.80)[0]:
                supported_cites += 1

        if qid in coverage_gold:
            _, _, f1 = coverage_f1(claims, coverage_gold[qid])
            coverage_f1s.append(f1)

    return {
        "faithfulness": supported_c / total_c if total_c > 0 else 0.0,
        "citation_precision": supported_cites / total_cites if total_cites > 0 else 0.0,
        "citation_recall": supported_cites / total_c if total_c > 0 else 0.0,
        "coverage_f1": float(np.mean(coverage_f1s)) if coverage_f1s else 0.0,
        "abstention": abstention_pr(preds, queries),
        "waterfall": compute_waterfall(preds, queries, list(runs_by_id.values()), k),
        "n_queries": len(preds), "n_claims": total_c, "n_citations": total_cites,
    }


# ══ CLI ═════════════════════════════════════════════════════════════════════

def _eval_retrieval(args):
    systems = args.systems.split(",")
    all_results = {}
    for sys_name in systems:
        run_path = Path(args.runs_dir) / f"{sys_name}.jsonl"
        if not run_path.exists():
            print(f"Run not found: {run_path}")
            continue
        results = evaluate_retrieval(run_path, Path(args.queries), args.gold)
        all_results[sys_name] = results
        agg = results["aggregate"]
        print(f"\n{sys_name} (Gold {args.gold}):  n={agg['n_queries']}")
        print(f"  R@1 {agg['R@1_any']:.4f}/{agg['R@1_all']:.4f}  R@3 {agg['R@3_any']:.4f}/{agg['R@3_all']:.4f}  "
              f"R@5 {agg['R@5_any']:.4f}/{agg['R@5_all']:.4f}  R@10 {agg['R@10_any']:.4f}/{agg['R@10_all']:.4f}  "
              f"MRR {agg['MRR']:.4f}  nDCG@10 {agg['nDCG@10']:.4f}")
        for style, sa in agg["by_style"].items():
            print(f"  {style} (n={sa['n']}): nDCG@10={sa['nDCG@10']:.4f}")
    out = Path(args.out) / f"eval_gold_{args.gold}.json"
    write_jsonl(out, [{"system": k, **v["aggregate"]} for k, v in all_results.items()])
    print(f"\nSaved -> {out}")

def _eval_answers(args):
    pred_path = Path(args.preds_dir) / f"{args.system}_{args.policy}.jsonl"
    if not pred_path.exists():
        raise FileNotFoundError(f"Predictions not found: {pred_path}")
    results = evaluate_answers(pred_path, Path(args.queries),
                               Path(args.runs_dir) / f"{args.system}.jsonl",
                               Path(args.coverage_gold), args.k)
    print(json.dumps(results, indent=1))
    out = Path(args.out) / f"score_{args.system}_{args.policy}.json"
    out.write_text(json.dumps(results, indent=1))
    print(f"Saved -> {out}")

def main():
    ap = argparse.ArgumentParser(description="Evaluation: retrieval (Exp-1) and answers (Exp-2)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("retrieval", help="Score retrieval systems (Exp-1)")
    p.add_argument("--systems", default="bm25", help="Comma-separated system names")
    p.add_argument("--runs-dir", default="data/runs")
    p.add_argument("--queries", default="data/queries.jsonl")
    p.add_argument("--split", choices=["dev", "test"], default="test")
    p.add_argument("--gold", choices=["A", "B"], default="A")
    p.add_argument("--out", default="data/eval/")
    p.add_argument("--compare", nargs=2, help="Compare two systems (name name)")
    p.add_argument("--gold-b-eval", action="store_true")
    p.set_defaults(func=_eval_retrieval)

    p = sub.add_parser("answers", help="Score answer predictions (Exp-2)")
    p.add_argument("--preds-dir", default="data/preds")
    p.add_argument("--queries", default="data/queries.jsonl")
    p.add_argument("--runs-dir", default="data/runs")
    p.add_argument("--system", required=True)
    p.add_argument("--policy", required=True, help="A|B|C|D|extractive")
    p.add_argument("--coverage-gold", default="data/coverage_gold.jsonl")
    p.add_argument("--k", type=int, default=10)
    p.add_argument("--out", default="data/eval/")
    p.set_defaults(func=_eval_answers)

    a = ap.parse_args()

    if a.cmd == "retrieval":
        if a.gold_b_eval:
            results = evaluate_gold_b(Path("data/gold_b_judgments.jsonl"), Path(a.queries))
            print(json.dumps(results, indent=1))
            Path(a.out, "gold_b_eval.json").write_text(json.dumps(results, indent=1))
            return
        if a.compare:
            s1, s2 = a.compare
            results = compare_systems(s1, Path(a.runs_dir) / f"{s1}.jsonl",
                                      s2, Path(a.runs_dir) / f"{s2}.jsonl",
                                      Path(a.queries), a.gold)
            print(json.dumps(results, indent=1))
            Path(a.out, f"compare_{s1}_vs_{s2}.json").write_text(json.dumps(results, indent=1))
            return
        ensure_dir(Path(a.out))
        _eval_retrieval(a)
    else:
        ensure_dir(Path(a.out))
        _eval_answers(a)


if __name__ == "__main__":
    main()