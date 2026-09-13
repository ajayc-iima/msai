"""src/retrieval.py — Unified retrieval: BM25, dense, RRF fusion, cross-encoder rerank.

Merged from index_lexical.py + index_dense.py + fusion.py + rerank.py + retrieve.py.
CLI: subcommands `build`, `sweep`, `search`, `fuse`, `rerank`.
"""
import argparse
import json
import os
import pickle
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import List, Dict, Any, Tuple

import numpy as np
from scipy.sparse import save_npz, load_npz, csr_matrix
from sklearn.feature_extraction.text import TfidfVectorizer
from tqdm import tqdm

from src.common import (load_jsonl, write_jsonl, save_npy, load_npy, ensure_dir,
                        setup_logging, log_json, rrf_fuse, configure_cpu_threads,
                        chunk_text, CHUNK_SIZE, CHUNK_OVERLAP, topk_for_scores)


# ── Constants ────────────────────────────────────────────────────────────────

BGE_MODEL = "BAAI/bge-small-en-v1.5"
DENSE_EMB_DIM = 384
BGE_HEAD_TOKENS = 2000
CROSS_ENC_MODEL = "cross-encoder/ms-marco-MiniLM-L6-v2"

BM25_DEFAULT_CONFIG = {
    "sublinear_tf": True,
    "norm": "l2",
    "min_df": 2,
    "max_features": 50000,
    "ngram_range": (1, 2),
    "stop_words": "english",
}


# ── Corpus helpers ───────────────────────────────────────────────────────────

def load_corpus(corpus_path: Path) -> Dict[str, Dict]:
    """Load corpus into {qslno: rec}. Optional filter keeps only retrievable+text."""
    return {r["qslno"]: r for r in load_jsonl(corpus_path)}


def load_corpus_texts(corpus_path: Path, split: str = None) -> Tuple[List[str], List[str]]:
    """Load retrievable texts + doc_ids, optionally filtered by dev/test year window."""
    texts, doc_ids = [], []
    for r in load_jsonl(corpus_path):
        if r["retrievable"] and r.get("text"):
            if split:
                year = int(r["answer_date"][:4]) if r["answer_date"] else 0
                if split == "dev" and not (2011 <= year <= 2018):
                    continue
                if split == "test" and not (2019 <= year <= 2024):
                    continue
            texts.append(r["text"])
            doc_ids.append(r["qslno"])
    return texts, doc_ids


def chunks_for_doc(doc: Dict) -> List[str]:
    """Split a doc's text into overlapping chunks."""
    return chunk_text(doc.get("text", ""), CHUNK_SIZE, CHUNK_OVERLAP)


# ── BM25 (TF-IDF) ────────────────────────────────────────────────────────────

def build_bm25_index(texts: List[str], config: Dict) -> Tuple[TfidfVectorizer, object]:
    vectorizer = TfidfVectorizer(**config)
    doc_vectors = vectorizer.fit_transform(texts)
    return vectorizer, doc_vectors


def _topk_1d(scores: np.ndarray, k: int) -> list:
    """(idx, score) pairs for top-k scores, descending."""
    idx = topk_for_scores(scores, k)
    return [(int(i), float(scores[i])) for i in idx]


def bm25_search(vectorizer, doc_vectors, queries: List[str], k: int = 100,
                batch_size: int = 256, num_threads: int = None) -> List[List[Tuple[int, float]]]:
    """Blocked batched BM25 search over many queries. Returns per-query (idx, score) lists."""
    if not queries:
        return []
    n_threads = int(num_threads or os.cpu_count() or 8)
    query_vecs = csr_matrix(vectorizer.transform(queries))
    scores = (doc_vectors @ query_vecs.T).toarray().astype(np.float32, copy=False)
    k = min(k, scores.shape[0])
    with ThreadPoolExecutor(max_workers=n_threads) as ex:
        futs = [ex.submit(_topk_1d, scores[:, qi], k) for qi in range(scores.shape[1])]
        return [f.result() for f in futs]


