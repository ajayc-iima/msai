"""vidhi2 source: PLFS Table 1/2 nine-number blocks + UR highlight.

Both annual reports print: round header, "15 years and above", then 9
values (rural m/f/p, urban m/f/p, combined m/f/p). The parser reads that
block structurally instead of cherry-picking figures.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

REPORTS = {
    "PLFS_2023_24": (
        "mospi_PLFS_2023-24_AnnualReport.pdf",
        "2023-24",
        "Jul 2023-Jun 2024",
        ["PLFS (2023-24)"],
    ),
    "PLFS_2025": (
        "mospi_PLFS_2025_F_REV_29052026.pdf",
        "2025",
        "Jan 2025-Dec 2025",
        ["PLFS 2025"],
    ),
}

TABLES = {
    "LFPR": ("Table 1", "Labour Force Participation"),
}

HIGHLIGHTS = {
    # indicator -> (statement phrase, age phrase); single all-India figure.
    "WPR": (
        "Worker Population Ratio (WPR) in usual status (ps+ss)",
        "persons of age 15 years and above in India",
    ),
    "UR": (
        "Unemployment Rate in usual status (ps+ss)",
        r"persons of all\s*age in India",
    ),
}


def _pages(raw_dir: Path, pdf: str) -> tuple[list[str], str]:
    try:
        import pymupdf as fitz
    except ImportError:
        import fitz

    p = raw_dir / pdf
    sha = hashlib.sha256(p.read_bytes()).hexdigest()
    return [pg.get_text() for pg in fitz.open(p)], sha


def _num(tok: str) -> float | None:
    try:
        return float(tok.replace(",", ""))
    except ValueError:
        return None


def nine_block(
    pages: list[str],
    table_no: str,
    table_about: str,
    round_label: str,
    variants: list[str],
) -> tuple[list[float], int]:
    """Find the page carrying table_no ABOUT table_about, then the round
    header, then the age line, then 9 values."""
    start = next(
        i
        for i, t in enumerate(pages)
        if table_no in t
        and table_about.lower() in t.lower()
        and "usual status (ps+ss)" in t
    )
    seg = "\n".join(pages[start : start + 6])
    labels = [round_label] + variants
    pos = -1
    for lab in labels:
        k = seg.find(lab, pos + 1)
        if k < 0:
            raise ValueError(f"{table_no}/{round_label}: header {lab!r} missing")
        pos = k
    age = seg.find("15 years and above", pos)
    if age < 0:
        raise ValueError(f"{table_no}/{round_label}: age line missing")
    vals: list[float] = []
    for line in seg[age:].splitlines()[1:]:
        v = _num(line.strip().rstrip("%"))
        if v is not None and not (1900 <= v <= 2100):
            vals.append(v)
        if len(vals) == 9:
            break
    if len(vals) != 9:
        raise ValueError(f"{table_no}/{round_label}: got {len(vals)}/9 values")
    pg = next(
        i + 1
        for i, t in enumerate(pages)
        if table_no in t
        and table_about.lower() in t.lower()
        and "usual status (ps+ss)" in t
    )
    return vals, pg


def highlight(pages: list[str], phrase: str, age: str) -> tuple[float, int]:
    for i, t in enumerate(pages):
        m = re.search(
            re.escape(phrase) + r"\s*for\s*" + age + r":\s*([\d.]+)%", t, re.DOTALL
        )
        if m:
            return float(m.group(1)), i + 1
    raise ValueError(f"highlight not found: {phrase} / {age}")


def ur_highlight(pages: list[str]) -> tuple[float, int]:
    for i, t in enumerate(pages):
        m = re.search(
            r"Unemployment Rate in usual status \(ps\+ss\) for persons of all "
            r"\s*age in India:\s*([\d.]+)%",
            t,
        )
        if m:
            return float(m.group(1)), i + 1
    raise ValueError("UR highlight not found")


def _row(
    survey: str,
    rnd: str,
    ref: str,
    ind: str,
    sex: str,
    val: float,
    unit: str,
    pdf: str,
    section: str,
    sha: str,
    pg: int,
) -> dict:
    return {
        "row_id": f"{survey}_{ind}_{rnd}_{sex}",
        "survey": survey,
        "round": rnd,
        "indicator": ind,
        "measure": "usual_status_ps_ss",
        "geography": "India",
        "state": None,
        "residence": "all",
        "sex": {"m": "male", "f": "female", "p": "all"}[sex],
        "age_group": "15plus" if ind in ("LFPR", "WPR") else "all",
        "reference_period": ref,
        "value": val,
        "unit": unit,
        "source_document": pdf,
        "table_or_section": section,
        "verification_status": "candidate",
        "provenance": {
            "extractor": "vidhi.sources.plfs",
            "pdf_sha256": sha,
            "pdf_page": pg,
        },
    }


def records(raw_dir: Path) -> tuple[list[dict], dict]:
    rows: list[dict] = []
    manifests = []
    for survey, (pdf, rnd, ref, variants) in REPORTS.items():
        pages, sha = _pages(raw_dir, pdf)
        vals, pg = nine_block(
            pages, TABLES["LFPR"][0], TABLES["LFPR"][1], rnd, variants
        )
        for sex, v in zip(("m", "f", "p"), (vals[6], vals[7], vals[8])):
            rows.append(
                _row(
                    survey,
                    rnd,
                    ref,
                    "LFPR",
                    sex,
                    v,
                    "percent",
                    pdf,
                    TABLES["LFPR"][0],
                    sha,
                    pg,
                )
            )
        manifests.append({"source": pdf, "pdf_sha256": sha})
    pages, sha = _pages(raw_dir, REPORTS["PLFS_2023_24"][0])
    wval, wpg = highlight(pages, *HIGHLIGHTS["WPR"])
    rows.append(
        {
            "row_id": "PLFS_2023_24_WPR_2023-24_all",
            "survey": "PLFS_2023_24",
            "round": "2023-24",
            "indicator": "WPR",
            "measure": "usual_status_ps_ss",
            "geography": "India",
            "state": None,
            "residence": "all",
            "sex": "all",
            "age_group": "15plus",
            "reference_period": "Jul 2023-Jun 2024",
            "value": wval,
            "unit": "percent",
            "source_document": REPORTS["PLFS_2023_24"][0],
            "table_or_section": "Highlights (Statement 4)",
            "verification_status": "candidate",
            "provenance": {
                "extractor": "vidhi.sources.plfs",
                "pdf_sha256": sha,
                "pdf_page": wpg,
            },
        }
    )
    uval, upg = highlight(pages, *HIGHLIGHTS["UR"])
    rows.append(
        {
            "row_id": "PLFS_2023_24_UR_2023-24_all",
            "survey": "PLFS_2023_24",
            "round": "2023-24",
            "indicator": "UR",
            "measure": "usual_status_ps_ss",
            "geography": "India",
            "state": None,
            "residence": "all",
            "sex": "all",
            "age_group": "all",
            "reference_period": "Jul 2023-Jun 2024",
            "value": uval,
            "unit": "percent",
            "source_document": REPORTS["PLFS_2023_24"][0],
            "table_or_section": "Highlights (Statement 14)",
            "verification_status": "candidate",
            "provenance": {
                "extractor": "vidhi.sources.plfs",
                "pdf_sha256": sha,
                "pdf_page": upg,
            },
        }
    )
    return rows, {"sources": manifests, "plfs_rows": len(rows)}
