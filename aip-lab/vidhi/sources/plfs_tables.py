"""PLFS Annual Report Highlights Tables 1-6: full national battery.

Both the PLFS 2023-24 Annual Report (mospi_PLFS_2023-24_AnnualReport.pdf)
and the PLFS 2025 Annual Report (mospi_PLFS_2025_F_REV_29052026.pdf) print
the same six nine-cell tables in their Highlights chapters:

    usual status  (ps+ss):  LFPR / WPR / UR
    current weekly status (CWS):  LFPR / WPR / UR

Each table carries one block per reference year (row label "PLFS 2025" or
"PLFS (2023-24)"), composed of two age-group rows -- "15 years and above"
and "all ages" -- of nine values each. Column order: rural m/f/p, urban
m/f/p, rural+urban m/f/p.

Integrity gates (build fails loudly on any drift):
  * dual file: the 2025 report is re-parsed from the independent
    dge_PLFS_2025_Annual_Report.pdf copy (distinct file bytes) and every
    cell must agree exactly;
  * anchored cells: mined values must reproduce figures already verified
    in the store (PLFS_2025 LFPR m/f/p 15+ = 79.1/40.0/59.3; PLFS_2023_24
    LFPR 15+ person 60.1 / female 41.7, WPR 15+ person 58.2, UR all-ages
    person 3.2).

Rows are candidates; vidhi_build merges them against vidhi.sources.plfs
rows (equal values REQUIRED on key collisions) and vidhi/audit.py traces
every value back to its source text before freezing the store.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

USUAL = "usual_status_ps_ss"
CWS = "CWS"

COLUMN_ORDER = (
    ("rural", "male"),
    ("rural", "female"),
    ("rural", "all"),
    ("urban", "male"),
    ("urban", "female"),
    ("urban", "all"),
    ("all", "male"),
    ("all", "female"),
    ("all", "all"),
)

AGES = (("15 years and above", "15plus"), ("all ages", "all"))

# Anchors: (round, indicator, measure, age, sex) -> r+u person-column value
# (the COLUMN_ORDER index of ("all", sex)). Verified store figures.
ANCHORS = {
    ("2025", "LFPR", USUAL, "15plus", "male"): 79.1,
    ("2025", "LFPR", USUAL, "15plus", "female"): 40.0,
    ("2025", "LFPR", USUAL, "15plus", "all"): 59.3,
    ("2023-24", "LFPR", USUAL, "15plus", "all"): 60.1,
    ("2023-24", "LFPR", USUAL, "15plus", "female"): 41.7,
    ("2023-24", "WPR", USUAL, "15plus", "all"): 58.2,
    ("2023-24", "UR", USUAL, "all", "all"): 3.2,
}

REPORTS = [
    {
        "pdf": "mospi_PLFS_2023-24_AnnualReport.pdf",
        "rounds": ["2023-24", "2022-23", "2021-22", "2020-21", "2019-20",
                   "2018-19", "2017-18"],
    },
    {
        "pdf": "mospi_PLFS_2025_F_REV_29052026.pdf",
        "rounds": ["2025", "2024", "2023", "2022"],
        "dual_pdf": "dge_PLFS_2025_Annual_Report.pdf",
    },
]


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _full_text(raw_dir: Path, pdf: str) -> str:
    try:
        import pymupdf as _f
    except ImportError:
        import fitz as _f  # type: ignore

    return "\n".join(pg.get_text() for pg in _f.open(raw_dir / pdf))


def _num(tok: str) -> float | None:
    t = tok.strip().rstrip("%").replace(",", "")
    try:
        return float(t)
    except ValueError:
        return None


def _ref_period(round_: str) -> str:
    if "-" in round_:
        y1, y2 = round_.split("-")
        y2 = y2 if len(y2) == 4 else "20" + y2
        return f"Jul {y1}-Jun {y2}"
    return f"Jan {round_}-Dec {round_}"


def _iter_tables(text: str):
    """Yield (indicator, measure, seg_start) for the Highlights tables.

    Header-spacing differs across reports ("Table 1:" vs "Table2:"), so the
    regex allows both. A table is the battery only if the 700-char window
    after its header says "usual status" or "current weekly status" AND
    names one of the three labour indicators.
    """
    for m in re.finditer(r"Table\s?\d+\s?:", text):
        window = text[m.start() : m.start() + 700]
        if "usual status" in window:
            measure = USUAL
        elif "current weekly status" in window:
            measure = CWS
        else:
            continue
        low = window.lower()
        if "participation" in low:
            ind = "LFPR"
        elif "worker population" in low or re.search(r"\bwpr\b", low):
            ind = "WPR"
            ind = "WPR"
        elif "unemployment rate" in low:
            ind = "UR"
        else:
            continue
        yield ind, measure, m.end()


def _parse_segment(text: str, start: int, rounds: list[str]) -> dict:
    """Parse one table's year blocks -> {round: {age_id: [9 floats]}}."""
    seg_end = text.find("refers to the period", start)
    if seg_end < 0:
        raise ValueError("year-note footer missing after Highlights table")
    seg = text[start:seg_end]
    out: dict[str, dict] = {}
    pos = 0
    for rnd in rounds:
        m = re.search(
            r"PLFS\s*\(" + re.escape(rnd) + r"\)|PLFS\s+" + re.escape(rnd),
            seg[pos:],
        )
        if not m:
            raise ValueError(f"round label {rnd} missing in highlights table")
        p = pos + m.end()
        ages: dict[str, list] = {}
        for age_txt, age_id in AGES:
            a = seg.find(age_txt, p)
            if a < 0:
                raise ValueError(f"age line {age_txt!r} missing for {rnd}")
            vals: list[float] = []
            for line in seg[a:].splitlines()[1:]:
                toks = line.strip()
                if not toks:
                    if vals:
                        break
                    continue
                if "(" in toks and not re.fullmatch(r"[\d.,%\s]+", toks):
                    if vals:
                        break
                    continue  # column-marker line "(1) (2) ..." before values
                v = _num(toks)
                if v is None:
                    if vals:
                        break
                    continue
                if not (1900 <= v <= 2100):
                    vals.append(v)
                if len(vals) == 9:
                    break
            if len(vals) != 9:
                raise ValueError(f"{rnd}/{age_id}: got {len(vals)}/9 values")
            ages[age_id] = vals
            p = a + len(age_txt)
        out[rnd] = ages
        pos = pos + m.end()
    return out


