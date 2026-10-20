"""vidhi2 store: the built truth artifact. Generated, never hand-edited.

Build: sources/* emit candidate rows with provenance -> audit marks
verified/unverified -> build() freezes the JSON + manifest.
Serve: lookup() answers ONLY from verified rows under strict matching
(a specific claim filter is satisfied only by the SAME row value; an
all-India row never answers a female/urban/Bihar question). The converse
also holds: an unspecified filter is never satisfied by ONE narrowed row.
If the store publishes that slice completely (rural AND urban; both
imputation legs), complete_slice() returns the WHOLE slice -- every cell
with its own row id -- and the firewall answers that instead of narrowing.
A slice the store does not publish completely is not answered at all.
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
            if cv in (None, ""):
                continue
            if rv in (None, ""):
                continue
            if cv != rv:
                ok = False
                break
            spec += 1
        if ok and (spec, agg) > best_spec:
            best, best_spec = r, (spec, agg)
    return best


# Dimensions the store publishes as a complete set for a slice. A slice is
# answered only when EVERY side exists (rural AND urban; both imputation
# legs), so the firewall never substitutes one side for the whole.
SLICE_DOMAINS: dict[str, tuple[str, ...]] = {
    "residence": ("rural", "urban"),
    "measure": ("with_imputation", "without_imputation"),
}

# Dimensions that must be aggregate ("all"/empty) when the claim leaves
# them open and the slice is NOT split on them.
_AGGREGATE = ("all", "", "none", None)


def complete_slice(doc: dict, claim) -> list[dict]:
    """Every verified side of an under-specified slice, or [].

    The firewall invariant is "an unspecified dimension is never answered by
    a single narrowed row" (a bare "MPCE" must not return the rural figure
    as if it were the whole). This function generalises the answer instead
    of narrowing it: when the claim leaves a dimension open and the store
    carries the COMPLETE set of sides for it, all sides are returned, each
    with its own row id, so the user sees the whole slice.

    Returns [] when the slice is not complete in the store (the caller then
    abstains honestly) or when the claim's geography has no rows at all
    (a state question never falls back to another state or to all-India).
    """
    survey = _norm(getattr(claim, "survey", None))
    indicator = _norm(getattr(claim, "indicator", None))
    if not survey or not indicator:
        return []
    cs = _norm(getattr(claim, "state", None))
    cr = _norm(getattr(claim, "round", None))

    rows = []
    for r in doc.get("rows", []):
        if r.get("verification_status") != "verified":
            continue
        if _norm(r.get("survey")) != survey:
            continue
        if _norm(r.get("indicator")) != indicator:
            continue
        if cr and _norm(r.get("round")) not in ("", None) and _norm(r.get("round")) != cr:
            continue
        # Geography: a state question only ever sees that state; a national
        # question only ever sees national rows.
        rs = _norm(r.get("state"))
        if cs:
            if rs != cs:
                continue
        elif rs not in ("", None, "all", "all-india"):
            continue
        # Dimensions the claim fixed, and dimensions it left open that are
        # not split dimensions, must be the aggregate.
        ok = True
        for dim in ("sex", "age_group", "activity"):
            cv = _norm(getattr(claim, dim, None))
            rv = _norm(r.get(dim))
            if cv:
                if rv != cv:
                    ok = False
                    break
            elif rv not in _AGGREGATE:
                ok = False
                break
        if not ok:
            continue
        rows.append(r)
    if not rows:
        return []

    # Which open dimensions can be completed? A dimension qualifies only if
    # the store carries EVERY side of its domain for this slice.
    split_dims: list[str] = []
    for dim, domain in SLICE_DOMAINS.items():
        cv = _norm(getattr(claim, dim, None))
        if cv:
            continue  # the claim fixed this dimension; no split needed
        vals = {_norm(r.get(dim)) for r in rows}
        if vals == set(domain):
            split_dims.append(dim)
        else:
            # Incomplete slice: showing one side would narrow silently.
            return []
    if not split_dims:
        return []

    final = [
        r
        for r in rows
        if all(_norm(r.get(d)) in SLICE_DOMAINS[d] for d in split_dims)
    ]
    if len(final) < 2:
        return []
    return sorted(
        final,
        key=lambda r: (
            tuple(
                _norm(r.get(d)) for d in sorted(SLICE_DOMAINS)
                if d in split_dims
            ),
            str(r.get("row_id")),
        ),
    )


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
