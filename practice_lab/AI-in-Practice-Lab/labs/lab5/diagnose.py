#!/usr/bin/env python3
"""Lab 5 — the failure classifier.

    python labs/lab5/diagnose.py --input reports/lab4.json
    python labs/lab5/diagnose.py --input reports/lab4.json --pareto

Implements the T4 §5 diagnostic tree. Everything that can be decided by code
is decided by code; mode 2 needs your eyes and the script says so.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from aip.chunking import markdown_chunks
from labs.lab3.search import load_corpus, load_questions

MODES = {
    1: "missing_content",
    2: "chunk_boundary",
    3: "embedding_mismatch",
    4: "ranking",
    5: "reranker",
    6: "generation",
    7: "presentation",
}

_STOP = frozenset(
    ["the", "and", "for", "with", "that", "this", "from", "are", "was", "were", "have", "has", "not", "but", "any", "all", "can", "may", "will", "its", "their", "there", "here", "which", "what", "when", "who", "whom", "how", "why", "into", "onto", "than", "then", "also", "such", "some", "more", "most", "other", "same", "only", "over", "under", "out", "up", "down", "do", "does", "did", "done", "been", "being", "be", "to", "of", "in", "on", "at", "by", "as", "if", "or", "nor", "a", "an"]
)
_TOKEN = re.compile(r"[a-z0-9]+(?:\.[a-z0-9]+)?")
_NUM = re.compile(r"\d+(?:[.,]\d+)*%?")
_REFUSE_PREFIX = re.compile(
    r"^\s*(?:PARTIAL\s+)?REFUSE(?:\s+on\s+[^.]+)?\.\s*", re.IGNORECASE
)


def _norm(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^\w\s.%₹$]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _content_tokens(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(_norm(text)) if len(t) > 2 and t not in _STOP]


def _numbers(text: str) -> list[str]:
    return [n.replace(",", "") for n in _NUM.findall(text)]


def _num_present(num: str, hay: str) -> bool:
    """Match 30 / 30.0 / 1,00,000 style numbers with light normalisation."""
    variants = {num, num.lstrip("0") or "0"}
    if "." in num:
        variants.add(num.rstrip("0").rstrip("."))
    return any(v and v in hay for v in variants)


def answer_in_corpus(gold_answer: str, corpus: dict[str, str],
                     relevant_docs: list[str]) -> bool:
    """Mode 1 test: is the gold answer's content actually in the relevant docs?

    PROVIDED: a deliberately weak substring/overlap check. It will pass on a
    paraphrase and fail on a rewording, so it over-reports mode 1 and sends
    you hunting for data problems that are really retrieval problems.

    Improving it is part of the lab (see RUNSHEET.md): normalise, check key numbers
    and entities rather than whole strings, handle REFUSE / PARTIAL REFUSE.
    """
    raw = (gold_answer or "").strip()
    if re.match(r"^REFUSE\b", raw, re.IGNORECASE) and not re.match(
            r"^PARTIAL\s+REFUSE\b", raw, re.IGNORECASE):
        return False
    body = re.sub(r"^\s*(?:PARTIAL\s+)?REFUSE(?:\s+on\s+[^.]+)?\.\s*",
                  "", raw, flags=re.IGNORECASE)
    text = " ".join(corpus.get(d, "") for d in relevant_docs).lower()
    if not text:
        return False
    if not body.strip():
        return True
    # Weak check: any content word of length > 4 appearing in the docs.
    tokens = [t for t in re.findall(r"[a-z0-9]+", body.lower())
              if len(t) > 4 and t not in _STOP]
    if not tokens:
        return body.lower() in text
    hits = sum(1 for t in tokens if t in text)
    return hits / len(tokens) >= 0.4


_RETRIEVER_CACHE: dict = {}
_GOLD_FIX_CACHE: dict[str, bool | None] = {}


def _retriever():
    if "r" not in _RETRIEVER_CACHE:
        from labs.lab4.evaluate import build_retriever
        _RETRIEVER_CACHE["r"] = build_retriever()
    return _RETRIEVER_CACHE["r"]


def _gold_passage(q: dict, corpus: dict[str, str]) -> str:
    """Best single chunk from the gold docs for the mode-3 self-retrieval test."""
    ans_tokens = set(_content_tokens(q.get("gold_answer") or ""))
    best, best_score = "", -1.0
    for d in q.get("relevant_docs") or []:
        text = corpus.get(d, "")
        if not text:
            continue
        for chunk in markdown_chunks(text, d, size=400):
            toks = set(_content_tokens(chunk.text))
            if not toks:
                continue
            score = len(ans_tokens & toks) / max(len(ans_tokens), 1)
            if score > best_score:
                best_score, best = score, chunk.text
    if not best:
        for d in q.get("relevant_docs") or []:
            if corpus.get(d):
                return corpus[d][:600]
    return best


def _gold_context_fixes(q: dict, corpus: dict[str, str]) -> bool | None:
    """One generate + one judge: does gold context recover correctness >= 2?"""
    key = q["id"]
    if key in _GOLD_FIX_CACHE:
        return _GOLD_FIX_CACHE[key]
    docs = [corpus[d] for d in q.get("relevant_docs") or [] if d in corpus]
    if not docs:
        _GOLD_FIX_CACHE[key] = False
        return False
    try:
        from labs.lab4.evaluate import judge_correctness
        from labs.lab4.rag import answer_with_gold_context

        g = answer_with_gold_context(q["question"], docs)
        score = judge_correctness(q["question"], g.text, q["gold_answer"])
        fixed = score is not None and score >= 2
    except Exception:  # noqa: BLE001 - probe failure means "unknown", not crash
        fixed = None
    _GOLD_FIX_CACHE[key] = fixed
    return fixed


def classify(row: dict, q: dict, corpus: dict[str, str], *,
             gold_context_fixes_it: bool | None = None,
             in_top_30: bool | None = None,
             dropped_by_reranker: bool | None = None,
             probe: bool = True) -> tuple[int, str]:
    """TODO (core of the lab): walk the T4 §5 diagnostic tree.

    Returns (mode, evidence). Branches in tree order (keeps modes exclusive):

      C1  Mode 7 first: correctness >= 2 and not citations_valid -> presentation
      C2  Mode 1: not answer_in_corpus(...) -> missing content
      C3  Mode 6: gold_context_fixes_it is False -> generation
          *** INVERSION: gold context FIXING it means RETRIEVAL failed,
              not generation. gold_context_fixes_it True falls through. ***
      C4  Mode 4/5: in_top_30 and not gold_in_final -> ranking (5 if dropped_by_reranker)
      C5  Mode 3/2: not in_top_30 -> probe gold chunk's own text;
          self-retrieves -> mode 3 (embedding mismatch), else mode 2 needs_human_check
      C6  gold in final k and gold_context_fixes_it True -> mode 6 (generation-side:
          distractors / wrong chunk)
      C7  else -> mode 2 needs_human_check

    probe=False skips LLM/top-30 calls; branches that need them fall through
    to needs_human_check.
    """
    raise NotImplementedError(
        "TODO: implement classify - walk C1..C7 (mode 7, 1, 6, 4/5, 3/2, 6, 2). "
        "Remember the mode-6 inversion."
    )


def pareto(tally: Counter) -> str:
    total = sum(tally.values()) or 1
    lines, cum = ["failure mode          n    share   cumulative"], 0
    for mode, n in tally.most_common():
        cum += n
        bar = "█" * round(30 * n / total)
        lines.append(f"{MODES[mode]:<20} {n:>3}   {n/total:>5.1%}   "
                     f"{cum/total:>5.1%}  {bar}")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="reports/lab4.json")
    ap.add_argument("--pareto", action="store_true")
    ap.add_argument("--save", default="reports/lab5_diagnosis.json")
    ap.add_argument("--no-llm", action="store_true",
                    help="skip gold-context / top-30 probes (offline triage)")
    args = ap.parse_args()

    rows = json.loads((ROOT / args.input).read_text(encoding="utf-8"))
    questions = {q["id"]: q for q in load_questions(include_unanswerable=True)}
    corpus = load_corpus()

    failures = [r for r in rows
                if r.get("correctness", 2) < 2 or not r.get("citations_valid", True)]
    print(f"{len(failures)} failures out of {len(rows)}\n")

    out, tally = [], Counter()
    for r in failures:
        q = questions[r["id"]]
        try:
            mode, evidence = classify(r, q, corpus,
                                      dropped_by_reranker=False,
                                      probe=not args.no_llm)
        except Exception as exc:  # noqa: BLE001 - one bad probe != dead diagnosis
            mode, evidence = 2, f"needs_human_check: probe error {type(exc).__name__}"
        tally[mode] += 1
        out.append({"id": r["id"], "kind": q["kind"], "mode": mode,
                    "mode_name": MODES[mode], "evidence": evidence,
                    "question": q["question"], "answer": r["answer"][:300]})
        print(f"  {r['id']:<5} {MODES[mode]:<20} {evidence}", flush=True)
        p = ROOT / args.save
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\n" + pareto(tally))
    print("\nCases marked needs_human_check are Part A2. Open them.")

    p = ROOT / args.save
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nsaved -> {p}")


if __name__ == "__main__":
    main()
