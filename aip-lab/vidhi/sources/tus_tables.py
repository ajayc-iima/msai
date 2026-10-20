"""TUS 2024: factsheet Tables 1-11 battery + report Statements cross-check.

The factsheet prints the same nine ICATUS major divisions in nine tables,
grouped in three batches of three, in the same physical text order:

    batch 1 (participation rate %):     gender, then sector, then age
    batch 2 (per participant, minutes): gender, then sector, then age
    batch 3 (per person, minutes):      gender, then sector, then age

(the printed table numbers are T1/T3/T2 etc.: on pages 7, 9 and 11 the
sector table's rows precede the age table's in extraction order, while
the header numbering runs 1,2,3 / 4,6,5 / 7,9,8. The parser assigns
triples by physical order, not by table number.)

Every occurrence of a division name is followed (within a few lines) by
three values; grouping consecutive occurrences per division yields EXACTLY
nine triples per division -- the i-th triple maps to the semantics above.
Any drift in count aborts the build.

Structure taken from the factsheet is cross-checked against the full
report (mospi_TUS_2024_Report.pdf), which states the same battery in a
DIFFERENT layout (Statements 1-3: sector-major 9-column rows; Statements
5/6: age-group blocks; Statement 18: learning 6-14/15-29):

    factsheet gender triple (r+u m/f/p)
        == Statement 1/2/3 row columns 6-8
    factsheet sector triple (r/urban/r+u, persons)
        == Statement 1/2/3 row columns 2,5,8
    factsheet age triple cols 1-2 (15-29, 15-59)
        == Statement 5/6 person-block row cols 0-1
    factsheet learning 6-14 cells == Statement 18 person rural+urban row

(The factsheet's per-person-by-age tables [battery triples #9] have no
report twin: the report's Statement 13 is a normal-day/other-day
statistic on a different basis; those cells carry the structural-gate +
anchor guarantees only.)

Rows emitted:
  * factsheet battery rows (gender/sector/age triples, all nine divisions
    plus the Table 10/11 unpaid/paid/residual group rows);
  * report Statement 5/6/13 rows: age 15-29/15-59/60plus crossed with
    sex (male/female/person) -- coverage the factsheet never prints.

measure: None for participation_rate; "per_participant" (Tables 4-6/10,
Statement 6) / "per_person" (Tables 7-9/11, Statement 13) for
average_time. vidhi.claims defaults TUS time questions to per_participant
and maps "per person" wording to per_person, so lookups stay deterministic.
Age rows use ids 6-14 / 15-29 / 15-59 / 60plus (explicit age wording
required to reach them); gender/sector rows sit on the 6plus sample.

vidhi_build merges rows across extractors with equal values REQUIRED on
key collisions; vidhi/audit.py traces every value into its source text.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

FACTSHEET = "mospi_TUS_2024_Factsheet.pdf"
REPORT = "mospi_TUS_2024_Report.pdf"

DIVISION_PREFIXES = (
    ("employment and related", "employment"),
    ("production of goods", "production_own_use"),
    ("unpaid domestic", "unpaid_domestic"),
    ("unpaid caregiving", "caregiving"),
    ("unpaid volunteer", "unpaid_volunteer"),
    ("learning", "learning"),
    ("socializing", "socializing_religious"),
    ("culture, leisure", "culture_leisure"),
    ("self-care", "selfcare"),
)

GROUP_ROWS = (  # Table 10/11 activity-group rows
    ("unpaid activities", "unpaid_activities"),
    ("paid activities", "paid_activities"),
    ("unpaid and paid activities", "unpaid_paid"),
    ("residual other activities", "residual_other"),
)

# battery triple index i (0-8, doc order) -> (indicator, measure, segment)
TRIPLE_SEMANTICS = [
    ("participation_rate", None, "gender"),
    ("participation_rate", None, "sector"),
    ("participation_rate", None, "age"),
    ("average_time", "per_participant", "gender"),
    ("average_time", "per_participant", "sector"),
    ("average_time", "per_participant", "age"),
    ("average_time", "per_person", "gender"),
    ("average_time", "per_person", "sector"),
    ("average_time", "per_person", "age"),
]

GENDER_SPLITS = (("male", "male"), ("female", "female"), ("person", "all"))
AGE_SPLITS = (("6-14 years", "6-14"), ("15-29 years", "15-29"),
              ("15-59 years", "15-59"))
SECTOR_SPLITS = (("rural", "rural"), ("urban", "urban"), ("all India", "all"))

# Statements from the full report used for cross-checks and extra coverage.
REPORT_STATEMENTS = {
    1: ("participation_rate", None, "sector_sex"),
    2: ("average_time", "per_participant", "sector_sex"),
    3: ("average_time", "per_person", "sector_sex"),
    5: ("participation_rate", None, "age_blocks"),
    6: ("average_time", "per_participant", "age_blocks"),
    13: ("average_time", "per_person", "age_blocks"),
}

REPORT_AGE_STATEMENTS = {  # stmt no -> (indicator, measure)
    5: ("participation_rate", None),
    6: ("average_time", "per_participant"),
    # Statement 13 is deliberately NOT used: it is a normal-day/other-day
    # statistic on a different basis from the factsheet's all-days
    # per-person tables; mixing bases would be unverifiable.
}

# Anchors: (act, triple_index, split_index) -> value; all are figures
# already verified in the store (prose-anchored rows, goldens V043-V057,
# or distinctive factsheet callouts confirmed by the report).
ANCHORS = [
    ("employment", 0, 0, 60.8), ("employment", 0, 1, 20.7),
    ("employment", 0, 2, 40.9),
    ("employment", 1, 0, 41.1), ("employment", 1, 1, 40.5),
    ("employment", 1, 2, 40.9),
    ("employment", 3, 0, 473), ("employment", 3, 1, 341),
    ("employment", 3, 2, 440),
    ("employment", 4, 0, 417), ("employment", 4, 1, 490),
    ("employment", 4, 2, 440),
    ("unpaid_domestic", 3, 0, 88), ("unpaid_domestic", 3, 1, 289),
    ("unpaid_domestic", 3, 2, 238),
    ("unpaid_domestic", 4, 0, 241), ("unpaid_domestic", 4, 1, 232),
    ("unpaid_domestic", 4, 2, 238),
    ("unpaid_domestic", 1, 0, 54.2), ("unpaid_domestic", 1, 1, 53.9),
    ("unpaid_domestic", 1, 2, 54.1),
    ("production_own_use", 1, 0, 21.6), ("production_own_use", 1, 1, 6.2),
    ("production_own_use", 1, 2, 16.8),
    ("caregiving", 3, 0, 75), ("caregiving", 3, 1, 137),
    ("caregiving", 4, 0, 115),
    ("culture_leisure", 3, 0, 177), ("culture_leisure", 3, 1, 164),
    ("culture_leisure", 3, 2, 171),
    ("caregiving", 4, 1, 117), ("caregiving", 4, 2, 116),
    ("selfcare", 3, 2, 708), ("selfcare", 4, 0, 711), ("selfcare", 4, 1, 701),
    ("learning", 2, 0, 89.3),   # age 6-14 participation (factsheet callout)
    ("learning", 5, 0, 413),    # age 6-14 per participant (factsheet callout)
    ("learning", 4, 0, 413),    # sector per participant, rural
]

# Table 10 (per participant) group anchors, factsheet prose verified:
# females spent 363 min on unpaid activities vs males 123 (persons 278);
# males 414 in paid activities vs females 302 (persons 386).
GROUP_ANCHORS = {
    "unpaid_activities": (123.0, 363.0, 278.0),
    "paid_activities": (414.0, 302.0, 386.0),
}


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _full_text(raw_dir: Path, pdf: str) -> str:
    try:
        import pymupdf as _f
    except ImportError:
        import fitz as _f  # type: ignore

    return "\n".join(pg.get_text() for pg in _f.open(raw_dir / pdf))


_NUMBER_LINE = re.compile(r"^[\d.,]+$")


def _after_numbers(lines: list[str], start: int, want: int) -> list[float]:
    """Collect `want` standalone-number lines after line index `start`;
    non-numeric lines before the first value are skipped (wrapped names,
    headers), after it they end the run."""
    vals: list[float] = []
    j = start
    scanned = 0
    while j < len(lines) and len(vals) < want and scanned < want * 3:
        l2 = lines[j].strip()
        if _NUMBER_LINE.match(l2):
            try:
                v = float(l2.replace(",", ""))
            except ValueError:
                break
            if 1900 <= v <= 2100:
                break
            vals.append(v)
        elif vals:
            break
        j += 1
        scanned += 1
    return vals


def _triples(text: str, prefixes, want: int, per_scan: int = 12) -> dict:
    """{row_id: [vals of `want` consecutive standalone numbers]} for each
    prefix-matching name line in doc order."""
    lines = [l.strip() for l in text.splitlines()]
    out: dict[str, list] = {}
    for i, line in enumerate(lines):
        low = line.lower()
        hit = next((pid for pre, pid in prefixes if low.startswith(pre)), None)
        if hit is None:
            continue
        vals = _after_numbers(lines, i + 1, want)
        if len(vals) == want:
            out.setdefault(hit, []).append(vals)
    return out


def _validate_battery(divs: dict[str, list], groups: dict[str, list]) -> None:
    # Exactly 9 triples per division: any extra occurrence (e.g. a callout
    # line forming a bogus triple) means the scan drifted -- abort.
    for pid, tr in divs.items():
        if len(tr) != 9:
            raise ValueError(
                f"TUS battery for {pid}: {len(tr)} triples (must be exactly 9)"
            )
    # Group rows (Tables 10/11): at least two occurrences in doc order --
    # some group names also label Figure 1 (participation in the unpaid /
    # paid groups) and only 'Unpaid/Paid Activities' carry that third
    # triple. The LAST two triples are Tables 10 and 11; GROUP_ANCHORS pin
    # Table 10 so a mis-slice aborts.
    for pid, tr in groups.items():
        if len(tr) < 2 or any(len(v) != 3 for v in tr):
            raise ValueError(f"TUS group battery for {pid}: {len(tr)} triples")


def _battery(text: str) -> tuple[dict, dict]:
    divs = _triples(text, DIVISION_PREFIXES, 3)
    groups = _triples(text, GROUP_ROWS, 3)
    _validate_battery(divs, groups)
    return divs, groups


def _find_statement(full: str, no: int) -> str:
    """Segment of `full` from 'Statement <no>:' to the next Statement
    header; the first occurrence is the table, later mentions are prose
    references to the same statement number."""
    pat = re.compile(rf"Statement {no} ?:")
    m = pat.search(full)
    if not m:
        raise ValueError(f"report Statement {no} not found")
    start = m.end()
    nxt = re.search(r"Statement \d+ ?:", full[start:])
    seg = full[start : start + (nxt.start() if nxt else 6000)]
    return seg


def _report_sector_rows(full: str, no: int) -> dict:
    """Statement 1/2/3: per division nine sector-major values
    (rural m/f/p, urban m/f/p, r+u m/f/p)."""
    seg = _find_statement(full, no)
    rows = _triples(seg, DIVISION_PREFIXES, 9)
    missing = [pid for _, pid in DIVISION_PREFIXES if pid not in rows]
    extra = [k for k in rows if len(rows[k]) != 1]
    if missing or extra:
        raise ValueError(f"Statement {no}: missing={missing} extra={extra}")
    return {k: v[0] for k, v in rows.items()}


def _report_age_rows(full: str, no: int) -> dict:
    """Statement 5/6/13: male/female/person blocks, each division carrying
    three age columns (15-29, 15-59, 60-plus). Pages also contain chart
    listings of the same division names (no numbers), and prose block
    markers, so candidate triplets (male, female, person) are tried in
    order and the FIRST complete one (all nine divisions with three
    values) is used."""
    seg = _find_statement(full, no)
    lines = [l.strip() for l in seg.splitlines()]
    marks = [i for i, l in enumerate(lines)
             if l.lower() in ("male", "female", "person")]
    kinds = [lines[i].lower() for i in marks]
    triplets = [
        (marks[i], marks[i + 1], marks[i + 2])
        for i in range(len(marks) - 2)
        if kinds[i : i + 3] == ["male", "female", "person"]
    ]
    if not triplets:
        # Statement 13-style layout: no sex blocks; each division carries
        # six values (normal day: 15-29/15-59/60+, then other day). The
        # normal-day first three are the all-persons age cells.
        rws = _triples(seg, DIVISION_PREFIXES, 6)
        rws = {k: v[0] for k, v in rws.items() if len(v) == 1 and len(v[0]) == 6}
        if sorted(rws) != sorted(pid for _, pid in DIVISION_PREFIXES):
            raise ValueError(
                f"Statement {no}: neither sex blocks nor normal-day layout "
                f"parsed"
            )
        return {"all": {k: v[:3] for k, v in rws.items()}}
    for ma, fe, pe in triplets:
        out = {}
        for sex, (a, b) in (
            ("male", (ma, fe)),
            ("female", (fe, pe)),
            ("all", (pe, len(lines))),
        ):
            blk = "\n".join(lines[a:b])
            rws = _triples(blk, DIVISION_PREFIXES, 3)
            rws = {k: v[0] for k, v in rws.items() if len(v) == 1}
            if sorted(rws) != sorted(pid for _, pid in DIVISION_PREFIXES):
                out = None
                break
            out[sex] = rws
        if out:
            return out
    raise ValueError(
        f"Statement {no}: no complete male/female/person triplet "
        f"(markers at {marks})"
    )


def _crosscheck(divs: dict, raw_dir: Path) -> dict:
    """Verify the factsheet battery against the report statements; returns
    the report-derived age rows as {(stmt no): {sex: {division: [3]}}}."""
    full = _full_text(raw_dir, REPORT)
    st: dict[int, dict] = {}

    def sector_map(no):
        st[no] = _report_sector_rows(full, no)

    def age_map(no):
        st[no] = _report_age_rows(full, no)

    sector_map(1), sector_map(2), sector_map(3)
    age_map(5), age_map(6)  # St13 is a normal/other-day statistic, not
    # the same battery; the factsheet's per-person age tables are the
    # only source for the all-days basis and carry no report twin.

    for act, trs in divs.items():
        for base, st_no, ind_msg in ((0, 1, "participation"),
                                     (3, 2, "per-participant"),
                                     (6, 3, "per-person")):
            row = st[st_no][act]
            gender_tr, sector_tr = trs[base], trs[base + 1]
            if [row[6], row[7], row[8]] != gender_tr:
                raise ValueError(
                    f"{act} {ind_msg}: gender {gender_tr} != "
                    f"Statement {st_no} r+u cols {row[6:9]}"
                )
            if [row[2], row[5], row[8]] != sector_tr:
                raise ValueError(
                    f"{act} {ind_msg}: sector {sector_tr} != "
                    f"Statement {st_no} person cols {row[2], row[5], row[8]}"
                )
        for base, st_no in ((2, 5), (5, 6)):
            row = st[st_no]["all"][act]
            age_tr = trs[base]
            if age_tr[1:3] != row[0:2]:
                raise ValueError(
                    f"{act} triple#{base}: age {age_tr} vs Statement "
                    f"{st_no} person {row}"
                )
    # Statement 18: learning 6-14/15-29 cells for participation +
    # per participant. Its rows are (participation 6-14, participation
    # 15-29, time 6-14, time 15-29) x sector x sex; check that the
    # factsheet's person cells appear as one such row.
    seg18 = _find_statement(full, 18)
    lines18 = [l.strip() for l in seg18.splitlines()]
    runs = []
    for i in range(len(lines18) - 3):
        quad = lines18[i : i + 4]
        if all(_NUMBER_LINE.match(x) for x in quad):
            runs.append([float(x) for x in quad])
    expected = [
        divs["learning"][2][0], divs["learning"][2][1],
        divs["learning"][5][0], divs["learning"][5][1],
    ]
    if not any(
        len(r) == 4 and all(abs(x - y) < 1e-9 for x, y in zip(r, expected))
        for r in runs
    ):
        raise ValueError(
            f"learning 6-14/15-29 mismatch: factsheet age triples "
            f"{divs['learning'][2]}, {divs['learning'][5]} vs Statement 18 "
            f"runs {runs[:3]}..."
        )
    return st


def _page_windows(raw_dir: Path, pdf: str) -> list[str]:
    """Single pages plus 2-page concatenations."""
    try:
        import pymupdf as _f
    except ImportError:
        import fitz as _f  # type: ignore

    d = _f.open(raw_dir / pdf)
    texts = [pg.get_text() for pg in d]
    d.close()
    wins = list(texts)
    wins.extend(texts[i] + "\n" + texts[i + 1] for i in range(len(texts) - 1))
    return wins


def _raw_triples(text: str) -> set:
    """Every ordered triple of consecutive standalone-number lines: the
    containment universe for the Table 10/11 group cross-check (the report
    reprints those two small tables without a Statements-style layout)."""
    lines = [l.strip() for l in text.splitlines()]
    out: set = set()
    for i in range(len(lines) - 2):
        t = []
        ok = True
        for j in range(3):
            l2 = lines[i + j]
            if not _NUMBER_LINE.match(l2):
                ok = False
                break
            try:
                t.append(round(float(l2.replace(",", "")), 6))
            except ValueError:
                ok = False
                break
        if ok:
            out.add(tuple(t))
    return out


def _dual_check_groups(groups: dict, raw_dir: Path, pdf: str) -> None:
    universe: set = set()
    for w in _page_windows(raw_dir, pdf):
        universe |= _raw_triples(w)
    for pid, trs in groups.items():
        for t in trs[-2:]:
            if tuple(round(v, 6) for v in t) not in universe:
                raise ValueError(
                    f"TUS group dual-source disagreement {pid}: {t} not in {pdf}"
                )


def _battery_rows(divs: dict, sha: str) -> list[dict]:
    rows: list[dict] = []
    for act_id, tr in divs.items():
        for i, vals in enumerate(tr):
            ind, measure, seg = TRIPLE_SEMANTICS[i]
            splits = {"gender": GENDER_SPLITS, "age": AGE_SPLITS,
                      "sector": SECTOR_SPLITS}[seg]
            for (txt, dim), v in zip(splits, vals):
                age_group, sex, residence = "6plus", "all", "all"
                if seg == "gender":
                    sex = dim
                elif seg == "age":
                    age_group = dim
                else:
                    residence = dim
                if seg == "gender":
                    rid = f"TUS_2024_{ind}_{act_id}_{age_group}_{sex}"
                elif seg == "age":
                    rid = f"TUS_2024_{ind}_{act_id}_age{age_group}_all"
                else:
                    rid = f"TUS_2024_{ind}_{act_id}_{age_group}_{residence}_all"
                if ind == "average_time":
                    # per-participant vs per-person rows differ only in
                    # measure: the basis token keeps row_ids unique.
                    rid += "_pp" if measure == "per_participant" else "_pperson"
                rows.append({
                    "row_id": rid,
                    "survey": "TUS_2024",
                    "round": "2024",
                    "indicator": ind,
                    "measure": measure,
                    "geography": "India",
                    "state": None,
                    "residence": residence,
                    "sex": sex,
                    "age_group": age_group,
                    "activity": act_id,
                    "reference_period": "Jan 2024-Dec 2024",
                    "value": v,
                    "unit": "percent" if ind == "participation_rate"
                    else "minutes",
                    "source_document": FACTSHEET,
                    "table_or_section": (
                        f"Factsheet battery triple #{i + 1} split={seg}"
                    ),
                    "verification_status": "candidate",
                    "provenance": {
                        "extractor": "vidhi.sources.tus_tables",
                        "pdf_sha256": sha,
                        "battery_index": i + 1,
                    },
                })
    return rows


def _group_rows(groups: dict, sha: str) -> list[dict]:
    rows: list[dict] = []
    for act_id, tr in groups.items():
        for i, vals in enumerate(tr[-2:]):  # T10, T11 (skip Figure-1 triple)
            measure = "per_participant" if i == 0 else "per_person"
            for (_, dim), v in zip(GENDER_SPLITS, vals):
                rows.append({
                    "row_id": (
                        f"TUS_2024_average_time_{act_id}_6plus_{dim}"
                        f"_{'pp' if measure == 'per_participant' else 'pperson'}"
                    ),
                    "survey": "TUS_2024",
                    "round": "2024",
                    "indicator": "average_time",
                    "measure": measure,
                    "geography": "India",
                    "state": None,
                    "residence": "all",
                    "sex": dim,
                    "age_group": "6plus",
                    "activity": act_id,
                    "reference_period": "Jan 2024-Dec 2024",
                    "value": v,
                    "unit": "minutes",
                    "source_document": FACTSHEET,
                    "table_or_section": (
                        f"Factsheet Table {10 + i} (unpaid/paid groups)"
                    ),
                    "verification_status": "candidate",
                    "provenance": {
                        "extractor": "vidhi.sources.tus_tables",
                        "pdf_sha256": sha,
                        "table_index": 10 + i,
                    },
                })
    return rows


REPORT_AGE_COLS = ("15-29", "15-59", "60plus")


def _report_statement_rows(st: dict, rsha: str) -> list[dict]:
    """Age x statement rows: Statement 5/6/13 give (15-29, 15-59, 60plus)
    for male/female/person blocks -- coverage the factsheet never prints.
    The 15-29/15-59 person cells duplicate the factsheet battery; the key
    collisions are resolved by vidhi_build with equal values REQUIRED."""
    rows: list[dict] = []
    for no, (ind, measure) in REPORT_AGE_STATEMENTS.items():
        for sex_token, act_map in st[no].items():
            sex = {"male": "male", "female": "female"}.get(sex_token, "all")
            for act_id, vals in act_map.items():
                for age, v in zip(REPORT_AGE_COLS, vals):
                    if v is None:
                        continue
                    rows.append({
                        "row_id": (
                            f"TUS_2024_{ind}_{act_id}_age{age}_{sex}"
                            + ("" if ind == "participation_rate"
                               else "_pp" if measure == "per_participant"
                               else "_pperson")
                        ),
                        "survey": "TUS_2024",
                        "round": "2024",
                        "indicator": ind,
                        "measure": measure,
                        "geography": "India",
                        "state": None,
                        "residence": "all",
                        "sex": sex,
                        "age_group": age,
                        "activity": act_id,
                        "reference_period": "Jan 2024-Dec 2024",
                        "value": v,
                        "unit": "percent" if ind == "participation_rate"
                        else "minutes",
                        "source_document": REPORT,
                        "table_or_section": (
                            f"Report Statement {no} ({sex} block)"
                        ),
                        "verification_status": "candidate",
                        "provenance": {
                            "extractor": "vidhi.sources.tus_tables",
                            "pdf_sha256": rsha,
                            "statement": no,
                        },
                    })
    return rows


def records(raw_dir: Path) -> tuple[list[dict], dict]:
    fsha = _sha(raw_dir / FACTSHEET)
    rsha = _sha(raw_dir / REPORT)
    divs, groups = _battery(_full_text(raw_dir, FACTSHEET))
    # Structure cross-check against the report's Statements + age coverage.
    st = _crosscheck(divs, raw_dir)
    # Group tables (10/11): report reprint containment + anchors.
    _dual_check_groups(groups, raw_dir, REPORT)
    rows = (
        _battery_rows(divs, fsha)
        + _group_rows(groups, fsha)
        + _report_statement_rows(st, rsha)
    )

    # Anchors: verified store figures must be reproduced by the battery.
    for act, ti, split, want in ANCHORS:
        got = divs.get(act, [[]] * 9)[ti][split]
        if abs(got - want) > 1e-9:
            raise ValueError(
                f"TUS anchor mismatch {act} battery#{ti + 1} split{split}: "
                f"{got} vs verified {want}"
            )
    for act, want in GROUP_ANCHORS.items():
        got = groups.get(act)
        if got is None:
            raise ValueError(f"TUS group anchor missing {act}")
        t10 = got[-2]  # first of the two kept triples = Table 10
        if any(abs(a - b) > 1e-9 for a, b in zip(t10, want)):
            raise ValueError(f"TUS group anchor mismatch {act}: {t10} vs {want}")
    return rows, {
        "source": FACTSHEET,
        "pdf_sha256": fsha,
        "rows": len(rows),
        "cross_check": (
            "report Statements 1/2/3 (sector-sex), 5/6 (age 15-29/15-59), "
            "18 (learning 6-14); group tables via report containment"
        ),
    }