def sweep_bm25(texts, doc_ids, queries, k: int = 100) -> Dict:
    """Tune BM25 config on dev queries by Recall@k."""
    configs = [
        {"sublinear_tf": True, "norm": "l2", "min_df": 2, "max_features": 50000, "ngram_range": (1, 1)},
        {"sublinear_tf": True, "norm": "l2", "min_df": 2, "max_features": 50000, "ngram_range": (1, 2)},
        {"sublinear_tf": True, "norm": "l2", "min_df": 5, "max_features": 50000, "ngram_range": (1, 2)},
        {"sublinear_tf": True, "norm": "l2", "min_df": 2, "max_features": 100000, "ngram_range": (1, 2)},
        {"sublinear_tf": False, "norm": "l2", "min_df": 2, "max_features": 50000, "ngram_range": (1, 2)},
        {"sublinear_tf": True, "norm": None, "min_df": 2, "max_features": 50000, "ngram_range": (1, 2)},
    ]
    best_config, best_score = None, -1
    query_texts = [q["title"] for q in queries]
    for config in configs:
        vectorizer, doc_vectors = build_bm25_index(texts, config)
        total = 0
        for s in range(0, len(query_texts), 256):
            block = queries[s:s + 256]
            results = bm25_search(vectorizer, doc_vectors, query_texts[s:s + 256], k)
            for q, res in zip(block, results):
                retrieved = {doc_ids[idx] for idx, _ in res}
                total += int(bool(set(q["gold"]) & retrieved))
        recall = total / len(queries)
        if recall > best_score:
            best_score, best_config = recall, config
        print(f"  config {config}: Recall@{k}={recall:.4f}")
    return best_config


def save_bm25_index(index_dir: Path, vectorizer, doc_vectors, doc_ids, config) -> None:
    ensure_dir(index_dir)
    with open(index_dir / "tfidf.pkl", "wb") as f:
        pickle.dump({"vectorizer": vectorizer, "doc_ids": doc_ids, "config": config}, f)
    save_npz(index_dir / "doc_vectors.npz", doc_vectors)


def load_bm25_index(index_dir: Path):
    with open(index_dir / "tfidf.pkl", "rb") as f:
        data = pickle.load(f)
    return data["vectorizer"], load_npz(index_dir / "doc_vectors.npz"), data["doc_ids"]


# ── Dense (BGE bi-encoder) ───────────────────────────────────────────────────

def load_dense_model(device: str = "cpu"):
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(BGE_MODEL, device=device)


def _encode_batched(texts: List[str], model, batch_size: int,
                    show_progress: bool = False) -> np.ndarray:
    """Single batched encode → float32 matrix."""
    emb = model.encode(texts, batch_size=batch_size, normalize_embeddings=True,
                       show_progress_bar=show_progress, convert_to_numpy=True)
    return np.asarray(emb)


def _dense_block_encode(recs: List[Dict], mode: str, model, batch_size: int,
                        doc_batch: int) -> np.ndarray:
    """Encode one doc-batch → (n_docs, D) float16 matrix (head or max-pooled chunked)."""
    texts = [(r.get("text") or "")[:BGE_HEAD_TOKENS] for r in recs]
    emb = _encode_batched(texts, model, batch_size)
    return emb.astype(np.float16)


