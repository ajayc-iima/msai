"""Measure typed-claim accuracy of the NL -> claim translator.

The firewall is only as good as the claim the translator builds: a
mistranslated claim yields a confidently wrong, correctly cited verdict.
This measures the translator on misspellings, abbreviations, paraphrases,
Hindi and multi-state questions -- against the CRITICAL fields only
(survey, indicator, state, round, sex, residence, measure).
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from vidhi.claims import extract  # noqa: E402

CRIT = ("survey", "indicator", "state", "round", "sex", "residence", "measure")

# (question, expected {field: value})  -- None means "must be empty".
CASES = [
    # --- canonical ---
    ("What was rural MPCE in HCES 2023-24?",
     {"survey": "HCES_2023_24", "indicator": "MPCE", "round": "2023-24", "residence": "rural"}),
    ("What was the CWS LFPR in PLFS 2025?",
     {"survey": "PLFS_2025", "indicator": "LFPR", "round": "2025", "measure": "cws"}),
    # --- misspellings / typos ---
    ("MPCE in maharastra 2023-24", {"state": "Maharashtra"}),
    ("MPCE in orissa", {"state": "Odisha"}),
    ("MPCE in pondicherry", {"state": "Puducherry"}),
    ("MPCE in biharr", {"state": "Bihar"}),
    ("MPCE in Karnatak", {"state": "Karnataka"}),
    ("MPCE in j&k", {"state": "Jammu & Kashmir"}),
    ("MPCE in dadra nagar haveli daman diu", {"state": "Dadra & Nagar Haveli and Daman & Diu"}),
    # --- abbreviations / codes ---
    ("mpce for mp", {"state": "Madhya Pradesh"}),
    ("MPCE in m.p.", {"state": "Madhya Pradesh"}),
    ("MPCE for up", {"state": "Uttar Pradesh"}),
    ("MPCE in mh", {"state": "Maharashtra"}),
    # --- paraphrases ---
    ("How much does a household spend on average per person each month in HCES 2023-24?",
     {"survey": "HCES_2023_24", "indicator": "MPCE"}),
    ("Tell me the labour force participation rate for 15 plus in PLFS 2025.",
     {"survey": "PLFS_2025", "indicator": "LFPR"}),
    ("How long do women spend on unpaid housework daily in TUS 2024?",
     {"survey": "TUS_2024", "sex": "female"}),
    # --- Hindi ---
    ("मध्य प्रदेश में MPCE क्या है?", {"state": "Madhya Pradesh", "indicator": "MPCE"}),
    ("PLFS 2025 में CWS LFPR कितना था?", {"survey": "PLFS_2025", "indicator": "LFPR"}),
    # --- multi-state ---
    ("MPCE in Madhya Pradesh, UP, Maharashtra",
     {"state": None, "states": ["Madhya Pradesh", "Uttar Pradesh", "Maharashtra"]}),
    # --- sex / residence ---
    ("What was female LFPR in rural India in PLFS 2025?",
     {"survey": "PLFS_2025", "indicator": "LFPR", "sex": "female", "residence": "rural"}),
    ("What was urban LFPR in PLFS 2025?", {"residence": "urban", "indicator": "LFPR"}),
]


def norm(v):
    return (v or "").lower().strip()


def main() -> int:
    ok = 0
    fails = []
    for q, exp in CASES:
        c = extract(q)
        got = {f: getattr(c, f, None) for f in CRIT}
        bad = []
        for k, v in exp.items():
            if k == "states":
                if list(getattr(c, "states", []) or []) != list(v):
                    bad.append(f"states={getattr(c, 'states', None)} expected {v}")
                continue
            if norm(got.get(k)) != norm(v):
                bad.append(f"{k}={got.get(k)!r} expected {v!r}")
        if bad:
            fails.append((q, bad))
        else:
            ok += 1
    n = len(CASES)
    print(f"typed-claim accuracy: {ok}/{n} = {ok / n:.3f}")
    for q, bad in fails:
        print("  FAIL:", q)
        for b in bad:
            print("       ", b)
    out = {
        "cases": n,
        "correct": ok,
        "accuracy": round(ok / n, 4),
        "fails": [{"question": q, "mismatches": b} for q, b in fails],
    }
    (ROOT / "evaluation" / "translator_accuracy.json").write_text(
        json.dumps(out, indent=2), encoding="utf-8"
    )
    print("saved evaluation/translator_accuracy.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
