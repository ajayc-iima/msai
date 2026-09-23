#!/usr/bin/env python3
"""Lab 4 — your RAG pipeline.

Write this yourself. `aip/rag.py` is the reference implementation; look at it
after Part A, not before. Labs 5-7 build on whichever of the two you prefer,
but you must be able to explain every line of the one you use.
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from aip.chunking import markdown_chunks
from aip.guards import UNTRUSTED_SYSTEM_CLAUSE, delimit_untrusted
from aip.llm import chat
from aip.retrieval import Hit, Retriever, format_context

# The exact string the system must emit when it cannot answer. Exact, because
# downstream code detects refusal by matching it -- a paraphrase is a bug.
REFUSAL = "I don't have enough information in the provided sources to answer that."

# TODO A: write this before you read aip/rag.py::ANSWER_SYSTEM.
# Six required elements (T4 §6.1):
#   1. only from numbered sources; no general knowledge
#   2. cite by index [1], [2][5]
#   3. never cite a number that was not supplied
#   4. exact refusal string, verbatim
#   5. sources disagree -> surface it, do not pick silently
#   6. length discipline (two or three sentences unless more is needed)
ANSWER_SYSTEM = f"""\
# TODO A: replace this stub with your system prompt.
# It MUST contain the exact REFUSAL string:
#   "{REFUSAL}"
# and all six required elements listed above.
"""


@dataclass
class Answer:
    question: str
    text: str
    hits: list[Hit] = field(default_factory=list)
    refused: bool = False
    citations_valid: bool = False
    invalid_citations: list[int] = field(default_factory=list)
    n_citations: int = 0
    truncated: bool = False
    repaired: bool = False


def is_refusal(text: str) -> bool:
    """Exact-match detection for the contract refusal (prefix is enough)."""
    return text.strip().startswith(REFUSAL[:40])


def _cited_indices(text: str) -> list[int]:
    return sorted({int(m) for m in re.findall(r"\[(\d+)\]", text)})


def validate_answer(text: str, n_sources: int, finish_reason: str | None = None) -> dict:
    """TODO B2. Return a dict with at least:

        {"valid": bool, "refused": bool, "invalid_citations": [ints],
         "n_citations": int, "truncated": bool, "reason": str}

    Checks:
      - every [n] is between 1 and n_sources
      - not truncated (finish_reason == "length" means the answer was cut off,
        and a cut-off prose answer LOOKS FINE -- this is T1 failure mode 4 and
        it is the dangerous one)
      - a non-refusal answer contains at least one citation

    A refusal needs no citation; truncation and out-of-range indices fail even
    on a refusal. valid = no problems found.
    """
    raise NotImplementedError(
        "TODO B2: implement validate_answer (in-range citations, not truncated, "
        "non-refusal has >=1 citation)"
    )


def _generate(question: str, hits: list[Hit], *, tier: str = "MAIN",
              max_tokens: int = 600, correction: str | None = None) -> tuple[str, str | None]:
    context = delimit_untrusted(format_context(hits))
    prompt = f"{context}\n\nQuestion: {question}\n\nAnswer with citations:"
    if correction:
        prompt = (f"{prompt}\n\nYour previous answer failed validation: {correction}\n"
                  "Rewrite the full answer correctly under the same rules.")
    res = chat(prompt, system=ANSWER_SYSTEM, tier=tier, temperature=0.0,
               max_tokens=max_tokens, return_full=True)
    return res["text"].strip(), res.get("finish_reason")


def _repair_note(v: dict, n_sources: int) -> str:
    parts: list[str] = []
    if v["invalid_citations"]:
        parts.append(f"citations {v['invalid_citations']} are out of range; "
                     f"only 1-{n_sources} were supplied")
    if v["truncated"]:
        parts.append("the answer was cut off before finishing")
    if not v["refused"] and v["n_citations"] == 0:
        parts.append("every factual sentence needs at least one [n] citation")
    if not parts and not v["refused"]:
        parts.append("follow the citation and refusal rules exactly")
    return "; ".join(parts)


def answer_question(question: str, retriever: Retriever, *, k: int = 12,
                    final_k: int = 5, reranker=None, tier: str = "MAIN") -> Answer:
    """TODO B3: retrieve -> (rerank) -> generate -> validate -> maybe repair.

    Pipeline shape:
      hits = retriever.search(question, k=k)
      if reranker: hits = reranker.rerank(question, hits, k=final_k)
      else: hits = hits[:final_k]
      text, finish = _generate(question, hits, tier=tier)
      v = validate_answer(text, len(hits), finish)
      if invalid and not refused: ONE corrective retry, else fall back to REFUSAL.

    B3: decide what happens when validation fails. Whatever you decide, the
    function must never return an Answer with citations_valid=False and
    refused=False. That combination is the thing you are being paid to prevent.

    Defend your repair choice in a comment (retry / strip / refuse).
    """
    raise NotImplementedError(
        "TODO B3: implement answer_question (retrieve -> generate -> validate -> repair)"
    )


def answer_with_gold_context(question: str, gold_docs: list[str], *,
                             tier: str = "MAIN") -> Answer:
    """TODO E2: same generator, but the context is the gold documents.

    No retrieval at all -- read data/corpus/<doc_id>.md for each gold doc,
    chunk it or pass it whole, and generate. The difference between this and
    answer_question() is the damage your retriever is doing.

    MUST use the same _generate / ANSWER_SYSTEM as answer_question, or the
    E2 comparison is meaningless.
    """
    raise NotImplementedError(
        "TODO E2: implement answer_with_gold_context (same generator, gold docs as context)"
    )
