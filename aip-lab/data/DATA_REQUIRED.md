# Data requirements — Vidhi Guardian (MoSPI official sources), v2 re-freeze Oct 2026

In-corpus (latest): PLFS 2023-24, HCES 2023-24, TUS 2024, NSS78 MIS 2020-21.
Superseded v1 rounds (2022-23/2019) are reference-only for round-mismatch guards.

No official MoSPI numbers are committed yet. Do NOT invent values.
Every `PASS` numeric answer requires a row in
`data/truth/ground_truth_tables.json` with `verification_status: verified`
plus `source_document + table_or_section + page`.

## 1. PDFs needed in `data/raw/` (official MoSPI domains only)

| # | File to place | Official report | Tables/pages needed |
|---|---------------|-----------------|---------------------|
| 1 | `PLFS_2022_23_Annual_Report.pdf` | PLFS Annual Report July 2022 – June 2023 | LFPR / WPR / UR, usual status (ps+ss) + CWS definitions, 15+ by sex × residence |
| 2 | `HCES_2022_23_Report.pdf` + `HCES_2022_23_Factsheet.pdf` | HCES 2022-23 (Aug 2022 – Jul 2023) | MPCE rural/urban, by state, with/without imputation; 2011-12 vs 2022-23 comparability note (transcribe verbatim) |
| 3 | `TUS_2019_Report.pdf` | Time Use Survey Jan–Dec 2019 | Participation rate + avg time by activity × sex, definitions |
| 4 | `NSS78_MIS_2020_21_Report.pdf` | NSS 78th Round MIS (2020-21) | Drinking-water indicator definition + rural/urban/all-India values |

## 1b. Version policy (2026-10-05)

- Frozen eval corpus stays PLFS 2022-23 / HCES 2022-23 / TUS 2019 / NSS78 MIS.
  Confirmed you flagged a newer file `PLFS_2025_F_REV_29052026.pdf` (URL resolves
  as `application/pdf`). It is registered as reference-only for round-mismatch
  detection, NOT as a PASS source. Switching in-corpus round would require
  re-verifying every ground-truth row + golden query — explicit scope change.
- DGE links (`dge.gov.in/...employment-survey`, `eus-archive`, `payroll`,
  `lok-sabha`, handbooks) are Directorate General of Employment publications,
  outside the 4-survey scope. Firewall treats them as `out_of_scope` → REFUSE.
  Do NOT place them in `data/raw/` unless scope is formally expanded.

## 2. Portal offline downloads (optional, reproducible alternative to live MCP)

From eSankhyiki Macro Indicators / Data Catalogue module:
- `esankhyiki_PLFS_2022_23_<filters>.csv`
- `esankhyiki_HCES_2022_23_<filters>.csv`
- `esankhyiki_TUS_2019_<filters>.csv`
- `esankhyiki_NSS78_MIS_<filters>.csv`
- Catalogue Excel statements matching the same report tables.

Record for each file: portal URL, download date, on-screen filter selection, sha256. Commit files; gate runs `AIP_OFFLINE=1`.

## 3. Shipped state (what runs out of the box)

- `vidhi/store.json` ships with **173 verified rows** (HCES 2023-24 Statement 7 state × rural/urban MPCE, all-India MPCE pairs, PLFS LFPR/WPR/UR, TUS minutes), each with provenance + per-row audit note. The firewall `PASS`es only from these verified rows.
- `data/truth/ground_truth_tables.json` is the legacy Lab-1 scratch table; the served pipeline reads `vidhi/store.json`. Until fresh official PDFs land in `data/raw/`, any question outside the 173 curated rows honestly returns `WARN_NO_DATA` — never invents.
- `data/excerpts/` contains only `SAFETY_B_ADVERSARIAL` synthetic test chunk (clearly marked, never cited as fact).
- Official excerpts + `citation_index.json` stay empty.
