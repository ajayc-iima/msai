#!/usr/bin/env python3
"""Prototype: machine-extract HCES factsheet Statement 7 -> truth rows.

Proves the scalable path: MoSPI (or anyone) does NOT hand-transcribe
10,000 rows. A deterministic parser extracts state MPCE pairs from the
official PDF; scripts/vidhi_audit_truth.py then verifies every value;
humans only review diffs. This script diffs machine output against the
hand-curated rows -- agreement proves the parser reproduces curation.

Usage:  python scripts/vidhi_ingest_factsheet.py
Exit 0 when every curated state row matches machine extraction.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Canonical name <- PDF printing ( MoSPI abbreviates one UT ).
CANON = {"Andaman & N Islands": "Andaman & Nicobar Islands"}

STATES = [
    "Andhra Pradesh",
    "Arunachal Pradesh",
    "Assam",
    "Bihar",
    "Chhattisgarh",
    "Delhi",
    "Goa",
    "Gujarat",
    "Haryana",
    "Himachal Pradesh",
    "Jharkhand",
    "Karnataka",
    "Kerala",
    "Madhya Pradesh",
    "Maharashtra",
    "Manipur",
    "Meghalaya",
    "Mizoram",
    "Nagaland",
    "Odisha",
    "Punjab",
    "Rajasthan",
    "Sikkim",
    "Tamil Nadu",
    "Telangana",
    "Tripura",
    "Uttar Pradesh",
    "Uttarakhand",
    "West Bengal",
    "Andaman & N Islands",
    "Chandigarh",
    "Dadra & Nagar Haveli and Daman & Diu",
    "Jammu & Kashmir",
    "Ladakh",
    "Lakshadweep",
    "Puducherry",
    "All-India",
]


def statement7_text() -> str:
    import fitz

    d = fitz.open(ROOT / "data" / "raw" / "mospi_HCES_2023-24_Factsheet.pdf")
    full = "\n".join(p.get_text() for p in d)
    i = full.find("Statement 7:")
    j = (
        full.find("Fact Sheet on HCES: 2023-24, M/o S&PI, GoI", i + 100)
        if i >= 0
        else -1
    )
    return full[i:j] if i >= 0 else ""


def parse_statement7(text: str) -> dict[str, tuple[int, int]]:
    """state -> (rural, urban). Raises on any unparseable state line."""
    out: dict[str, tuple[int, int]] = {}
    for s in STATES:
        m = re.search(re.escape(s) + r"\s+([\d,]+)\s+([\d,]+)", text)
        if not m:
            raise ValueError(f"no values parsed for {s!r}")
        out[s] = (int(m.group(1).replace(",", "")), int(m.group(2).replace(",", "")))
    return out


def main() -> int:
    machine = parse_statement7(statement7_text())
    truth = json.loads(
        (ROOT / "data" / "truth" / "ground_truth_tables.json").read_text(
            encoding="utf-8"
        )
    )["rows"]
    curated = {
        (CANON.get(r["state"], r["state"]), r["residence"]): r["value"]
        for r in truth
        if r.get("survey") == "HCES_2023_24"
        and r.get("indicator") == "MPCE"
        and r.get("geography") == "state"
        and r.get("round") == "2023-24"
        and r.get("measure") == "without_imputation"
        and r.get("verification_status") == "verified"
    }
    mism, missing = [], []
    for s, (rur, urb) in machine.items():
        canon = CANON.get(s, s)
        for res, val in (("rural", rur), ("urban", urb)):
            if (canon, res) not in curated:
                missing.append((canon, res, val))
            elif curated[(canon, res)] != val:
                mism.append((canon, res, curated[(canon, res)], val))
    print(f"machine-extracted state pairs: {len(machine)} ({2 * len(machine)} values)")
    print(f"curated state rows compared: {len(curated)}")
    print(f"mismatches: {len(mism)}  missing-from-curation: {len(missing)}")
    for m in mism:
        print("  MISMATCH:", m)
    for m in missing:
        print("  NOT CURATED:", m)
    if mism:
        return 1
    print(
        "OK: machine extraction reproduces every curated Statement 7 row; "
        f"curation gap is {len(missing)} rows, not a method gap."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
