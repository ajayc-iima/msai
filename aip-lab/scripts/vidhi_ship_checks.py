#!/usr/bin/env python3
"""Vidhi Lab7 ship checks: staleness + cache sweep + TTFT/p95 + load smoke.

    python scripts/vidhi_ship_checks.py

- Staleness: store manifest built_at age, stale if >90d.
- Cache: exact hit ~0ms; semantic sweep notes no safe threshold (field-guard carries safety).
- TTFT/p95 cached vs uncached via pipeline timing.
- Load smoke: 20 concurrent asks (threads), reports errors + p95.
- Gate: fails non-zero on stale store or p95 breach (>6000ms uncached).
Saves reports/vidhi_ship.json
"""
from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    import datetime

    from vidhi import pipeline as P

    doc = json.loads((ROOT / "vidhi" / "store.json").read_text(encoding="utf-8"))
    built = (doc.get("manifest") or {}).get("built_at")
    stale_days = None
    try:
        if built:
            dt = datetime.datetime.fromisoformat(str(built).replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=datetime.timezone.utc)
            stale_days = (datetime.datetime.now(datetime.timezone.utc) - dt).total_seconds() / 86400
    except Exception:
        pass
    print(f"store built_at={built} age_days={round(stale_days,1) if stale_days is not None else 'unknown'} stale={bool(stale_days and stale_days>90)}")

    P._EXACT.clear()
    q = "What was rural MPCE in HCES 2023-24?"
    # Warm model+retrieval once (service lifespan does this; cold start is 19s cliff)
    try:
        from vidhi import answer as _A
        from vidhi.claims import extract as _ex

        _c = _ex(q)
        _A.retrieve(_c, P.firewall().adjudicate(_c), top_k=1)
    except Exception:
        pass
    P._EXACT.clear()
    t0 = time.perf_counter(); P.ask(q); t_unc = (time.perf_counter()-t0)*1000
    t0 = time.perf_counter(); P.ask(q); t_cached = (time.perf_counter()-t0)*1000
    print(f"TTFT uncached={t_unc:.1f}ms cached={t_cached:.1f}ms (targets: TTFT<=1500 cached<=800 uncached<=6000; templated gen, no autoregression)")

    # 20-concurrent smoke (Lab7 stretch: SQLite/file lock suspected)
    errs: list = []
    lats: list[float] = []
    P._EXACT.clear()

    def worker():
        try:
            a = time.perf_counter(); P.ask(q); lats.append((time.perf_counter()-a)*1000)
        except Exception as e:  # noqa: BLE001
            errs.append(str(e)[:120])

    ts = [threading.Thread(target=worker) for _ in range(20)]
    [t.start() for t in ts]; [t.join() for t in ts]
    lats.sort()
    p95 = lats[int(0.95*len(lats))] if lats else 0
    print(f"load 20-concurrent: errs={len(errs)} p95={p95:.1f}ms {'ok' if not errs else errs[:2]}")
    print("Semantic cache: no safe cosine threshold (danger 0.80-0.97 vs paraphrase 0.78-0.95 bge-small); "
          "field-guard compatible() carries safety, THRESHOLD=0.97 proposes only.")
    print("Alert: refusal-rate doubling vs baseline => broken index; monitor /metrics p99 + refusal share.")
    out = ROOT / "reports" / "vidhi_ship.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"built_at": built, "stale_days": stale_days, "ttft_uncached_ms": round(t_unc,1),
                               "cached_ms": round(t_cached,1), "load_errs": len(errs), "load_p95": round(p95,1)}, indent=2), encoding="utf-8")
    print(f"saved -> {out}")
    fails = []
    if stale_days is not None and stale_days > 90:
        fails.append("stale store >90d: schedule rebuild")
    if p95 > 6000:
        fails.append(f"load p95 {p95:.0f}ms >6000ms")
    if errs:
        fails.append(f"{len(errs)} load errors")
    if fails:
        print("SHIP FAIL:", fails); return 1
    print("SHIP ok"); return 0


if __name__ == "__main__":
    sys.exit(main())
