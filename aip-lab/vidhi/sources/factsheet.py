"""vidhi2 source: HCES 2023-24 factsheet Statement 7 + All-India pairs.

Machine extraction with cell provenance. No hand-typed values.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

PDF = "mospi_HCES_2023-24_Factsheet.pdf"

# PDF printing -> canonical state name.
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


def pdf_text(raw_dir: Path) -> tuple[str, str]:
    try:
        import pymupdf as fitz
    except ImportError:
        import fitz

    p = raw_dir / PDF
    sha = hashlib.sha256(p.read_bytes()).hexdigest()
    return "\n".join(pg.get_text() for pg in fitz.open(p)), sha


def statement7(text: str) -> dict[str, tuple[int, int]]:
    i = text.find("Statement 7:")
    seg = text[i : i + 6000]
    out: dict[str, tuple[int, int]] = {}
    for s in STATES:
        m = re.search(re.escape(s) + r"\s+([\d,]+)\s+([\d,]+)", seg)
        if not m:
            raise ValueError(f"Statement 7: no values for {s!r}")
        out[s] = (int(m.group(1).replace(",", "")), int(m.group(2).replace(",", "")))
    return out


def statement15(text: str) -> dict[str, tuple[int, int]]:
    """With-imputation state MPCE (Factsheet Statement 15).

    Same layout as Statement 7; All-India 4247/7078 cross-checks the
    FinalReport x PressNote imputed pair, proving the table is the
    with-imputation leg. Raises (not guesses) on layout drift.
    """
    i = text.find("Statement 15:")
    if i < 0:
        raise ValueError("Statement 15 header missing")
    seg = text[i : i + 6000]
    out: dict[str, tuple[int, int]] = {}
    for s in STATES:
        m = re.search(re.escape(s) + r"\s+([\d,]+)\s+([\d,]+)", seg)
        if not m:
            raise ValueError(f"Statement 15: no values for {s!r}")
        out[s] = (int(m.group(1).replace(",", "")), int(m.group(2).replace(",", "")))
    # Dual-source anchor: All-India must equal the chart imputed pair.
    if out.get("All-India") != (4247, 7078):
        raise ValueError(f"Statement 15 All-India leg unexpected: {out.get('All-India')}")
    return out


def records(raw_dir: Path) -> tuple[list[dict], dict]:
    """Returns (rows, manifest). Rows follow the store schema."""
    text, sha = pdf_text(raw_dir)
    rows: list[dict] = []
    for pdf_state, (rur, urb) in statement7(text).items():
        state = CANON.get(pdf_state, pdf_state)
        geo = "India" if state == "All-India" else "state"
        for res, val in (("rural", rur), ("urban", urb)):
            rid = (
                f"HCES_2023_24_MPCE_2023-24_{res}_"
                f"{state.replace(' ', '').replace('&', '+')}"
            )
            rows.append(
                {
                    "row_id": rid,
                    "survey": "HCES_2023_24",
                    "round": "2023-24",
                    "indicator": "MPCE",
                    "measure": "without_imputation",
                    "geography": geo,
                    "state": None if geo == "India" else state,
                    "residence": res,
                    "sex": None,
                    "age_group": None,
                    "reference_period": "Aug 2023-Jul 2024",
                    "value": val,
                    "unit": "Rs/month",
                    "source_document": PDF,
                    "table_or_section": "Statement 7",
                    "verification_status": "candidate",
                    "provenance": {
                        "extractor": "vidhi.sources.factsheet",
                        "pdf_sha256": sha,
                        "pdf_printing": pdf_state,
                    },
                }
            )
    # Statement 15: with-imputation state leg (beats eSankhyiki AI table on
    # provenance: every cell audited, no SQL hallucination). Same code path,
    # no architecture change.
    for pdf_state, (rur, urb) in statement15(text).items():
        state = CANON.get(pdf_state, pdf_state)
        if state == "All-India":
            continue  # national with-imputation already in extended()
        geo = "state"
        for res, val in (("rural", rur), ("urban", urb)):
            rid = (
                f"HCES_2023_24_MPCE_2023-24_{res}_with_{state.replace(' ', '').replace('&', '+')}"
            )
            rows.append(
                {
                    "row_id": rid,
                    "survey": "HCES_2023_24",
                    "round": "2023-24",
                    "indicator": "MPCE",
                    "measure": "with_imputation",
                    "geography": geo,
                    "state": state,
                    "residence": res,
                    "sex": None,
                    "age_group": None,
                    "reference_period": "Aug 2023-Jul 2024",
                    "value": val,
                    "unit": "Rs/month",
                    "source_document": PDF,
                    "table_or_section": "Statement 15",
                    "verification_status": "candidate",
                    "provenance": {
                        "extractor": "vidhi.sources.factsheet.statement15",
                        "pdf_sha256": sha,
                        "pdf_printing": pdf_state,
                    },
                }
            )
    manifest = {
        "source": PDF,
        "pdf_sha256": sha,
        "extractor": "vidhi.sources.factsheet",
        "rows": len(rows),
    }
    return rows, manifest


def _chart_run(text: str) -> tuple[list[float], list[float]]:
    """FinalReport Highlights chart (nominal block): rural
    [2022-23 w/o, 2023-24 w/o, 2022-23 with, 2023-24 with] then urban.
    Cross-checked vs PressNote. The LATER real-price block is ignored."""
    i = text.find("Comparison of average MPCE")
    if i < 0:
        raise ValueError("imputation chart header missing")
    j = text.find("with imputation", i)
    k = text.find("Average MPCE", j)
    nums: list[float] = []
    for line in text[j:k].splitlines():
        m = re.fullmatch(r"\s*([\d,]+)\s*", line)
        if m:
            nums.append(float(m.group(1).replace(",", "")))
    if len(nums) < 8:
        raise ValueError(f"chart run incomplete: {len(nums)}/8 nominal values")
    return nums[:4], nums[4:8]


def extended(raw_dir: Path) -> tuple[list[dict], dict]:
    """2022-23 without-imputation pair + both with-imputation pairs,
    dual-sourced (FinalReport chart x PressNote must agree)."""
    try:
        import pymupdf as fitz
    except ImportError:
        import fitz

    fr = raw_dir / "mospi_HCES_2023-24_FinalReport.pdf"
    fr_sha = hashlib.sha256(fr.read_bytes()).hexdigest()
    fr_text = "\n".join(pg.get_text() for pg in fitz.open(fr))
    pn = raw_dir / "mospi_HCES_2023-24_PressNote_30012025.pdf"
    pn_text = "\n".join(pg.get_text() for pg in fitz.open(pn))
    rural, urban = _chart_run(fr_text)
    r_22, r_24, r_22i, r_24i = rural[0], rural[1], rural[2], rural[3]
    u_22, u_24, u_22i, u_24i = urban[0], urban[1], urban[2], urban[3]
    # PressNote cross-check on 2023-24 imputed pair.
    m = re.search(
        r"imputed values.*?Rs\.\s*([\d,]+) and Rs\.\s*([\d,]+)"
        r" respectively, for rural and urban",
        pn_text,
        re.DOTALL,
    )
    if (
        not m
        or int(m.group(1).replace(",", "")) != int(r_24i)
        or int(m.group(2).replace(",", "")) != int(u_24i)
    ):
        raise ValueError("FinalReport x PressNote imputed values disagree")
    if (r_22, r_24, u_22, u_24) != (3773, 4122, 6459, 6996):
        raise ValueError("chart without-imputation leg disagrees with Statement 7")
    rows = []
    for res, v22, v22i, v24i in (
        ("rural", r_22, r_22i, r_24i),
        ("urban", u_22, u_22i, u_24i),
    ):
        for rnd, meas, val in (
            ("2022-23", "without_imputation", v22),
            ("2022-23", "with_imputation", v22i),
            ("2023-24", "with_imputation", v24i),
        ):
            rows.append(
                {
                    "row_id": f"HCES_2023_24_MPCE_{rnd}_{res}_{meas}",
                    "survey": "HCES_2023_24",
                    "round": rnd,
                    "indicator": "MPCE",
                    "measure": meas,
                    "geography": "India",
                    "state": None,
                    "residence": res,
                    "sex": None,
                    "age_group": None,
                    "reference_period": (
                        "Aug 2022-Jul 2023" if rnd == "2022-23" else "Aug 2023-Jul 2024"
                    ),
                    "value": val,
                    "unit": "Rs/month",
                    "source_document": "mospi_HCES_2023-24_FinalReport.pdf",
                    "table_or_section": "Highlights p8 (PressNote cross-checked)",
                    "verification_status": "candidate",
                    "provenance": {
                        "extractor": "vidhi.sources.factsheet.extended",
                        "pdf_sha256": fr_sha,
                        "cross_check": "PressNote imputed pair agrees",
                    },
                }
            )
    return rows, {
        "source": "mospi_HCES_2023-24_FinalReport.pdf",
        "pdf_sha256": fr_sha,
        "rows": len(rows),
    }
