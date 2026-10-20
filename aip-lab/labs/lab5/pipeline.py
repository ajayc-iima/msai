#!/usr/bin/env python3
"""Lab 5 -- the v2 pipeline, and the three arms Part C measures.

    from labs.lab5.pipeline import answer, VARIANTS
    a = answer(question, retriever, variant="v2b")

Three arms, differing in exactly one thing each:

    v1    labs/lab4/rag.py, verbatim -- its ANSWER_SYSTEM imported, not
          re-typed.  The Lab 4 system, and the baseline every delta is against.
    v2a   v1 + ONE clause rewritten in the answer contract: completeness
          before brevity.  Targets the mode-6 cluster (n=12), where the
          generator produces the headline and drops the qualifiers, or refuses
          a question it has the numbers for.
    v2b   v2a + a second retrieval stage: retrieve k=30, cross-encoder rerank
          to final_k=5.  Targets the mode-4 cluster (n=4), whose material sits
          at dense ranks 8-18 and never makes the five-slot window.

Order matters and follows the tally: the biggest cluster is fixed first, alone.
The second fix is then layered on top so that v1->v2a and v2a->v2b each isolate
one variable.

Both fixes add **no model call per query**. The costs that move are prompt
tokens (a longer contract), completion tokens (longer answers) and ~0.6 s of
local CPU for the reranker.

Nothing here changes validation, the refusal string or the repair policy: those
are imported from labs/lab4/rag.py unchanged, so a difference in the numbers is
attributable to the fix and not to a looser contract.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from aip.guards import UNTRUSTED_SYSTEM_CLAUSE, delimit_untrusted
from aip.llm import chat as _chat
from aip.retrieval import Hit, Retriever, format_context
from labs.lab4.rag import (  # noqa: F401 - re-exported, unchanged
    ANSWER_SYSTEM,
    REFUSAL,
    Answer,
    _repair_note,
    is_refusal,
    validate_answer,
)

# ---------------------------------------------------------------------------
# transport hardening
# ---------------------------------------------------------------------------
# NVIDIA's developer key rate-limits in bursts and Lab 4's own log is full of
# 429s. A retried call is invisible in the metrics; an abandoned one silently
# becomes a refusal and shows up as a correctness loss that has nothing to do
# with the system under test. So we make the transport patient and leave the
# logic untouched.
_PATIENT = {"calls": 0, "waits": 0}


def _transient(exc: Exception) -> bool:
    text, name = str(exc), type(exc).__name__
    return ("429" in text or "RateLimit" in name or "503" in text
            or "ServiceUnavailable" in name or "Timeout" in name
            or "overloaded" in text.lower())


def patient_chat(*args, **kwargs):
    """chat() with outer retries for what aip.llm's 4 tries do not cover."""
    for attempt in range(10):
        try:
            out = _chat(*args, **kwargs)
            _PATIENT["calls"] += 1
            return out
        except Exception as exc:
            if not _transient(exc):
                raise
            backoff = min(60.0, 5.0 * (attempt + 1))
            _PATIENT["waits"] += 1
            print(f"    [throttle] {type(exc).__name__}: sleeping {backoff:.0f}s "
                  f"(retry {attempt + 1}/10)", flush=True)
            time.sleep(backoff)
    raise RuntimeError("still rate-limited after 10 patient retries")


def harden_transport() -> None:
    """Route every model call in the Lab 4/5 path through patient_chat.

    labs/lab4/rag.py does `from aip.llm import chat` at import time, so it needs
    the module attribute replaced; aip.evals.llm_judge imports inside the call,
    so patching aip.llm.chat is enough for the judges.
    """
    import aip.llm as llm_mod
    from labs.lab4 import rag

    llm_mod.chat = patient_chat
    rag.chat = patient_chat


# ---------------------------------------------------------------------------
# the answer contract
# ---------------------------------------------------------------------------
# v1's rule 5 is "Be concise. Two or three sentences unless the question needs
# more." Eleven of our seventeen failures are a correct first clause followed by
# a dropped qualifier, which is what a hard brevity rule invites. Fix 2 replaces
# the brevity rule with a completeness rule and keeps an upper bound, so this is
# a reordering of priorities rather than "write more".
ANSWER_SYSTEM_V2 = f"""\
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
5. COMPLETENESS BEFORE BREVITY. For every part of the question, state every
   condition, exception, cap, sub-limit, waiting period and qualifier that the
   sources attach to it -- the headline figure alone is an incomplete answer.
   If the sources attach a condition to a number, the condition is part of the
   number. Still keep it to the shortest complete answer: no preamble, no
   restating the question, no summary paragraph.

{UNTRUSTED_SYSTEM_CLAUSE}
"""

