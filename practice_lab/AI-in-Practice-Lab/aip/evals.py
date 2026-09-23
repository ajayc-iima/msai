"""The evaluation harness.

A GenAI system is a stochastic function; the only way to reason about a change
is to let a harness arbitrate. The shape is always the same:

    cases  : a golden set — inputs with known-good outputs
    system : a callable, input -> output
    metric : (output, expected) -> dict[str, float]
    report : per-case rows + aggregate + cost + latency, saveable to disk
"""
from __future__ import annotations

import json
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Sequence

from aip.llm import Budget


# ===========================================================================
# metrics
# ===========================================================================
def field_accuracy(pred: dict | Any, gold: dict,
                   fields: Sequence[str] | None = None) -> dict[str, float]:
    """Per-field correctness for structured extraction, reported two ways:

      field_accuracy  — fraction of individual fields correct. Good for
                        tracking incremental progress.
      record_accuracy — fraction of records with *every* field correct. The
                        number the business feels: one wrong field still sends
                        the record to a human.
    """
    if hasattr(pred, "model_dump"):
        pred = pred.model_dump()
    pred = pred if isinstance(pred, dict) else {}
    keys = list(fields) if fields else list(gold.keys())
    per = {}
    for k in keys:
        p, g = pred.get(k), gold.get(k)
        if isinstance(g, str) and isinstance(p, str):
            ok = p.strip().lower() == g.strip().lower()
        else:
            ok = p == g
        per[f"field.{k}"] = float(ok)
    correct = sum(per.values())
    return {
        **per,
        "field_accuracy": correct / len(keys) if keys else 0.0,
        "record_accuracy": float(correct == len(keys)),
    }


def exact_match(pred: Any, gold: Any) -> dict[str, float]:
    return {"exact_match": float(str(pred).strip().lower() == str(gold).strip().lower())}


def _log2(x: float) -> float:
    import math

    return math.log2(x)


def retrieval_metrics(retrieved: Sequence[str], relevant: Sequence[str],
                      ks: Sequence[int] = (1, 3, 5, 10)) -> dict[str, float]:
    """Standard IR metrics for one query.

    retrieved : ranked list of ids (most relevant first)
    relevant  : set of ids that are actually relevant (unranked, binary)

    hit_rate@k  — did at least one relevant doc appear in the top k?
    recall@k    — what fraction of all relevant docs appeared in the top k?
    precision@k — what fraction of the top k are relevant?
    mrr         — 1 / rank of the first relevant doc.
    ndcg@k      — rank-discounted gain. Lab 3 headline (nDCG@10).
    """
    rel = set(relevant)
    ranked = list(retrieved)
    out: dict[str, float] = {}

    for k in ks:
        topk = ranked[:k]
        n_hit = len(rel & set(topk))
        out[f"hit_rate@{k}"] = float(n_hit > 0)
        out[f"recall@{k}"] = n_hit / len(rel) if rel else 0.0
        out[f"precision@{k}"] = n_hit / k if k else 0.0
        dcg = sum(1.0 / _log2(i + 2) for i, d in enumerate(topk) if d in rel)
        idcg = sum(1.0 / _log2(i + 2) for i in range(min(len(rel), k)))
        out[f"ndcg@{k}"] = dcg / idcg if idcg else 0.0

    out["mrr"] = next(
        (1.0 / (i + 1) for i, d in enumerate(ranked) if d in rel), 0.0
    )
    return out


# ===========================================================================
# 3. LLM-as-judge
# ===========================================================================
JUDGE_RUBRIC_FAITHFULNESS = """\
You are grading whether an ANSWER is fully supported by the provided CONTEXT.

Rules:
- Judge support only. Do NOT judge whether the answer is helpful, well written,
  or matches your own knowledge.
- An answer is unsupported if it states anything the context does not contain,
  even if that statement is true in the real world.
- Refusing to answer when the context is genuinely insufficient is SUPPORTED.

CONTEXT:
{context}

ANSWER:
{answer}

Reply as JSON: {{"score": 0 or 1, "unsupported_claims": [..], "reason": "one sentence"}}
"""

JUDGE_RUBRIC_CORRECTNESS = """\
Compare a CANDIDATE answer to a REFERENCE answer for the same question.

Score 2 = same substantive content as the reference (wording may differ).
Score 1 = partially correct: some correct content, but omits something the
          reference states, or adds something the reference contradicts.
Score 0 = wrong, or refuses when the reference answers.

QUESTION: {question}
REFERENCE: {reference}
CANDIDATE: {candidate}

Reply as JSON: {{"score": 0|1|2, "reason": "one sentence"}}
"""


