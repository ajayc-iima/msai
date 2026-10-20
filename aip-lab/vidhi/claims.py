# ruff: noqa: BLE001, S110 - intentional guarded fallbacks (offline/API-degraded paths)
"""vidhi2 claims: the translator. Maps natural language to a typed claim.

The claim is the ONLY thing rules adjudicate. Extraction assigns structure
and a structural confidence; it never judges validity.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Literal

from pydantic import BaseModel, Field

ClaimType = Literal[
    "descriptive",
    "comparative",
    "causal",
    "forecast",
    "microdata",
    "out_of_scope",
    "definitional",
]

# Fields that define claim identity for cache keys and frozen hashes.
CANON_FIELDS = (
    "survey",
    "round",
    "indicator",
    "measure",
    "geography",
    "state",
    "residence",
    "sex",
    "age_group",
    "activity",
    "claim_type",
)

# Fields where a cache hit with different values would be a wrong answer.
CRITICAL_FIELDS = (
    "survey",
    "indicator",
    "measure",
    "residence",
    "geography",
    "state",
    "sex",
    "age_group",
    "activity",
    "round",
    "claim_type",
)


class Claim(BaseModel):
    survey: str | None = None
    round: str | None = None
    indicator: str | None = None
    measure: str | None = None
    geography: str | None = None
    state: str | None = None
    residence: str | None = None
    sex: str | None = None
    age_group: str | None = None
    activity: str | None = None
    claim_type: ClaimType = "descriptive"
    comparison_surveys: list[str] = Field(default_factory=list)
    mixes_measures: list[str] = Field(default_factory=list)
    user_asserted_value: float | None = None
    user_asserted_unit: str | None = None
    asserted_pairs: list[dict] = Field(default_factory=list)
    wants_forecast: bool = False
    wants_causal: bool = False
    wants_political_judgment: bool = False
    wants_microdata: bool = False
    asserts_poverty_or_real_change: bool = False
    extraction_confidence: float = 0.0
    extraction_notes: str = ""
    raw_question: str = ""

    def canonical(self) -> dict:
        out: dict = {}
        for f in CANON_FIELDS:
            v = getattr(self, f, None)
            if v is None:
                continue
            out[f] = v.strip().lower() if isinstance(v, str) else v
        return out

    def key(self) -> str:
        return hashlib.sha256(
            json.dumps(self.canonical(), sort_keys=True).encode()
        ).hexdigest()

    def canonical_text(self) -> str:
        return json.dumps(self.canonical(), sort_keys=True)

    def canonical_key(self) -> str:
        return json.dumps(self.canonical(), sort_keys=True)


def compatible(a: dict, b: dict) -> bool:
    """Field-guard: a cached verdict may be reused only when every critical
    field agrees exactly — and a null on one side is a *meaningful* value, not
    a wildcard. This -- not any cosine threshold -- is what makes the cache
    safe (see DESIGN guarantee 3).

    The v1 defect skipped a field whenever either side was null, so an
    all-India (residence=null) cached verdict was "compatible" with an
    "urban" claim. Exact equality closes that one-sided reuse."""
    for f in CRITICAL_FIELDS:
        if a.get(f) != b.get(f):
            return False
    return True


def confidence(c: Claim) -> tuple[float, str]:
    notes: list[str] = []
    score = 0.0
    if c.survey:
        score += 0.25
    else:
        notes.append("missing survey")
    if c.indicator:
        score += 0.25
    else:
        notes.append("missing indicator")
    if (
        c.claim_type in ("forecast", "causal", "microdata", "out_of_scope")
        or c.geography
        or c.round
        or c.measure
    ):
        score += 0.2
    else:
        notes.append("no disaggregation context")
    if c.raw_question and len(c.raw_question) >= 10:
        score += 0.1
    score += 0.1  # asserted-value presence is neutral either way
    if c.comparison_surveys:
        score += 0.1
    return round(min(score, 1.0), 2), "; ".join(notes) or "complete"


_SURVEYS = (
    # Specific aliases must precede the generic "plfs" alias: the first match
    # wins, and a fixed round must not be re-derived from a bare survey token.
    ("plfs 2025", "PLFS_2025", "2025"),
    ("plfs 2023-24", "PLFS_2023_24", "2023-24"),
    ("plfs 2023", "PLFS_2023_24", "2023-24"),
    ("plfs", "PLFS_2025", "2025"),
    ("hces", "HCES_2023_24", "2023-24"),
    ("mpce", "HCES_2023_24", "2023-24"),
    ("consumption", "HCES_2023_24", "2023-24"),
    ("time use", "TUS_2024", "2024"),
    ("tus", "TUS_2024", "2024"),
    ("mis", "NSS78_MIS_2020_21", "2020-21"),
    ("multiple indicator", "NSS78_MIS_2020_21", "2020-21"),
    ("drinking water", "NSS78_MIS_2020_21", "2020-21"),
)

_INDICATORS = (
    ("labour force participation", "LFPR"),
    ("lfpr", "LFPR"),
    ("worker population", "WPR"),
    ("wpr", "WPR"),
    ("unemployment", "UR"),
    ("jobless", "UR"),
    ("ur", "UR"),
    ("consumption expenditure", "MPCE"),
    ("mpce", "MPCE"),
    ("per capita", "MPCE"),
    ("participation rate", "participation_rate"),
    ("average time", "average_time"),
    ("time spent", "average_time"),
    ("minutes", "average_time"),
    ("drinking water", "drinking_water"),
)

_ACTIVITIES = (
    ("unpaid domestic", "unpaid_domestic"),
    ("domestic services", "unpaid_domestic"),
    ("caregiving", "caregiving"),
    ("caring for", "caregiving"),
    ("caring their", "caregiving"),
    ("culture", "culture_leisure"),
    ("leisure", "culture_leisure"),
    ("mass media", "culture_leisure"),
    ("learning", "learning"),
    ("self-care", "selfcare"),
    ("self care", "selfcare"),
    ("selfcare", "selfcare"),
    ("employment and related", "employment"),
    ("employment", "employment"),
)

_STATES = (
    "andhra pradesh",
    "arunachal pradesh",
    "assam",
    "bihar",
    "chhattisgarh",
    "delhi",
    "goa",
    "gujarat",
    "haryana",
    "himachal pradesh",
    "jharkhand",
    "karnataka",
    "kerala",
    "madhya pradesh",
    "maharashtra",
    "manipur",
    "meghalaya",
    "mizoram",
    "nagaland",
    "odisha",
    "punjab",
    "rajasthan",
    "sikkim",
    "tamil nadu",
    "telangana",
    "tripura",
    "uttar pradesh",
    "uttarakhand",
    "west bengal",
    "chandigarh",
    "puducherry",
    "lakshadweep",
    "ladakh",
    "jammu & kashmir",
    "jammu and kashmir",
    "andaman & nicobar islands",
    "andaman and nicobar islands",
    "dadra & nagar haveli and daman & diu",
    "dadra and nagar haveli and daman and diu",
    "india",
)

# Input-variant -> canonical store state name (only needed where the
# title-joined form would differ from the store's spelling).
_STATE_CANON = {
    "jammu and kashmir": "Jammu & Kashmir",
    "andaman and nicobar islands": "Andaman & Nicobar Islands",
    "dadra and nagar haveli and daman and diu": (
        "Dadra & Nagar Haveli and Daman & Diu"
    ),
}


def _w(q: str, alias: str) -> bool:
    """Whole-word match on a punctuation-insensitive form: 'employment' must
    not fire inside 'unemployment', trailing punctuation ('LFPR?') must not
    block a match, and hyphenated aliases ('plfs 2023-24', 'self-care') must
    match too. Both sides are normalized the same way."""
    qn = re.sub(r"[^a-z0-9 ]", " ", q)
    an = re.sub(r"[^a-z0-9 ]", " ", alias)
    return f" {an} " in f" {qn} "


# An explicit survey-year token, e.g. 2025, 2023-24, 2011-12, 2011-2012.
_YEAR_TOKEN = re.compile(r"\b((?:19|20)\d{2})(?:-([0-9]{2,4}))?\b")


def extract(question: str) -> Claim:
    """Deterministic heuristic translator. Never judges; only structures."""
    q = question.lower()
    c = Claim(raw_question=question)

    for alias, sid, rnd in _SURVEYS:
        if _w(q, alias) and c.survey is None:
            c.survey, c.round = sid, rnd
    for alias, ind in _INDICATORS:
        if _w(q, alias):
            c.indicator = ind
            break
    for alias, act in _ACTIVITIES:
        if _w(q, alias):
            c.activity = act
            break
    if c.survey == "TUS_2024" and c.activity and c.indicator is None:
        c.indicator = "average_time"  # time-use activity questions ask minutes
    if (
        c.indicator is None
        and "spend" in q
        and any(w in q for w in ("household", "monthly", "family"))
    ):
        c.indicator = "MPCE"
        if c.survey is None:
            c.survey, c.round = "HCES_2023_24", "2023-24"
    # Bare-year inference for labour indicators.
    if c.survey is None and c.indicator in ("LFPR", "WPR", "UR"):
        if "2025" in q:
            c.survey, c.round = "PLFS_2025", "2025"
        elif "2023" in q:
            c.survey, c.round = "PLFS_2023_24", "2023-24"

    if "usual" in q:
        c.measure = "usual_status_ps_ss"
    elif "cws" in q or "current weekly" in q:
        c.measure = "CWS"
    if "usual" in q and "cws" in q:
        c.measure, c.mixes_measures = "mixed", ["usual_status_ps_ss", "CWS"]
    if "without imputation" in q or "without considering imputed" in q:
        c.measure = "without_imputation"
    elif "with imputation" in q or "imputed" in q:
        c.measure = "with_imputation"

    for tok in ("rural", "urban"):
        if tok in q:
            c.residence = (
                tok if c.residence is None else ("mixed" if c.residence != tok else tok)
            )
    if re.search(r"\bfemales?\b|\bwom[ae]n\b", q):
        c.sex = "female"
    elif re.search(r"\bmales?\b|\bmen\b", q):
        c.sex = "male"

    for geo in _STATES:
        if geo in q:
            if geo == "india":
                c.geography, c.state = "India", None
            else:
                name = _STATE_CANON.get(
                    geo, " ".join(w.title() for w in geo.split())
                )
                c.geography, c.state = "state", name
            break
    if c.geography is None:
        c.geography = "India"
    if re.search(r"15\s*(?:years?|\+|yrs)", q) or "15+" in q:
        c.age_group = "15plus"

    # Round tokens override alias defaults. An explicit round that matches no
    # curated row yields an honest WARN_NO_DATA downstream -- the one thing
    # that must never happen is silently serving a different round's figure
    # for a question pinned to an explicit year.
    if c.survey and c.survey.startswith("PLFS"):
        if "2025" in q:
            c.survey, c.round = "PLFS_2025", "2025"
        elif "2023" in q:
            c.survey, c.round = "PLFS_2023_24", "2023-24"
        else:
            m = _YEAR_TOKEN.search(q)
            if m:
                # Non-curated round (2017-18, 2022, 2022-23, 2024,
                # 2024-25, ...): keep the survey identity so metadata
                # validation still applies, but pin the requested round, which
                # matches no curated row -> WARN_NO_DATA (never 2025 data).
                yr, end = m.group(1), m.group(2)
                c.round = f"{yr}-{end}" if end else yr
    if c.survey and c.survey.startswith("HCES"):
        if "2023" in q:
            c.round = "2023-24"
        else:
            m = _YEAR_TOKEN.search(q)
            if m:
                # Explicit pre-break or non-curated round (2011-12, 2022-23,
                # 2024, 2025, ...): pin the requested round. A descriptive
                # question then falls through to WARN_NO_DATA; the 2023-24
                # figure is never silently served for another round, and a
                # cross-round comparison still trips the comparability stage.
                yr, end = m.group(1), m.group(2)
                c.round = f"{yr}-{end}" if end else yr
            else:
                c.round = "2023-24"
    if c.survey == "TUS_2024":
        m = _YEAR_TOKEN.search(q)
        if m:
            yr, end = m.group(1), m.group(2)
            req = f"{yr}-{end}" if end else yr
            if req != "2024":
                c.round = req  # explicit non-curated round -> WARN_NO_DATA

    # User-asserted figures ("Is X 5,000?") for numeric verification.
    for m in re.finditer(
        r"(rs\.?|inr|₹)?\s*([\d,]+(?:\.\d+)?)\s*(%|percent|rs\.?|inr|₹)?", q
    ):
        try:
            v = float(m.group(2).replace(",", ""))
        except ValueError:
            continue
        if 1900 <= v <= 2100 and not (m.group(3) or "").strip(" ."):
            continue  # calendar year
        unit = m.group(3) or ""
        if any(w in q for w in ("is ", "was ", "of ", "=", ":", "correct")):
            if "%" in unit or "percent" in unit:
                c.user_asserted_value, c.user_asserted_unit = v, "percent"
                break
            if m.group(1) or "rs" in unit or "₹" in unit or v > 1000:
                c.user_asserted_value, c.user_asserted_unit = v, "Rs/month"
                break
            # Not a figure (e.g. the "24" in "2023-24", or "15" in "15+"):
            # keep scanning so a real asserted value later in the sentence wins.

    if any(w in q for w in (" vs ", "versus", "compar", "trend", "between")):
        c.claim_type = "comparative"
        ss = set()
        if "2011" in q:
            ss.add("HCES_2011_12")
        if "eus" in q or "employment-unemployment" in q:
            ss.add("NSS_EUS_2011_12")
        if "2025" in q:
            ss.add("PLFS_2025")
        if "2023" in q:
            ss.add("PLFS_2023_24" if "plfs" in q else "HCES_2023_24")
        if "2022" in q:
            # Pre-2025 PLFS annuals and HCES 2022-23 have their own ids so the
            # revamp/method-break caveats in rules.py can fire on them.
            ss.add("PLFS_2022_23" if "plfs" in q else "HCES_2022_23")
        if c.survey:
            ss.add(c.survey)
        c.comparison_surveys = sorted(ss)
    # Two-value trend sentences: "to NEW in R2 ... from OLD in R1".
    pat = (
        r"(?:to|is|was|rose to)\s*(?:rs\.?|inr|₹)?\s*([\d,]+(?:\.\d+)?)"
        r"\s*(?:%|percent|rs\.?)?\s*in\s*(\d{4}[-–]\d{2,4}|\d{4})"
        r"[^.]{0,80}from\s*(?:rs\.?|inr|₹)?\s*([\d,]+(?:\.\d+)?)"
        r"\s*(?:%|percent|rs\.?)?\s*in\s*(\d{4}[-–]\d{2,4}|\d{4})"
    )
    m = re.search(pat, q)
    if m:
        try:
            new_v, new_r, old_v, old_r = (
                float(m.group(1).replace(",", "")),
                m.group(2),
                float(m.group(3).replace(",", "")),
                m.group(4),
            )
            c.asserted_pairs = [
                {"value": old_v, "round": old_r},
                {"value": new_v, "round": new_r},
            ]
            c.claim_type = "comparative"
            if c.survey:
                c.comparison_surveys = sorted(set(c.comparison_surveys) | {c.survey})
        except ValueError:
            pass
    if any(w in q for w in ("will ", "forecast", "2027", "2030", "predict")):
        c.claim_type, c.wants_forecast = "forecast", True
    if any(w in q for w in ("cause", "impact of", "leads to", "why did")):
        c.claim_type, c.wants_causal = "causal", True
    if any(
        w in q
        for w in ("government failing", "political", "vote", "bjp", "congress", "modi")
    ):
        c.wants_political_judgment = True
    if "household level data" in q or "individual record" in q or "microdata" in q:
        c.claim_type, c.wants_microdata = "microdata", True
    if "poverty" in q or "real change" in q or "actually rose" in q:
        c.asserts_poverty_or_real_change = True
    # Definitional only when the user asks about a concept. "What is the UR in
    # PLFS 2023-24?" is a value question (a round/year is present), and
    # forecast/causal/microdata intents are never downgraded to methodology.
    if c.claim_type not in ("forecast", "causal", "microdata") and (
        any(w in q for w in ("define", "definition", "meaning of"))
        or ("what is" in q and not re.search(r"\b(?:19|20)\d{2}\b", q))
    ):
        c.claim_type = "definitional"
    if c.survey is None and c.indicator is None:
        anchored = any(
            w in q
            for w in (
                "cws",
                "usual status",
                "ps+ss",
                "mpce",
                "lfpr",
                "wpr",
                "methodology",
                "survey",
                "plfs",
                "hces",
                "tus",
                "mis",
            )
        )
        if c.claim_type != "definitional" or not anchored:
            c.claim_type = "out_of_scope"

    c.extraction_confidence, c.extraction_notes = confidence(c)
    return c


def repair_json(raw: str) -> dict:
    """Lab1 repair loop: strip fences, extract object, defaults for missing fields.

    Naive json.loads fails on markdown fences, trailing commas, single quotes.
    This tolerant parse + schema validation mirrors labs/lab1 extract.py B-variant.
    """
    import json as _json

    t = raw.strip()
    # strip markdown fences
    if t.startswith("```"):
        # drop first fence line and last fence
        lines = t.splitlines()
        lines = [l for l in lines if not l.strip().startswith("```")]
        t = "\n".join(lines)
    start, end = t.find("{"), t.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("no JSON object found")
    blob = t[start : end + 1]
    # tolerate trailing commas and single quotes
    blob = re.sub(r",\s*([}\]])", r"\1", blob)
    try:
        return _json.loads(blob)
    except Exception:
        return _json.loads(blob.replace("'", '"'))


def extract_llm(question: str) -> Claim:
    """Flexible translator via LLM. Used only when VIDHI_USE_LLM=1;
    the LLM translates NL -> Claim and NEVER judges. Output is validated
    against the Claim schema; any failure falls back to extract()."""
    import json as _json

    fields = (
        "survey",
        "round",
        "indicator",
        "measure",
        "geography",
        "state",
        "residence",
        "sex",
        "age_group",
        "claim_type",
    )
    prompt = (
        "Translate this Indian official-statistics question into JSON with "
        f"exactly these keys: {list(fields)}. "
        "survey: PLFS_2025 | PLFS_2023_24 | HCES_2023_24 | TUS_2024 | "
        "NSS78_MIS_2020_21 | null. indicator: LFPR | WPR | UR | MPCE | null. "
        "measure: usual_status_ps_ss | CWS | with_imputation | "
        "without_imputation | null. residence: rural | urban | null. "
        "sex: male | female | null. claim_type: descriptive | comparative | "
        "causal | forecast | microdata | out_of_scope | definitional. "
        "Output ONLY the JSON object.\n\nQ: " + question
    )
    try:
        from aip.llm import generate
        raw = generate(prompt, max_tokens=300, temperature=0.0)
        try:
            data = repair_json(raw)
        except Exception:
            data = _json.loads(raw[raw.find("{") : raw.rfind("}") + 1])
        # schema-first: validate, repair missing/invalid claim_type
        if data.get("claim_type") not in (
            "descriptive",
            "comparative",
            "causal",
            "forecast",
            "microdata",
            "out_of_scope",
            "definitional",
        ):
            data["claim_type"] = "descriptive"
        c = Claim(raw_question=question, **{k: data.get(k) for k in fields})
    except Exception:
        return extract(question)
    c.extraction_confidence, c.extraction_notes = confidence(c)
    return c


def translate(question: str) -> Claim:
    import os as _os

    use_llm = _os.getenv("VIDHI_USE_LLM", "0").strip().lower()
    if use_llm in {"1", "true"}:
        try:
            return extract_llm(question)
        except Exception:
            pass
    return extract(question)


StructuredStatisticalClaim = Claim
heuristic_extract = extract
field_compatible = compatible
