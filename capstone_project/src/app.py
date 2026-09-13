"""src/app.py — FastAPI web interface for the Rajya Sabha QA system.

Endpoints:
    GET  /health                 — service + index status
    POST /retrieve               — retrieve top-k evidence for a question
    POST /answer                 — full pipeline: retrieve → gate → generate → verify
    GET  /queries/{query_id}     — query metadata
    GET  /docs/{qslno}           — corpus document text + meta

Lazy-loads the index/corpus on first request. LLM answers require NVIDIA_API_KEY;
without it the app falls back to the extractive answerer (no API needed).
"""
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from src.common import load_jsonl, setup_logging, log_json, chunk_text, topk_for_scores, rrf_fuse
from src.retrieval import (load_corpus, load_bm25_index, load_dense_index, load_dense_model,
                           load_rerank_model, rerank_block)
from src.gating import evidence_gate, verify_answer_claims
from src.answer import get_llm_client, build_llm_answer, build_extractive_answer

logger = setup_logging("app")

app = FastAPI(
    title="Rajya Sabha QA",
    version="2.0.0",
    description="Cited, evidence-grounded QA over Rajya Sabha parliamentary records.",
)


# ── Lazy state ──────────────────────────────────────────────────────────────

class Runtime:
    corpus: Dict = None
    bm25 = None            # (vectorizer, doc_vectors, doc_ids)
    dense = None           # (vectors, doc_ids)
    dense_model = None
    rerank_model = None    # cross-encoder, loaded on first rerank request
    queries: Dict = None   # query_id -> query, loaded on first /queries call
    loaded_at: float = 0.0


def ensure_state(refresh: bool = False) -> float:
    """Load corpus + indexes on first call. Returns load time in seconds."""
    if Runtime.corpus is not None and not refresh:
        return Runtime.loaded_at
    t0 = time.time()
    data = Path("data")
    if not (data / "corpus.jsonl").exists():
        raise HTTPException(status_code=503, detail="corpus.jsonl not found — run: python src/build_corpus.py")
    Runtime.corpus = load_corpus(data / "corpus.jsonl")

    index_dir = data / "index"
    Runtime.bm25 = None
    Runtime.dense = None
    Runtime.dense_model = None
    if (index_dir / "tfidf.pkl").exists():
        Runtime.bm25 = load_bm25_index(index_dir)
    if (index_dir / "dense_head.npy").exists():
        Runtime.dense = load_dense_index(index_dir, "head")
        Runtime.dense_model = load_dense_model()
    Runtime.loaded_at = time.time() - t0
    log_json(logger, event="state_loaded", seconds=round(Runtime.loaded_at, 2),
             corpus=len(Runtime.corpus), bm25=bool(Runtime.bm25), dense=bool(Runtime.dense))
    return Runtime.loaded_at


def _to_chunks(doc_ids: List[str], k: int = 8) -> List[Dict]:
    """Build [{text, meta, chunk_idx, doc_id}] for top-k docs from the corpus."""
    chunks = []
    for doc_id in doc_ids[:k]:
        doc = Runtime.corpus.get(doc_id)
        if not doc:
            continue
        for ci, chunk in enumerate(chunk_text(doc.get("text", ""))):
            chunks.append({"text": chunk,
                           "meta": {kk: vv for kk, vv in doc.items() if kk != "text"},
                           "chunk_idx": ci, "doc_id": doc_id})
    return chunks


def _bm25_scores(vectorizer, doc_vectors, question: str, k: int, doc_ids: List[str]) -> List[Dict]:
    query_vec = vectorizer.transform([question])
    scores = (doc_vectors @ query_vec.T).toarray().ravel().astype(np.float32)
    idx = topk_for_scores(scores, k)
    return [{"doc_id": doc_ids[i], "score": float(scores[i]), "rank": r + 1}
            for r, i in enumerate(idx)]


def _dense_scores(dense_vecs, dense_doc_ids, question: str, k: int) -> List[Dict]:
    q_emb = Runtime.dense_model.encode([question], normalize_embeddings=True,
                                       convert_to_numpy=True).astype(np.float32)[0]
    dscores = np.asarray(dense_vecs, dtype=np.float32) @ q_emb
    idx = topk_for_scores(dscores, k)
    return [{"doc_id": dense_doc_ids[i], "score": float(dscores[i]), "rank": r + 1}
            for r, i in enumerate(idx)]