def llm_judge(prompt: str, *, tier: str = "LARGE",
              max_tokens: int = 2048) -> dict[str, Any]:
    """One judge call. Returns the parsed JSON verdict.

    Uses a *different and stronger* tier than the system under test by
    default. Self-preference bias is real and well documented: a model rates
    its own output higher than a neutral judge does (Zheng et al. 2023). Never
    judge a model with itself when you can avoid it, and when you cannot, say
    so in your report.
    """
    from aip.llm import chat, extract_json

    # max_tokens must be generous. Reasoning-capable judges spend most of their
    # output budget on invisible thinking tokens, and a 512-token cap truncates
    # the JSON *after* the thinking -- which surfaces as an unparseable verdict
    # scored 0, i.e. a silent, systematic downward bias on your headline metric.
    # This is T1 failure mode #4, and it cost this module a faithfulness score
    # of 0.667 that was really 0.911.
    res = chat(prompt, tier=tier, temperature=0.0, max_tokens=max_tokens,
               return_full=True)
    out, finish = res["text"], res.get("finish_reason")

    if finish == "length":
        res = chat(prompt, tier=tier, temperature=0.0, max_tokens=max_tokens * 2,
                   return_full=True)
        out, finish = res["text"], res.get("finish_reason")

    try:
        verdict = extract_json(out)
    except ValueError:
        return {"score": 0, "parse_error": True, "truncated": finish == "length",
                "reason": f"unparseable judge output "
                          f"({'truncated' if finish == 'length' else 'malformed'}): "
                          f"{out[:200]}"}

    # Judges return a bare list surprisingly often -- typically a one-element
    # list wrapping the verdict, sometimes a list of per-claim verdicts. Callers
    # do verdict.get("score"), so an unnormalised list is an AttributeError
    # deep inside an eval run that has already cost money. Normalise here.
    if isinstance(verdict, list):
        dicts = [v for v in verdict if isinstance(v, dict)]
        if not verdict:
            return {"score": 0, "parse_error": True,
                    "reason": "judge returned an empty list -- usually a truncated object"}
        if len(dicts) == 1:
            verdict = dicts[0]
        elif dicts:
            # Several verdicts: take the minimum score, which is the
            # conservative reading for a faithfulness-style rubric.
            verdict = min(dicts, key=lambda d: d.get("score", 0))
        else:
            return {"score": 0, "parse_error": True,
                    "reason": f"judge returned a non-dict list: {str(verdict)[:200]}"}
    if not isinstance(verdict, dict):
        return {"score": 0, "parse_error": True,
                "reason": f"judge returned {type(verdict).__name__}: {str(verdict)[:200]}"}
    return verdict


def judge_agreement(judge_scores: Sequence[float], human_scores: Sequence[float]
                    ) -> dict[str, float]:
    """Calibrate a judge against human labels before trusting it.

    Rule for this module: you may not report an LLM-judge number in a lab
    unless you have hand-labelled at least 20 cases and reported the agreement
    here. If Cohen's kappa is below ~0.4, your judge is measuring something
    other than what you think, and the fix is the rubric, not the model.
    """
    if len(judge_scores) != len(human_scores) or not judge_scores:
        raise ValueError("judge and human score lists must be non-empty and equal length")
    n = len(judge_scores)
    agree = sum(1 for a, b in zip(judge_scores, human_scores) if a == b) / n

    labels = sorted(set(judge_scores) | set(human_scores))
    pj = {l: sum(1 for s in judge_scores if s == l) / n for l in labels}
    ph = {l: sum(1 for s in human_scores if s == l) / n for l in labels}
    pe = sum(pj[l] * ph[l] for l in labels)
    kappa = (agree - pe) / (1 - pe) if pe < 1 else 1.0
    return {"raw_agreement": agree, "cohens_kappa": kappa, "n": float(n)}


# ===========================================================================
# runner and report
# ===========================================================================
@dataclass
class Case:
    id: str
    input: Any
    expected: Any = None


@dataclass
class CaseResult:
    id: str
    output: Any = None
    metrics: dict[str, float] = field(default_factory=dict)
    error: str | None = None
    latency_ms: float = 0.0


