#!/usr/bin/env python3
"""Lab 5, Part A2 -- the evidence sheet. You read this; the script cannot.

    python labs/lab5/inspect_failures.py --input reports/lab4.json

For every failing question, prints the facts a mode-2 judgement needs:

  * the exact five chunks the generator was given (the delivered window)
  * which chunk of each gold document actually carries the missing words/numbers
  * where that chunk sits in the dense ranking -- ">30" means the retriever
    never surfaced it at all, which is a different failure from "found but
    trimmed"
  * which gold documents never reached the window, and their best rank

Everything here is deterministic and free -- no model calls -- so it is safe to
re-run and it is the same evidence every time.

    --dump Q04,Q20    print one question's evidence and exit
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from aip.retrieval import format_context
from labs.lab3.search import build_chunks, load_corpus, load_questions
from labs.lab5.diagnose import (
    _content_tokens,
    _is_failure,
    _norm,
    _num_present,
    _numbers,
    answer_span_in_context,
)

TOP_K = 30


def _sent(text: str, n: int = 150) -> str:
    return " ".join(text.split())[:n]


def _case(r: dict, q: dict, retriever, chunks) -> list[str]:
    gold_docs = list(q.get("relevant_docs") or [])
    hits = retriever.search(q["question"], k=TOP_K)
    rank_of = {h.chunk.chunk_id: h.rank + 1 for h in hits}
    window = hits[:5]
    window_ids = {h.chunk.chunk_id for h in window}
    ctx = format_context(window)

    span_ok, span_ev = answer_span_in_context(q["gold_answer"], ctx)
    missing_nums = [n for n in _numbers(_norm(q["gold_answer"]))
                    if not _num_present(n, _norm(ctx))]
    ctx_toks = set(_content_tokens(ctx))
    missing_toks = sorted({t for t in set(_content_tokens(q["gold_answer"]))
                           if t not in ctx_toks})

    def rk(cid: str) -> str:
        return str(rank_of[cid]) if cid in rank_of else f">{TOP_K}"

    out = [
        "=" * 100,
        (f"{r['id']}  [{q['kind']}]  correctness={r.get('correctness')} "
         f"faithfulness={r.get('faithfulness')} refused={r.get('refused')}"),
        f"  Q     : {q['question']}",
        f"  GOLD  : {_sent(q['gold_answer'], 320)}",
        f"  GOT   : {_sent(r['answer'], 320)}",
        f"  span in delivered window: {span_ok}  ({span_ev})",
        f"  missing numbers: {missing_nums}",
        f"  missing words  : {missing_toks}",
        f"  gold docs: {gold_docs}",
        "",
        "  -- delivered window (what the generator saw) --",
    ]
    for i, h in enumerate(window, 1):
        mark = "*" if h.doc_id in gold_docs else " "
        out.append(f"   [{i}]{mark} dense-rank {h.rank + 1:>2}  {h.doc_id:<36} "
                   f"{_sent(h.text, 120)}")

    out += ["", "  -- gold-doc chunks carrying the missing material --"]
    for d in gold_docs:
        doc_chunks = [c for c in chunks if c.doc_id == d]
        ranks = sorted(rank_of[c.chunk_id] for c in doc_chunks if c.chunk_id in rank_of)
        best = f"rank {ranks[0]}" if ranks else f"none in top-{TOP_K}"
        in_doc = "DELIVERED" if any(h.doc_id == d for h in window) else "NOT DELIVERED"
        out.append(f"   {d}  [{in_doc}]  {len(doc_chunks)} chunks, best {best}")
        carriers = []
        for c in doc_chunks:
            hay = set(_content_tokens(c.text))
            hn = _norm(c.text)
            hw = [t for t in missing_toks if t in hay]
            hnum = [n for n in missing_nums if _num_present(n, hn)]
            if hw or hnum:
                carriers.append((len(hw) + len(hnum), c, hw, hnum))
        carriers.sort(key=lambda t: -t[0])
        for _score, c, hw, hnum in carriers[:3]:
            where = "IN WINDOW" if c.chunk_id in window_ids else "outside window"
            out.append(f"     dense-rank {rk(c.chunk_id):>4}  {where:<15} "
                       f"covers words {hw} numbers {hnum}")
            out.append(f"        {_sent(c.text, 200)}")
    out.append("")
    return out


def inspect(rows: list[dict], only: list[str] | None = None) -> str:
    from labs.lab4.evaluate import build_retriever

    questions = {q["id"]: q for q in load_questions(include_unanswerable=True)}
    corpus = load_corpus()
    retriever = build_retriever()
    chunks = build_chunks(corpus, "markdown", 400)   # Lab 3/4 winning config

    lines: list[str] = []
    for r in rows:
        if not _is_failure(r):
            continue
        if only and r["id"] not in only:
            continue
        lines += _case(r, questions[r["id"]], retriever, chunks)
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="reports/lab4.json")
    ap.add_argument("--out", default="reports/lab5_evidence.txt")
    ap.add_argument("--dump", default="", help="comma-separated ids; prints, no save")
    args = ap.parse_args()
    rows = json.loads((ROOT / args.input).read_text(encoding="utf-8"))
    only = [s.strip() for s in args.dump.split(",") if s.strip()] or None
    text = inspect(rows, only)
    if only:
        print(text)
        return
    p = ROOT / args.out
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    print(f"wrote {p}  ({len(text.splitlines())} lines)")


if __name__ == "__main__":
    main()