def _retrieve(question: str, k: int = 8, system: str = "auto") -> List[Dict]:
    """Retrieve ranked evidence for a question.

    system: "auto"|"hybrid" (RRF-fuse when both indexes exist, else best available),
            "bm25" | "dense" (force one index; 503 if unavailable),
            "rerank"|"hybrid_rerank" (RRF-fuse then cross-encoder rerank of the top-k).
    """
    ensure_state()
    if system in ("dense",) and not Runtime.dense:
        raise HTTPException(status_code=503, detail="Dense index not built — run: python -m src.retrieval dense --mode head")
    if system in ("bm25", "auto", "hybrid") and not Runtime.bm25:
        if system == "hybrid":
            raise HTTPException(status_code=503, detail="BM25 index not found — run: python -m src.retrieval build")
        if not Runtime.dense:
            raise HTTPException(status_code=503, detail="No index found — build indexes first")
    if system in ("rerank", "hybrid_rerank") and not (Runtime.bm25 and Runtime.dense):
        raise HTTPException(status_code=503,
                            detail="Rerank needs both indexes — run: python -m src.retrieval build && python -m src.retrieval dense --mode head")

    vectorizer, doc_vectors, bm25_doc_ids = Runtime.bm25
    if system == "bm25":
        return _bm25_scores(vectorizer, doc_vectors, question, k, bm25_doc_ids)
    if system == "dense":
        return _dense_scores(*Runtime.dense, question, k)

    dense_vecs, dense_doc_ids = Runtime.dense
    dense_index = {d: i for i, d in enumerate(dense_doc_ids)}
    dense_res = _dense_scores(dense_vecs, dense_doc_ids, question, k)
    bm25_res = _bm25_scores(vectorizer, doc_vectors, question, k, bm25_doc_ids)
    fused = rrf_fuse([[r["doc_id"] for r in bm25_res], [r["doc_id"] for r in dense_res]], k=k)
    if system in ("rerank", "hybrid_rerank"):
        if Runtime.rerank_model is None:
            Runtime.rerank_model = load_rerank_model()
        block = [{"query_id": "user", "title": question}]
        fused_run = {"query_id": "user", "system": "hybrid", "ranked_list": fused}
        reranked = rerank_block(block, {"user": fused_run}, Runtime.corpus, Runtime.rerank_model,
                                top_k=k, batch_size=64)
        return reranked[0]["ranked_list"]
    return [{"doc_id": d, "score": float(dscores[dense_index.get(d, 0)]),
             "rank": i + 1} for i, d in enumerate(fused)]


def _answer(question: str, policy: str = "extractive", tau: float = 0.80,
            model: str = None, use_llm: bool = False, system: str = "auto") -> Dict[str, Any]:
    """Full pipeline: retrieve → gate → generate → verify."""
    ranked = _retrieve(question, k=8, system=system)
    chunks = _to_chunks([r["doc_id"] for r in ranked], k=8)

    gate = evidence_gate(chunks)
    gate_passed = gate["pass"]

    if not gate_passed and policy in ("C", "D"):
        return {"query_id": None, "question": question, "policy": policy,
                "abstained": True, "claims": [], "citations": [],
                "gate_reason": gate["reason"], "evidence": ranked[:3]}

    if use_llm and os.environ.get("NVIDIA_API_KEY"):
        client = get_llm_client()
        cache_path = Path("data/cache/llm_responses.json")
        cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
        answer = build_llm_answer(question, chunks, policy, client,
                                  model or "nvidia/llama-3.1-nemotron-70b-instruct",
                                  cache, cache_path)
    else:
        answer = build_extractive_answer(chunks, question)

    if policy == "D" and answer.get("claims"):
        verification = verify_answer_claims(answer["claims"], answer["citations"], tau)
        answer["verification"] = verification
        if not verification["all_supported"]:
            answer = {"claims": [], "citations": [], "abstained": True,
                      "verification": verification, "gate_reason": "VERIFICATION_FAILED"}

    return {
        "query_id": None, "question": question, "policy": policy,
        "abstained": answer.get("abstained", False),
        "claims": answer.get("claims", []),
        "citations": answer.get("citations", []),
        "gate_reason": gate["reason"],
        "verification": answer.get("verification", {"all_supported": True, "skipped_short_claims": 0}),
        "evidence": ranked[:3],
    }


# ── Schemas ─────────────────────────────────────────────────────────────────

class RetrieveRequest(BaseModel):
    question: str = Field(..., min_length=3)
    k: int = Field(8, ge=1, le=50)
    system: str = Field("auto", pattern="^(auto|hybrid|bm25|dense|hybrid_rerank|rerank)$", description="Which index to search")

class AnswerRequest(BaseModel):
    question: str = Field(..., min_length=3)
    policy: str = Field("extractive", pattern="^(A|B|C|D|extractive)$")
    use_llm: bool = False
    model: Optional[str] = Field(None, description="LLM id (default: nvidia/llama-3.1-nemotron-70b-instruct)")
    tau: float = Field(0.80, ge=0.0, le=1.0)
    system: str = Field("auto", pattern="^(auto|hybrid|bm25|dense|hybrid_rerank|rerank)$", description="Which index to search")


# ── Endpoints ───────────────────────────────────────────────────────────────

@app.get("/health")
def health() -> Dict[str, Any]:
    ensure_state()
    return {"status": "ok", "corpus_docs": len(Runtime.corpus),
            "bm25_ready": bool(Runtime.bm25), "dense_ready": bool(Runtime.dense),
            "load_seconds": round(Runtime.loaded_at, 2)}


@app.post("/retrieve")
def retrieve(req: RetrieveRequest) -> Dict[str, Any]:
    ranked = _retrieve(req.question, k=req.k, system=req.system)
    return {"question": req.question, "k": req.k, "system": req.system,
            "ranked_list": [{"doc_id": r["doc_id"], "score": r["score"], "rank": r["rank"]}
                            for r in ranked]}


@app.post("/answer")
def answer(req: AnswerRequest) -> Dict[str, Any]:
    return _answer(req.question, req.policy, req.tau, model=req.model,
                   use_llm=req.use_llm, system=req.system)


@app.get("/queries/{query_id}")
def get_query(query_id: str) -> Dict[str, Any]:
    if Runtime.queries is None:
        qpath = Path("data/queries.jsonl")
        if not qpath.exists():
            raise HTTPException(status_code=503, detail="queries.jsonl not found — run: python -m src.make_queries")
        Runtime.queries = {q["query_id"]: q for q in load_jsonl(qpath)}
    q = Runtime.queries.get(query_id)
    if q is None:
        raise HTTPException(status_code=404, detail="Query not found")
    return q


@app.get("/docs/{qslno}")
def get_doc(qslno: int) -> Dict[str, Any]:
    ensure_state()
    doc = Runtime.corpus.get(qslno)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.app:app", host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))