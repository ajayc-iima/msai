"""vidhi2 source: live MoSPI eSankhyiki API (flexible primary source).

No hardcoded values anywhere: indicator/state/gender/sector/age codes are
discovered from the API's own filter endpoints at fetch time. Callers pass
a Claim; the adapter translates dimensions to API params and returns
normalized store rows with API provenance.

Runs at RELEASE time (online). The query path stays offline against the
frozen store. Dual-source rule: API values must equal the PDF parsers'
values for overlapping rows (checked by vidhi2 audit) -- agreement of two
independent MoSPI channels is the provenance.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

# Lab7 TLS: the pinned esankhyiki client exposes only ``base_url``; it has no
# verify= knob, so certificate verification is delegated to the runtime CA
# store. Never monkey-patch verify=False here. For MoSPI-internal use, pin the
# Ministry CA or route through the Ministry gateway.
BASE_URL = os.getenv("VIDHI_ESANKHYIKI_URL", os.getenv("VIDHI2_ESANKHYIKI_URL", "https://api.mospi.gov.in"))

INDICATORS = {"LFPR": 1, "WPR": 2, "UR": 3}  # PLFS codes (from get_plfs_indicators)
YEAR_TYPE = {"2023-24": 1, "2022-23": 1, "2025": 2, "2024": 2}  # 1=agri, 2=calendar
GENDER = {"male": 1, "female": 2, "all": 3}
SECTOR = {"rural": 1, "urban": 2, "all": 3}
AGE = {"15plus": 1, "all": 4}


def _client():
    from esankhyiki import MoSPI

    return MoSPI(base_url=BASE_URL)


def _state_code(client, name: str) -> int:
    states = client.get_plfs_filters(1)["data"]["state"]
    want = (name or "All India").lower()
    for s in states:
        if s["description"].lower() == want:
            return s["state_code"]
    raise ValueError(f"state {name!r} not in eSankhyiki PLFS states")


def fetch_claim(claim, measures=("usual_status_ps_ss",)) -> list[dict]:
    """Fetch every API row matching the claim's dimensions (baseline cuts:
    religion/social/education = all). Returns normalized candidate rows."""
    if claim.indicator not in INDICATORS:
        raise ValueError(f"indicator {claim.indicator!r} not PLFS-mapped")
    if (claim.survey or "") not in ("PLFS_2023_24", "PLFS_2025"):
        raise ValueError(f"survey {claim.survey!r} not PLFS-mapped")
    c = _client()
    year = claim.round or "2023-24"
    all_india_code = _state_code(c, "All India")
    state_code = (
        all_india_code
        if (claim.geography or "India") == "India"
        else _state_code(c, claim.state or "All India")
    )
    is_india = state_code == all_india_code
    params = {
        "indicator_code": INDICATORS[claim.indicator],
        "frequency_code": 1,
        "year_type_code": YEAR_TYPE.get(year, 2),
        "year": year,
        "state_code": state_code,
        "gender_code": GENDER.get(claim.sex or "all", 3),
        "age_code": AGE.get(claim.age_group or "15plus", 1),
        "sector_code": SECTOR.get(claim.residence or "all", 3),
    }
    resp = c.get_data("PLFS", params)
    now = datetime.now(timezone.utc).isoformat()
    rows = []
    for d in resp.get("data", []):
        if (
            d.get("religion") != "all"
            or d.get("socialGroup") != "all"
            or d.get("General_Education") != "all"
        ):
            continue
        meas = {"PS+SS": "usual_status_ps_ss", "CWS": "CWS"}.get(
            d.get("weekly_status"), d.get("weekly_status")
        )
        if meas not in measures:
            continue
        rows.append(
            {
                "indicator": claim.indicator,
                "measure": meas,
                "survey": claim.survey,
                "round": year,
                "geography": "India" if is_india else "state",
                "state": None if is_india else d.get("state"),
                "residence": {
                    "rural + urban": "all",
                    "rural": "rural",
                    "urban": "urban",
                }.get((d.get("sector") or "").strip().lower(), "all"),
                "sex": {"male": "male", "female": "female"}.get(d.get("gender"), "all"),
                "age_group": "15plus"
                if "15 years and above" in str(d.get("AgeGroup"))
                else "all",
                "reference_period": (
                    "Jan 2025-Dec 2025"
                    if year == "2025"
                    else (
                        "Jan 2024-Dec 2024"
                        if year in ("2024", "2024-25")
                        else "Jul 2023-Jun 2024"
                    )
                ),
                "value": float(str(d["value"]).replace(",", "")),
                "unit": "percent",
                "source_document": "eSankhyiki PLFS API",
                "table_or_section": f"indicator {d.get('indicator')}",
                "verification_status": "candidate",
                "provenance": {
                    "extractor": "vidhi.sources.esankhyiki",
                    "api": BASE_URL,
                    "params": params,
                    "fetched_at": now,
                },
            }
        )
    for r in rows:
        r["row_id"] = (
            f"ESANKHYIKI_{r['survey']}_{r['indicator']}_{r['round']}_"
            f"{r['residence']}_{r['sex']}_{r['measure']}"
        )
    return rows
