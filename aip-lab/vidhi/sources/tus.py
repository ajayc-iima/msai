"""vidhi2 source: TUS 2024 factsheet highlight sentences.

Sentence-anchored extraction: every value must sit inside its anchor
sentence (same audit principle as the truth audit). Chart-position
parsing is deliberately NOT used (fragile). Covers average-time and
the one clean participation-rate sentence; detailed activity tables
stay out until a robust table parser exists.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

PDF = "mospi_TUS_2024_Factsheet.pdf"

# (indicator, activity, sex, age_group, unit, anchor pattern, value)
PATTERNS = [
    (
        "average_time",
        "unpaid_domestic",
        "female",
        "6plus",
        "minutes",
        r"Females spent (\d+) minutes on an average in a day in unpaid\s*\n?domestic services",
        289,
    ),
    (
        "average_time",
        "unpaid_domestic",
        "male",
        "6plus",
        "minutes",
        r"Male members\s*\n?spent (\d+) minutes in a day in such activities",
        88,
    ),
    (
        "average_time",
        "caregiving",
        "female",
        "6plus",
        "minutes",
        r"Females spent (\d+) minutes in a day in caring",
        137,
    ),
    (
        "average_time",
        "caregiving",
        "male",
        "6plus",
        "minutes",
        r"(\d+) minutes spent by male members of\s*\n?the household",
        75,
    ),
    (
        "average_time",
        "culture_leisure",
        "all",
        "6plus",
        "minutes",
        r"(\d+) minutes on average in a day was spent in activities related\s*\n?to culture, leisure",
        171,
    ),
    (
        "average_time",
        "culture_leisure",
        "male",
        "6plus",
        "minutes",
        r"Male and female participants spent (\d+) minutes\s*\n?and \d+ minutes respectively",
        177,
    ),
    (
        "average_time",
        "culture_leisure",
        "female",
        "6plus",
        "minutes",
        r"Male and female participants spent \d+ minutes\s*\n?and (\d+) minutes respectively",
        164,
    ),
    (
        "participation_rate",
        "learning",
        "all",
        "6-14",
        "percent",
        r"([\d.]+)% of children aged 6 to 14 years reported engaging in\s*\n?learning",
        89.3,
    ),
    (
        "average_time",
        "learning",
        "all",
        "6-14",
        "minutes",
        r"children aged 6 to 14 years reported engaging in\s*\n?learning-related activities during the day and spent (\d+)\s*\n?minutes",
        413,
    ),
    (
        "average_time",
        "selfcare",
        "all",
        "6plus",
        "minutes",
        r"Self-care and maintenance activities comprised an average of\s*\n?(\d+) minutes",
        708,
    ),
    (
        "average_time",
        "employment",
        "all",
        "6plus",
        "minutes",
        r"Persons doing employment and related activities spent (\d+)\s*\n?minutes",
        440,
    ),
    (
        "average_time",
        "employment",
        "male",
        "6plus",
        "minutes",
        r"Male participants spent (\d+)\s*\n?minutes while female participants",
        473,
    ),
    (
        "average_time",
        "employment",
        "female",
        "6plus",
        "minutes",
        r"while female participants spent (\d+) minutes",
        341,
    ),
]


def records(raw_dir: Path) -> tuple[list[dict], dict]:
    try:
        import pymupdf as fitz
    except ImportError:
        import fitz

    p = raw_dir / PDF
    sha = hashlib.sha256(p.read_bytes()).hexdigest()
    text = "\n".join(pg.get_text() for pg in fitz.open(p))
    rows = []
    for ind, act, sex, age, unit, pat, expected in PATTERNS:
        m = re.search(pat, text)
        if not m:
            raise ValueError(f"TUS anchor missing: {pat[:60]}")
        val = float(m.group(1))
        if abs(val - expected) > 1e-9:
            raise ValueError(f"TUS value drift: {pat[:40]} got {val}, want {expected}")
        rows.append(
            {
                "row_id": f"TUS_2024_{ind}_{act}_{age}_{sex}",
                "survey": "TUS_2024",
                "round": "2024",
                "indicator": ind,
                # Every factsheet-prose average-time figure is a
                # per-participant statistic ("female participants spent...");
                # the same slice is carried by the Tables 4-6 battery, and
                # vidhi_build's merge requires equal values on the collision.
                "measure": "per_participant" if ind == "average_time" else None,
                "geography": "India",
                "state": None,
                "residence": "all",
                "sex": sex,
                "age_group": age,
                "activity": act,
                "reference_period": "Jan 2024-Dec 2024",
                "value": val,
                "unit": unit,
                "source_document": PDF,
                "table_or_section": "Factsheet HIGHLIGHTS",
                "verification_status": "candidate",
                "provenance": {
                    "extractor": "vidhi.sources.tus",
                    "pdf_sha256": sha,
                    "method": "sentence-anchored",
                },
            }
        )
    return rows, {"source": PDF, "pdf_sha256": sha, "rows": len(rows)}