def build_dense_index(corpus_path: Path, index_dir: Path, mode: str = "head",
                      limit: int = None, batch_size: int = 256,
                      doc_batch: int = 4096, num_threads: int = None) -> Dict[str, Any]:
    """Build dense index (head-only or chunked-maxpool). Batched all-CPU encode.

    Checkpointed: each doc-batch appends to dense_{mode}.partial.npy +
    dense_{mode}.ckpt.json, so a killed run resumes instead of restarting.
    """
    logger = setup_logging("retrieval")
    ensure_dir(index_dir)
    n_threads = configure_cpu_threads(num_threads)
    model = load_dense_model()

    recs = [r for r in load_jsonl(corpus_path) if r["retrievable"] and r.get("text")]
    if limit:
        recs = recs[:limit]
    doc_ids = [r["qslno"] for r in recs]
    n_docs = len(doc_ids)
    tag = {"mode": mode, "n_docs": n_docs, "limit": limit,
           "first": doc_ids[0] if doc_ids else None,
           "last": doc_ids[-1] if doc_ids else None}
    print(f"Encoding {n_docs} docs mode={mode} threads={n_threads}", flush=True)

    ckpt_path = index_dir / f"dense_{mode}.ckpt.json"
    part_path = index_dir / f"dense_{mode}.partial.npy"
    start = 0
    blocks: List[np.ndarray] = []
    if ckpt_path.exists() and part_path.exists():
        try:
            ck = json.loads(ckpt_path.read_text(encoding="utf-8"))
            if all(ck.get(k) == v for k, v in tag.items()):
                prev = np.load(part_path)
                if prev.shape[0] <= n_docs and prev.shape[0] % doc_batch in (0, prev.shape[0]):
                    # resume only on exact block boundary
                    start = int(prev.shape[0] - (prev.shape[0] % doc_batch)) if prev.shape[0] % doc_batch else int(prev.shape[0])
                    if start == prev.shape[0]:
                        blocks.append(np.asarray(prev, dtype=np.float16))
                        print(f"Resuming {mode}: {start}/{n_docs} docs from checkpoint", flush=True)
                    else:
                        start = 0  # ragged partial: restart cleanly
                else:
                    start = 0
            else:
                print(f"Ignoring stale checkpoint (tag mismatch): {ck.get('n_docs')} docs", flush=True)
        except Exception as e:
            print(f"Ignoring unreadable checkpoint ({e}); starting over", flush=True)
            start = 0
            blocks = []

    t0 = time.time()
    for s in tqdm(range(start, n_docs, doc_batch), desc=f"Encoding ({mode}, batched)"):
        block = recs[s:s + doc_batch]
        if mode == "head":
            vecs = _dense_block_encode(block, mode, model, batch_size, doc_batch)
        else:  # chunked: flatten chunks, encode flat, max-pool to doc
            flat, counts = [], []
            for r in block:
                chs = chunk_text(r.get("text") or "", CHUNK_SIZE, CHUNK_OVERLAP)
                counts.append(len(chs))
                flat.extend(chs)
            if flat:
                emb = np.asarray(model.encode(flat, batch_size=batch_size,
                                              normalize_embeddings=True,
                                              show_progress_bar=False,
                                              convert_to_numpy=True))
                vecs = np.zeros((len(block), emb.shape[1]), dtype=np.float16)
                start_ptr = 0
                for bi, cnt in enumerate(counts):
                    if cnt:
                        vecs[bi] = np.max(emb[start_ptr:start_ptr + cnt].astype(np.float16), axis=0)
                    start_ptr += cnt
            else:
                vecs = np.zeros((len(block), DENSE_EMB_DIM), dtype=np.float16)
        blocks.append(vecs)
        done = min(s + doc_batch, n_docs)
        elapsed = time.time() - t0
        # checkpoint: full prefix to disk every block (≤50MB write; crash-safe resume)
        try:
            np.save(part_path, np.concatenate(blocks, axis=0))
            ckpt_path.write_text(json.dumps({**tag, "done": done}, indent=1), encoding="utf-8")
        except Exception as e:
            print(f"  checkpoint write failed (continuing): {e}", flush=True)
        rate = done / max(elapsed, 1e-6)
        print(f"  [{mode}] {done}/{n_docs} docs, {rate:.1f} docs/s, {elapsed/60:.1f} min elapsed", flush=True)
        log_json(logger, stage="encoding", processed=done, total=n_docs,
                 rate=f"{rate:.0f} seq/s")

    vectors = np.concatenate(blocks, axis=0) if blocks else np.zeros((0, DENSE_EMB_DIM), dtype=np.float16)
    elapsed = time.time() - t0

    fname = "dense_head.npy" if mode == "head" else "dense_chunked.npy"
    save_npy(index_dir / fname, vectors)
    write_jsonl(index_dir / f"dense_{mode}_doc_ids.jsonl", [{"qslno": q} for q in doc_ids])
    write_jsonl(index_dir / "dense_doc_ids.jsonl", [{"qslno": q} for q in doc_ids])
    for p in (part_path, ckpt_path):  # success: drop checkpoints
        try:
            p.unlink(missing_ok=True)
        except Exception:
            pass

    stats = {"mode": mode, "n_docs": len(doc_ids), "dim": DENSE_EMB_DIM,
             "dtype": "float16", "size_mb": round(vectors.nbytes / 1e6, 1),
             "encode_time_sec": round(elapsed, 1),
             "rate_seq_per_sec": round(len(vectors) / max(elapsed, 1e-6), 1),
             "threads": n_threads}
    log_json(logger, **stats)
    return stats


