#!/usr/bin/env python3
"""Lab 2 — the configurations under test.

Each variant is a callable `str -> dict`. `grid.py` runs them all through the
same harness, so the only thing that differs between rows of your table is the
thing you intended to differ.

Requires a finished Lab 1: this module imports SYSTEM_PROMPT, TicketRecordC,
extract_deterministic, and apply_business_rules from labs/lab1/extract.py.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from aip.llm import StructuredOutputError, structured  # noqa: E402
from labs.lab1.extract import (  # noqa: E402
    SYSTEM_PROMPT,
    CATEGORIES,
    TicketRecordC,
    apply_business_rules,
    extract_deterministic,
)

# ---------------------------------------------------------------------------
# A1 — your six chosen examples.
# ---------------------------------------------------------------------------
# TODO A1: choose 6 dev-set tickets. For EACH, write one line saying what it
#          teaches that prose cannot. Pick edges, not averages:
#            - the billing/complaint boundary
#            - a ticket with no policy number (teaches null)
#            - a Hinglish ticket
#            - a satisfied-but-urgent ticket (the sentiment/urgency trap)
#            - a ticket whose policy number is only in a quoted reply
#            - one you got wrong in Lab 1
FEW_SHOT_IDS: list[str] = [
    # "Txxxx",  # teaches: ...
]


def load_examples(ids: list[str]) -> list[dict]:
    rows = [json.loads(l) for l in
            (ROOT / "data/eval/extraction_dev.jsonl").open(encoding="utf-8")]
    by_id = {r["id"]: r for r in rows}
    missing = [i for i in ids if i not in by_id]
    if missing:
        raise KeyError(f"unknown example ids: {missing}")
    return [by_id[i] for i in ids]


def few_shot_block(ids: list[str]) -> str:
    """Render the examples into the prompt.

    The example output format must be byte-identical to the format you are
    asking the model to produce. A mismatch here is a classic own goal.

    TODO A2: load each example, build the desired output object from
             `expected` (evidence / category / urgency / sentiment /
             product / language), and append one block per example:

                 --- Example Ticket (Txxxx) ---
                 <ticket text>
                 Output JSON:
                 { ... }

             Return the joined blocks ready to concatenate onto SYSTEM_PROMPT.
    """
    if not ids:
        raise ValueError("TODO A1: fill FEW_SHOT_IDS before running few_shot")
    raise NotImplementedError("TODO A2: implement few_shot_block()")


# ---------------------------------------------------------------------------
# The variants
# ---------------------------------------------------------------------------
def zero_shot(ticket: str, tier: str = "SMALL") -> dict:
    """Lab 1 Part C, no examples. This is your baseline."""
    det = extract_deterministic(ticket)
    try:
        rec = structured(ticket, schema=TicketRecordC, system=SYSTEM_PROMPT, tier=tier)
        m_dict = rec.model_dump()
        m_dict["needs_human_review"] = False
        m_dict["review_reason"] = ""
    except (StructuredOutputError, Exception) as exc:
        m_dict = {
            "evidence": "",
            "category": "information",
            "urgency": 1,
            "sentiment": "neutral",
            "product": "unknown",
            "language": "en",
            "needs_human_review": True,
            "review_reason": f"{type(exc).__name__}: {exc}",
        }
    merged = {**m_dict, **det}
    return apply_business_rules(merged, ticket)


_CACHED_FEW_SHOT_SYSTEM: str | None = None


def _get_few_shot_system_prompt() -> str:
    global _CACHED_FEW_SHOT_SYSTEM
    if _CACHED_FEW_SHOT_SYSTEM is None:
        _CACHED_FEW_SHOT_SYSTEM = SYSTEM_PROMPT + "\n" + few_shot_block(FEW_SHOT_IDS)
    return _CACHED_FEW_SHOT_SYSTEM


def few_shot(ticket: str, tier: str = "SMALL") -> dict:
    """zero_shot + the few-shot block."""
    det = extract_deterministic(ticket)
    system_prompt = _get_few_shot_system_prompt()
    try:
        rec = structured(ticket, schema=TicketRecordC, system=system_prompt, tier=tier)
        m_dict = rec.model_dump()
        m_dict["needs_human_review"] = False
        m_dict["review_reason"] = ""
    except (StructuredOutputError, Exception) as exc:
        m_dict = {
            "evidence": "",
            "category": "information",
            "urgency": 1,
            "sentiment": "neutral",
            "product": "unknown",
            "language": "en",
            "needs_human_review": True,
            "review_reason": f"{type(exc).__name__}: {exc}",
        }
    merged = {**m_dict, **det}
    return apply_business_rules(merged, ticket)


class TicketRecordReasoned(BaseModel):
    """Add a `reasoning: str` field FIRST so it conditions the answer.

    Pydantic keeps declaration order, and field order in the JSON Schema
    influences generation order. Putting reasoning first makes it condition the
    answer; putting it last makes it a post-hoc rationalisation. You want the
    first. Measure the difference in output tokens.
    """

    reasoning: str = Field(
        description="Brief step-by-step reasoning explaining category, urgency, "
                    "sentiment, product, and language decisions before producing them."
    )
    evidence: str = Field(
        max_length=200,
        description="The span of the ticket that determined the category, quoted "
                    "verbatim from the text. At most 200 characters."
    )
    category: CATEGORIES = Field(
        description=TicketRecordC.model_fields["category"].description
        if "category" in TicketRecordC.model_fields
        else "Ticket category: billing, claims, policy_change, technical, "
             "complaint, or information."
    )
    urgency: int = Field(
        ge=1, le=5,
        description=TicketRecordC.model_fields["urgency"].description
        if "urgency" in TicketRecordC.model_fields
        else "Ticket urgency 1-5. Anchor: 1 = self-service, 3 = stuck/waiting, "
             "5 = tense with money or access at stake."
    )
    sentiment: Literal["angry", "frustrated", "neutral", "satisfied"] = Field(
        description="Customer tone. 'frustrated' requires a referenced prior "
                    "failure; 'satisfied' only when the ticket reports a good outcome."
    )
    product: Literal["bronze", "silver", "gold", "platinum", "unknown"] = Field(
        description="Aurora product tier named in the ticket, or 'unknown' when "
                    "none is stated. Do not guess."
    )
    language: Literal["en", "hi-en"] = Field(
        description="'en' for English; 'hi-en' when Hindi words appear in an "
                    "otherwise English ticket (code-mixing)."
    )
    needs_human_review: bool = False
    review_reason: str = ""


def few_shot_reasoned(ticket: str, tier: str = "SMALL") -> dict:
    """few_shot with TicketRecordReasoned."""
    det = extract_deterministic(ticket)
    system_prompt = _get_few_shot_system_prompt()
    try:
        rec = structured(ticket, schema=TicketRecordReasoned, system=system_prompt, tier=tier)
        m_dict = rec.model_dump()
        m_dict.pop("reasoning", None)
        m_dict["needs_human_review"] = False
        m_dict["review_reason"] = ""
    except (StructuredOutputError, Exception) as exc:
        m_dict = {
            "evidence": "",
            "category": "information",
            "urgency": 1,
            "sentiment": "neutral",
            "product": "unknown",
            "language": "en",
            "needs_human_review": True,
            "review_reason": f"{type(exc).__name__}: {exc}",
        }
    merged = {**m_dict, **det}
    return apply_business_rules(merged, ticket)


def cascade(ticket: str) -> dict:
    """SMALL first; escalate to MAIN on a trigger you choose.

    Diagram:
        SMALL
          |-- validates AND evidence non-empty --> accept
          |-- otherwise --> MAIN --> accept, or flag for review

    Record which path each ticket took -- set rec['_path'] = 'small' | 'large'
    so grid.py can report the escalation rate.

    TODO C: implement the trigger. Weak to strong:
              1. validation / extraction failed (you already catch that)
              2. evidence field empty or too short
              3. self-consistency: second SMALL sample at temperature > 0
                 disagrees on category. Temperature MUST be > 0 -- at
                 temperature 0 the cache serves the second call from the
                 first, answers are byte-identical, and escalation silently
                 becomes 0% while everything looks fine.

            Then report escalation rate, blended cost, blended accuracy.
            And measure whether disagreement carries signal: agreement rate
            when correct vs when wrong.

            Record which path each ticket took -- set rec['_path'] = 'small'
            so grid.py can report the escalation rate.
    """
    det = extract_deterministic(ticket)

    # First call: SMALL at temperature 0.0 (default deterministic).
    # Replace the body below with your trigger logic; _call_main is given.
    try:
        rec1 = structured(ticket, schema=TicketRecordC, system=SYSTEM_PROMPT, tier="SMALL")
        m_dict1 = rec1.model_dump()
        ev1 = m_dict1.get("evidence", "").strip()
        # TODO C: choose your escalation trigger(s) here.
        #   e.g. if len(ev1) < 5: return _call_main(ticket, det)
        #   e.g. second sample at temperature=0.7; if categories differ: escalate
        _ = ev1  # unused until you implement the trigger
    except Exception:
        return _call_main(ticket, det)

    m_dict1["needs_human_review"] = False
    m_dict1["review_reason"] = ""
    m_dict1["_path"] = "small"
    merged = {**m_dict1, **det}
    return apply_business_rules(merged, ticket)


def _call_main(ticket: str, det: dict) -> dict:
    """Escalation path to MAIN tier. Written for you."""
    try:
        rec = structured(ticket, schema=TicketRecordC, system=SYSTEM_PROMPT, tier="MAIN")
        m_dict = rec.model_dump()
        m_dict["needs_human_review"] = False
        m_dict["review_reason"] = ""
    except (StructuredOutputError, Exception) as exc:
        m_dict = {
            "evidence": "",
            "category": "information",
            "urgency": 1,
            "sentiment": "neutral",
            "product": "unknown",
            "language": "en",
            "needs_human_review": True,
            "review_reason": f"{type(exc).__name__}: {exc}",
        }
    m_dict["_path"] = "large"
    merged = {**m_dict, **det}
    return apply_business_rules(merged, ticket)


VARIANTS = {
    "zero_shot": lambda t: zero_shot(t, "SMALL"),
    "zero_shot_main": lambda t: zero_shot(t, "MAIN"),
    "few_shot": lambda t: few_shot(t, "SMALL"),
    "few_shot_main": lambda t: few_shot(t, "MAIN"),
    "few_shot_reasoned": lambda t: few_shot_reasoned(t, "SMALL"),
    "few_shot_reasoned_main": lambda t: few_shot_reasoned(t, "MAIN"),
    "cascade": cascade,
}
