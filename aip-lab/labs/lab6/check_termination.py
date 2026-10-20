#!/usr/bin/env python3
"""Lab 6, Part A2/A3 -- prove each termination condition fires.

    python labs/lab6/check_termination.py

Three budgets, each triggered deliberately:
  1. tool-call budget .... R02 ("search a..z, aa..") against ToolGuard(max_calls=2)
  2. wall clock ........... max_seconds=0.001; the loop must stop, not hang
  3. spend ................ BudgetExceeded. On this provider every model is
                           UNPRICED (spent stays $0.00), so a live run cannot
                           trip the wire; the test trips the same wire with a
                           synthetic priced usage and asserts it raises.
A3: an unanswerable question with max_iterations=2 terminates via the call
budget instead of looping forever.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from aip.cost import Budget, BudgetExceeded, Usage
from aip.guards import ToolGuard
from labs.lab6.agent import deny_all, run_agent
from labs.lab6.redteam import inject_documents, load_suite

R02 = next(c for c in load_suite() if c["id"] == "R02")["payload"]
UNANSWERABLE = "What is Aurora's claim settlement ratio for last year?"


def check(name: str, cond: bool, detail: str) -> bool:
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}: {detail}")
    return cond


def main() -> None:
    inject_documents(load_suite())
    ok = True

    # R02's "search the alphabet" does not reliably make THIS model call tools
    # (it answers without calling -- also fine, and still terminates). To trip
    # the call budget deterministically, ask a question that needs two tools
    # with a budget of one: the second call must be denied.
    r = run_agent(
        "What is the remaining sum insured on AUR-1234567, and what would "
        "a Gold premium be at eldest age 50 with 3 members?",
        guard=ToolGuard(max_calls=1, confirm_fn=deny_all), layers=set())
    ok &= check("max_calls", r["stopped_because"] == "max_calls",
                f"stopped={r['stopped_because']} calls={len(r['tool_log'])}")

    r = run_agent("What is the grace period?", guard=None,
                  max_seconds=0.001, layers=set())
    ok &= check("wall_clock", r["stopped_because"] == "timeout",
                f"stopped={r['stopped_because']}")

    b = Budget(limit_usd=0.0, label="lab6-spend-test")
    try:
        b.record(Usage("priced-model/x", 100, 100, 0.001, 5.0,
                       cached=False, calls=1, priced=True))
        tripped = False
    except BudgetExceeded:
        tripped = True
    ok &= check("spend_wire", tripped, "BudgetExceeded raised on priced usage")
    print("  (note: live spend-trip cannot fire on this profile -- every model "
          "is UNPRICED so spent stays $0.00. The Budget context still wraps "
          "every run_agent call; the wire is armed, never taut.)")

    r = run_agent(UNANSWERABLE, guard=None, max_iterations=2, layers=set())
    ok &= check("A3_unanswerable", r["stopped_because"] in
                ("answered", "max_calls", "max_iterations"),
                f"stopped={r['stopped_because']} "
                f"answer={r['answer'][:80]!r}")

    print("\nALL PASS" if ok else "\nSOME FAILED")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
