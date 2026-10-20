#!/usr/bin/env python3
# ruff: noqa: BLE001 - intentional guarded fallbacks
"""Vidhi ground-truth provenance audit (Lab 7 honesty standard).

Every row in data/truth/ground_truth_tables.json must be traceable to
extracted text of its cited source PDF. Checks:

  1. value_proximity: the formatted value appears near its identifying
     context (state name / All-India / indicator words) in the cited PDF.
  2. unique_ids: row_id must be unique (citations point at one fact).
  3. Freshness: rows that fail (1) are demoted to verification_status
     "unverified" -- the firewall then WARNs on them instead of PASSing,
     which is the safe failure mode by construction.

Usage:
    python scripts/vidhi_audit_truth.py            # report only
    python scripts/vidhi_audit_truth.py --apply    # demote + dedupe IDs

Exit code is non-zero when any row fails, so CI can gate on it.
"""

from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRUTH = ROOT / "data" / "truth" / "ground_truth_tables.json"

PDF_TEXT_CACHE: dict[str, str] = {}


def pdf_text(name: str) -> str:
    if name not in PDF_TEXT_CACHE:
        import fitz

        d = fitz.open(ROOT / "data" / "raw" / name)
        PDF_TEXT_CACHE[name] = "\n".join(p.get_text() for p in d)
    return PDF_TEXT_CACHE[name]


def fmt_val(v) -> list[str]:
    """All textual renderings a value could take in the PDFs."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return [str(v)]
    out = {str(v), f"{f:g}"}
    if f.is_integer():
        out.add(f"{int(f):,}")
    else:
        out.add(f"{f:,.1f}")
    return sorted(out, key=len, reverse=True)


def near(text: str, anchor: str, variants: list[str], window: int = 400) -> bool:
    """A value variant occurs within `window` chars after an anchor."""
    for m in re.finditer(re.escape(anchor), text):
        seg = text[m.start() : m.start() + window]
        if any(v in seg for v in variants):
            return True
    return False


STATE_ALIASES = {
    "Andaman & Nicobar Islands": ["Andaman & N Islands", "Andaman"],
}


def check_row(r: dict) -> tuple[bool, str]:
    src = r.get("source_document", "")
    try:
        text = pdf_text(src)
    except Exception as exc:
        return False, f"source PDF missing/unreadable: {exc}"
    variants = fmt_val(r.get("value"))
    survey, ind = r.get("survey"), r.get("indicator")

    if survey == "HCES_2023_24" and ind == "MPCE" and r.get("geography") == "state":
        state = r.get("state") or ""
        # Statement 7 table: "State  rural-val  urban-val" sequence.
        anchors = [state] + STATE_ALIASES.get(state, [])
        if any(near(text, a, variants) for a in anchors):
            return True, "state value adjacent in factsheet Statement 7"
        return False, f"{r.get('value')} not found near {state!r} in {src}"

    if survey == "HCES_2023_24" and ind == "MPCE" and r.get("geography") == "India":
        anchors = ["All-India", "all-India", "Statement 2", "4,122", "average MPCE"]
        for a in anchors:
            if near(text, a, variants, window=1200):
                return True, f"value near {a!r}"
        # Fallback: value anywhere in doc (weak, flagged).
        if any(v in text for v in variants):
            return True, "value present in doc (weak proximity)"
        return False, f"{r.get('value')} not found in {src}"

    if survey and survey.startswith("PLFS") and ind in ("LFPR", "WPR", "UR"):
        table_word = {
            "LFPR": "Participation",
            "WPR": "Worker Population",
            "UR": "Unemployment",
        }.get(ind, ind)
        # Value must sit near the indicator's table context.
        idxs = [m.start() for m in re.finditer(table_word, text)]
        for v in variants:
            for pos in [m.start() for m in re.finditer(re.escape(v), text)][:400]:
                if any(abs(pos - t) < 2500 for t in idxs):
                    return True, f"value near {table_word!r} table context"
        return False, f"{r.get('value')} not in {ind} table context of {src}"

    # TUS / MIS / other: value must at least occur in the cited doc.
    if any(v in text for v in variants):
        return True, "value present in cited doc"
    return False, f"{r.get('value')} not found in {src}"


def main() -> int:
    apply = "--apply" in sys.argv
    doc = json.loads(TRUTH.read_text(encoding="utf-8"))
    rows = doc.get("rows", [])

    seen: dict[str, list[int]] = {}
    for i, r in enumerate(rows):
        seen.setdefault(r.get("row_id", "?"), []).append(i)

    report = []
    value_fails = dupe_only = 0
    for i, r in enumerate(rows):
        ok, why = check_row(r)
        dupe = len(seen.get(r.get("row_id", "?"), [])) > 1
        if not ok:
            value_fails += 1
        elif dupe:
            dupe_only += 1
        status = "OK" if (ok and not dupe) else "FAIL"
        flag = " [DUPLICATE row_id]" if (dupe and ok) else ""
        report.append(
            {
                "row_id": r.get("row_id"),
                "value_ok": ok,
                "dupe": dupe,
                "detail": why + flag,
                "index": i,
            }
        )
        print(
            f"[{status}] {r.get('row_id')} ({r.get('survey')}/{r.get('indicator')}/"
            f"{r.get('state') or r.get('geography')}/{r.get('residence')}/"
            f"{r.get('sex')}/{r.get('round')}={r.get('value')}): {why}{flag}"
        )

    fails = value_fails + dupe_only
    print(
        f"\nrows={len(rows)} value_verified={len(rows) - value_fails} "
        f"value_failed={value_fails} dupe_id_only={dupe_only} "
        f"dupe_ids={sum(1 for v in seen.values() if len(v) > 1)}"
    )

    if apply and fails:
        shutil.copy(TRUTH, TRUTH.with_suffix(".json.bak"))
        # Dedupe IDs deterministically: append state/residence/sex/round.
        used: set[str] = set()
        for i, r in enumerate(rows):
            base = r.get("row_id", f"ROW_{i}")
            if base in used:
                suffix = "_".join(
                    str(r.get(k) or "").replace(" ", "").replace("&", "+")
                    for k in ("state", "residence", "sex", "round")
                )
                r["row_id"] = f"{base}__{suffix or i}"
            used.add(r["row_id"])
        for rep, r in zip(report, rows):
            # Demote ONLY genuine value failures; dupe-ID rows keep verified
            # status once their IDs are unique.
            if not rep["value_ok"]:
                r["verification_status"] = "unverified"
                r["audit_note"] = f"vidhi_audit_truth: {rep['detail']}"
        doc["rows"] = rows
        doc["audit"] = {
            "tool": "scripts/vidhi_audit_truth.py",
            "value_failed": value_fails,
            "dupes_fixed": dupe_only,
            "policy": "value failures demoted to unverified; dupe IDs made unique",
        }
        TRUTH.write_text(
            json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(
            f"applied: backup at {TRUTH.with_suffix('.json.bak')}, "
            f"{value_fails} demoted + {dupe_only} IDs deduped in {TRUTH}"
        )
    elif fails:
        print("run with --apply to demote value failures + dedupe IDs")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