@dataclass
class EvalReport:
    name: str
    results: list[CaseResult]
    budget: dict[str, Any]

    @property
    def n(self) -> int:
        return len(self.results)

    @property
    def n_errors(self) -> int:
        return sum(1 for r in self.results if r.error)

    def aggregate(self) -> dict[str, float]:
        keys: set[str] = set()
        for r in self.results:
            keys |= set(r.metrics)
        agg = {k: statistics.fmean(r.metrics[k] for r in self.results if k in r.metrics)
               for k in sorted(keys)}
        agg["error_rate"] = self.n_errors / self.n if self.n else 0.0
        return agg

    def summary(self) -> str:
        agg = {k: v for k, v in self.aggregate().items() if not k.startswith("field.")}
        width = max((len(k) for k in agg), default=10)
        lines = [f"── {self.name} ── n={self.n}  errors={self.n_errors}"]
        lines += [f"   {k:<{width}}  {v:.4f}" for k, v in agg.items()]
        b = self.budget
        lines.append(
            f"   {'cost_usd':<{width}}  {b.get('cost_usd', 0):.4f}   "
            f"(p50 {b.get('latency_p50_ms', 0):.0f} ms / p95 {b.get('latency_p95_ms', 0):.0f} ms, "
            f"{b.get('calls', 0)} calls, {b.get('cached_calls', 0)} cached)"
        )
        return "\n".join(lines)

    def failures(self, metric: str = "record_accuracy", limit: int = 10) -> list[CaseResult]:
        """The cases you should actually read. Error triage starts here."""
        bad = [r for r in self.results if r.error or r.metrics.get(metric, 1.0) < 1.0]
        return sorted(bad, key=lambda r: r.metrics.get(metric, -1.0))[:limit]

    def to_dict(self) -> dict[str, Any]:
        def jsonable(x: Any) -> Any:
            return x.model_dump() if hasattr(x, "model_dump") else x

        return {
            "name": self.name,
            "n": self.n,
            "aggregate": self.aggregate(),
            "budget": self.budget,
            "results": [
                {"id": r.id, "metrics": r.metrics, "error": r.error,
                 "latency_ms": round(r.latency_ms, 1), "output": jsonable(r.output)}
                for r in self.results
            ],
        }

    def save(self, path: str | Path) -> Path:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.to_dict(), indent=2, default=str), encoding="utf-8")
        return p


def load_cases(path: str | Path, input_key: str = "input",
               expected_key: str = "expected") -> list[Case]:
    """Load a JSONL golden set."""
    cases = []
    with Path(path).open(encoding="utf-8") as fh:
        for i, line in enumerate(fh):
            if not line.strip():
                continue
            row = json.loads(line)
            cases.append(Case(id=str(row.get("id", i)), input=row[input_key],
                              expected=row.get(expected_key)))
    return cases


def run_eval(
    name: str,
    cases: Sequence[Case],
    system: Callable[[Any], Any],
    metric: Callable[[Any, Any], dict[str, float]],
    *,
    budget_usd: float = 1.0,
    workers: int = 4,
    progress: bool = True,
) -> EvalReport:
    """Run `system` over `cases`, score with `metric`, return a report.

    A failing case is data, not a crash: it becomes an error row in the report.
    Keep `workers` modest on free tiers or you will spend the saved time in
    429 backoff.
    """
    budget = Budget(limit_usd=budget_usd, label=name)

    def run_one(case: Case) -> CaseResult:
        t0 = time.perf_counter()
        try:
            out = system(case.input)
            m = metric(out, case.expected)
            return CaseResult(case.id, out, m, None, (time.perf_counter() - t0) * 1000)
        except Exception as exc:  # noqa: BLE001
            return CaseResult(
                case.id, None, {"error": 1.0}, f"{type(exc).__name__}: {exc}",
                (time.perf_counter() - t0) * 1000,
            )

    with budget:
        if workers <= 1:
            results = []
            for i, c in enumerate(cases, 1):
                results.append(run_one(c))
                if progress:
                    print(f"  {name}: {i}/{len(cases)}", end="\r")
        else:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                results = list(pool.map(run_one, cases))
        if progress:
            print(" " * 60, end="\r")

    return EvalReport(name, results, budget.as_dict())


def compare(*reports: EvalReport, metrics: Sequence[str] | None = None) -> str:
    """Side-by-side table of several runs. Print it and paste it in your report."""
    if not reports:
        return "(no reports)"
    aggs = [r.aggregate() for r in reports]
    keys = metrics or sorted(
        {k for a in aggs for k in a if not k.startswith("field.")}
    )
    name_w = max(len(k) for k in [*keys, "cost_usd", "latency_p95_ms"])
    col_w = max(12, max(len(r.name) for r in reports) + 2)
    header = f"{'metric':<{name_w}}" + "".join(f"{r.name:>{col_w}}" for r in reports)
    lines = [header, "-" * len(header)]
    for k in keys:
        row = f"{k:<{name_w}}"
        best = max((a.get(k, float("-inf")) for a in aggs), default=0)
        for a in aggs:
            v = a.get(k)
            cell = "—" if v is None else f"{v:.4f}" + ("*" if v == best and len(reports) > 1 else "")
            row += f"{cell:>{col_w}}"
        lines.append(row)
    for bk in ("cost_usd", "latency_p95_ms"):
        row = f"{bk:<{name_w}}"
        for r in reports:
            row += f"{r.budget.get(bk, 0):>{col_w}.4f}"
        lines.append(row)
    lines.append("")
    lines.append("* = best on that metric. Read the cost row before celebrating.")
    return "\n".join(lines)