def load_dense_index(index_dir: Path, mode: str = "head"):
    fname = "dense_head.npy" if mode == "head" else "dense_chunked.npy"
    vpath = index_dir / fname
    if not vpath.exists():
        part_path = index_dir / f"dense_{mode}.partial.npy"
        if part_path.exists():
            print(f"Finalizing {mode} index from partial checkpoint...")
            prev = np.load(part_path)
            save_npy(vpath, prev)
            corpus = [r["qslno"] for r in load_jsonl(Path("data/corpus.jsonl")) if r.get("retrievable") and r.get("text")]
            write_jsonl(index_dir / f"dense_{mode}_doc_ids.jsonl", [{"qslno": q} for q in corpus[:len(prev)]])
    vectors = load_npy(vpath)
    id_file = index_dir / f"dense_{mode}_doc_ids.jsonl"
    if not id_file.exists():
        id_file = index_dir / "dense_doc_ids.jsonl"
    doc_ids = [r["qslno"] for r in load_jsonl(id_file)]
    return vectors, doc_ids


def dense_search_batched(queries: List[Dict], model, vectors, doc_ids, k: int = 100,
                         encode_batch_size: int = 256, score_batch: int = 256,
                         num_threads: int = None) -> List[Dict]:
    """Batch-encode queries, blocked GEMM, pooled top-k. Returns run dicts."""
    import hashlib
    n_threads = int(num_threads or os.cpu_count() or 8)
    query_texts = [q["title"] for q in queries]
    h = hashlib.md5("".join(f"{q['query_id']}:{q['title']}" for q in queries).encode("utf-8")).hexdigest()
    cache_path = Path("data/index") / f"q_emb_{h}_{len(queries)}.npy"
    if cache_path.exists():
        q_emb = np.load(cache_path)
    else:
        q_emb = model.encode(query_texts, batch_size=encode_batch_size,
                             normalize_embeddings=True, show_progress_bar=True,
                             convert_to_numpy=True).astype(np.float32)
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            np.save(cache_path, q_emb)
        except Exception:
            pass
    v = np.asarray(vectors, dtype=np.float32)
    k = min(k, len(doc_ids))
    runs: List[Dict] = [None] * len(queries)
    for s in tqdm(range(0, len(queries), score_batch), desc="Dense scoring (blocked)"):
        e = min(s + score_batch, len(queries))
        scores = v @ q_emb[s:e].T
        b = e - s
        with ThreadPoolExecutor(max_workers=n_threads) as ex:
            futs = [ex.submit(topk_for_scores, scores[:, j], k) for j in range(b)]
            for j, fu in enumerate(futs):
                idx = fu.result()
                col = scores[:, j]
                runs[s + j] = {"query_id": queries[s + j]["query_id"], "system": "dense",
                               "ranked_list": [{"doc_id": doc_ids[ii], "score": float(col[ii]), "rank": r + 1}
                                               for r, ii in enumerate(idx)]}
    return runs


# ── Fusion + rerank ──────────────────────────────────────────────────────────

