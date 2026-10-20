"""HCES 2023-24 factsheet Statement 10: trend in consumption since 2011-12.

Statement 10 (All-India) carries, per sector, the average MPCE under
2011-12 (68th round), 2022-23 and 2023-24 -- all on the with-imputation
(MMRP-comparable) basis:

    Sector | 2011-12 | 2022-23 | 2023-24
    Rural  |  1,430  |  3,860  |  4,247
    Urban  |  2,630  |  6,521  |  7,078

The 2022-23 and 2023-24 columns must reproduce the already-verified
store rows exactly (dual-source anchor: the factsheet restates figures
that vidhi.sources.factsheet.mined from Statement 15 and the Final
Report chart) -- a mismatch aborts the build. The 2011-12 legs are then
emitted as new verified-visible rows (round 2011-12, measure
with_imputation), so "rural MPCE in 2011-12?" is finally answerable
*from the committed PDF text* instead of abstaining.
"""

from __future__ import annotations

import re
from pathlib import Path

from vidhi.sources.factsheet import PDF as FACTSHEET_PDF, pdf_text

# Segment markers.
_HEAD = "Statement 10: Trend in level of Consumption since 2011-12: All-India"
_END = "Statement 11"

# (sector, round) -> expected value (verified store figures for 22-23/23-24)
_COLS = ("2011-12", "2022-23", "2023-24")
_EXPECTED = {
    ("rural", "2022-23"): 3860.0,
    ("rural", "2023-24"): 4247.0,
    ("urban", "2022-23"): 6521.0,
    ("urban", "2023-24"): 7078.0,
}
_REF2011 = "Jul 2011-Jun 2012"


def records(raw_dir: Path) -> tuple[list[dict], dict]:
    text, sha = pdf_text(raw_dir)
    i = text.find(_HEAD)
    if i < 0:
        raise ValueError("HCES factsheet Statement 10 header not found")
    j = text.find(_END, i)
    if j < 0:
        raise ValueError("HCES factsheet Statement 11 not found after St10")
    seg = text[i:j]
    got = _rows_from(seg)
    for (res, rnd), want in _EXPECTED.items():
        if abs(got[(res, rnd)] - want) > 1e-9:
            raise ValueError(
                f"Statement 10 anchor mismatch {res}/{rnd}: "
                f"{got[(res, rnd)]} vs verified {want}"
            )
    rows = []
    for res in ("rural", "urban"):
        v = got[(res, "2011-12")]
        rows.append(
            {
                "row_id": (
                    f"HCES_2023_24_MPCE_2011-12_{res}_with_imputation"
                ),
                "survey": "HCES_2023_24",
                "round": "2011-12",
                "indicator": "MPCE",
                "measure": "with_imputation",
                "geography": "India",
                "state": None,
                "residence": res,
                "sex": None,
                "age_group": None,
                "reference_period": _REF2011,
                "value": v,
                "unit": "Rs/month",
                "source_document": FACTSHEET_PDF,
                "table_or_section": "Statement 10 (trend since 2011-12)",
                "verification_status": "candidate",
                "provenance": {
                    "extractor": "vidhi.sources.hces_trend",
                    "pdf_sha256": sha,
                },
            }
        )
    return rows, {
        "source": "HCES 2023-24 Factsheet Statement 10",
        "pdf_sha256": sha,
        "rows": len(rows),
        "anchor_check": "2022-23/2023-24 columns == verified store rows",
    }


def _rows_from(seg: str) -> dict:
    """Parse the Rural/Urban rows of the Statement-10 segment."""
    out: dict[tuple[str, str], float] = {}

    def parse(sector: str) -> None:
        m = re.search(rf"^{sector}\s*$", seg, re.M)
        if not m:
            raise ValueError(f"Statement 10 {sector} row label missing")
        vals = []
        for line in seg[m.end() :].splitlines():
            toks = line.strip()
            if re.fullmatch(r"[\d,]+(?:\.\d+)?", toks):
                vals.append(float(toks.replace(",", "")))
            if len(vals) == 3:
                break
        if len(vals) != 3:
            raise ValueError(
                f"Statement 10 {sector}: got {len(vals)}/3 values"
            )
        for col, v in zip(_COLS, vals):
            out[(sector.lower(), col)] = v

    parse("Rural")
    parse("Urban")
    return out
