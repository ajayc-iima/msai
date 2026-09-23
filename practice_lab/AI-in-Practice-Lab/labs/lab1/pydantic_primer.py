#!/usr/bin/env python3
"""Pydantic primer — 8 exercises covering exactly the surface Lab 1 uses.

    python labs/lab1/pydantic_primer.py

No API key, no cost. You are ready when it prints `8/8 passing`.
"""
from __future__ import annotations

import sys
import traceback
from typing import Literal

from pydantic import BaseModel, Field, ValidationError, field_validator

# ---------------------------------------------------------------------------
# Exercises. Edit the models/functions marked TODO until they pass.
# ---------------------------------------------------------------------------


def ex1() -> None:
    """BaseModel + required fields. `Ticket` must require `category: str` and
    `urgency: int` at construction time."""
    class Ticket(BaseModel):
        # TODO: add the two fields
        pass

    t = Ticket(category="billing", urgency=3)
    assert t.category == "billing" and t.urgency == 3
    try:
        Ticket(category="billing")  # type: ignore[call-arg]
        raise AssertionError("missing urgency should have raised ValidationError")
    except ValidationError:
        pass


def ex2() -> None:
    """Field constraints. `urgency` must be an int between 1 and 5 inclusive."""
    class Ticket(BaseModel):
        category: str
        # TODO: constrain urgency

    Ticket(category="billing", urgency=5)
    try:
        Ticket(category="billing", urgency=6)
        raise AssertionError("urgency=6 should have failed")
    except ValidationError:
        pass


def ex3() -> None:
    """Literal. `category` must accept only the six allowed strings."""
    class Ticket(BaseModel):
        # TODO: category as Literal over:
        #   billing, claims, policy_change, technical, complaint, information
        pass

    Ticket(category="claims")
    try:
        Ticket(category="support")  # type: ignore[arg-type]
        raise AssertionError("category outside the set should have failed")
    except ValidationError:
        pass


def ex4() -> None:
    """Optional fields with constraints. `policy_number` must be `str | None`,
    default None, and must match AUR-<7 digits> when present."""
    class Ticket(BaseModel):
        category: str
        # TODO: policy_number
        pass

    assert Ticket(category="claims").policy_number is None
    Ticket(category="claims", policy_number="AUR-1234567")
    try:
        Ticket(category="claims", policy_number="aur-1234567")  # type: ignore[arg-type]
        raise AssertionError("badly formatted policy number should have failed")
    except ValidationError:
        pass


def ex5() -> None:
    """field_validator — normalise on the way in. `evidence` must be capped at
    200 characters: strings longer than that should be TRUNCATED, not rejected.
    """
    class Ticket(BaseModel):
        category: str
        # TODO: evidence: str with a validator that truncates to 200 chars
        pass

    t = Ticket(category="claims", evidence="x" * 500)
    assert len(t.evidence) == 200


def ex6() -> None:
    """ValidationError — catch it and read it. Return the list of missing
    field names from a failed construction, or [] if it validates.
    """
    class Ticket(BaseModel):
        category: str
        urgency: int

    # TODO: implement missing_fields so the asserts pass.
    def missing_fields(data: dict) -> list[str]:
        raise NotImplementedError

    assert missing_fields({"category": "claims", "urgency": 2}) == []
    assert missing_fields({"category": "claims"}) == ["urgency"]
    assert set(missing_fields({})) == {"category", "urgency"}


def ex7() -> None:
    """The three model_* methods you will use constantly:
      model_json_schema() -> the dict shipped to the model
      model_validate(obj) -> dict -> instance (raises ValidationError)
      model_dump()        -> instance -> dict
    """
    class Ticket(BaseModel):
        category: Literal["billing", "claims"]
        urgency: int = Field(ge=1, le=5)

    # TODO: use the three methods to make the asserts pass.
    schema = None    # the JSON-schema dict
    instance = None  # build from {"category": "claims", "urgency": 2} via model_validate
    dumped = None    # dict from the instance

    assert isinstance(schema, dict) and "properties" in schema
    assert instance.urgency == 2
    assert dumped == {"category": "claims", "urgency": 2}


def ex8() -> None:
    """Nested models and why field order matters. The dump must nest cleanly.
    Also: the order you declare fields is the order the model sees in the
    JSON schema — put `evidence` immediately after the field it justifies.
    """
    class Judgement(BaseModel):
        category: Literal["billing", "claims", "complaint"]
        # TODO: evidence: str (<= 200 chars), declared right after category

    class TicketRecord(BaseModel):
        ticket_id: str
        judgement: Judgement

    rec = TicketRecord.model_validate(
        {"ticket_id": "T1", "judgement": {"category": "claims", "evidence": "refund"}}
    )
    assert rec.judgement.category == "claims"
    assert rec.model_dump()["judgement"]["evidence"] == "refund"


EXERCISES = [ex1, ex2, ex3, ex4, ex5, ex6, ex7, ex8]


def main() -> None:
    passed = 0
    for i, fn in enumerate(EXERCISES, 1):
        try:
            fn()
            passed += 1
            print(f"ex{i}  PASS")
        except (AssertionError, NotImplementedError) as exc:
            print(f"ex{i}  FAIL  ({exc})")
        except Exception as exc:  # noqa: BLE001
            print(f"ex{i}  FAIL  ({type(exc).__name__}: {exc})")
            traceback.print_exc(limit=2)
    print(f"\n{passed}/{len(EXERCISES)} passing")
    if passed < len(EXERCISES):
        print("Work the TODOs above until all 8 pass.")
        sys.exit(1)


if __name__ == "__main__":
    main()