def fuse_runs(run_paths: List[Path], k: int = 100, rrf_k: int = 60) -> List[Dict]:
    """RRF-fuse multiple run files (doc-granularity). System stem = run name."""
    runs_by = {}
    for path in run_paths:
        runs_by[path.stem] = {r["query_id"]: r for r in load_jsonl(path)}
    all_ids = set().union(*(r.keys() for r in runs_by.values()))

    fused_runs = []
    for qid in all_ids:
        ranked_lists = []
        for system, runs in runs_by.items():
            if qid in runs:
                ranked_lists.append([item["doc_id"] for item in runs[qid]["ranked_list"]])
        if not ranked_lists:
            continue
        fused_ids = rrf_fuse(ranked_lists, k=k, rrf_k=rrf_k)

        # Average scores across systems where present
        rank_map = {}
        for system, runs in runs_by.items():
            if qid in runs:
                rank_map[system] = {item["doc_id"]: item["score"] for item in runs[qid]["ranked_list"]}
        results = []
        for i, doc_id in enumerate(fused_ids):
            scores = [rm[doc_id] for rm in rank_map.values() if doc_id in rm]
            results.append({"doc_id": doc_id,
                            "score": sum(scores) / len(scores) if scores else 0.0,
                            "rank": i + 1})
        fused_runs.append({"query_id": qid, "system": "hybrid", "ranked_list": results})
    return fused_runs


def load_rerank_model(device: str = "cpu", max_length: int = 512):
    from sentence_transformers import CrossEncoder
    return CrossEncoder(CROSS_ENC_MODEL, device=device, max_length=max_length)


def rerank_block(queries: List[Dict], fused_by_query: Dict, corpus: Dict,
                 model, top_k: int, batch_size: int) -> List[Dict]:
    """Rerank one block of queries with a single flattened predict call."""
    block_pairs: List[List[str]] = []
    block_owner: List[int] = []
    block_doc: List[str] = []
    per_query_docs: List[List[str]] = []

    for qi, q in enumerate(queries):
        fused = fused_by_query.get(q["query_id"])
        doc_ids = [item["doc_id"] for item in fused["ranked_list"][:top_k]] if fused else []
        per_query_docs.append(doc_ids)
        for d in doc_ids:
            if d in corpus and corpus[d]:
                doc = corpus[d]
                first_chunk = chunk_text(doc.get("text", ""), CHUNK_SIZE, CHUNK_OVERLAP)
                if first_chunk:
                    block_pairs.append([q["title"], first_chunk[0]])
                    block_owner.append(qi)
                    block_doc.append(d)

    all_scores = np.zeros(len(block_pairs), dtype=np.float32)
    if block_pairs:
        all_scores = np.asarray(model.predict(block_pairs, batch_size=batch_size,
                                              show_progress_bar=False), dtype=np.float32)

    per_query: List[List] = [[[], []] for _ in queries]
    for pos, qi in enumerate(block_owner):
        per_query[qi][0].append(block_doc[pos])
        per_query[qi][1].append(float(all_scores[pos]))

    reranked = []
    for qi, q in enumerate(queries):
        docs, sc = per_query[qi]
        if docs:
            order = np.argsort(-np.asarray(sc))
            ranked_list = [{"doc_id": docs[i], "score": sc[i], "rank": r + 1}
                           for r, i in enumerate(order)]
            seen = set(docs)
        else:
            ranked_list, seen = [], set()
        for d in per_query_docs[qi]:
            if d not in seen:
                ranked_list.append({"doc_id": d, "score": 0.0, "rank": len(ranked_list) + 1})
        reranked.append({"query_id": q["query_id"], "system": "hybrid_rerank",
                         "ranked_list": ranked_list})
    return reranked


# ── Unified pipeline ─────────────────────────────────────────────────────────

