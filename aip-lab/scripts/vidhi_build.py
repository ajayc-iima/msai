#!/usr/bin/env python3
"""vidhi end-to-end build: ingest -> audit -> freeze store.

    python scripts/vidhi_build.py [--with-api]

--with-api also pulls PLFS rows from the live eSankhyiki API and requires
agreement with the PDF parsers on overlapping rows (dual-source rule).
Without it the build is fully offline from committed PDFs.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from vidhi import audit as A
from vidhi import store as S
from vidhi.sources import factsheet as F
from vidhi.sources import plfs as P
from vidhi.sources import tus as T

RAW = ROOT / "data" / "raw"
OUT = ROOT / "vidhi" / "store.json"


def main() -> int:
    rows, manifests = [], []
    for fn in (F.records, F.extended, P.records, T.records):
        r, m = fn(RAW)
        rows.extend(r)
        manifests.append(m)
    if "--with-api" in sys.argv:
        from vidhi.claims import extract
        from vidhi.sources import esankhyiki as E

        api_rows = []
        for q in [
            "What was all-India LFPR for age 15+ in usual status in PLFS 2023-24?",
            "What was female LFPR for age 15+ in usual status in PLFS 2023-24?",
            "What was WPR for age 15+ in usual status in PLFS 2023-24?",
            "What was the unemployment rate in PLFS 2023-24?",
        ]:
            api_rows.extend(E.fetch_claim(extract(q)))
        # Dual-source rule on overlap (same survey/round/indicator/measure/
        # residence/sex): API and PDF must agree exactly.
        pdf = {
            (
                r["survey"],
                r["round"],
                r["indicator"],
                r["measure"],
                r["residence"],
                r["sex"],
            ): r["value"]
            for r in rows
        }
        for a in api_rows:
            key = (
                a["survey"],
                a["round"],
                a["indicator"],
                a["measure"],
                a["residence"],
                a["sex"],
            )
            if key in pdf and float(pdf[key]) != float(a["value"]):
                print(
                    f"DUAL-SOURCE DISAGREEMENT on {key}: "
                    f"pdf={pdf[key]} api={a['value']}"
                )
                return 1
        print(f"dual-source agreement: {len(api_rows)} API rows checked")
        manifests.append(
            {
                "source": "eSankhyiki PLFS API",
                "rows": len(api_rows),
                "role": "cross-check only",
            }
        )
    rows, fails = A.audit_rows(RAW, rows)
    info = S.build(rows, OUT, {"inputs": manifests, "audit_failures": fails})
    print(f"store: {info['rows']} rows, {info['verified']} verified -> {OUT}")
    for f in fails:
        print("FAIL:", f)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())

