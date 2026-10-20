"""Full-store reachability probe: every verified row must be answerable
through the real claim-extract -> firewall pipeline with its exact figure.

    python scripts/coverage_probe.py

The store now carries ~1700 verified rows: the whole PLFS Highlights battery
(11 survey rounds x usual+CWS x LFPR/WPR/UR x {15+/all ages} x 9 sector-sex
cells), the TUS 2024 battery (nine ICATUS divisions x gender/sector/age x
participation/per-participant/per-person + Tables 10/11 group rows + report
Statement 5/6 age-sex rows) and the HCES 2023-24 factsheet trend columns.
The probe prints every row that cannot be reached naturally. Exit 0 iff all
rows are reachable with exact values.

`question_for(r)` is imported by tests/test_vidhi.py, so the guarantee is
enforced on every test run, not just when this script is run by hand.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, ".")

from vidhi.claims import extract
from vidhi import pipeline as P

ROOT = Path(__file__).resolve().parents[1]

STATE_TXT = {
    "Jammu & Kashmir": "jammu and kashmir",
    "Andaman & Nicobar Islands": "andaman and nicobar islands",
    "Dadra & Nagar Haveli and Daman & Diu": "dadra and nagar haveli and daman and diu",
}
ACT_PHRASE = {
    "unpaid_domestic": "unpaid domestic services",
    "caregiving": "caring for",
    "culture_leisure": "leisure and culture activities",
    "employment": "paid employment activities",
    "learning": "learning activities",
    "selfcare": "self care",
    "production_own_use": "production of goods for own use",
    "unpaid_volunteer": "volunteer and other unpaid work",
    "socializing_religious": "socializing and religious practice",
    "unpaid_activities": "unpaid activities",
    "paid_activities": "paid activities",
    "unpaid_paid": "unpaid and paid activities",
    "residual_other": "residual other activities",
}
IMP = {"with_imputation": "with imputation", "without_imputation": "without imputation"}
STATUS = {"usual_status_ps_ss": "in usual status", "CWS": "in current weekly status"}
SEX = {"male": "male", "female": "female"}
RES_PFX = {"rural": "rural ", "urban": "urban "}
TUS_AGE = {
    "6-14": "aged 6-14 ",
    "15-29": "aged 15-29 ",
    "15-59": "aged 15-59 ",
    "60plus": "aged 60 and above ",
}


def question_for(r: dict) -> tuple[str, object]:
    """Natural-language question that must reach exactly this store row."""
    survey, rnd, ind = r["survey"], r["round"], r["indicator"]
    if survey.startswith("HCES"):
        res = RES_PFX.get(r.get("residence"), "")
        st = (STATE_TXT.get(r["state"], (r["state"] or "").lower())
              if r.get("state") else "india")
        imp = IMP.get(r.get("measure"))
        q = (f"What was the {res}monthly per capita consumption expenditure "
             f"{imp} in {st} in HCES {rnd}?")
        return " ".join(q.split()), r["value"]
    if survey.startswith("PLFS"):
        sex = SEX.get(r.get("sex"), "")
        status = STATUS.get(r.get("measure"), "")
        res = RES_PFX.get(r.get("residence"), "")
        phrase = {"LFPR": "LFPR", "WPR": "WPR", "UR": "unemployment rate"}[ind]
        age = "for all ages" if r.get("age_group") == "all" else "for age 15+"
        q = (f"What was the {res}{sex} {phrase} {age} {status} "
             f"in PLFS {rnd}?")
        return " ".join(q.split()), r["value"]
    if survey.startswith("TUS"):
        act = ACT_PHRASE[r.get("activity")]
        sex = SEX.get(r.get("sex"), "")
        res = RES_PFX.get(r.get("residence"), "")
        agerm = TUS_AGE.get(r.get("age_group"), "")
        if ind == "participation_rate":
            q = (f"What was the {res}{sex} participation rate for {act} "
                 f"{agerm}as per TUS {rnd}?")
        else:
            pp = " per person" if r.get("measure") == "per_person" else ""
            q = (f"How much time did {res}{sex} persons {agerm}"
                 f"spend{pp} on {act} as per TUS {rnd}?")
        return " ".join(q.split()), r["value"]
    raise AssertionError(survey)


def probe(fw) -> tuple[int, list]:
    doc = json.loads((ROOT / "vidhi" / "store.json").read_text(encoding="utf-8"))
    rows = [r for r in doc.get("rows", [])
            if r.get("verification_status") == "verified"]
    fails, ok = [], 0
    for r in rows:
        q, expected = question_for(r)
        v = fw.adjudicate(extract(q))
        if v.decision == "PASS" and v.value == r["value"] and v.row_id == r["row_id"]:
            ok += 1
        else:
            fails.append((r["row_id"], q, f"{v.decision}/{v.sub_code}",
                          v.value, expected, v.row_id))
    return ok, len(rows), fails


def main() -> int:
    fw = P.firewall()
    ok, total, fails = probe(fw)
    print(f"reachable with exact figure: {ok} / {total}")
    for row_id, q, dec, got, exp, rid in fails:
        print(f"\nFAIL {row_id}\n  q: {q!r}\n  got: {dec} value={got} row={rid}\n  exp: {exp}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
