"""vidhi2 consistency: post-retrieval contradiction check.

Downgrades PASS -> WARN only on genuine disagreement: same round AND same
filters AND same measure basis AND same unit. Every ambiguity rule below
exists because a real incident proved the naive version wrong:

* %-gap figures ("Difference as % of Rural MPCE: 69.7") are not Rs levels
  (unit screen);
* in "2022-23: ... 6,459. 2023-24: ..." lists, a number belongs to the
  PRECEDING round token, not the nearer following one (segment ownership);
* an excerpt silent on imputation basis cannot contradict a
  with/without-imputation claim (unknown basis is never contradiction).
"""

from __future__ import annotations

import re

_NUM = re.compile(r"(?<![0-9–-])(\d{1,3}(?:,\d{3})*(?:\.\d+)?)(?![0-9–-])")
_ROUND = re.compile(r"\d{4}[–-]\d{2,4}|\d{4}")

DIMS = (("residence", ["rural", "urban"]), ("sex", ["male", "female"]))
STATES = (
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
    "andaman & nicobar islands",
    "dadra & nagar haveli",
)
MEASURE_TOKENS = {
    "without_imputation": ["without"],
    "with_imputation": ["with imputation", "with imput", "imputed"],
}

# Lab4/5 fix: TUS rows are distinguished by activity. Without this,
# any same-sex number (e.g. 289 unpaid-domestic) contradicts a
# different-activity claim (e.g. 137 caregiving). Conservative: no
# activity anchor nearby -> never contradiction (DESIGN guarantee 5).
ACTIVITY_PHRASES = {
    "unpaid_domestic": ["unpaid domestic", "domestic services"],
    "caregiving": ["caring", "caregiving"],
    "culture_leisure": ["culture", "leisure", "mass media"],
    "employment": ["employment"],
    "learning": ["learning"],
    "selfcare": ["self-care", "self care", "selfcare", "maintenance"],
}


def _nearest_activity(text: str, pos: int, span: int = 300) -> str | None:
    best, best_d = None, span + 1
    for act_key, phrases in ACTIVITY_PHRASES.items():
        for ph in phrases:
            try:
                pat = r"\b" + re.escape(ph) + r"\b"
                for m in re.finditer(pat, text, re.IGNORECASE):
                    d = abs(m.start() - pos)
                    if d <= span and d < best_d:
                        best, best_d = act_key, d
            except re.error:
                continue
    return best


def _nearest_round(text: str, pos: int, span: int = 120) -> str | None:
    for m in reversed(list(_ROUND.finditer(text[max(0, pos - span) : pos]))):
        return m.group(0)
    for m in _ROUND.finditer(text[pos : pos + 40]):
        return m.group(0)
    return None


def _same_round(tok: str | None, claim_round: str | None) -> bool:
    if not tok or not claim_round:
        return tok == claim_round
    return tok == claim_round or (len(tok) == 4 and claim_round.startswith(tok))


def _near(text: str, pos: int, toks: list[str], span: int = 120) -> str | None:
    best, best_d = None, span + 1
    for tok in toks:
        # Plural-tolerant: "Females spent 289" must match "female".
        pat = r"\b" + re.escape(tok) + ("" if tok.endswith("s") else r"s?") + r"\b"
        for m in re.finditer(pat, text, re.IGNORECASE):
            if abs(m.start() - pos) <= span and abs(m.start() - pos) < best_d:
                best, best_d = tok.lower(), abs(m.start() - pos)
    return best


def _unit_conflict(text: str, pos: int, unit: str | None) -> bool:
    if not unit:
        return False
    win = text[max(0, pos - 60) : pos + 60]
    if re.search(
        r"as\s*%\s*of|difference[^.]{0,80}%|%\s*(difference|gap)",
        text[max(0, pos - 150) : pos],
        re.IGNORECASE,
    ):
        return "rs" in unit.lower() or "inr" in unit.lower()
    if not re.search(r"%\b|percent", win, re.IGNORECASE):
        return False
    before = text[max(0, pos - 12) : pos]
    if "rs" in unit.lower() or "inr" in unit.lower():
        return not bool(re.search(r"(rs\.?|inr|₹)", before, re.IGNORECASE))
    return bool(re.search(r"(rs\.?|inr|₹)", before, re.IGNORECASE))


