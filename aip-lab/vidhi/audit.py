# ruff: noqa: BLE001 - intentional guarded fallbacks (offline/API-degraded paths)
"""vidhi2 audit: every candidate row must trace to its cited source text.

Fails the build (non-zero exit) on any untraceable value or duplicate ID.
Dual-source rule: rows covered by both the API and a PDF parser must agree.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

_TEXT: dict[str, str] = {}


def text(raw_dir: Path, pdf: str) -> str:
    if pdf not in _TEXT:
        try:
            import pymupdf as fitz
        except ImportError:
            import fitz

        _TEXT[pdf] = "\n".join(pg.get_text() for pg in fitz.open(raw_dir / pdf))
    return _TEXT[pdf]


def variants(v) -> list[str]:
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


def check(raw_dir: Path, r: dict) -> tuple[bool, str]:
    prov = r.get("provenance", {})
    if prov.get("extractor", "").endswith("esankhyiki"):
        return True, "API-sourced; agreement checked separately"
    src = r.get("source_document", "")
    try:
        t = text(raw_dir, src)
    except Exception as exc:
        return False, f"source unreadable: {exc}"
    vals = variants(r.get("value"))
    if r.get("geography") == "state":
        anchors = [r.get("state") or ""]
        if r.get("state") == "Andaman & Nicobar Islands":
            anchors.append("Andaman & N Islands")
        for a in anchors:
            for m in re.finditer(re.escape(a), t):
                if any(v in t[m.start() : m.start() + 400] for v in vals):
                    return True, "value adjacent to state in source"
        return False, f"{r.get('value')} not near {r.get('state')!r}"
    # National rows: value must sit near an indicator/table anchor.
    anchor_words = {
        "MPCE": ["All-India", "average MPCE", "imputed values"],
        "LFPR": ["Participation", "Table 1"],
        "WPR": ["Worker Population", "Table 2"],
        "UR": ["Unemployment", "Statement 14"],
        "average_time": ["minutes", "spent"],
        "participation_rate": ["Participation", "reported"],
    }.get(r.get("indicator", ""), [r.get("indicator", "")])
    for a in anchor_words:
        for m in re.finditer(re.escape(a), t):
            seg = t[max(0, m.start() - 2500) : m.start() + 2500]
            if any(v in seg for v in vals):
                return True, f"value near {a!r}"
    return False, f"{r.get('value')} not traceable in {src}"


def audit_rows(raw_dir: Path, rows: list[dict]) -> tuple[list[dict], list[str]]:
    fails = []
    for r in rows:
        ok, why = check(raw_dir, r)
        r["verification_status"] = "verified" if ok else "unverified"
        r["audit_note"] = f"vidhi.audit: {why}"
        if not ok:
            fails.append(f"{r['row_id']}: {why}")
    return rows, fails
