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
You answer questions for an insurance helpdesk using ONLY the numbered sources provided.

Rules, in priority order:
1. Answer only from the numbered sources. Do not use general knowledge, and do
   not guess. If the sources do not contain the answer, reply with exactly this
   sentence and nothing else:
   "{REFUSAL}"
   If only part of the question is supported, answer that part with citations
   and refuse the unsupported part by appending the same sentence.
2. Every factual sentence must end with a citation of the source(s) that
   support it, in the form [1] or [2][5].
3. Never cite a number that was not given to you in the sources.
4. If the sources disagree, say so and cite both. Do not pick one silently.
5. Be concise. Two or three sentences unless the question needs more.

{UNTRUSTED_SYSTEM_CLAUSE}
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
    """
    stripped = text.strip()
    refused = is_refusal(stripped)
    empty = not stripped
    truncated = finish_reason == "length"

    cited = _cited_indices(stripped)
    invalid = [c for c in cited if c < 1 or c > n_sources]
    n_citations = len(cited)

    reasons: list[str] = []
    if empty:
        reasons.append("empty")
    if truncated:
        reasons.append("truncated")
    if invalid:
        reasons.append(f"invalid_citations={invalid}")
    if not refused and not empty and n_citations == 0:
        reasons.append("no_citations")

    # A refusal needs no citation; everything else must be complete, in-range,
    # and cited. Truncation and out-of-range indices fail even on a refusal.
    valid = not reasons
    reason = "ok" if valid else "; ".join(reasons)

    return {
        "valid": valid,
        "refused": refused,
        "invalid_citations": invalid,
        "n_citations": n_citations,
        "truncated": truncated,
        "reason": reason,
    }


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
    """TODO: retrieve -> (rerank) -> generate -> validate -> maybe repair.

    B3: decide what happens when validation fails. Whatever you decide, the
    function must never return an Answer with citations_valid=False and
    refused=False. That combination is the thing you are being paid to prevent.
    """
    hits = retriever.search(question, k=k)
    if reranker is not None:
        hits = reranker.rerank(question, hits, k=final_k)
    else:
        hits = hits[:final_k]

    text, finish = _generate(question, hits, tier=tier)
    v = validate_answer(text, len(hits), finish)

    # B3 strategy: one corrective retry, then fall back to the exact refusal.
    #
    # Why not strip bad citations? Removing a bogus [n] leaves the claim
    # standing with no pointer -- it looks grounded and is no longer auditable.
    # Why not silently return? An out-of-range citation is a *provable*
    # hallucination; shipping it is the one wrong answer. Refusal is honest,
    # machine-detectable, and keeps citation validity at 1.00 by construction.
    repaired = False
    if not v["valid"] and not v["refused"]:
        max_tokens = 1200 if v["truncated"] else 600
        text, finish = _generate(
            question, hits, tier=tier, max_tokens=max_tokens,
            correction=_repair_note(v, len(hits)),
        )
        v2 = validate_answer(text, len(hits), finish)
        if v2["valid"]:
            repaired = True
            v = v2
        else:
            text = REFUSAL
            v = validate_answer(REFUSAL, len(hits), None)
            repaired = True

    return Answer(
        question=question,
        text=text,
        hits=list(hits),
        refused=v["refused"],
        citations_valid=v["valid"] or v["refused"],
        invalid_citations=v["invalid_citations"],
        n_citations=v["n_citations"],
        truncated=v["truncated"],
        repaired=repaired,
    )


def answer_with_gold_context(question: str, gold_docs: list[str], *,
                             tier: str = "MAIN") -> Answer:
    """TODO E2: same generator, but the context is the gold documents.

    No retrieval at all -- read data/corpus/<doc_id>.md for each gold doc,
    chunk it or pass it whole, and generate. The difference between this and
    answer_question() is the damage your retriever is doing.
    """
    hits: list[Hit] = []
    for i, doc in enumerate(gold_docs):
        for chunk in markdown_chunks(doc, f"gold{i}", size=800):
            hits.append(Hit(chunk, 1.0, "gold"))

    text, finish = _generate(question, hits, tier=tier)
    v = validate_answer(text, len(hits), finish)
    if not v["valid"] and not v["refused"]:
        max_tokens = 1200 if v["truncated"] else 600
        text, finish = _generate(
            question, hits, tier=tier, max_tokens=max_tokens,
            correction=_repair_note(v, len(hits)),
        )
        v2 = validate_answer(text, len(hits), finish)
        if v2["valid"]:
            v = v2
        else:
            text = REFUSAL
            v = validate_answer(REFUSAL, len(hits), None)

    return Answer(
        question=question,
        text=text,
        hits=hits,
        refused=v["refused"],
        citations_valid=v["valid"] or v["refused"],
        invalid_citations=v["invalid_citations"],
        n_citations=v["n_citations"],
        truncated=v["truncated"],
    )
