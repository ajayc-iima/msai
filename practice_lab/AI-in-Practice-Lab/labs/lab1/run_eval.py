#!/usr/bin/env python3
"""Lab 1 harness. Written for you — read it, then use it.

    python labs/lab1/run_eval.py --split dev  --variant b
    python labs/lab1/run_eval.py --split dev  --variant c --compare b
    python labs/lab1/run_eval.py --split test --variant c --save reports/lab1_test.json

Discipline: iterate on `dev`. Run `test` when you have a candidate, and report
what it says — including if it is worse than dev.
"""
from __future__ import annotations

import argparse
import importlib
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from aip.evals import compare, field_accuracy, load_cases, run_eval  # noqa: E402

GRADED_FIELDS = ["category", "urgency", "sentiment", "policy_number",
                 "product", "escalate", "contains_pii", "language"]


def make_metric(fields: list[str]):
    def metric(pred, gold) -> dict[str, float]:
        m = field_accuracy(pred, gold, fields)
        if hasattr(pred, "model_dump"):
            pred = pred.model_dump()
        m["schema_valid"] = float(isinstance(pred, dict) and bool(pred))
        m["needs_review"] = float(bool(isinstance(pred, dict)
                                       and pred.get("needs_human_review")))
        return m
    return metric


def confusion(report, cases, field: str) -> str:
    gold_by_id = {c.id: (c.expected or {}).get(field) for c in cases}
    counts: Counter[tuple] = Counter()
    for r in report.results:
        pred = r.output.model_dump() if hasattr(r.output, "model_dump") else r.output
        p = (pred or {}).get(field) if isinstance(pred, dict) else None
        counts[(gold_by_id.get(r.id), p)] += 1

    labels = sorted({v for pair in counts for v in pair if v is not None}, key=str)
    w = max((len(str(v)) for v in labels), default=8) + 2
    head = " " * w + "".join(f"{str(v)[:w - 1]:>{w}}" for v in labels)
    lines = [f"confusion for {field!r}  (rows = gold, cols = predicted)", head]
    for g in labels:
        row = f"{str(g):<{w}}"
        for p in labels:
            row += f"{(counts.get((g, p), 0) or '.'):>{w}}"
        lines.append(row)
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=["dev", "test"], default="dev")
    ap.add_argument("--variant", choices=["b", "c"], required=True)
    ap.add_argument("--compare", nargs="*", default=[],
                    help="other variants to show side by side")
    ap.add_argument("--n", type=int, default=0, help="limit cases (debugging only)")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--budget", type=float, default=0.30)
    ap.add_argument("--save", default="")
    args = ap.parse_args()

    mod = importlib.import_module("extract")
    cases = load_cases(ROOT / f"data/eval/extraction_{args.split}.jsonl")
    if args.n:
        cases = cases[: args.n]

    systems = {"b": mod.extract_b, "c": mod.extract_c}
    reports = []
    for v in [args.variant, *args.compare]:
        fields = GRADED_FIELDS if v == "c" else [f for f in GRADED_FIELDS if f != "escalate"]
        rep = run_eval(f"lab1-{v}-{args.split}", cases, systems[v], make_metric(fields),
                       budget_usd=args.budget, workers=args.workers)
        print(rep.summary())
        print()
        reports.append(rep)

    if len(reports) > 1:
        print(compare(*reports, metrics=["field_accuracy", "record_accuracy",
                                         "schema_valid", "error_rate"]))
        print()

    main_report = reports[0]
    print(confusion(main_report, cases, "category"))
    print()

    per_field = {k: v for k, v in main_report.aggregate().items() if k.startswith("field.")}
    print("per-field accuracy (worst first):")
    for k, v in sorted(per_field.items(), key=lambda kv: kv[1]):
        print(f"  {k:<28} {v:.3f}")
    print()

    n_imperfect = sum(1 for r in main_report.results
                      if r.metrics.get("record_accuracy", 1) < 1)
    print(f"{n_imperfect} imperfect records; worst {min(8, n_imperfect)}:")
    for r in main_report.failures("record_accuracy", limit=8):
        wrong = [k.removeprefix("field.") for k, v in r.metrics.items()
                 if k.startswith("field.") and v == 0.0]
        print(f"  {r.id}  wrong={wrong}  {r.error or ''}")

    if args.save:
        p = main_report.save(ROOT / args.save)
        print(f"\nsaved -> {p}")
        if args.split == "test":
            print("You have now used the test split. Do not iterate against it.")


if __name__ == "__main__":
    main()