def cells_tables(text: str, rounds: list[str]) -> dict:
    """All six battery tables -> {(round, indicator, measure, age): [9 flts]}.

    Exactly one table per (indicator, measure) must be found; a repeat
    (e.g. a summary table with the same wording later in the file) or a
    missing one aborts the build.
    """
    found: dict[tuple[str, str], int] = {}
    cells: dict[tuple, list] = {}
    for ind, measure, start in _iter_tables(text):
        found[(ind, measure)] = found.get((ind, measure), 0) + 1
        if found[(ind, measure)] > 1:
            raise ValueError(
                f"second highlights table for {ind}/{measure}: parse drifted"
            )
        for rnd, ages in _parse_segment(text, start, rounds).items():
            for age_id, nine in ages.items():
                cells[(rnd, ind, measure, age_id)] = nine
    missing = [k for k, n in found.items() if n == 0]
    for key in [("LFPR", USUAL), ("WPR", USUAL), ("UR", USUAL),
                ("LFPR", CWS), ("WPR", CWS), ("UR", CWS)]:
        if key not in found:
            missing.append(key)
    if missing:
        raise ValueError(f"highlights tables not found: {missing}")
    return cells


def records(raw_dir: Path) -> tuple[list[dict], dict]:
    rows: list[dict] = []
    per_pdf: dict[str, dict] = {}
    for cfg in REPORTS:
        pdf = cfg["pdf"]
        sha = _sha(raw_dir / pdf)
        cells = cells_tables(_full_text(raw_dir, pdf), cfg["rounds"])
        per_pdf[pdf] = cells
        if cfg.get("dual_pdf"):
            dcells = cells_tables(
                _full_text(raw_dir, cfg["dual_pdf"]), cfg["rounds"])
            if dcells != cells:
                diff = [k for k in cells
                        if k not in dcells or cells[k] != dcells[k]]
                raise ValueError(
                    f"dual-source disagreement ({pdf} vs {cfg['dual_pdf']}) "
                    f"at {diff[:3]}"
                )
        for (rnd, ind, measure, age), nine in cells.items():
            ref = _ref_period(rnd)
            rr = rnd.replace("-", "_")
            for (res, sex), v in zip(COLUMN_ORDER, nine):
                row = {
                    "row_id": (
                        f"PLFS_{rr}_{ind}_{rnd}_{measure}_{res}_{sex}_{age}"
                    ),
                    "survey": f"PLFS_{rr}",
                    "round": rnd,
                    "indicator": ind,
                    "measure": measure,
                    "geography": "India",
                    "state": None,
                    "residence": res,
                    "sex": sex,
                    "age_group": age,
                    "reference_period": ref,
                    "value": v,
                    "unit": "percent",
                    "source_document": pdf,
                    "table_or_section": (
                        "Highlights Tables 1-6 ("
                        f"{'usual (ps+ss)' if measure == USUAL else 'CWS'})"
                    ),
                    "verification_status": "candidate",
                    "provenance": {
                        "extractor": "vidhi.sources.plfs_tables",
                        "pdf_sha256": sha,
                    },
                }
                if cfg.get("dual_pdf"):
                    row["provenance"]["cross_check_agrees"] = cfg["dual_pdf"]
                rows.append(row)

    # Anchor verification AFTER mining: reproduce the already-verified values.
    for (rnd, ind, measure, age, sex), want in ANCHORS.items():
        got = per_pdf["mospi_PLFS_2025_F_REV_29052026.pdf" if rnd == "2025"
                      else "mospi_PLFS_2023-24_AnnualReport.pdf"].get(
            (rnd, ind, measure, age))
        if got is None:
            raise ValueError(f"anchor slice {(rnd, ind, measure, age)} missing")
        idx = COLUMN_ORDER.index(("all", sex))
        if abs(got[idx] - want) > 1e-9:
            raise ValueError(
                f"anchor mismatch {(rnd, ind, measure, age, sex)}: "
                f"table {got[idx]} vs verified {want}"
            )

    return rows, {
        "source": "PLFS annual reports (Highlights Tables 1-6)",
        "pdf_sha256": _sha(raw_dir / "mospi_PLFS_2023-24_AnnualReport.pdf"),
        "rows": len(rows),
    }
