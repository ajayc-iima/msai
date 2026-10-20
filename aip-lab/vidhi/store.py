"""vidhi2 store: the built truth artifact. Generated, never hand-edited.

Build: sources/* emit candidate rows with provenance -> audit marks
verified/unverified -> build() freezes the JSON + manifest.
Serve: lookup() answers ONLY from verified rows under strict matching
(a specific claim filter is satisfied only by the SAME row value; an
all-India row never answers a female/urban/Bihar question). The converse
also holds: an unspecified filter is satisfied only by an aggregate row,
so a bare "MPCE" question can never be silently answered with the rural
slice.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


def _norm(v):
    return v.strip().lower() if isinstance(v, str) else v


def build(rows: list[dict], out: Path, manifest: dict) -> dict:
    import datetime

    seen: dict[str, int] = {}
    for r in rows:
        seen[r["row_id"]] = seen.get(r["row_id"], 0) + 1
    dupes = {k: n for k, n in seen.items() if n > 1}
    if dupes:
        raise ValueError(f"duplicate row_ids: {sorted(dupes)}")
    manifest = dict(manifest)
    manifest["built_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    doc = {
        "version": 1,
        "note": "Built artifact. Only verified rows may PASS.",
        "manifest": manifest,
        "rows": rows,
    }
    blob = json.dumps(doc, indent=2, ensure_ascii=False)
    out.write_text(blob, encoding="utf-8")
    return {
        "rows": len(rows),
        "verified": sum(1 for r in rows if r.get("verification_status") == "verified"),
        "sha256": hashlib.sha256(blob.encode()).hexdigest(),
    }


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def find_row(doc: dict, row_id: str | None) -> dict | None:
    """Return the store row with the given row_id, or None."""
    if not row_id:
        return None
    for r in doc.get("rows", []):
        if r.get("row_id") == row_id:
            return r
    return None


def lookup(doc: dict, claim, round_override: str | None = None) -> dict | None:
    """Strict verified-only match. Returns the best row or None."""
    if getattr(claim, "round", None) and round_override:
        claim = claim.model_copy(update={"round": round_override})
    best, best_spec = None, (-1, -1)
    for r in doc.get("rows", []):
        if r.get("verification_status") != "verified":
            continue
        if _norm(r.get("survey")) != _norm(claim.survey):
            continue
        if _norm(r.get("indicator")) != _norm(claim.indicator):
            continue
        if (
            claim.round
            and r.get("round")
            and _norm(r.get("round")) != _norm(claim.round)
        ):
            continue
        ok, spec, agg = True, 0, 0
        for f in ("residence", "sex", "state", "geography", "activity"):
            cv, rv = _norm(getattr(claim, f, None)), _norm(r.get(f))
            if cv in (None, "", "all"):
                if rv in ("all", None, ""):
                    agg += 1  # unspecified claim prefers the aggregate row
                else:
                    # Never silently narrow an unspecified dimension: answering
                    # "MPCE" with the rural figure is a wrong-granularity PASS.
                    ok = False
                    break
                continue
            if rv in (None, "", "all") or cv != rv:
                ok = False
                break
            spec += 1
        if not ok:
            continue
        for f in ("measure", "age_group"):
            cv, rv = _norm(getattr(claim, f, None)), _norm(r.get(f))
            if cv in (None, "", "all") or rv in (None, "", "all"):
                continue
            if cv != rv:
                ok = False
                break
            spec += 1
        if ok and (spec, agg) > best_spec:
            best, best_spec = r, (spec, agg)
    return best


def coverage(doc: dict, claim) -> dict:
    """Live-computed coverage for honest WARNs: what exists for this
    survey+indicator, and the closest verified context (never endorsed)."""
    rows = [
        r
        for r in doc.get("rows", [])
        if r.get("verification_status") == "verified"
        and (not claim.survey or r.get("survey") == claim.survey)
        and (not claim.indicator or r.get("indicator") == claim.indicator)
    ]
    slices = sorted(
        {
            "/".join(
                str(r.get(k) or "all") for k in ("residence", "sex", "state", "round")
            )
            for r in rows
        }
    )
    # Never substitute a *different* state. A state-specific question may fall
    # back to the all-India aggregate (clearly labelled as context), and a
    # national question stays on aggregate rows. Residence/sex may be relaxed
    # last, so the closest row still agrees on as many requested dimensions as
    # the store allows.
    cs = getattr(claim, "state", None)

    def _state_ok(r: dict) -> bool:
        rs = str(r.get("state") or "").lower()
        if not cs:
            return rs in ("", "all", "none")
        return rs in ("", "all", "none") or rs == str(cs).lower()

    pool = [r for r in rows if _state_ok(r)]

    def _match(r: dict, dims: tuple[str, ...]) -> bool:
        return all(
            not getattr(claim, d, None)
            or str(getattr(claim, d)).lower() in ("all", "none")
            or str(r.get(d) or "all").lower() == str(getattr(claim, d)).lower()
            for d in dims
        )

    best = None
    for dims in (("residence", "sex"), ("residence",), ("sex",), ()):
        cand = [r for r in pool if _match(r, dims)]
        if cand:
            best = max(
                cand,
                key=lambda r: sum(
                    1
                    for d in ("residence", "sex", "state")
                    if str(r.get(d) or "all").lower()
                    == str(getattr(claim, d) or "all").lower()
                ),
            )
            break
    return {"n": len(rows), "slices": slices, "closest": best}
