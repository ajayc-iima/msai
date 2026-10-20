#!/usr/bin/env python3
"""Lab 5 -- run the three arms back to back, in order, on purpose.

    python labs/lab5/run_all_arms.py

Why a driver instead of three commands: the arms have to be sequential. They
share one NVIDIA developer key that rate-limits in bursts, and running them
concurrently would convert 429s into refusals -- which would show up in the
metrics as quality loss caused by the harness rather than by the pipeline.

Each arm resumes from its own partial file, so re-running after a crash picks
up where it stopped and the earlier arms cost nothing (their model calls are
already in the content-addressed cache).
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

ARMS = [
    ("v1", "reports/lab5_v1.json"),
    ("v2a", "reports/lab5_v2a.json"),
    ("v2b", "reports/lab5_v2b.json"),
]


def main() -> None:
    only = sys.argv[1:] or None
    for variant, save in ARMS:
        if only and variant not in only:
            continue
        log = ROOT / "reports" / f"lab5_{variant}_run.log"
        print(f"\n{'=' * 70}\n== {variant} -> {save}\n{'=' * 70}", flush=True)
        t0 = time.time()
        with log.open("w", encoding="utf-8") as fh:
            proc = subprocess.run(
                [sys.executable, "labs/lab5/run_eval.py",
                 "--variant", variant, "--save", save],
                cwd=ROOT, stdout=fh, stderr=subprocess.STDOUT, text=True,
                check=False,
            )
        dt = time.time() - t0
        print(f"   exit={proc.returncode} in {dt / 60:.1f} min  (log: {log})",
              flush=True)
        mp = ROOT / "reports" / f"{Path(save).stem}.meta.json"
        if mp.exists():
            meta = json.loads(mp.read_text(encoding="utf-8"))
            print(f"   stage-1 ndcg@10={meta['stage1']['ndcg@10']:.3f}  "
                  f"calls={meta['cost']['calls']}  "
                  f"p95={meta['gen_latency_ms']['p95']}ms", flush=True)
    print("\nall arms done")


if __name__ == "__main__":
    main()
