"""aip — a tiny library for the AI-in-Practice labs.

    from aip import chat, structured, Budget

    text = chat("Summarise in one line:\n" + doc, tier="SMALL")

    class Ticket(BaseModel):
        category: Literal["billing", "claims"]

    t = structured(prompt, schema=Ticket, tier="SMALL")   # -> Ticket

Modules:
    config — model tiers, pricing, environment settings
    llm    — chat(), structured() with validation + repair loop
    guards — PII patterns / redaction
    evals  — golden-set loader, runner, metrics, reports
"""
from aip.llm import (
    Budget,
    BudgetExceeded,
    StructuredOutputError,
    chat,
    extract_json,
    structured,
)

__all__ = ["chat", "structured", "extract_json", "Budget", "BudgetExceeded",
           "StructuredOutputError"]