def retrieve_for_queries(queries: List[Dict], system: str, index_dir: Path,
                         k: int = 100, batch_size: int = 256,
                         search_batch: int = 256, score_batch: int = 256,
                         num_threads: int = None) -> List[Dict]:
    """One-call retrieval for any system: bm25 | dense_head | dense_chunked | hybrid | hybrid_rerank."""
    configure_cpu_threads(num_threads)
    runs = []

    need_bm25 = system in ("bm25", "hybrid", "hybrid_rerank")
    need_dense = system in ("dense_head", "dense_chunked", "hybrid", "hybrid_rerank")

    vectorizer = doc_vectors = bm25_doc_ids = None
    dense_vectors = dense_doc_ids = model = None

    if need_bm25:
        vectorizer, doc_vectors, bm25_doc_ids = load_bm25_index(index_dir)
    if need_dense:
        mode = "chunked" if system == "dense_chunked" else "head"
        dense_vectors, dense_doc_ids = load_dense_index(index_dir, mode)
        model = load_dense_model()

    if system == "bm25":
        for s in range(0, len(queries), search_batch):
            batch = queries[s:s + search_batch]
            results = bm25_search(vectorizer, doc_vectors, [q["title"] for q in batch],
                                  k, search_batch, num_threads)
            for q, res in zip(batch, results):
                runs.append({"query_id": q["query_id"], "system": system,
                             "ranked_list": [{"doc_id": bm25_doc_ids[idx], "score": sc, "rank": r + 1}
                                             for r, (idx, sc) in enumerate(res)]})
    elif system in ("dense_head", "dense_chunked"):
        runs = dense_search_batched(queries, model, dense_vectors, dense_doc_ids, k,
                                    batch_size, score_batch, num_threads)
        for r in runs:
            r["system"] = system
    elif system in ("hybrid", "hybrid_rerank"):
        # BM25 blocked
        bm25_all = []
        for s in range(0, len(queries), search_batch):
            batch = queries[s:s + search_batch]
            bm25_all.extend(bm25_search(vectorizer, doc_vectors,
                                        [q["title"] for q in batch], k, search_batch, num_threads))
        dense_runs = dense_search_batched(queries, model, dense_vectors, dense_doc_ids, k,
                                          batch_size, score_batch, num_threads)
        dense_by_q = {r["query_id"]: r["ranked_list"] for r in dense_runs}
        for q, bres in zip(queries, bm25_all):
            bm25_results = [{"doc_id": bm25_doc_ids[idx], "score": sc, "rank": r + 1}
                            for r, (idx, sc) in enumerate(bres)]
            fused_ids = rrf_fuse([[i["doc_id"] for i in bm25_results],
                                  [i["doc_id"] for i in dense_by_q[q["query_id"]]]], k=k)
            bm25_scores = {i["doc_id"]: i["score"] for i in bm25_results}
            dense_scores = {i["doc_id"]: i["score"] for i in dense_by_q[q["query_id"]]}
            runs.append({"query_id": q["query_id"], "system": system,
                         "ranked_list": [{"doc_id": d, "score": bm25_scores.get(d, 0) + dense_scores.get(d, 0),
                                          "rank": i + 1} for i, d in enumerate(fused_ids)]})
    elif system == "oracle":
        for q in queries:
            gold = list(q.get("gold", []))
            runs.append({"query_id": q["query_id"], "system": "oracle",
                         "ranked_list": [{"doc_id": d, "score": 1.0 - i * 0.001, "rank": i + 1}
                                         for i, d in enumerate(gold[:k])]})
    else:
        raise ValueError(f"Unknown system: {system}")
    return runs


# ── CLI ──────────────────────────────────────────────────────────────────────

def _build(args):
    texts, doc_ids = load_corpus_texts(Path(args.corpus))
    config = args.config
    if config is None:
        config = BM25_DEFAULT_CONFIG
    elif isinstance(config, str):
        s = config.strip()
        if s.lstrip().startswith("{"):
            config = json.loads(s)
        elif Path(s).exists():
            config = json.loads(Path(s).read_text(encoding="utf-8"))
            # saved sweep configs store ngram_range as list; TfidfVectorizer needs tuple
            if isinstance(config.get("ngram_range"), list):
                config["ngram_range"] = tuple(config["ngram_range"])
        else:
            config = BM25_DEFAULT_CONFIG
    vectorizer, doc_vectors = build_bm25_index(texts, config)
    save_bm25_index(Path(args.index_dir), vectorizer, doc_vectors, doc_ids, config)
    print(f"BM25 index: {len(doc_ids)} docs, {doc_vectors.shape[1]} features")


