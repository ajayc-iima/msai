#!/usr/bin/env python3
"""One-time bulk unit-data CSV download for in-corpus rounds.

Bulk rows are INFERENCE-only (never PASS truth). Reads key from .env.
Campus MITM: set MOSPI_VERIFY_SSL=0.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass

JOBS = [
    ("DDI-IND-NSO-PLFS-Jan2025-Dec2025", "Data_in_CSV.zip"),
    ("DDI-IND-MOSPI-NSS-HCES23-24", "HCES_Data_2023-24_Csv.zip"),
    ("DDI-IND-NSO-TUS-2024-24", "TUS2024.zip"),
    ("DDI-IND-CSO-MIS-78-2020", "CSV_MIS_78.zip"),
]


def main() -> int:
    import urllib3

    urllib3.disable_warnings()
    import requests

    key = os.getenv("MOSPI_MICRODATA_API_KEY", "")
    if not key:
        print("MOSPI_MICRODATA_API_KEY missing in .env", file=sys.stderr)
        return 1
    verify = os.getenv("MOSPI_VERIFY_SSL", "1").strip().lower() not in {"0", "false", "no"}
    base = "https://microdata.gov.in/NADA/index.php/api"
    headers = {"X-API-KEY": key}
    out = ROOT / "data" / "raw"
    out.mkdir(parents=True, exist_ok=True)
    for ds, name in JOBS:
        dest = out / f"microdata_{ds}__{name}"
        if dest.exists():
            print("exists", dest.name, round(dest.stat().st_size / 1e6, 1), "MB")
            continue
        fl = requests.get(
            base + "/datasets/" + ds + "/fileslist",
            headers=headers, verify=verify, timeout=60,
        ).json().get("files", [])
        by = {f["name"]: f for f in fl}
        if name not in by:
            print("MISSING", ds, name, sorted(by)[:10], file=sys.stderr)
            continue
        url = base + "/fileslist/download/" + ds + "/" + by[name]["base64"]
        for att in range(5):
            r = requests.get(url, headers=headers, verify=verify, timeout=900)
            if r.status_code not in (401, 429, 500, 502, 503, 504):
                break
            time.sleep(5 * (att + 1))
        r.raise_for_status()
        dest.write_bytes(r.content)
        print("got", dest.name, round(len(r.content) / 1e6, 1), "MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
