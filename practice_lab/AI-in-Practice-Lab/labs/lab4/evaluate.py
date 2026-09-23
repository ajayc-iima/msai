#!/usr/bin/env python3
"""Lab 4 evaluation. Scaffolding provided; the judges are yours.

    python labs/lab4/evaluate.py --full --save reports/lab4.json
    python labs/lab4/evaluate.py --gold-context
    python labs/lab4/evaluate.py --calibrate      # writes the hand-label sheet
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from aip.cost import Budget
from aip.evals import judge_agreement, llm_judge
from aip.retrieval import DenseRetriever, format_context
from labs.lab3.search import build_chunks, load_corpus, load_questions
from labs.lab4.rag import (
    answer_question,
    answer_with_gold_context,
    is_refusal,
)

GOLDEN = ROOT / "data/eval/rag_golden.jsonl"
LABEL_SHEET = ROOT / "labs/lab4/calibration_labels.jsonl"

# Single-criterion rubrics (T3 §4.2). The aip.evals templates are starting
# points; these handle the cases the shipped ones miss.
# Single-criterion rubrics (T3 §4.2). Start from aip.evals and IMPROVE them.
# TODO D1: these are starting points, not answers. Edit before you trust a
# judge number. Copy your improved versions here from the notebook.
from aip.evals import JUDGE_RUBRIC_CORRECTNESS as _START_CORRECTNESS
from aip.evals import JUDGE_RUBRIC_FAITHFULNESS as _START_FAITHFULNESS

RUBRIC_FAITHFULNESS = _START_FAITHFULNESS  # TODO D1.1: improve
RUBRIC_CORRECTNESS = _START_CORRECTNESS    # TODO D1.2: handle REFUSE / PARTIAL REFUSE


def build_retriever():
    """TODO: put YOUR Lab 3 winning configuration here.

    Leaving the placeholder throws away Lab 3. Read reports/lab3_sweeps.json
    (or your report.md) for the winning strategy, size, and retriever type.
    Placeholder below is markdown-400 dense (the reference config) ONLY so
    the harness runs before you fill it in.
    """
    corpus = load_corpus()
    # TODO: replace with your winner, e.g. build_chunks(corpus, "markdown", 400)
    chunks = build_chunks(corpus, "markdown", 400)
    return DenseRetriever(chunks, show_progress=False)


# ---------------------------------------------------------------------------
# judges (ours)
# ---------------------------------------------------------------------------
def _verdict_score(verdict: dict, lo: int, hi: int) -> int | None:
    """Parse-failure is missing data, not a failing answer (T1 trap #2)."""
    if verdict.get("parse_error"):
        return None
    try:
        score = int(verdict.get("score"))
    except (TypeError, ValueError):
        return None
    if score < lo or score > hi:
        return None
    return score


def judge_faithfulness(answer_text: str, context: str) -> int | None:
    """TODO D1.1: improved single-criterion rubric; returns 0, 1, or None.

    None = judge parse failure (missing data). Callers must exclude it rather
    than score 0 -- scoring 0 is a silent downward bias on the headline metric.

    Shape:
        verdict = llm_judge(RUBRIC_FAITHFULNESS.format(
            context=context[:8000], answer=answer_text), tier="LARGE")
        return _verdict_score(verdict, 0, 1)
    """
    raise NotImplementedError(
        "TODO D1.1: implement judge_faithfulness (llm_judge + _verdict_score, return None on parse_error)"
    )


def _reference_declines(reference: str) -> str:
    """'full', 'partial', or '' from the gold answer's REFUSE marker."""
    head = reference.lstrip()[:40].upper()
    if head.startswith("PARTIAL REFUSE"):
        return "partial"
    if head.startswith("REFUSE"):
        return "full"
    return ""


def judge_correctness(question: str, candidate: str, reference: str) -> int | None:
    """TODO D1.2: returns 0, 1, 2, or None (judge parse failure).

    Handle refusal DETERMINISTICALLY first:
      - reference starts with REFUSE -> refusal scores 2, confident answer 0
      - reference does NOT decline and candidate refuses -> 0
      - PARTIAL REFUSE still goes to the judge (supported/declined split)
    Then: verdict = llm_judge(RUBRIC_CORRECTNESS.format(...), tier="LARGE")
          return _verdict_score(verdict, 0, 2)
    """
    raise NotImplementedError(
        "TODO D1.2: implement judge_correctness (deterministic refusal branch + llm_judge)"
    )


def _mean(vals: list) -> float | None:
    vals = [v for v in vals if v is not None]
    return statistics.fmean(vals) if vals else None


def _fmt(v: float | None) -> str:
    return "n/a (all judge parse failures)" if v is None else f"{v:.3f}"


# ---------------------------------------------------------------------------
def _safe_judge(fn, *args):
    """Judge call that never raises: timeout/parse failure is missing data."""
    try:
        return fn(*args)
    except Exception:  # noqa: BLE001 - a dead judge is None, not a dead run
        return None


def run_full(save: str = "") -> None:
    questions = load_questions(include_unanswerable=True)
    retriever = build_retriever()
    rows: list[dict] = []
    done: set[str] = set()

    # Resume: incremental saves mean a timeout mid-run is recoverable.
    if save and (ROOT / save).exists():
        try:
            rows = json.loads((ROOT / save).read_text(encoding="utf-8"))
            done = {r["id"] for r in rows}
            print(f"resuming: {len(done)} rows already in {save}", flush=True)
        except Exception:  # noqa: BLE001 - corrupt partial file -> start clean
            rows, done = [], set()

    with Budget(limit_usd=1.00, label="lab4-full") as b:
        for i, q in enumerate(questions, 1):
            if q["id"] in done:
                continue
            try:
                a = answer_question(q["question"], retriever)
                ctx = format_context(a.hits)
                row = {
                    "id": q["id"], "kind": q["kind"],
                    "unanswerable": (not q["relevant_docs"]
                                     or q["kind"] == "unanswerable"),
                    "answer": a.text, "refused": a.refused,
                    "citations_valid": a.citations_valid,
                    "invalid_citations": a.invalid_citations,
                    "repaired": a.repaired,
                    "faithfulness": _safe_judge(judge_faithfulness, a.text, ctx),
                    "correctness": _safe_judge(
                        judge_correctness, q["question"], a.text, q["gold_answer"]),
                    "retrieved": [h.doc_id for h in a.hits],
                    "relevant": q["relevant_docs"],
                }
            except Exception as exc:  # noqa: BLE001 - one dead question != dead run
                print(f"  {q['id']} ERROR {type(exc).__name__}: {exc}", flush=True)
                row = {
                    "id": q["id"], "kind": q["kind"],
                    "unanswerable": (not q["relevant_docs"]
                                     or q["kind"] == "unanswerable"),
                    "answer": f"[run failed: {type(exc).__name__}]",
                    "refused": False, "citations_valid": False,
                    "invalid_citations": [], "repaired": False,
                    "faithfulness": None, "correctness": None,
                    "retrieved": [], "relevant": q["relevant_docs"],
                    "error": str(exc)[:200],
                }
            rows.append(row)
            print(f"  {q['id']} {i}/{len(questions)}", flush=True)
            if save:
                p = ROOT / save
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(json.dumps(rows, indent=2, ensure_ascii=False),
                             encoding="utf-8")

    ans = [r for r in rows if not r["unanswerable"]]
    una = [r for r in rows if r["unanswerable"]]
    refusals = [r for r in rows if r["refused"]]
    faith = _mean([r["faithfulness"] for r in rows])
    corr = _mean([r["correctness"] for r in ans])

    print(f"\nn = {len(rows)}  ({len(ans)} answerable, {len(una)} unanswerable)")
    print(f"citation validity   {statistics.fmean(r['citations_valid'] for r in rows):.3f}"
          "   (target 1.000)")
    print(f"faithfulness        {_fmt(faith)}   "
          f"(excluded judge parse failures: "
          f"{sum(1 for r in rows if r['faithfulness'] is None)})")
    print(f"correctness (0-2)   {_fmt(corr)}"
          f"  normalised {_fmt(corr / 2 if corr is not None else None)}")
    print(f"repair rate         {statistics.fmean(r['repaired'] for r in rows):.3f}")
    rec = (sum(1 for r in una if r["refused"]) / len(una)) if una else 0.0
    prec = (sum(1 for r in refusals if r["unanswerable"]) / len(refusals)) if refusals else 1.0
    print(f"refusal recall      {rec:.3f}   ({sum(1 for r in una if r['refused'])}/{len(una)})")
    print(f"refusal precision   {prec:.3f}   ({len(refusals)} refusals total)")
    print("\n" + b.report())

    print("\nby question kind (mean correctness / 2):")
    kinds = sorted({r["kind"] for r in ans})
    for kind in kinds:
        sub = [r for r in ans if r["kind"] == kind]
        k_corr = _mean([r["correctness"] for r in sub])
        print(f"  {kind:<16} {_fmt(k_corr) if k_corr is None else f'{k_corr/2:.3f}'}"
              f"  n={len(sub)}")

    if save:
        p = ROOT / save
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nsaved -> {p}   (Lab 5 reads this file)")


def run_gold_context() -> None:
    """E2: the decomposition. This is the highest-value 10 minutes in the lab."""
    questions = [q for q in load_questions() if q["relevant_docs"]]
    retriever = build_retriever()
    corpus = load_corpus()

    retrieved_scores, gold_scores = [], []
    with Budget(limit_usd=1.00, label="lab4-decomposition"):
        for q in questions:
            a = answer_question(q["question"], retriever)
            s = judge_correctness(q["question"], a.text, q["gold_answer"])
            if s is not None:
                retrieved_scores.append(s / 2)
            g = answer_with_gold_context(
                q["question"], [corpus[d] for d in q["relevant_docs"] if d in corpus])
            s = judge_correctness(q["question"], g.text, q["gold_answer"])
            if s is not None:
                gold_scores.append(s / 2)

    A, B = statistics.fmean(gold_scores), statistics.fmean(retrieved_scores)
    print(f"\ncorrectness with GOLD context       A = {A:.3f}   <- generation ceiling")
    print(f"correctness with RETRIEVED context  B = {B:.3f}   <- your system")
    print(f"retrieval-attributable loss   A - B = {A - B:.3f}")
    print(f"generation-attributable loss  1 - A = {1 - A:.3f}")
    print("\nWhichever is larger is where Lab 5 goes.")


def make_calibration_sheet() -> None:
    """D2: writes 20 answers for you to hand-label BEFORE seeing the judge."""
    rows = json.loads((ROOT / "reports/lab4.json").read_text(encoding="utf-8"))
    sample = rows[:20]
    LABEL_SHEET.write_text("\n".join(json.dumps({
        "id": r["id"], "answer": r["answer"],
        "human_faithfulness": None, "human_correctness": None,
    }, ensure_ascii=False) for r in sample) + "\n", encoding="utf-8")
    print(f"wrote {LABEL_SHEET}")
    print("Fill in human_faithfulness (0/1) and human_correctness (0/1/2), then:")
    print("  python labs/lab4/evaluate.py --kappa")


def report_kappa() -> None:
    human = [json.loads(l) for l in LABEL_SHEET.open(encoding="utf-8")]
    machine = {r["id"]: r for r in
               json.loads((ROOT / "reports/lab4.json").read_text(encoding="utf-8"))}
    for field in ("faithfulness", "correctness"):
        pairs = [(machine[r["id"]][field], r[f"human_{field}"]) for r in human
                 if r[f"human_{field}"] is not None
                 and machine.get(r["id"], {}).get(field) is not None]
        h = [p[1] for p in pairs]
        m = [p[0] for p in pairs]
        if not h:
            print(f"{field}: no human labels yet")
            continue
        print(f"{field}: {judge_agreement(m, h)}")
    print("\nkappa < 0.4 -> fix the rubric, not the model. Read your disagreements.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--gold-context", action="store_true")
    ap.add_argument("--calibrate", action="store_true")
    ap.add_argument("--kappa", action="store_true")
    ap.add_argument("--save", default="")
    a = ap.parse_args()
    if a.full:
        run_full(a.save)
    if a.gold_context:
        run_gold_context()
    if a.calibrate:
        make_calibration_sheet()
    if a.kappa:
        report_kappa()
    if not any([a.full, a.gold_context, a.calibrate, a.kappa]):
        ap.print_help()
