"""src/common.py — Shared utilities: IO, hashing, text, threading, math, logging."""
import hashlib
import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

import numpy as np


# ── File IO ──────────────────────────────────────────────────────────────────

def load_dotenv(path: str = ".env", override: bool = False) -> int:
    """Best-effort load of KEY=value lines into os.environ.

    Uses python-dotenv if available, else a minimal stdlib parser. Existing
    environment variables win unless override=True. Returns number of keys set.
    """
    try:
        from dotenv import load_dotenv as _load
        return 1 if _load(path, override=override) else 0
    except ImportError:
        pass
    p = Path(path)
    if not p.exists():
        return 0
    n = 0
    for raw in p.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip().strip('"').strip("'")
        if key and (override or key not in os.environ):
            os.environ[key] = val
            n += 1
    return n


load_dotenv()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows

def write_jsonl(path: Path, rows: List[Dict[str, Any]], append: bool = False) -> None:
    with open(path, "a" if append else "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

def load_manifest(path: Path) -> Dict[str, Any]:
    manifest = json.loads(Path(path).read_text(encoding="utf-8"))
    meta_path = path.parent / "meta.jsonl"
    if meta_path.exists():
        actual_sha = sha256_file(meta_path)
        expected_sha = manifest.get("sha256_meta")
        if expected_sha and actual_sha != expected_sha:
            raise ValueError(f"Manifest SHA mismatch: expected {expected_sha}, got {actual_sha}")
    return manifest

def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)

def load_npy(path: Path) -> np.ndarray:
    return np.load(path, mmap_mode="r")

def save_npy(path: Path, arr: np.ndarray) -> None:
    np.save(path, arr)


# ── Logging ──────────────────────────────────────────────────────────────────

def setup_logging(name: str, level: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(level)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    if not logger.handlers:
        logger.addHandler(handler)
    return logger

def log_json(logger: logging.Logger, **kwargs) -> None:
    logger.info(json.dumps(kwargs, ensure_ascii=False))


# ── Text ─────────────────────────────────────────────────────────────────────

def normalize_text(text: str) -> str:
    return " ".join(text.lower().split())

STOP = set("the a an of to in and for is on by that with as be from are was it not has have been will "
           "per govt india government ministry minister be pleased state answer answers".split())

def norm_upper(s: str) -> str:
    return (s or "").strip().upper()

def extract_tokens(title: str) -> set:
    words_re = re.compile(r"[A-Za-z']{4,}")
    return {w.lower() for w in words_re.findall(title or "")} - STOP

def extract_subparts(text: str) -> list:
    """Extract (a)/(b)/(c) sub-parts from answer text, splitting at the LAST \\bANSWER\\b marker."""
    parts = []
    answer_splits = list(re.finditer(r"\bANSWER\b", text or "", re.IGNORECASE))
    if not answer_splits:
        return []
    answer_text = text[answer_splits[-1].start():]
    subpart_pattern = re.compile(r'\(([a-z])\)\s*(.*?)(?=\([a-z]\)|$)', re.DOTALL | re.IGNORECASE)
    for match in subpart_pattern.finditer(answer_text):
        parts.append(match.group(2).strip())
    return parts


# ── Chunking ─────────────────────────────────────────────────────────────────

CHUNK_SIZE = 1800
CHUNK_OVERLAP = 1500

def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    """Split text into overlapping chunks (window = chunk_size, stride = overlap)."""
    if not text:
        return []
    return [text[j:j + chunk_size] for j in range(0, len(text), chunk_size - overlap)] if len(text) > chunk_size else [text]


# ── CPU Threading ────────────────────────────────────────────────────────────

def configure_cpu_threads(num_threads: int = None) -> int:
    """Pin torch + BLAS + tokenizers to all CPUs. Returns thread count."""
    n = int(num_threads or os.cpu_count() or 8)
    os.environ["TOKENIZERS_PARALLELISM"] = "true"
    os.environ.setdefault("OMP_NUM_THREADS", str(n))
    os.environ.setdefault("MKL_NUM_THREADS", str(n))
    os.environ.setdefault("OPENBLAS_NUM_THREADS", str(n))
    try:
        import torch
        torch.set_num_threads(n)
        torch.set_num_interop_threads(n)
    except Exception:
        pass
    return n


# ── Linear algebra / ranking ─────────────────────────────────────────────────

def l2_normalize(arr: np.ndarray, axis: int = -1) -> np.ndarray:
    norms = np.linalg.norm(arr, axis=axis, keepdims=True)
    norms[norms == 0] = 1
    return arr / norms

def cosine_similarity(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return a @ b.T

def rrf_fuse(ranked_lists: List[List[str]], k: int = 60, rrf_k: int = 60) -> List[str]:
    """Reciprocal Rank Fusion (doc-granularity)."""
    scores: Dict[str, float] = {}
    for ranked in ranked_lists:
        for rank, doc_id in enumerate(ranked):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (rrf_k + rank + 1)
    return sorted(scores.keys(), key=lambda x: scores[x], reverse=True)[:k]

def topk_for_scores(scores_1d: np.ndarray, k: int) -> np.ndarray:
    """Partial sort: return indices of top-k scores (descending)."""
    n = len(scores_1d)
    if k >= n:
        return np.argsort(-scores_1d)[:k]
    idx = np.argpartition(-scores_1d, k)[:k]
    return idx[np.argsort(-scores_1d[idx])]


# ── Statistics ───────────────────────────────────────────────────────────────

def bootstrap_ci(metric_fn, sys1_scores: List[float], sys2_scores: List[float],
                 n_bootstrap: int = 10000, alpha: float = 0.05) -> tuple:
    """Paired bootstrap confidence interval for metric difference."""
    n = len(sys1_scores)
    diffs = []
    for _ in range(n_bootstrap):
        indices = np.random.choice(n, n, replace=True)
        sample1 = [sys1_scores[i] for i in indices]
        sample2 = [sys2_scores[i] for i in indices]
        diffs.append(metric_fn(sample1) - metric_fn(sample2))
    diffs = np.array(diffs)
    mean_diff = np.mean(diffs)
    lo = np.percentile(diffs, 100 * alpha / 2)
    hi = np.percentile(diffs, 100 * (1 - alpha / 2))
    return mean_diff, lo, hi

def wilson_interval(successes: int, trials: int, alpha: float = 0.05) -> tuple:
    """Wilson score interval for binomial proportion."""
    if trials == 0:
        return 0.0, 0.0, 0.0
    from scipy import stats
    z = stats.norm.ppf(1 - alpha / 2)
    p = successes / trials
    denominator = 1 + z**2 / trials
    centre = (p + z**2 / (2 * trials)) / denominator
    half = z * np.sqrt(p * (1 - p) / trials + z**2 / (4 * trials**2)) / denominator
    return centre, centre - half, centre + half

def cohens_kappa(annotations1: List[int], annotations2: List[int]) -> float:
    from sklearn.metrics import cohen_kappa_score
    return cohen_kappa_score(annotations1, annotations2)


# ── Device ───────────────────────────────────────────────────────────────────

def get_device() -> str:
    try:
        import torch
        if torch.cuda.is_available():
            return "cuda"
    except ImportError:
        pass
    return "cpu"
