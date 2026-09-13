"""src/answer.py — Answer generation with policies A-D and extractive mode."""
import argparse
import json
import os
import random
import re
import time
from pathlib import Path
from typing import List, Dict, Any, Optional

from openai import OpenAI
from tqdm import tqdm

from src.common import load_jsonl, write_jsonl, ensure_dir, setup_logging, log_json, sha256_bytes, chunk_text
from src.gating import evidence_gate, log_gate_decision, verify_answer_claims


# Policy prompts
POLICY_PROMPTS = {
    "A": "Answer the question based on the provided context.",
    "B": "Answer ONLY from the provided evidence. Cite ministry, session, and answer date for each claim. If the evidence does not contain the answer, say you cannot answer.",
    "C": "Answer ONLY from the provided evidence. Cite ministry, session, and answer date for each claim. If the evidence does not contain the answer, say you cannot answer.",
    "D": "Answer ONLY from the provided evidence. Cite ministry, session, and answer date for each claim. If the evidence does not contain the answer, say you cannot answer.",
}

EXTRACTIVE_PROMPT = """Extract the answer directly from the provided evidence.
Return only verbatim spans from the evidence that answer the question.
Format each span as: [ministry: X, session: Y, date: Z] "span text"
If no answer exists in the evidence, output: ABSTAIN"""


def get_llm_client() -> Optional[OpenAI]:
    """Get NVIDIA API client if available, else None."""
    api_key = os.environ.get("NVIDIA_API_KEY")
    if not api_key:
        return None
    return OpenAI(
        base_url="https://integrate.api.nvidia.com/v1",
        api_key=api_key,
    )


def get_cache_key(model: str, prompt: str, temperature: float, max_tokens: int) -> str:
    """Generate cache key for LLM response."""
    content = f"{model}|{prompt}|{temperature}|{max_tokens}"
    return sha256_bytes(content.encode())[:16]


def load_cache(cache_path: Path) -> Dict[str, Any]:
    """Load LLM response cache."""
    if cache_path.exists():
        return json.loads(cache_path.read_text(encoding="utf-8"))
    return {}


def save_cache(cache_path: Path, cache: Dict[str, Any]) -> None:
    """Save LLM response cache."""
    cache_path.write_text(json.dumps(cache, indent=1), encoding="utf-8")


def call_llm(client: Optional[OpenAI], model: str, prompt: str, temperature: float = 0.0,
             max_tokens: int = 1024, cache: Dict = None, cache_path: Path = None,
             retries: int = 3) -> str:
    """Call LLM with caching + exp-backoff retry on 429/5xx."""
    import random as _rng
    key = get_cache_key(model, prompt, temperature, max_tokens)

    if cache and key in cache:
        return cache[key]["response"]

    # Also check alternative models in cache
    if cache:
        for alt in ["openai/gpt-oss-20b", "nvidia/llama-3.1-nemotron-70b-instruct"]:
            if alt != model:
                alt_key = get_cache_key(alt, prompt, temperature, max_tokens)
                if alt_key in cache:
                    return cache[alt_key]["response"]

    if client is None:
        raise RuntimeError("No LLM client available and prompt not in cache")

    last_err = None
    for attempt in range(retries):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=120,
            )
            text = response.choices[0].message.content or ""
            break
        except Exception as e:
            last_err = e
            status = getattr(getattr(e, "response", None), "status_code", None) or getattr(e, "status_code", None)
            if status is not None and status < 500 and status != 429:
                raise
            sleep = 2.0 * (2 ** attempt) + _rng.random()
            print(f"  llm retry {attempt+1}/{retries} after {type(e).__name__} ({str(e)[:100]}); sleep {sleep:.1f}s")
            time.sleep(sleep)
    else:
        raise RuntimeError(f"LLM call failed after {retries} attempts: {last_err}")

    if cache is not None:
        cache[key] = {
            "response": text,
            "model": model,
            "prompt_hash": key,
            "timestamp": time.time(),
        }
        if cache_path:
            save_cache(cache_path, cache)

    return text


