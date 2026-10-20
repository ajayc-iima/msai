#!/usr/bin/env python3
"""Lab 7 — the service.

    uvicorn labs.lab7.service:app --reload --port 8000
    curl -s localhost:8000/ask -H 'content-type: application/json' \
         -d '{"question":"How long do I have to file a claim?"}' | jq
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from aip import cache, tracing
from aip.cost import BudgetExceeded, global_budget

app = FastAPI(title="Aurora Policy Assistant", version="1.0")

_PIPELINE = None
_STARTED = time.time()


def pipeline():
    """Build Labs 3-5 pipeline once at startup and cache it, wired with Lab 6 guards."""
    global _PIPELINE
    if _PIPELINE is None:
        from vidhi import pipeline as P
        _PIPELINE = P
    return _PIPELINE


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1000)
    top_k: int = Field(default=5, ge=1, le=20)
    mode: str = Field(default="rag", pattern="^(rag|tools)$")


class Citation(BaseModel):
    index: int
    doc_id: str
    excerpt: str


class AskResponse(BaseModel):
    answer: str
    refused: bool
    citations: list[Citation]
    sources: list[str]
    latency_ms: float
    cost_usd: float
    cached: bool
    trace_id: str


@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest) -> AskResponse:
    """Return answer, citations, cost and trace_id in response body."""
    t0 = time.perf_counter()
    try:
        with tracing.trace("http.ask", question=req.question[:120]):
            p = pipeline()
            out = p.ask(req.question, top_k=req.top_k)

        latency_ms = round((time.perf_counter() - t0) * 1000, 1)
        refused = (out.get("decision") == "REFUSE")

        cites = [
            Citation(
                index=c["index"],
                doc_id=c["doc_id"],
                excerpt=c.get("text", "")[:300],
            )
            for c in out.get("citations", [])
        ]

        return AskResponse(
            answer=out.get("answer", ""),
            refused=refused,
            citations=cites,
            sources=out.get("sources", [c.doc_id for c in cites]),
            latency_ms=latency_ms,
            cost_usd=out.get("cost_usd", 0.0),
            cached=out.get("cached", False),
            trace_id=out.get("trace_id", "trace-0"),
        )
    except BudgetExceeded as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="upstream model unavailable",
                            headers={"Retry-After": "30"}) from exc


@app.get("/health")
def health() -> dict:
    """Index size, model profile, cache stats, uptime."""
    from vidhi import pipeline as P
    from vidhi.service import _index_stats
    return {
        "status": "ok",
        "uptime_s": round(time.time() - _STARTED, 1),
        "cache": cache.stats(),
        "rules": P.firewall().rule_version,
        "index": _index_stats(),
    }


@app.get("/metrics")
def metrics() -> dict:
    """Cost today, cost/query, cache hit rate, p50/p95/p99, error rate by type.

    Budget ledger gives cost + call counts + latency percentiles; the trace
    files give error rate by type and tool-call counts (Part C2).
    """
    import json

    from aip.config import settings
    from vidhi.service import _index_stats

    b = global_budget()
    d = b.as_dict()
    calls = d["calls"] or 0
    d.update({
        "cost_per_query_usd": round(d["cost_usd"] / calls, 6) if calls else 0.0,
        "cache_hit_rate": round(d["cached_calls"] / calls, 4) if calls else 0.0,
        "p99_latency_ms": round(b.percentile(99), 1),
    })

    errors_by_type: dict[str, int] = {}
    tool_calls = 0
    refusals = asks = 0
    try:
        for f in settings.trace_dir.glob("*.jsonl"):
            for line in f.open(encoding="utf-8"):
                if not line.strip():
                    continue
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                name = str(r.get("name", ""))
                if r.get("status") == "error":
                    errors_by_type[name] = errors_by_type.get(name, 0) + 1
                if name.startswith("tool.") or name == "llm.call":
                    tool_calls += 1
                if name in ("http.ask", "vidhi.ask"):
                    asks += 1
                    if r.get("decision") == "REFUSE" or r.get("refused"):
                        refusals += 1
    except OSError:
        pass
    d.update({
        "errors_by_type": errors_by_type,
        "error_count": sum(errors_by_type.values()),
        "tool_calls": tool_calls,
        "refusal_rate": round(refusals / asks, 4) if asks else 0.0,
        "index": _index_stats(),
    })
    return d


@app.post("/ask/stream")
async def ask_stream(req: AskRequest):
    """Server-sent events streaming (Part B2/B3).

    B3 design choice: buffer, validate, THEN stream. The full answer is
    produced and citation-validated first; only then are tokens streamed,
    followed by a citations event and done(trace_id). This deliberately
    trades away part of the TTFT benefit in exchange for never sending an
    unvalidated answer the UI has already shown — the failure mode the lab
    grades. TTFT here ≈ full-answer latency; total ≈ TTFT + chunk overhead.
    """
    import asyncio

    from sse_starlette.sse import EventSourceResponse

    async def gen():
        resp = ask(req)
        yield {"event": "verdict", "data": "REFUSED" if resp.refused else "ACCEPTED"}
        words = resp.answer.split()
        for i in range(0, len(words), 8):
            await asyncio.sleep(0)
            yield {"event": "token", "data": " ".join(words[i:i + 8])}
        yield {"event": "citations", "data": str([c.doc_id for c in resp.citations])}
        yield {"event": "done", "data": resp.trace_id}

    return EventSourceResponse(gen())