# v1 uses Lab 4's contract IMPORTED, not re-typed. Re-typing it would be a
# silent second variable: one whitespace difference and the "v1" arm stops being
# the Lab 4 baseline.
#
# v2a and v2b share ANSWER_SYSTEM_V2 on purpose -- fix 1 (the completeness
# clause) is present in both, and the only difference between them is the
# reranker. Keeping the two in step here is what makes v1 -> v2a and
# v2a -> v2b each isolate exactly one change.
SYSTEMS = {"v1": ANSWER_SYSTEM, "v2a": ANSWER_SYSTEM_V2, "v2b": ANSWER_SYSTEM_V2}

VARIANTS: dict[str, dict] = {
    # name   rerank   completeness-prompt
    "v1":   {"rerank": False, "completeness": False},
    "v2a":  {"rerank": False, "completeness": True},
    "v2b":  {"rerank": True,  "completeness": True},
}

_ACTIVE = "v1"


def activate(name: str) -> None:
    global _ACTIVE
    if name not in VARIANTS:
        raise ValueError(f"unknown variant {name!r}; choose from {sorted(VARIANTS)}")
    _ACTIVE = name


def active() -> str:
    return _ACTIVE


# ---------------------------------------------------------------------------
# generation
# ---------------------------------------------------------------------------
def _generate(question: str, hits: list[Hit], *, system: str,
              max_tokens: int = 600,
              correction: str | None = None) -> tuple[str, str | None]:
    context = delimit_untrusted(format_context(hits))
    prompt = f"{context}\n\nQuestion: {question}\n\nAnswer with citations:"
    if correction:
        prompt = (f"{prompt}\n\nYour previous answer failed validation: {correction}\n"
                  "Rewrite the full answer correctly under the same rules.")
    res = _chat(prompt, system=system, tier="MAIN", temperature=0.0,
                max_tokens=max_tokens, return_full=True)
    return res["text"].strip(), res.get("finish_reason")


def _retrieve(question: str, retriever: Retriever, *, rerank: bool,
              _rr) -> list[Hit]:
    """Stage 1 (dense k=12) and, for v2a/v2b, stage 2 (cross-encoder -> 5)."""
    if not rerank:
        return retriever.search(question, k=12)[:5]
    hits = retriever.search(question, k=30)
    return _rr.rerank(question, hits, k=5)


_RERANKER = None


def _reranker():
    """One shared cross-encoder. Loaded lazily: ~90 MB, and the v1 arm must not
    pay for it."""
    global _RERANKER
    if _RERANKER is None:
        from aip.retrieval import CrossEncoderReranker
        t0 = time.perf_counter()
        _RERANKER = CrossEncoderReranker()
        print(f"[lab5] cross-encoder loaded in {time.perf_counter() - t0:.1f}s",
              flush=True)
    return _RERANKER


def answer(question: str, retriever: Retriever, *, variant: str | None = None,
           rr=None) -> Answer:
    """v1 / v2a / v2b. Identical validation and repair to Lab 4."""
    cfg = VARIANTS[variant or _ACTIVE]
    rr = _reranker() if cfg["rerank"] else None

    hits = _retrieve(question, retriever, rerank=cfg["rerank"], _rr=rr)
    text, finish = _generate(question, hits, system=SYSTEMS[variant or _ACTIVE])

    v = validate_answer(text, len(hits), finish)
    repaired = False
    if not v["valid"] and not v["refused"]:
        max_tokens = 1200 if v["truncated"] else 600
        text, finish = _generate(question, hits, system=SYSTEMS[variant or _ACTIVE],
                                 max_tokens=max_tokens,
                                 correction=_repair_note(v, len(hits)))
        v2 = validate_answer(text, len(hits), finish)
        if v2["valid"]:
            repaired, v = True, v2
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
