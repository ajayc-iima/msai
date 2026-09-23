#!/usr/bin/env python3
"""Warm the response cache for an eval split, serially and paced.

The Gemini free tier trips a per-minute quota under bursty parallel load,
which would otherwise degrade eval runs into needs_human_review fallbacks.
This driver walks the split one ticket at a time, waits out any 429 (up to
five minutes per call), and sleeps briefly between calls. Afterwards,
`run_eval.py` replays everything from cache for free.

    python labs/lab1/_warm_cache.py --split dev  --variant c
    python labs/lab1/_warm_cache.py --split test --variant c
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from aip.evals import load_cases  # noqa: E402
from extract import extract_b, extract_c  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=["dev", "test"], default="dev")
    ap.add_argument("--variant", choices=["b", "c"], default="c")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    root = Path(__file__).resolve().parents[2]
    cases = load_cases(root / f"data/eval/extraction_{args.split}.jsonl")
    if args.limit:
        cases = cases[: args.limit]
    fn = extract_b if args.variant == "b" else extract_c

    done = failed = 0
    for i, case in enumerate(cases, 1):
        for attempt in range(10):
            try:
                out = fn(case.input)
            except Exception as exc:  # noqa: BLE001 - expected: 429 quota
                if "429" not in str(exc):
                    raise
                out = None
                err = str(exc)
            else:
                dump = out.model_dump() if hasattr(out, "model_dump") else out
                # extract_* never raises: a 429 arrives as a review record.
                # A model-set review flag (no quota error in the reason) is a
                # legitimate result, not a failure.
                err = (dump or {}).get("review_reason", "")
                if "429" not in err and "RuntimeError" not in err:
                    done += 1
                    break
            wait = min(300.0, 30.0 * (attempt + 1))
            print(f"\n  {case.id}: 429 quota, waiting {wait:.0f}s "
                  f"(attempt {attempt + 1}) {err[:80]}", flush=True)
            time.sleep(wait)
        else:
            failed += 1
            print(f"\n  {case.id}: GAVE UP after 10 attempts", flush=True)
        print(f"[{i}/{len(cases)}] ok={done} failed={failed}", end="\r", flush=True)
        time.sleep(4.0)

    print(f"\nwarm complete: {done} ok, {failed} failed (all cached)")


if __name__ == "__main__":
    main()
