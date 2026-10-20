# ruff: noqa: BLE001 - intentional guarded fallbacks (offline/API-degraded paths)
"""vidhi2 pipeline: question -> trace -> exact cache -> translate ->
firewall (frozen) -> retrieve (untrusted) -> consistency -> render."""

from __future__ import annotations

import sys
import threading
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from aip import cost, tracing
from vidhi import answer as A
from vidhi import consistency as C
from vidhi import rules as R
from vidhi import store as S
from vidhi.claims import compatible, translate

_DOC = None
_FW: R.Firewall | None = None
_EXACT: dict[str, dict] = {}
_SEEN: list[tuple[dict, dict]] = []  # (canonical claim, cache payload)
_LOCK = threading.Lock()
THRESHOLD = 0.97  # cosine gate; the field-guard carries safety, not this


def _doc() -> dict:
    global _DOC
    if _DOC is None:
        _DOC = S.load(ROOT / "vidhi" / "store.json")
    return _DOC


def firewall() -> R.Firewall:
    global _FW
    if _FW is None:
        _FW = R.Firewall(_doc())
    return _FW


def _embed(text: str):
    try:
        import numpy as np

        from aip.embed import embed

        return np.asarray(embed(text, input_type="query"), dtype="float32")
    except Exception:
        return None


def json_text(canon: dict) -> str:
    import json

    return json.dumps(canon, sort_keys=True)


def _live_source(claim, verdict) -> dict | None:
    """SOURCED tier: for descriptive claims the frozen store doesn't cover,
    ask MoSPI's own live API. Returns labeled evidence (never a verdict);
    the WARN stands, but the user gets an answer with provenance."""
    import os

    if os.getenv("AIP_OFFLINE", "0").strip().lower() in {"1", "true"}:
        return None
    # The adapter only serves PLFS LFPR/WPR/UR; skip everything else quietly
    # instead of making an API call that is guaranteed to fail.
    if (claim.survey or "") not in ("PLFS_2023_24", "PLFS_2025"):
        return None
    if claim.indicator not in ("LFPR", "WPR", "UR"):
        return None
    try:
        import contextlib
        import io

        from vidhi.sources import esankhyiki as E

        with contextlib.redirect_stdout(io.StringIO()):
            rows = E.fetch_claim(claim)
    except Exception as exc:
        print(f"vidhi live-source unavailable: {exc}")
        return None
    for r in rows:
        if (
            r.get("measure") != (claim.measure or "usual_status_ps_ss")
            and claim.measure is not None
        ):
            continue
        return {
            "tier": "SOURCED",
            "value": r["value"],
            "unit": r["unit"],
            "origin": "MoSPI eSankhyiki live API",
            "indicator": r["indicator"],
            "round": r["round"],
            "params": r["provenance"].get("params"),
            "note": (
                "Sourced live from MoSPI's API with the exact "
                "requested dimensions; not yet frozen into the "
                "verified store. Treat as sourced, not certified."
            ),
        }
    return None


def _semantic_guard(canon: dict):
    """Shadow field-guarded semantic probe: cosine proposes, fields dispose.

    This is measurement only. A compatible near-duplicate is reported in
    ``cache_info`` but the verdict is always recomputed; semantic reuse is
    never served. That keeps the freeze-before-retrieval guarantee strict
    even if an embedder maps two different claims close together.
    """
    v = _embed(json_text(canon))
    if v is None or not _SEEN:
        return {"hit": False}
    scored = []
    for cc, payload, w in _SEEN:
        if w is not None and w.shape == v.shape and compatible(canon, cc):
            scored.append((float(v @ w), payload))
    if not scored:
        return {"hit": False, "note": "rejected by field-guard"}
    sim, payload = max(scored, key=lambda t: t[0])
    if sim >= THRESHOLD:
        return {"hit": True, "similarity": round(sim, 4), **payload}
    return {"hit": False, "best": round(sim, 4)}


def ask(question: str, top_k: int = 3) -> dict:
    t0 = time.perf_counter()
    trace_id = uuid.uuid4().hex[:12]
    norm = " ".join(question.lower().split())
    key = "vidhi:" + norm
    try:
        from aip.guards import redact_pii

        _q_log, _ = redact_pii(question[:120])
    except Exception:
        _q_log = question[:120]
    with tracing.trace("vidhi.ask", trace_id=trace_id, question=_q_log):
        with _LOCK:
            hit = _EXACT.get(key)
        if hit is not None:
            out = dict(hit)
            out.update(
                {
                    "cached": True,
                    "trace_id": trace_id,
                    "latency_ms": round((time.perf_counter() - t0) * 1000, 1),
                    "cost_usd": round(cost.global_budget().spent_usd, 6),
                }
            )
            # The stored payload came from a miss; this replay *is* an exact hit.
            out["cache_info"] = {**out.get("cache_info", {}), "exact": True}
            return out
        claim = translate(question)
        guard = _semantic_guard(claim.canonical())
        verdict = firewall().adjudicate(claim)
        hits = A.retrieve(claim, verdict, top_k=top_k)
        down = C.check(claim, verdict, hits)
        if down is not None:
            verdict = down
            hits = A.retrieve(claim, verdict, top_k=top_k)
        # F1: bind the displayed figure to the frozen verdict + source cell.
        verdict.attest(S.find_row(_doc(), verdict.row_id))
        sourced = None
        if verdict.sub_code == "WARN_NO_DATA" and claim.claim_type == "descriptive":
            sourced = _live_source(claim, verdict)
        resp = A.render(claim, verdict, hits, sourced=sourced)
        ok, bad = A.validate(resp.headline, hits)
        # A REFUSE has no evidence by design; a WARN with zero hits abstains
        # without making a claim. Both are valid. A WARN that *does* cite still
        # has its citation indices validated.
        if verdict.decision == "REFUSE" or not hits:
            ok = True
        resp.trace_id, resp.latency_ms = (
            trace_id,
            round((time.perf_counter() - t0) * 1000, 1),
        )
        out = resp.to_dict()
        out.update(
            {
                "claim": claim.model_dump(),
                "sources": [h["doc_id"] for h in hits],
                "citations_valid": ok,
                "invalid_citations": bad,
                "value": verdict.value,
                "unit": verdict.unit,
                "verdict_attestation": verdict.attestation,
                "cache_info": {"exact": False, "semantic": guard},
                "cost_usd": round(cost.global_budget().spent_usd, 6),
                "cached": False,
            }
        )
        with _LOCK:
            _EXACT[key] = {
                k: v
                for k, v in out.items()
                if k not in ("trace_id", "latency_ms", "cached")
            }
            _SEEN.append(
                (
                    claim.canonical(),
                    {"decision": verdict.decision},
                    _embed(json_text(claim.canonical())),
                )
            )
    return out
