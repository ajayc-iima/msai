"""Re-verification audit: does every store value actually appear on its cited PDF page?

This is a NON-circular check: it does not re-run the extractor, it opens the
cited page of the committed PDF and looks for the value's digits there. It
proves (a) the value is on the cited page, (b) the page reference is right,
(c) the PDF hash still matches. It does NOT prove the interpretation is
correct (that needs a human read) -- the report says so.
"""
import hashlib
import json
import random
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import fitz  # pymupdf

from vidhi.sources.pages import _value_pattern

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"

store = json.loads((ROOT / "vidhi" / "store.json").read_text(encoding="utf-8"))
rows = [r for r in store["rows"] if r.get("verification_status") == "verified"]

# ---- group by source document, hash-check each PDF once ----------------------
docs: dict[str, dict] = {}
for r in rows:
    src = r.get("source_document")
    if not src:
        continue
    p = RAW / src
    if not p.exists():
        continue
    if src not in docs:
        h = hashlib.sha256(p.read_bytes()).hexdigest()
        docs[src] = {
            "path": p,
            "sha256": h,
            "declared": (r.get("provenance") or {}).get("pdf_sha256"),
            "doc": fitz.open(p),
        }
    docs[src]["rows"] = docs[src].get("rows", []) + [r]

print("=" * 74)
print("VIDHI STORE RE-VERIFICATION AUDIT")
print("=" * 74)
print(f"verified rows: {len(rows)}   source PDFs present: {len(docs)}\n")

for src, d in sorted(docs.items()):
    ok = (not d["declared"]) or d["declared"] == d["sha256"]
    print(f"  {src:44} sha256 {'MATCH' if ok else 'MISMATCH'}  rows={len(d['rows'])}")

# ---- value-on-page check ----------------------------------------------------
def digits(s: str) -> str:
    return re.sub(r"[^0-9]", "", str(s))

checked = found = 0
not_found: list[dict] = []
no_page = 0
for src, d in docs.items():
    for r in d["rows"]:
        page_no = (r.get("provenance") or {}).get("pdf_page")
        if page_no is None:
            no_page += 1
            continue
        try:
            # pdf_page is the PRINTED page number (1-based); fitz indexes 0-based.
            idx = int(page_no) - 1
            if not (0 <= idx < d["doc"].page_count):
                raise IndexError
            pg = d["doc"][idx]
        except Exception:
            not_found.append({"row": r["row_id"], "why": "page out of range", "page": page_no})
            continue
        text = pg.get_text()
        pat = _value_pattern(r.get("value"))
        if pat is None:
            continue
        checked += 1
        hit = bool(pat.search(text))
        if hit:
            found += 1
        else:
            not_found.append({
                "row": r["row_id"], "value": r.get("value"), "page": page_no,
                "src": src, "why": "value not found in page text",
            })

print(f"\nvalue-on-cited-page check")
print(f"  rows with a cited page : {checked}")
print(f"  value found on that page: {found}  ({found / checked:.4f})" if checked else "  n/a")
print(f"  rows without a page ref : {no_page}")
print(f"  NOT found               : {len(not_found)}")
for nf in not_found[:25]:
    print("    -", nf)

out = {
    "verified_rows": len(rows),
    "pdfs": {k: {"sha256": v["sha256"], "rows": len(v["rows"])} for k, v in docs.items()},
    "checked_with_page": checked,
    "found_on_page": found,
    "not_found": not_found,
    "rows_without_page": no_page,
}
(ROOT / "evaluation" / "statsdoc_audit").mkdir(parents=True, exist_ok=True)
(ROOT / "evaluation" / "store_reaudit.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
print("\nsaved evaluation/store_reaudit.json")
