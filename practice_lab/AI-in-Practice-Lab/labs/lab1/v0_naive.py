#!/usr/bin/env python3
"""Lab 1, Part A — the version everyone writes first.

Run it. Do not fix it. Characterise how it fails.

    python labs/lab1/v0_naive.py --n 40

The output is in two halves. Part 1 is what v0 actually did: how many records
bare `json.loads()` accepted and why it refused the rest. Part 2 is what was
hiding behind that refusal — the defects *inside* the JSON you never got to
see, because one trivial bug stopped you at the door.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from aip import Budget, chat  # noqa: E402

PROMPT = """Extract the following from this support ticket and return JSON:
category, urgency, sentiment, policy_number, product.

Ticket:
{ticket}
"""

ALLOWED_CATEGORIES = {
    "billing", "claims", "policy_change", "technical", "complaint", "information",
}

FENCE = re.compile(r"```")


def extract_v0(ticket: str) -> dict:
    """The version everyone writes first. Do not fix this — it is the exhibit."""
    out = chat(PROMPT.format(ticket=ticket), tier="SMALL", max_tokens=300)
    return json.loads(out)  # <-- the failure mode, waiting to happen


# --- diagnostics only. v0 does none of this; that is the whole point. ------

def classify_parse_failure(raw: str) -> str:
    """Name the reason a bare json.loads() rejected this string."""
    if FENCE.search(raw):
        return "markdown_fence"
    start, end = raw.find("{"), raw.rfind("}")
    if start != -1 and end > start:
        try:
            json.loads(raw[start : end + 1])
            return "prose_around_json"
        except json.JSONDecodeError:
            return "malformed_json"
    if start != -1:
        return "truncated_json"
    return "not_json_at_all"


def salvage(raw: str) -> dict | None:
    """Tolerantly recover the JSON object, the way Part B eventually will."""
    text = FENCE.sub("", raw)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        obj = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None


def content_problems(rec: dict, ticket: str) -> list[str]:
    """The defects that live *inside* a successfully parsed object."""
    problems = []
    for f in ("category", "urgency", "sentiment", "policy_number", "product"):
        if f not in rec:
            problems.append(f"missing:{f}")
    if isinstance(rec.get("urgency"), str):
        problems.append("urgency_is_string")
    if rec.get("category") not in ALLOWED_CATEGORIES:
        problems.append("category_out_of_set")
    pn = rec.get("policy_number")
    if pn and str(pn) not in ticket:
        problems.append("policy_number_invented")
    return problems


def _dump(title: str, counter: Counter[str], examples: dict[str, str]) -> None:
    print(f"  {title}")
    if not counter:
        print("    (none)")
        return
    for k, v in counter.most_common():
        print(f"    {k:<26} {v:>3}   e.g. {examples[k]}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=40)
    args = ap.parse_args()

    root = Path(__file__).resolve().parents[2]
    with (root / "data/eval/extraction_dev.jsonl").open(encoding="utf-8") as fh:
        rows = [json.loads(line) for line in fh][: args.n]

    blocked: Counter[str] = Counter()   # why bare json.loads() refused
    hidden: Counter[str] = Counter()    # defects behind the parse failure
    crashed: Counter[str] = Counter()   # everything else
    ex_blocked: dict[str, str] = {}
    ex_hidden: dict[str, str] = {}
    ex_crashed: dict[str, str] = {}
    parsed_strict = 0
    parsed_salvaged = 0
    ok = 0                   # strict parse AND no content problems
    ok_if_tolerant = 0       # would be clean if parsing were tolerant

    def tally(counter, examples, key, tid):
        counter[key] += 1
        examples.setdefault(key, tid)

    with Budget(limit_usd=0.10, label="lab1-v0") as b:
        for r in rows:
            try:
                raw = chat(PROMPT.format(ticket=r["input"]), tier="SMALL", max_tokens=300)
            except Exception as exc:  # noqa: BLE001
                tally(crashed, ex_crashed, f"exception:{type(exc).__name__}", r["id"])
                continue

            try:
                rec = json.loads(raw)  # exactly what v0 does
                parsed_strict += 1
                strict_ok = True
            except json.JSONDecodeError:
                tally(blocked, ex_blocked, classify_parse_failure(raw), r["id"])
                strict_ok = False
                rec = salvage(raw)
                if rec is None:
                    continue
                parsed_salvaged += 1

            problems = content_problems(rec, r["input"])
            for p in problems:
                tally(hidden, ex_hidden, p, r["id"])
            if not problems:
                ok_if_tolerant += 1
                if strict_ok:
                    ok += 1

    n = len(rows)
    print(f"\n{'=' * 64}\nPART 1 — what v0 actually did\n{'=' * 64}")
    print(f"  bare json.loads() parsed      {parsed_strict:>3}/{n}")
    print(f"  clean records                 {ok:>3}/{n}")
    print()
    _dump("why the parse failed:", blocked, ex_blocked)
    if crashed:
        print()
        _dump("unhandled exceptions:", crashed, ex_crashed)

    print(f"\n{'=' * 64}\nPART 2 — what was hiding behind it\n{'=' * 64}")
    print("  (diagnostics only — v0 does none of this)")
    print(f"  recovered by stripping the wrapper   {parsed_salvaged:>3}")
    print(f"  would be clean if parsing were tolerant   {ok_if_tolerant:>3}/{n}")
    print()
    _dump("defects INSIDE the recovered JSON:", hidden, ex_hidden)

    print("\n" + b.report())
    print("\nNow answer, in your notes:")
    print(f"  1. Fixing ONE line takes you from {parsed_strict}/{n} parsed to "
          f"{parsed_strict + parsed_salvaged}/{n} parsed — but only "
          f"{ok_if_tolerant}/{n} CLEAN. Why is that second number the whole "
          "justification for Part B?")
    print("  2. Which failure modes does tolerant parsing NOT fix?")
    print("  3. Which of these would a human reviewer even notice in production?")


if __name__ == "__main__":
    main()
