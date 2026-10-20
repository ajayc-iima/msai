"""Locate the source PDF page for every verified store row.

The extractors parse whole-document text, so most rows carry no page
anchor. This module searches the cited PDF for the value in its printed
form and anchors the row to the page where it actually appears.

It is deliberately conservative: a row is anchored only when the page can
be identified unambiguously by the value plus context fingerprints (the
printed label, the state name, the table identifier, the indicator and the
basis). Rows that stay ambiguous are left un-anchored rather than guessed -
the store then reports them as "value + table + sha256, no single-page
anchor".
"""
from __future__ import annotations

import re
from pathlib import Path

import fitz

# Tokens that identify a table/section in the page text.
_TABLE_TOKENS = re.compile(
    r"(statement\s+\d+[a-z]?|table\s+\d+[a-z]?|highlights|"
    r"factsheet|summary statement|factsheet highlights|"
    r"chapter\s+[ivx0-9]+)",
    re.IGNORECASE,
)

# The table title on the page names the indicator and the basis, which is
# what disambiguates a value that appears in several highlights tables.
_INDICATOR_TOKENS = {
    "lfpr": ["labour force participation rate", "participation rate"],
    "wpr": ["worker population ratio"],
    "ur": ["unemployment rate"],
    "mpce": ["per capita consumption expenditure", "consumption expenditure"],
}
_MEASURE_TOKENS = {
    "usual_status_ps_ss": ["usual status"],
    "cws": ["current weekly status"],
    "with_imputation": ["imputation"],
    "without_imputation": ["without imputation"],
}


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def _value_pattern(value) -> re.Pattern | None:
    """Match the value in its printed form, not as a fragment of a bigger number.

    The PDFs print thousands with commas ("5,327") and percentages as
    "80.2", so the pattern accepts an optional comma between digit pairs
    while refusing to match inside a longer number.
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, float) and value.is_integer():
        v: object = int(value)
    elif isinstance(value, int):
        v = value
    else:
        try:
            f = float(value)
        except (TypeError, ValueError):
            return None
        v = int(f) if f.is_integer() else f
    txt = str(v)
    if txt in ("0", ""):
        return None
    ip, _, dp = txt.partition(".")
    ip_pat = ",?".join(ip)
    core = ip_pat + (r"\." + re.escape(dp) if dp else "")
    return re.compile(r"(?<![\d.,])" + core + r"(?![\d])")


def _fingerprints(row: dict) -> tuple[list[str], list[str]]:
    """(required, optional) context strings for disambiguating the page.

    Required tokens must all be present. Optional ones only break ties.
    """
    prov = row.get("provenance") or {}
    req: list[str] = []
    opt: list[str] = []

    printed = prov.get("pdf_printing")
    if printed:
        req.append(_norm(printed).lower())
    st = row.get("state")
    if st:
        req.append(_norm(st).lower())

    sec = row.get("table_or_section") or ""
    sec_low = sec.lower()
    for m in _TABLE_TOKENS.finditer(sec):
        t = m.group(1).lower()
        if t.startswith("statement") or t.startswith("table"):
            req.append(t)
        else:
            opt.append(t)

    ind = str(row.get("indicator") or "").lower()
    for key, phrases in _INDICATOR_TOKENS.items():
        if ind == key or ind.startswith(key):
            req.extend(phrases)
    if ind.startswith("participation_rate"):
        req.append("participation rate")
    if ind.startswith("average_time"):
        req.append("average time")

    meas = str(row.get("measure") or "").lower()
    for key, phrases in _MEASURE_TOKENS.items():
        if meas == key or key in meas:
            req.extend(phrases)

    # TUS splits: the page carrying a gender split has the three sex
    # columns; a sector split has rural/urban/India.
    if "split=gender" in sec_low:
        opt.extend(["male", "female", "person"])
    elif "split=sector" in sec_low:
        opt.extend(["rural", "urban", "all india"])
    elif "split=age" in sec_low:
        opt.append("age group")
    for n in re.findall(r"statement\s+(\d+)", sec_low):
        req.append(f"statement {n}")

    for m in re.finditer(r"\((?:usual|current weekly)\s*\([^)]*\)\)", sec, re.IGNORECASE):
        req.append(m.group(0).lower())

    req = [t for t in dict.fromkeys(req) if len(t) >= 3]
    opt = [t for t in dict.fromkeys(opt) if len(t) >= 3]
    return req, opt


def locate_pages(doc: dict, raw_dir: Path) -> dict:
    """Return {row_id: {"pdf_page": n, "pdf_page_confidence": str}}.

    `pdf_page` is the PRINTED (1-based) page number.
    """
    rows = [r for r in doc.get("rows", []) if r.get("verification_status") == "verified"]
    by_doc: dict[str, list[dict]] = {}
    for r in rows:
        src = r.get("source_document")
        if src:
            by_doc.setdefault(src, []).append(r)

    out: dict[str, dict] = {}
    for src, rws in by_doc.items():
        pdf = raw_dir / src
        if not pdf.exists():
            continue
        with fitz.open(pdf) as f:
            pages = [pg.get_text() for pg in f]
        page_low = [re.sub(r"\s+", " ", t).lower() for t in pages]
        for r in rws:
            pat = _value_pattern(r.get("value"))
            if pat is None:
                continue
            hits = [i for i, t in enumerate(pages) if pat.search(t)]
            if not hits:
                continue
            req, opt = _fingerprints(r)
            if len(hits) > 1 and req:
                # Score each candidate page by how much of the row's context it
                # carries, keep the best, then break ties with the optional
                # tokens. A page that carries none of the context is rejected.
                scored = [(i, sum(1 for t in req if t in page_low[i])) for i in hits]
                best = max(s for _, s in scored)
                if best < 1:
                    continue
                keep = [i for i, s in scored if s == best]
                if len(keep) > 1 and opt:
                    scored2 = [(i, sum(1 for t in opt if t in page_low[i])) for i in keep]
                    best2 = max(s for _, s in scored2)
                    if best2:
                        keep = [i for i, s in scored2 if s == best2]
                hits = keep
            if len(hits) != 1:
                continue
            conf = "value+context" if req else "value only"
            out[r["row_id"]] = {
                "pdf_page": hits[0] + 1,
                "pdf_page_confidence": conf,
            }
    return out