def _sweep(args):
    # Fit on FULL corpus (deployment index holds everything 1995-2024);
    # dev queries only SCORE configs. A dev-only index would make out-of-split
    # gold unretrievable and bias the tuning (see PLAN §4 out-of-split fix).
    dev_queries = [q for q in load_jsonl(Path(args.queries)) if q["split"] == "dev"]
    texts, doc_ids = load_corpus_texts(Path(args.corpus))
    best = sweep_bm25(texts, doc_ids, dev_queries, args.k)
    out_file = Path(getattr(args, "out", None) or args.config)
    ensure_dir(out_file.parent)
    out_file.write_text(json.dumps(best, indent=1))
    print(f"Best config -> {out_file}: {best}")


def _search(args):
    queries = load_jsonl(Path(args.queries))
    if args.split != "all":
        queries = [q for q in queries if q["split"] == args.split]
    runs = retrieve_for_queries(queries, args.system, Path(args.index_dir), args.k,
                                args.batch_size, args.search_batch, args.score_batch,
                                args.threads)
    out = Path(args.out) / f"{args.system}.jsonl"
    ensure_dir(out.parent)
    write_jsonl(out, runs)
    print(f"Wrote {len(runs)} runs -> {out}")


def _fuse(args):
    fused = fuse_runs([Path(p) for p in args.runs if Path(p).exists()], args.k, args.rrf_k)
    ensure_dir(Path(args.out).parent)
    write_jsonl(Path(args.out), fused)
    print(f"Fused {len(fused)} queries -> {args.out}")


def _rerank(args):
    from src.common import log_json
    logger = setup_logging("retrieval")
    ensure_dir(Path(args.out).parent)
    model = load_rerank_model(device="cpu")
    corpus = load_corpus(Path(args.corpus))
    fused_by = {r["query_id"]: r for r in load_jsonl(Path(args.fused))}
    queries = load_jsonl(Path(args.queries))
    if args.split != "all":
        queries = [q for q in queries if q["split"] == args.split]
    limit = args.limit or 2000
    queries_to_rerank = queries[:limit]

    reranked = []
    t0 = time.time()
    for s in tqdm(range(0, len(queries_to_rerank), args.query_block), desc="Reranking"):
        block = [q for q in queries_to_rerank[s:s + args.query_block] if q["query_id"] in fused_by]
        if block:
            reranked.extend(rerank_block(block, fused_by, corpus, model, args.top_k, args.batch_size))
    # Fill remaining queries from fused hybrid so all queries are present
    reranked_ids = {r["query_id"] for r in reranked}
    for q in queries:
        qid = q["query_id"]
        if qid not in reranked_ids and qid in fused_by:
            reranked.append({"query_id": qid, "system": "hybrid_rerank",
                             "ranked_list": fused_by[qid]["ranked_list"]})
    elapsed = time.time() - t0
    write_jsonl(Path(args.out), reranked)
    log_json(logger, n_queries=len(reranked), seconds=round(elapsed, 1),
             sec_per_query=round(elapsed / max(len(queries_to_rerank), 1), 4))
    print(f"Reranked {len(queries_to_rerank)} queries (total output {len(reranked)}) in {elapsed:.1f}s -> {args.out}")


def _dense(args):
    do_build = not getattr(args, "no_build", False)
    if do_build and args.mode in ("head", "both"):
        stats = build_dense_index(Path(args.corpus), Path(args.index_dir), "head",
                                  args.limit, args.batch_size, args.doc_batch, args.threads)
        print(f"Head index: {stats}")
    if do_build and args.mode in ("chunked", "both"):
        stats = build_dense_index(Path(args.corpus), Path(args.index_dir), "chunked",
                                  args.limit, args.batch_size, args.doc_batch, args.threads)
        print(f"Chunked index: {stats}")
    if args.search:
        mode = "chunked" if args.mode == "chunked" else "head"
        vectors, doc_ids = load_dense_index(Path(args.index_dir), mode)
        model = load_dense_model()
        queries = load_jsonl(Path(args.queries))
        if args.split != "all":
            queries = [q for q in queries if q["split"] == args.split]
        system = args.system or f"dense_{mode}"
        runs = dense_search_batched(queries, model, vectors, doc_ids, args.k,
                                    args.batch_size, args.score_batch, args.threads)
        for r in runs:
            r["system"] = system
        out = Path(args.out) / f"{system}.jsonl"
        write_jsonl(out, runs)
        print(f"Ranked -> {out}")


