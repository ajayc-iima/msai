# ruff: noqa: BLE001, S110 - intentional guarded fallbacks (offline/API-degraded paths)
"""vidhi2 answer plane: post-freeze retrieval + user-focused rendering.

Retrieved text is UNTRUSTED: it may inform wording and citations but can
never change the frozen verdict. The Response is what the user needs --
figure, exact source, caveats, and honest coverage -- in one object with
concise-text and JSON views. WARN/REFUSE wording stays templated.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


@dataclass
class Response:
    decision: str
    sub_code: str
    reason_code: str
    headline: str
    figure: dict | None = None
    evidence_tier: str = "NONE"  # VERIFIED | SOURCED | NONE
    caveats: list[str] = field(default_factory=list)
    citations: list[dict] = field(default_factory=list)
    coverage: dict | None = None
    frozen_hash: str = ""
    attestation: str = ""
    rule_version: str = ""
    trace_id: str = ""
    latency_ms: float = 0.0

    def text(self) -> str:
        return self.headline

    def to_dict(self) -> dict:
        val = self.figure.get("value") if isinstance(self.figure, dict) else None
        unit = self.figure.get("unit") if isinstance(self.figure, dict) else None
        return {
            "decision": self.decision,
            "sub_code": self.sub_code,
            "reason_code": self.reason_code,
            "answer": self.headline,
            "figure": self.figure,
            "value": val,
            "unit": unit,
            "evidence_tier": self.evidence_tier,
            "caveats": self.caveats,
            "citations": self.citations,
            "coverage": self.coverage,
            "verdict_frozen_hash": self.frozen_hash,
            "verdict_attestation": self.attestation,
            "rule_version": self.rule_version,
            "trace_id": self.trace_id,
            "latency_ms": self.latency_ms,
        }


def _excerpt_meta(p: Path) -> dict:
    raw = p.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", raw, re.DOTALL)
    meta: dict = {}
    if m:
        import yaml

        meta = yaml.safe_load(m.group(1)) or {}
        meta["_body"] = m.group(2).strip()
    else:
        meta["_body"] = raw.strip()
    return meta


def _get_model():
    if not hasattr(_get_model, "m"):
        try:
            import os

            # Offline-first: never touch the HF Hub on the query path. Use the
            # cached embedding model if present, else degrade to keyword-only
            # retrieval (behavior never gets worse). This keeps the "no network"
            # demo promise and removes the unauthenticated-HF-request warning.
            if os.getenv("AIP_OFFLINE", "0").strip().lower() in {"1", "true"}:
                os.environ.setdefault("HF_HUB_OFFLINE", "1")
                os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
            from sentence_transformers import SentenceTransformer

            _get_model.m = SentenceTransformer("BAAI/bge-small-en-v1.5")
        except Exception:
            _get_model.m = None
    return _get_model.m


_EXC_VECS: dict[str, object] = {}
_EXC_MODEL: str | None = None


def _exc_vecs(model, docs: list[tuple[str, str]]):
    """Precomputed excerpt vectors (index-time encoding). Keyed by doc_id;
    rebuilt only if the corpus changes."""
    global _EXC_MODEL
    key = getattr(model, "_vidhi2_id", None) or str(id(model))
    ids = [d for d, _ in docs]
    if _EXC_MODEL != key or set(_EXC_VECS) != set(ids):
        import numpy as np

        vecs = model.encode(
            [t[:600] for _, t in docs],
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        _EXC_VECS.clear()
        _EXC_VECS.update({d: np.asarray(v, dtype="float32") for d, v in zip(ids, vecs)})
        _EXC_MODEL = key
    return _EXC_VECS


_CORPUS: dict | None = None


def _corpus() -> dict | None:
    """Full-PDF corpus (Lab 3 stack): BM25 + precomputed dense matrix.
    Built once by scripts/vidhi2_index.py; absent -> excerpts only."""
    global _CORPUS
    if _CORPUS is not None:
        return _CORPUS
    idx = ROOT / "vidhi" / "index"
    if not (idx / "vectors.npy").exists():
        _CORPUS = {}
        return _CORPUS
    import json as _json

    import numpy as _np

    from aip.chunking import Chunk

    chunks = []
    with (idx / "chunks.jsonl").open(encoding="utf-8") as f:
        for line in f:
            d = _json.loads(line)
            chunks.append(Chunk(d["text"], d["pdf"], d["doc_id"], {}))
    try:
        from aip.retrieval import Bm25Retriever

        bm25 = Bm25Retriever(chunks)
    except Exception:
        bm25 = None
    _CORPUS = {"chunks": chunks, "bm25": bm25, "matrix": _np.load(idx / "vectors.npy")}
    return _CORPUS


def _corpus_hits(query: str, k: int) -> list[dict]:
    """RRF fusion of BM25 + dense over the full-PDF index (Lab 3 hybrid)."""
    corp = _corpus()
    if not corp or not corp.get("chunks"):
        return []
    model = _get_model()
    dense_rank: dict[str, int] = {}
    if model is not None:
        try:
            import numpy as _np

            q = model.encode(query, normalize_embeddings=True)
            scores = corp["matrix"] @ _np.asarray(q, dtype="float32")
            for rank, i in enumerate(_np.argsort(-scores)[: max(k * 4, 20)]):
                dense_rank[corp["chunks"][int(i)].chunk_id] = rank
        except Exception:
            pass
    bm25_rank: dict[str, int] = {}
    if corp.get("bm25") is not None:
        try:
            for h in corp["bm25"].search(query, k=max(k * 4, 20)):
                bm25_rank.setdefault(h.chunk.chunk_id, h.rank)
        except Exception:
            pass
    fused: dict[str, float] = {}
    best: dict[str, dict] = {}
    for rank_map in (bm25_rank, dense_rank):
        for cid, rank in rank_map.items():
            fused[cid] = fused.get(cid, 0.0) + 1.0 / (60 + rank + 1)
    by_id = {c.chunk_id: c for c in corp["chunks"]}
    for cid in fused:
        c = by_id[cid]
        best[cid] = {"doc_id": cid, "text": c.text[:1200], "pdf": c.doc_id}
    ordered = sorted(fused.items(), key=lambda kv: -kv[1])[:k]
    return [best[cid] for cid, _ in ordered]


def retrieve(claim, verdict, top_k: int = 3) -> list[dict]:
    """Post-verdict evidence lookup. Untrusted by construction.

    Curated excerpts first (stable, citable evidence); full-corpus hybrid
    hits (Lab 3 BM25+dense RRF over all lab PDFs) fill remaining depth."""
    if verdict.decision == "REFUSE":
        return []
    exc = ROOT / "data" / "excerpts"
    scored: list[tuple[int, dict]] = []
    for p in sorted(exc.glob("*.md")):
        if p.name == "README.md" or "ADVERSARIAL" in p.name:
            continue
        meta = _excerpt_meta(p)
        body = meta.get("_body", "")
        hit = {"doc_id": meta.get("excerpt_id", p.stem), "text": body[:1200]}
        score = 0
        for tok in (claim.indicator or "", claim.survey or ""):
            if tok and tok.lower().replace("_", " ") in body.lower():
                score += 2
        if meta.get("survey") == claim.survey:
            score += 3
        if score > 0 or claim.claim_type == "definitional":
            scored.append((score, hit))
    # Bi-encoder rerank (big-tech retrieval 101): cosine between the claim
    # and excerpts blends with the keyword score. Embeddings unavailable
    # (offline CI) -> keyword order stands; behavior never gets worse.
    model = _get_model()
    if model is not None and scored:
        try:
            import numpy as np

            q = model.encode(claim.canonical_text(), normalize_embeddings=True)
            vecs = _exc_vecs(model, [(h["doc_id"], h["text"]) for _, h in scored])
            kws = [s for s, _ in scored]
            klo, khi = min(kws), max(kws)
            ranked = []
            for kw, h in scored:
                vec = vecs.get(h["doc_id"])
                if vec is None:
                    continue
                cos = float(np.dot(q, np.asarray(vec, dtype="float32")))
                kwn = (kw - klo) / (khi - klo) if khi > klo else 1.0
                ranked.append((0.7 * cos + 0.3 * kwn, h))
            ranked.sort(key=lambda t: -t[0])
            scored = ranked
        except Exception:
            scored.sort(key=lambda t: -t[0])
    else:
        scored.sort(key=lambda t: -t[0])
    out = [{"index": i, **h} for i, (_, h) in enumerate(scored[:top_k], start=1)]
    if len(out) < top_k and verdict.decision != "REFUSE":
        # Corpus depth: hybrid hits excluding anything already cited.
        seen = {h["doc_id"] for h in out}
        query = (
            (claim.raw_question or "")
            + " "
            + " ".join(
                str(x) for x in (claim.indicator, claim.survey, claim.measure) if x
            )
        )
        for h in _corpus_hits(query, top_k * 2):
            if h["doc_id"] not in seen:
                h["index"] = len(out) + 1
                out.append(h)
                seen.add(h["doc_id"])
            if len(out) >= top_k:
                break
    return out


def _fmt(v) -> str:
    try:
        f = float(v)
        return str(int(f)) if f.is_integer() else str(f)
    except (TypeError, ValueError):
        return str(v)


def _sibling_note(claim) -> str | None:
    """List every verified slice of a state question whose dimensions are open.

    "rural MPCE in Bihar" (no basis) and "MPCE in Bihar" (no sector, no
    basis) are answered with the primary figure *plus* the full set of
    published cells, each with its source row id, so a single number never
    stands in for the whole slice. A question naming several states gets
    one table covering all of them.
    """
    from vidhi import store as _S

    try:
        _doc = _S.load(ROOT / "vidhi" / "store.json")
    except Exception:
        return None

    def _rows_for(state: str | None) -> list[dict]:
        return [
            r
            for r in _doc.get("rows", [])
            if r.get("verification_status") == "verified"
            and r.get("survey") == claim.survey
            and r.get("indicator") == claim.indicator
            and r.get("round") == claim.round
            and (r.get("state") or "").lower() == (state or "").lower()
        ]

    states = list(getattr(claim, "states", None) or [])
    if not states and getattr(claim, "state", None):
        states = [claim.state]

    if not states:
        # No state named: say what the store covers, so the user knows the
        # state question is answerable.
        any_state = [
            r
            for r in _doc.get("rows", [])
            if r.get("verification_status") == "verified"
            and r.get("survey") == claim.survey
            and r.get("indicator") == claim.indicator
            and r.get("round") == claim.round
            and r.get("state")
        ]
        covered = sorted({r.get("state") for r in any_state})
        if covered:
            return (
                f"State-wise figures are curated for all {len(covered)} "
                f"states/UTs in this table — ask e.g. "
                f"“{claim.indicator} in {covered[0]}” for a state's numbers."
            )
        return None

    if getattr(claim, "residence", None) and getattr(claim, "measure", None):
        return None  # the question fixed both dimensions: nothing to add

    parts: list[str] = []
    for st in states:
        sibs = _rows_for(st)
        if len(sibs) < 2:
            return None
        for r in sorted(
            sibs,
            key=lambda x: (x.get("residence") or "", x.get("measure") or ""),
        ):
            parts.append(
                f"{st} {r.get('residence')} {r.get('value')} "
                f"({r.get('measure')}, row {r.get('row_id')})"
            )
    if len(parts) < 2:
        return None
    return "All verified slices: " + "; ".join(parts) + "."


def validate(headline: str, hits: list[dict]) -> tuple[bool, list[int]]:
    cited = sorted({int(m) for m in re.findall(r"\[(\d+)\]", headline)})
    bad = [c for c in cited if c < 1 or c > len(hits)]
    return (not bad and bool(cited)), bad


validate_citations = validate


def polish_pass(
    template: str, must_contain: list[str], hits: list[dict], _chat=None
) -> str:
    """Optional LLM polish for PASS prose only. Keeps figures and citation tags identical."""
    try:
        if _chat is not None:
            out = _chat(
                "Rephrase in one or two sentences. Keep every number and every "
                "[n] tag character-identical. Output ONLY the rephrased text.\n\n"
                + template
            ).strip()
        else:
            return template
    except Exception:
        return template
    if not all(tok in out for tok in must_contain):
        return template
    ok, _ = validate(out, hits)
    return out if ok else template


def render(claim, verdict, hits: list[dict], sourced: dict | None = None) -> Response:
    from vidhi import store as S

    cites = " ".join(f"[{h['index']}]" for h in hits[:3])
    base = {
        "decision": verdict.decision,
        "sub_code": verdict.sub_code,
        "reason_code": verdict.reason_code,
        "frozen_hash": verdict.frozen_hash,
        "attestation": getattr(verdict, "attestation", ""),
        "rule_version": verdict.rule_version,
    }
    if verdict.decision == "REFUSE":
        return Response(
            headline=f"I can't answer that. [{verdict.reason_code}] {verdict.message}",
            **base,
        )
    if verdict.decision == "WARN":
        if verdict.value is not None:
            return Response(
                headline=f"Caution — {verdict.message} Official figure: "
                f"{_fmt(verdict.value)} {verdict.unit or ''} "
                f"(row {verdict.row_id}). {cites}".strip(),
                figure={
                    "value": verdict.value,
                    "unit": verdict.unit,
                    "row_id": verdict.row_id,
                    "source": claim.survey,
                    "round": claim.round,
                },
                evidence_tier="VERIFIED",
                caveats=[verdict.message],
                citations=hits,
                **base,
            )
        cov, caveats = None, [verdict.message]
        tier, fig = "NONE", None
        if verdict.reason_code == "R_NO_CURATED_ROW":
            doc = S.load(ROOT / "vidhi" / "store.json")
            info = S.coverage(doc, claim)
            cov = {"verified_rows": info["n"], "slices": info["slices"][:8]}
            req = f"{claim.residence or 'all'} × {claim.sex or 'all'}" + (
                f" × {claim.state}" if claim.state else ""
            )
            if sourced is not None:
                # SOURCED tier (online only): verdict stays WARN; figure comes
                # from the live API, NOT from the excerpt hits. Hits are
                # supporting context only. Reviewer rule: never show the
                # "sourced, not certified" sentence without value+origin+params.
                tier = "SOURCED"
                fig = {
                    "value": sourced["value"],
                    "unit": sourced["unit"],
                    "origin": sourced["origin"],
                    "indicator": sourced.get("indicator"),
                    "round": sourced.get("round"),
                    "params": sourced.get("params"),
                }
                head = (
                    f"{claim.indicator} ({req}, {claim.round}): "
                    f"{_fmt(sourced['value'])} {sourced['unit'] or ''}, "
                    f"sourced live from {sourced['origin']} "
                    f"(indicator {sourced.get('indicator')}, round {sourced.get('round')}). "
                    f"{sourced['note']} Verdict stays WARN ({verdict.reason_code}); "
                    f"API params {sourced.get('params')}. "
                    f"Excerpts {cites} are context only, not evidence for this figure.".strip()
                )
                caveats.append(
                    f"Not yet in the verified store ({info['n']} verified "
                    f"{claim.indicator} rows for {claim.survey}); "
                    f"treat as sourced, not certified. Verdict stays WARN. {cites}".strip()
                )
                return Response(
                    headline=head,
                    figure=fig,
                    evidence_tier=tier,
                    caveats=caveats,
                    citations=hits,
                    coverage=cov,
                    **base,
                )
            # Coverage-only (offline or live unavailable): no figure, no
            # sourced sentence. Lead with the NOT-answer guard; label hits
            # as context only so [1][2] can't read as endorsement.
            note = (
                f"No verified figure for requested slice [{req}] "
                f"({claim.survey}, {claim.indicator}, {claim.round}) — "
                f"no figure endorsed for it. "
                f"Coverage: {info['n']} verified {claim.indicator} "
                f"row(s) for {claim.survey}."
            )
            if info["closest"] is not None:
                b = info["closest"]
                note += (
                    f" Closest verified context (NOT the requested "
                    f"figure, do not cite as the answer): {b.get('residence')}/{b.get('sex')} = "
                    f"{_fmt(b['value'])} {b.get('unit') or ''} "
                    f"(row {b.get('row_id')})."
                )
            note += f" Sources {cites} are context only, not evidence for a figure."
            return Response(
                headline=f"Caution — {note}".strip(),
                caveats=[note],
                citations=hits,
                coverage=cov,
                **base,
            )
        return Response(
            headline=f"Caution — {' '.join(caveats)} {cites}".strip(),
            caveats=caveats,
            citations=hits,
            coverage=cov,
            **base,
        )
    if verdict.sub_code == "PASS_METHODOLOGY_ONLY" and hits:
        return Response(
            headline=f"Per the official notes [{hits[0]['index']}]: "
            f"{hits[0]['text'][:400]}",
            citations=hits,
            **base,
        )
    # Every verified slice of a state question, listed with its own row id,
    # whenever the question left a dimension open (rural/urban, imputation
    # basis). The primary figure never stands in for the whole slice.
    table_note = _sibling_note(claim)
    # Lab6-beats-eSankhyiki: split claims carry figs in message but value=None.
    # Render the frozen message (verdict unchanged, presentation only).
    if verdict.value is None and "Official figures" in (verdict.message or ""):
        head = f"{claim.indicator} ({claim.round}): {verdict.message} {cites}".strip()
        if table_note:
            head = f"{head} {table_note}"
        return Response(
            headline=head,
            figure={"value": None, "unit": verdict.unit, "row_id": verdict.row_id,
                    "note": verdict.message},
            evidence_tier="VERIFIED",
            citations=hits,
            **base,
        )
    # Underspecified state query (e.g. "mpce for bihar", no residence/measure):
    # eSankhyiki shows 4 rows (rural/urban x with/without). Match it with a
    # frozen-verdict table: primary figure stays the looked-up row (contract),
    # siblings listed with row_ids. No verdict change, no architecture change.
    head = (f"{claim.indicator}: {_fmt(verdict.value)} "
            f"{verdict.unit or ''} [{claim.survey}, {claim.round}]. "
            f"Row {verdict.row_id}. {cites}".strip())
    if table_note:
        head = f"{head} {table_note}"
    return Response(
        headline=head,
        figure={
            "value": verdict.value,
            "unit": verdict.unit,
            "row_id": verdict.row_id,
            "source": claim.survey,
            "round": claim.round,
        },
        evidence_tier="VERIFIED",
        citations=hits,
        **base,
    )
