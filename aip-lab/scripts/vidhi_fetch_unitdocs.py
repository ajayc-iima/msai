#!/usr/bin/env python3
"""Download Vidhi doc files from microdata.gov.in (docs only, no bulk unit data).

Reads MOSPI_MICRODATA_API_KEY from .env. Campus MITM requires
MOSPI_VERIFY_SSL=0 (else SSL verify fails). Records manifest with sha256.

    MOSPI_VERIFY_SSL=0 python scripts/vidhi_fetch_unitdocs.py
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass

DOCS: dict[str, list[str]] = {
    # v1 superseded rounds pruned Oct 2026 (re-freeze to latest). Do not re-add.
    "DDI-IND-CSO-MIS-78-2020": [
        "78th_Vol_II_Final.pdf",
        "78th_Vol_I_Final.pdf",
        "Final_Estimation_Procedure_NSS_78th.pdf",
        "Final_Tabulation_Plan_78th.pdf",
        "Readme78_MIS.pdf",
        "MIS_NMDS_2.0_V2.xlsx",
        "NSS_78th_Layout_Sch_5.1_mult_post.xls",
        "Tabulation_state.xlsx",
    ],
    # Latest rounds (Oct 2026 re-freeze): docs only, bulk unit zips skipped.
    "DDI-IND-CSO-PLFS-2023-24": [
        "1_README.docx",
        "2_1_Instruction_manual_PLFS_Vol_I.pdf",
        "2_2_Instruction_Manual_PLFS_Vol-II.pdf",
        "3_1_Estimation_Procedure_PLFS.pdf",
        "Data_LayoutPLFS_2023-24.xlsx",
        "District_codes_PLFS_Panel_4_202324_2024.xlsx",
        "NMDS_2dot0_PLFS_final_upd.docx",
        "Note_on_Updated_Instruction_for_PLFS_2023-24.pdf",
    ],
    "DDI-IND-MOSPI-NSS-HCES23-24": [
        "HCES2023-24_Vol_II-2.pdf",
        "HCES_2023_24_Imputation_Rate.xlsx",
        "Layout_HCES 2023-24.xlsx",
        "Objective_of_HCES.pdf",
        "Readme_HCES2023.docx",
        "Rider_for_users_of_unit_level_data_of_HCES.pdf",
        "Survey_methodology_and_Estimation_Procedure.pdf",
        "tabulation_state_code.xlsx",
    ],
    "DDI-IND-NSO-PLFS-Jan2025-Dec2025": [
        "Bstrm_file.xlsx",
        "FV_Data_LayoutPLFS_2025.xlsx",
        "Indian_Districts_CodeName.xlsx",
        "Indian_States_and_UTs_CodeName.xlsx",
        "mplus_identifier.xlsx",
        "PLFS_Vol_I_Instruction_to_FieldStaff_Jul_Dece2025.pdf",
        "PLFS_Vol_I_Instruction_to_Field_Staff_January_June 2025.pdf",
        "Readme million-plus identification.docx",
        "README2025.docx",
        "Schedule10_4_FIRSTVISIT_Janaury-June_2025.pdf",
        "Schedule10_4_FIRSTVISIT_July-Dec_2025.pdf",
        "Schedule10_4_REVISIT_Janaury-June_2025.pdf",
        "Schedule10_4_REVISIT_July-Dec_2025.pdf",
        "Schedule_0_0_PLFS_January-December_2025.pdf",
    ],
    "DDI-IND-NSO-TUS-2024-24": [
        "CODEs for Blocks of Sch 10.6 (2).xlsx",
        "Data_Layout_TUS_2024 (1).xlsx",
        "Instructions_TUS_2024 (2).pdf",
        "NMDS_2.0_TUS.xlsx",
        "Note_for_data_user (1).docx",
        "README_TUS_2024 (1).docx",
        "SampleDesign_EstimationProcedure_TUS 2024.pdf",
        "Vol_II TUS_2024.pdf",
    ],
}


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
    outdir = ROOT / "data" / "raw"
    outdir.mkdir(parents=True, exist_ok=True)
    manifest = []
    for ds, names in DOCS.items():
        files = requests.get(f"{base}/datasets/{ds}/fileslist", headers=headers,
                             verify=verify, timeout=60).json().get("files", [])
        by_name = {f["name"]: f for f in files}
        for name in names:
            if name not in by_name:
                print(f"SKIP missing {ds} :: {name}", file=sys.stderr)
                continue
            b64 = by_name[name]["base64"]
            url = f"{base}/fileslist/download/{ds}/{b64}"
            dest = outdir / f"microdata_{ds}__{name.replace(' ', '_')}"
            if dest.exists():
                print(f"exists {dest.name}")
            else:
                ok = False
                for att in range(4):
                    r = requests.get(url, headers=headers, verify=verify, timeout=300)
                    if r.status_code not in (401, 429, 500, 502, 503, 504):
                        break
                    time.sleep(3 * (att + 1))
                try:
                    r.raise_for_status()
                    dest.write_bytes(r.content)
                    print(f"got {dest.name} {len(r.content)/1e6:.1f}MB")
                    ok = True
                except Exception as e:
                    print(f"FAIL {ds} :: {name}: {e}", file=sys.stderr)
                    continue
            h = hashlib.sha256(dest.read_bytes()).hexdigest()
            manifest.append({"dataset": ds, "file": name, "local": str(dest.relative_to(ROOT)),
                             "bytes": dest.stat().st_size, "sha256": h,
                             "downloaded_at": datetime.now(timezone.utc).isoformat()})
    (outdir / "microdata_manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"manifest {len(manifest)} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