def main():
    ap = argparse.ArgumentParser(description="Unified retrieval: BM25 / dense / hybrid / rerank")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("build", help="Build BM25 index")
    p.add_argument("--corpus", default="data/corpus.jsonl")
    p.add_argument("--index-dir", default="data/index")
    p.add_argument("--config", default=None, help="JSON config string or path")
    p.set_defaults(func=_build)

    p = sub.add_parser("sweep", help="Tune BM25 on dev")
    p.add_argument("--corpus", default="data/corpus.jsonl")
    p.add_argument("--queries", default="data/queries.jsonl")
    p.add_argument("--config", default="data/index/bm25_config.json")
    p.add_argument("--out", default=None, help="Output config path (alias for --config)")
    p.add_argument("--k", type=int, default=100)
    p.set_defaults(func=_sweep)

    p = sub.add_parser("dense", help="Build dense index (+ search with --search)")
    p.add_argument("--corpus", default="data/corpus.jsonl")
    p.add_argument("--index-dir", default="data/index")
    p.add_argument("--mode", choices=["head", "chunked", "both"], default="head")
    p.add_argument("--limit", type=int)
    p.add_argument("--batch-size", type=int, default=256)
    p.add_argument("--doc-batch", type=int, default=4096)
    p.add_argument("--search", action="store_true")
    p.add_argument("--queries", default="data/queries.jsonl")
    p.add_argument("--k", type=int, default=100)
    p.add_argument("--score-batch", type=int, default=256)
    p.add_argument("--split", choices=["dev", "test", "all"], default="test")
    p.add_argument("--out", default="data/runs/")
    p.add_argument("--system", default=None)
    p.add_argument("--threads", type=int)
    p.add_argument("--no-build", action="store_true",
                   help="Skip index build (use with --search on an existing index)")
    p.set_defaults(func=_dense)

    p = sub.add_parser("search", help="Retrieve with any system")
    p.add_argument("--queries", default="data/queries.jsonl")
    p.add_argument("--index-dir", default="data/index")
    p.add_argument("--system", required=True,
                   choices=["bm25", "dense_head", "dense_chunked", "hybrid", "hybrid_rerank", "oracle"])
    p.add_argument("--k", type=int, default=100)
    p.add_argument("--split", choices=["dev", "test", "all"], default="test")
    p.add_argument("--out", default="data/runs/")
    p.add_argument("--batch-size", type=int, default=256)
    p.add_argument("--search-batch", type=int, default=256)
    p.add_argument("--score-batch", type=int, default=256)
    p.add_argument("--threads", type=int)
    p.set_defaults(func=_search)

    p = sub.add_parser("fuse", help="RRF-fuse run files")
    p.add_argument("--runs", nargs="+", required=True)
    p.add_argument("--k", type=int, default=100)
    p.add_argument("--rrf-k", type=int, default=60)
    p.add_argument("--out", default="data/runs/hybrid.jsonl")
    p.set_defaults(func=_fuse)

    p = sub.add_parser("rerank", help="Cross-encoder rerank")
    p.add_argument("--fused", default="data/runs/hybrid.jsonl")
    p.add_argument("--queries", default="data/queries.jsonl")
    p.add_argument("--corpus", default="data/corpus.jsonl")
    p.add_argument("--top-k", type=int, default=20)
    p.add_argument("--batch-size", type=int, default=256)
    p.add_argument("--query-block", type=int, default=500)
    p.add_argument("--split", choices=["dev", "test", "all"], default="test")
    p.add_argument("--limit", type=int)
    p.add_argument("--out", default="data/runs/hybrid_rerank.jsonl")
    p.add_argument("--threads", type=int)
    p.set_defaults(func=_rerank)

    a = ap.parse_args()
    a.func(a)


if __name__ == "__main__":
    main()