def build_extractive_answer(chunks: List[Dict], query: str) -> Dict[str, Any]:
    """Build extractive answer from top chunks."""
    claims = []
    citations = []

    for i, ch in enumerate(chunks[:8]):
        text = ch.get("text", "").strip()
        meta = ch.get("meta", {})
        if len(text) < 50:
            continue

        # Split into sentences and take first few
        sentences = re.split(r'(?<=[.!?])\s+', text)
        for sent in sentences[:3]:
            if len(sent) > 30:
                claims.append(sent)
                citations.append({
                    "doc_id": meta.get("qslno"),
                    "chunk_idx": ch.get("chunk_idx", 0),
                    "span": sent[:500],
                    "ministry": meta.get("ministry"),
                    "session": meta.get("ses_no"),
                    "date": meta.get("answer_date"),
                })

    return {
        "claims": claims[:5],
        "citations": citations[:5],
        "abstained": len(claims) == 0,
    }


def build_llm_answer(query: str, chunks: List[Dict], policy: str,
                     client: OpenAI, model: str, cache: Dict, cache_path: Path) -> Dict[str, Any]:
    """Build LLM answer with given policy."""
    # Prepare context
    context_parts = []
    for i, ch in enumerate(chunks[:8]):
        text = ch.get("text", "").strip()
        meta = ch.get("meta", {})
        if len(text) < 50:
            continue
        ctx = f"[Doc {meta.get('qslno')}, Chunk {ch.get('chunk_idx', 0)}] "
        ctx += f"Ministry: {meta.get('ministry')}, Session: {meta.get('ses_no')}, Date: {meta.get('answer_date')}\n"
        ctx += text[:2000]
        context_parts.append(ctx)

    context = "\n\n---\n\n".join(context_parts)

    prompt = f"{POLICY_PROMPTS[policy]}\n\nQuestion: {query}\n\nEvidence:\n{context}\n\nAnswer:"

    response = call_llm(client, model, prompt, temperature=0.0, max_tokens=1024, cache=cache, cache_path=cache_path)

    # Parse claims and citations from response
    # Simple heuristic: split by sentences, extract citations from brackets
    claims = []
    citations = []

    # Look for citation patterns like [ministry: X, session: Y, date: Z]
    cite_pattern = re.compile(r'\[ministry:\s*([^,\]]+),\s*session:\s*([^,\]]+),\s*date:\s*([^\]]+)\]')

    for sent in re.split(r'(?<=[.!?])\s+', response):
        sent = sent.strip()
        if not sent:
            continue
        # Check for inline citations
        cites = cite_pattern.findall(sent)
        if cites:
            for ministry, session, date in cites:
                citations.append({
                    "ministry": ministry.strip(),
                    "session": session.strip(),
                    "date": date.strip(),
                    "span": sent,
                })
        claims.append(sent)

    return {
        "claims": claims,
        "citations": citations,
        "abstained": "cannot answer" in response.lower() or "unable to answer" in response.lower(),
    }


def apply_policy_d_verification(answer: Dict, chunks: List[Dict], tau: float = 0.80) -> Dict[str, Any]:
    """Apply Policy D: verify claims and demote to abstain if any unsupported."""
    verification = verify_answer_claims(answer["claims"], answer["citations"], tau)

    if not verification["all_supported"]:
        return {
            "claims": [],
            "citations": [],
            "abstained": True,
            "verification": verification,
            "gate_reason": "VERIFICATION_FAILED",
        }

    return {
        **answer,
        "verification": verification,
    }


