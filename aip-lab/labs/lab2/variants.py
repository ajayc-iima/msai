#!/usr/bin/env python3
"""Lab 2 — the configurations under test.

Each variant is a callable `str -> dict`. `grid.py` runs them all through the
same harness, so the only thing that differs between rows of your table is the
thing you intended to differ.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from labs.lab1.extract import (  # noqa: E402
    SYSTEM_PROMPT, TicketRecord, apply_business_rules, extract_deterministic,
)

# ---------------------------------------------------------------------------
# A1 — your six chosen examples.
# ---------------------------------------------------------------------------
# TODO A1: choose 6 dev-set tickets. For EACH, write one line saying what it
#          teaches that prose cannot. Pick edges, not averages (T2 §2.2):
#            - the billing/complaint boundary
#            - a ticket with no policy number (teaches null)
#            - a Hinglish ticket
#            - a satisfied-but-urgent ticket (the sentiment/urgency trap)
#            - a ticket whose policy number is only in a quoted reply
#            - one you got wrong in Lab 1
FEW_SHOT_IDS: list[str] = [
    "T0097",   # teaches: billing/complaint boundary — "3rd time writing", double debit,
               # explicit ombudsman threat and demand for refund still scores as
               # billing, not complaint. Anger + escalation language alone doesn't
               # flip the category; the underlying issue (a transaction error) does.

    "T0048",   # teaches: no policy number anywhere in the ticket → policy_number
               # must be null, not a guessed/hallucinated AUR-xxxxxxx value.

    "T0021",   # teaches: hi-en handling — "Jaldi karo please" mixed into an
               # otherwise English ticket is enough to tag language as hi-en,
               # and genuine urgency here (blocked at a hospital desk, real-time
               # deadline) legitimately drives urgency to 5 — contrast with T0201
               # below where the same phrase does NOT justify high urgency.

    "T0222",   # teaches: sentiment/urgency trap — ticket opens with praise
               # ("Very good", fast cashless approval) and asks a routine
               # follow-up question. A model anchoring on "policy/claim history"
               # keywords might inflate urgency; correct output is satisfied,
               # urgency 1. Positive tone overrides surface complexity.

    "T0037",   # teaches: policy number extraction from forwarded/quoted body —
               # the ticket is a "---------- Forwarded message ----------" wrapper;
               # AUR-5878606 sits inside the forwarded content itself, not in a
               # header or the outermost text. Extraction can't just grep the
               # first few lines.

    "T0153",   # teaches: complaint/claims boundary, the one I got wrong — cashless
               # denied at a network hospital, admission tomorrow. This reads like
               # a claims-process issue (compare T0165, same scenario → claims),
               # but the accusatory "this is your problem, not mine" framing and
               # absence of a claim reference number makes it a complaint about
               # service, not a claims-status question. Tone decides the category
               # when the facts alone are ambiguous.
]

def load_examples(ids: list[str]) -> list[dict]:
    rows = [json.loads(l) for l in
            (ROOT / "data/eval/extraction_dev.jsonl").open(encoding="utf-8")]
    by_id = {r["id"]: r for r in rows}
    missing = [i for i in ids if i not in by_id]
    if missing:
        raise KeyError(f"unknown example ids: {missing}")
    return [by_id[i] for i in ids]


from typing import Literal
from pydantic import BaseModel, Field

from aip.llm import StructuredOutputError, structured
from labs.lab1.extract import CATEGORIES, TicketRecordC


def few_shot_block(ids: list[str]) -> str:
    """Render the examples into the prompt.

    The example output format must be byte-identical to the format you are
    asking the model to produce. A mismatch here is a classic own goal.
    """
    examples = load_examples(ids)
    # Pre-computed accurate evidence quotes and fields matching TicketRecordC schema
    known_evidence = {
        "T0097": "THIS IS THE THIRD TIME I am writing about teh double debit on AUR-7548999. Rs 8750 taken twice, nobody has called back in 45 days. Refund it or I am going to teh ombudsman.",
        "T0048": "Please add my mother as a dependent on my policy. She is 63. What will teh premium impact be?",
        "T0021": "Your portal has been down all morning and I am standing at the hospital insurance desk trying to show my Aurora Gold policy my policy.",
        "T0222": "Can you confirm the restoration benefit is still available this year on AUR-4940770?",
        "T0037": "My father is admitted in ICU right now and the hospital says cashless is DENIED on AUR-5878606. We need approval immediately.",
        "T0153": "The network hospital refused cashless saying you have not settled their dues. This is your problem, not mine. Policy my Aurora Silver policy, admission is tomorrow.",
    }

    blocks = ["\n# Examples of Input and Desired Output:"]
    for ex in examples:
        tid = ex["id"]
        exp = ex["expected"]
        ev = known_evidence.get(tid, "")
        output_obj = {
            "evidence": ev,
            "category": exp.get("category"),
            "urgency": exp.get("urgency"),
            "sentiment": exp.get("sentiment"),
            "product": exp.get("product"),
            "language": exp.get("language"),
        }
        blocks.append(
            f"\n--- Example Ticket ({tid}) ---\n"
            f"{ex['input'].strip()}\n"
            f"Output JSON:\n"
            f"{json.dumps(output_obj, indent=2)}"
        )
    return "\n".join(blocks) + "\n"


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
    """Add a `reasoning: str` field FIRST (T2 §3.3).

    Pydantic keeps declaration order, and field order in the JSON Schema
    influences generation order. Putting reasoning first makes it condition the
    answer; putting it last makes it a post-hoc rationalisation. You want the
    first. Measure the difference in output tokens.
    """

    reasoning: str = Field(
        description="Brief step-by-step reasoning explaining category, urgency, sentiment, "
                    "product, and language decisions before producing them."
    )
    evidence: str = Field(
        max_length=200,
        description="The span of the ticket that determined the category, quoted "
                    "verbatim from the text. At most 200 characters."
    )
    category: CATEGORIES = Field(
        description=TicketRecordC.model_fields["category"].description
    )
    urgency: int = Field(
        ge=1, le=5,
        description=TicketRecordC.model_fields["urgency"].description
    )
    sentiment: Literal["angry", "frustrated", "neutral", "satisfied"] = Field(
        description=TicketRecordC.model_fields["sentiment"].description
    )
    product: Literal["bronze", "silver", "gold", "platinum", "unknown"] = Field(
        description=TicketRecordC.model_fields["product"].description
    )
    language: Literal["en", "hi-en"] = Field(
        description=TicketRecordC.model_fields["language"].description
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

    Triggers:
      1. Validation / extraction failed or empty/short evidence.
      2. Self-consistency disagreement: sample a second time from SMALL at
         temperature=0.7. If the predicted category differs, the model is
         uncertain -> escalate to MAIN tier.

    Record which path each ticket took -- set rec['_path'] = 'small' | 'large'
    so grid.py can report the escalation rate.
    """
    det = extract_deterministic(ticket)

    # First call: SMALL at temperature 0.0 (default deterministic)
    try:
        rec1 = structured(ticket, schema=TicketRecordC, system=SYSTEM_PROMPT, tier="SMALL")
        m_dict1 = rec1.model_dump()
        ev1 = m_dict1.get("evidence", "").strip()
        cat1 = m_dict1.get("category")
    except Exception:
        # If SMALL call fails, escalate immediately to MAIN
        return _call_main(ticket, det)

    # If evidence is missing or too short, escalate to MAIN
    if len(ev1) < 5:
        return _call_main(ticket, det)

    # Check self-consistency with a second SMALL sample at temperature 0.7
    # (T > 0 prevents identical cache hit and measures sampling uncertainty)
    try:
        rec2 = structured(
            ticket,
            schema=TicketRecordC,
            system=SYSTEM_PROMPT,
            tier="SMALL",
            temperature=0.7,
        )
        m_dict2 = rec2.model_dump()
        cat2 = m_dict2.get("category")
        if cat1 != cat2:
            # Models disagree on category -> escalate to MAIN
            return _call_main(ticket, det)
    except Exception:
        return _call_main(ticket, det)

    # If consistent and well-formed, accept SMALL result
    m_dict1["needs_human_review"] = False
    m_dict1["review_reason"] = ""
    m_dict1["_path"] = "small"
    merged = {**m_dict1, **det}
    return apply_business_rules(merged, ticket)


def _call_main(ticket: str, det: dict) -> dict:
    """Escalation path to MAIN tier."""
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
