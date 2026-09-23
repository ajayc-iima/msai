#!/usr/bin/env python3
"""Lab 1, Parts B and C — the extractor you actually ship.

Complete the TODOs. `run_eval.py` imports `extract_b` and `extract_c` from
here, so keep those two function names.

The gold labels live in data/eval/extraction_dev.jsonl under "expected"; the
rules the labels were made from are in data/README.md (annotation guidelines).
Read both before writing anything. The lab brief — targets, checkpoints, and
the step-by-step assignment — is labs/lab1/README.md.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from aip.guards import PII_PATTERNS  # noqa: E402
from aip.llm import StructuredOutputError, structured  # noqa: E402

CATEGORIES = Literal["billing", "claims", "policy_change",
                     "technical", "complaint", "information"]


# ===========================================================================
# PART B — the schema
# ===========================================================================
class TicketRecord(BaseModel):
    """The contract: everything the model is allowed to say, and nothing else.

    Field `description`s are shipped to the model as part of the JSON Schema.
    They are the highest-leverage place for an instruction, because they sit
    next to the thing they govern. Write them as instructions to the model,
    not as documentation for a human.
    """

    # TODO B1a: `evidence` — declare it BEFORE or AFTER the fields it
    #           justifies? The order changes what the model writes there.
    #           Decide, and leave a one-line comment saying why.

    # TODO B1b: category — keep the Literal, write a description defining each
    #           of the six categories in one clause. Mind the boundary between
    #           "complaint" and the category the complaint is *about*.
    category: CATEGORIES = Field(description="TODO B1b")

    # TODO B1c: urgency — int, ge=1 le=5, with a description that defines the
    #           scale concretely (anchor at least 1, 3 and 5; state the 4/5
    #           tense rule and the 1/2 lookup rule from data/README.md).
    urgency: int = Field(ge=1, le=5, description="TODO B1c")

    # TODO B1d: sentiment  -> Literal["angry", "frustrated", "neutral", "satisfied"]
    #           (frustrated requires a referenced prior failure — say so.)
    # TODO B1e: product    -> Literal["bronze", "silver", "gold", "platinum", "unknown"]
    #           ("unknown" is legal; say explicitly when to use it.)
    # TODO B1f: language   -> Literal["en", "hi-en"]
    # TODO B1g: evidence   -> str, max_length=200, the span of the ticket that
    #           decided the category, quoted verbatim.

    # Part B only: the model decides these. In Part C you delete them from the
    # schema and compute them in code instead.
    policy_number: str | None = Field(
        default=None,
        description="TODO B1h: state the exact format, state that null is "
                    "required when none appears in the LIVE message, and "
                    "forbid inventing or reformatting one.",
    )
    contains_pii: bool = Field(default=False, description="TODO B1i")

    # Set by our code, never by the model.
    needs_human_review: bool = False
    review_reason: str = ""

    @field_validator("policy_number")
    @classmethod
    def _policy_format(cls, v: str | None) -> str | None:
        # TODO B1j: reject anything that is not exactly AUR-<7 digits>.
        #           Return None rather than raising if the model returned an
        #           empty string or the literal "null".
        return v


SYSTEM_PROMPT = """\
TODO B2: write this prompt.

It should be shorter than your first instinct — most of what you want to say
belongs in the field descriptions above. Order it for attention AND for prompt
caching: stable instructions first, volatile data last. The ticket text is
injected by the caller, after this.
"""


def extract_b(ticket: str) -> TicketRecord:
    """Part B: the model decides everything."""
    # TODO B3: call aip.llm.structured with TicketRecord and SYSTEM_PROMPT.
    #          (max_tokens=4096 is a sane budget on the current SMALL model.)
    # TODO B4: catch StructuredOutputError and return a record with
    #          needs_human_review=True and a review_reason. This function
    #          must never raise.
    raise NotImplementedError


# ===========================================================================
# PART C — move the deterministic work out of the model
# ===========================================================================
POLICY_RE = re.compile(r"\bAUR-\d{7}\b")

# Everything after a '>' line is quoted history from an earlier thread.
QUOTED_LINE = re.compile(r"^\s*>.*$", re.MULTILINE)


def extract_deterministic(ticket: str) -> dict:
    """TODO C1: return {'policy_number', 'contains_pii'} without a model call.

    policy_number:
        Find AUR-<7 digits>.

        TODO C3 — the trap. Some tickets contain TWO policy-number-shaped
        strings: one in the live body, one in the quoted reply below the '>'
        lines. They are not always the same number. Decide a rule, write it
        in a comment right here, implement it. Then ask yourself whether it
        generalises or whether you fitted it to this dataset.

    contains_pii:
        True if the ticket contains a phone number or an email address.
        aip.guards.PII_PATTERNS has the patterns; Aurora's own published
        addresses (support@ / grievance@aurorahealth.example) do NOT count,
        and a personal name alone does not either.
    """
    raise NotImplementedError


def apply_business_rules(fields: dict, ticket: str) -> dict:
    """TODO C1b: compute `escalate` in code.

        escalate = urgency >= 4 or 'ombudsman' appears in the ticket

    A business rule belongs in code, where it can be read by a compliance
    officer, changed without touching a prompt, and unit-tested.
    """
    raise NotImplementedError


class TicketRecordC(BaseModel):
    """TODO C2: the reduced schema the model sees in Part C.

    Copy TicketRecord and delete the fields you now compute in code. Fewer
    fields means a shorter prompt, fewer output tokens, and those fields at
    100% accuracy. Measure all three effects.
    """


def extract_c(ticket: str) -> dict:
    """Part C: model for judgement, code for everything else.

    Returns a plain dict (model fields + deterministic fields + business
    rules) so run_eval.py can score it against the gold labels directly.
    Must never raise.
    """
    raise NotImplementedError


if __name__ == "__main__":
    import json

    root = Path(__file__).resolve().parents[2]
    with (root / "data/eval/extraction_dev.jsonl").open(encoding="utf-8") as fh:
        sample = json.loads(fh.readline())
    print("--- ticket ---")
    print(sample["input"][:600])
    print("\n--- gold ---")
    print(sample["expected"])
    print("\n--- yours ---")
    print(extract_c(sample["input"]))