def process_query(query: Dict, chunks: List[Dict], policy: str,
                  client: OpenAI = None, model: str = None,
                  cache: Dict = None, cache_path: Path = None,
                  no_llm: bool = False, tau: float = 0.80) -> Dict[str, Any]:
    """Process a single query with given policy."""
    query_id = query["query_id"]
    query_text = query["title"]

    # Run evidence gate
    gate_result = evidence_gate(chunks)

    if not gate_result["pass"] and policy in ("C", "D"):
        return {
            "query_id": query_id,
            "policy": policy,
            "abstained": True,
            "claims": [],
            "citations": [],
            "gate_reason": gate_result["reason"],
            "verification": {"all_supported": True, "skipped_short_claims": 0},
        }

    if no_llm or policy == "extractive":
        answer = build_extractive_answer(chunks, query_text)
    else:
        try:
            answer = build_llm_answer(query_text, chunks, policy, client, model, cache, cache_path)
        except Exception as e:
            print(f"  [fallback extractive for {query_id}: {e}]")
            answer = build_extractive_answer(chunks, query_text)

    if policy == "A":
        answer["citations"] = []

    # Verify claims against citations for all policies
    verification = verify_answer_claims(answer["claims"], answer["citations"], tau)
    answer["verification"] = verification

    # Policy D: demote whole answer to abstain if any claim is unsupported
    if policy == "D" and not verification["all_supported"]:
        answer["claims"] = []
        answer["citations"] = []
        answer["abstained"] = True
        answer["gate_reason"] = "VERIFICATION_FAILED"

    return {
        "query_id": query_id,
        "policy": policy,
        "abstained": answer.get("abstained", False),
        "claims": answer.get("claims", []),
        "citations": answer.get("citations", []),
        "gate_reason": answer.get("gate_reason", gate_result["reason"]),
        "verification": answer.get("verification", {"all_supported": True, "skipped_short_claims": 0}),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--queries", default="data/queries.jsonl")
    ap.add_argument("--runs-dir", default="data/runs")
    ap.add_argument("--system", required=True, help="Retriever system (bm25, dense_head, hybrid, etc.)")
    ap.add_argument("--policy", choices=["A", "B", "C", "D", "extractive"], required=True)
    ap.add_argument("--out", default="data/preds/")
    ap.add_argument("--model", default="openai/gpt-oss-20b")
    ap.add_argument("--no-llm", action="store_true", help="Use extractive mode only (replay cache)")
    ap.add_argument("--tau", type=float, default=0.80)
    ap.add_argument("--split", choices=["dev", "test"], default="test")
    ap.add_argument("--limit", type=int, default=200,
                    help="Cap queries scored (tier sampling; default: 200 for quantitative tier)")
    ap.add_argument("--seed", type=int, default=7,
                    help="Seed for --limit subsampling (seeded shuffle, then take first --limit)")
    ap.add_argument("--query-ids", default=None,
                    help="Path to JSON list of query_ids to score (exact tier set; overrides --limit)")
    a = ap.parse_args()

    logger = setup_logging("answer")
    ensure_dir(Path(a.out))

    # Load queries
    queries = load_jsonl(Path(a.queries))
    queries = [q for q in queries if q["split"] == a.split]
    if a.query_ids:
        want = set(json.loads(Path(a.query_ids).read_text(encoding="utf-8")))
        queries = [q for q in queries if q["query_id"] in want]
    if a.limit:
        rng = random.Random(a.seed)
        queries = sorted(queries, key=lambda q: q["query_id"])
        rng.shuffle(queries)
        queries = queries[:a.limit]
    print(f"Scoring {len(queries)} queries (split={a.split}, limit={a.limit}, seed={a.seed})")

    # Load retrieval results
    run_path = Path(a.runs_dir) / f"{a.system}.jsonl"
    if not run_path.exists():
        raise FileNotFoundError(f"Run file not found: {run_path}")
    runs = load_jsonl(run_path)
    run_by_query = {r["query_id"]: r for r in runs}

    # Load corpus for chunk texts
    corpus = {r["qslno"]: r for r in load_jsonl(Path("data/corpus.jsonl"))}

    # Setup LLM
    client = None
    cache = {}
    cache_path = Path("data/cache/llm_responses.json")
    ensure_dir(cache_path.parent)
    if not a.no_llm and a.policy != "extractive":
        try:
            client = get_llm_client()
        except Exception:
            client = None
        cache = load_cache(cache_path)

    # Process queries
    preds = []
    for q in tqdm(queries, desc=f"Answering ({a.policy})"):
        run = run_by_query.get(q["query_id"])
        if not run:
            continue

        # Get top chunks with metadata
        chunks = []
        for item in run["ranked_list"][:8]:
            doc_id = item["doc_id"]
            if doc_id in corpus:
                doc = corpus[doc_id]
                # Split into chunks (same as build_corpus)
                for ci, chunk_text_ in enumerate(chunk_text(doc.get("text", ""))):
                    chunks.append({
                        "text": chunk_text_,
                        "meta": {k: v for k, v in doc.items() if k != "text"},
                        "chunk_idx": ci,
                    })

        pred = process_query(q, chunks, a.policy, client, a.model, cache, cache_path, a.no_llm, a.tau)
        preds.append(pred)

        # Log gate decision
        log_json(logger, **log_gate_decision(
            q["query_id"], a.policy,
            {"pass": pred["gate_reason"] == "MER_PASS", "reason": pred["gate_reason"], "best": chunks[0] if chunks else None}
        ))

    # Save predictions
    out_path = Path(a.out) / f"{a.system}_{a.policy}.jsonl"
    write_jsonl(out_path, preds)
    print(f"Predictions written to {out_path}")

    # Save cache
    if cache:
        save_cache(cache_path, cache)


if __name__ == "__main__":
    main()