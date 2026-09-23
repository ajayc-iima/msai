"""Token accounting and hard budget enforcement.

Thin facade over aip.llm so embed/retrieval call sites can say
``from aip import cost`` without a second ledger. One Usage, one Budget,
one global ceiling — cost is a first-class metric in every lab.
"""
from __future__ import annotations

from aip.llm import (
    Budget,
    BudgetExceeded,
    Usage,
    _record as record,
    global_budget,
    is_priced,
    price_of,
)

__all__ = [
    "Budget",
    "BudgetExceeded",
    "Usage",
    "record",
    "global_budget",
    "is_priced",
    "price_of",
]