def _attributed(text: str, pos: int, claim, unit: str | None) -> bool:
    if not _same_round(_nearest_round(text, pos), claim.round):
        return False
    for dim, vals in DIMS:
        cv = getattr(claim, dim, None)
        fixed = (
            str(cv).lower() if cv and str(cv).lower() not in ("all", "mixed") else None
        )
        near = _near(text, pos, vals)
        if fixed:
            if near is not None and near != fixed:
                return False
            if (
                near is None
                and dim == "sex"
                and _near(text, pos, vals, span=300) is not None
            ):
                # Unqualified figure in an excerpt that mixes sex cuts
                # (e.g. all-person 440 next to male 473): cannot attribute.
                return False
        elif near is not None:
            return False
    near_state = _near(text, pos, list(STATES))
    if claim.state:
        if near_state != claim.state.lower():
            return False
    elif near_state is not None:
        return False  # subgroup figure; claim is unfiltered
    claim_act = getattr(claim, "activity", None)
    if claim_act and str(claim_act).lower() not in ("all", "mixed", "none", ""):
        got_act = _nearest_activity(text, pos, span=300)
        if got_act is None:
            return False
        if got_act != str(claim_act).lower():
            return False
    toks = [t for toks in MEASURE_TOKENS.values() for t in toks]
    hit = _near(text, pos, toks)
    if (claim.measure or None) in MEASURE_TOKENS or hit is not None:
        # Basis agreement: a figure stated on one imputation basis cannot
        # contradict a claim on another basis (or none); unknown-vs-unknown
        # still attributes.
        got = (
            None
            if hit is None
            else ("without_imputation" if hit == "without" else "with_imputation")
        )
        if got != (claim.measure or None):
            return False
    return not _unit_conflict(text, pos, unit)


def numbers(text: str, claim, unit: str | None) -> list[float]:
    out = []
    for m in _NUM.finditer(text):
        try:
            v = float(m.group(1).replace(",", ""))
        except ValueError:
            continue
        if 1900 <= v <= 2100 and v.is_integer():
            continue  # calendar year, not a figure
        if v.is_integer() and abs(v) < 100:
            continue  # counters ("7 days", "Table 7"), not figures
        if _attributed(text, m.start(), claim, unit):
            out.append(v)
    return out


def check(claim, verdict, hits: list[dict]):
    """Return a downgraded WARN verdict on genuine disagreement, else None."""
    if verdict.decision != "PASS" or verdict.value is None:
        return None
    if getattr(claim, "asserted_pairs", None):
        return None  # pair claims are verified cell-by-cell in rules._pairs;
        # single-round excerpt attribution cannot judge a two-round claim.
    from vidhi.rules import Verdict

    for h in hits:
        if h.get("doc_id") == (verdict.row_id or ""):
            continue
        for n in numbers(h.get("text", ""), claim, verdict.unit):
            try:
                same = abs(n - float(verdict.value)) <= 1e-9
            except (TypeError, ValueError):
                continue
            if not same:
                w = Verdict(
                    "WARN",
                    "WARN_NUMERIC_MISMATCH",
                    "R_NUMERIC_MISMATCH",
                    f"Retrieved evidence states {n:g} for the same "
                    f"round/filters but the official table gives "
                    f"{verdict.value} {verdict.unit or ''} "
                    f"(row {verdict.row_id}).",
                    "consistency",
                    verdict.row_id,
                    verdict.value,
                    verdict.unit,
                )
                w.freeze(claim, verdict.rule_version + "+consistency")
                return w
    return None
