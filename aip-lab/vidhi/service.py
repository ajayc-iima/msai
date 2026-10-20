#!/usr/bin/env python3
"""Statistical Evidence & Validity Firewall service (isolated; labs/lab7 untouched).

    python -m uvicorn vidhi.service:app --port 8001

Demo webapp: GET /demo. Streaming: POST /ask/stream (buffered-then-send:
verdict and citations are validated BEFORE any PASS prose is emitted).
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from aip import cache, tracing  # noqa: E402
from aip.cost import BudgetExceeded, global_budget  # noqa: E402
from vidhi import pipeline as P  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Pay model-load once at startup, never on first user request."""
    from vidhi import answer as A
    from vidhi.claims import extract

    P.firewall()
    model = A._get_model()
    if model is not None:
        c = extract("What was rural MPCE in HCES 2023-24?")
        A.retrieve(c, P.firewall().adjudicate(c), top_k=1)
    yield


app = FastAPI(title="Statistical Evidence & Validity Firewall", version="2.0", lifespan=lifespan)
_STARTED = time.time()


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1000)
    top_k: int = Field(default=3, ge=1, le=10)


@app.post("/ask")
def ask(req: AskRequest) -> dict:
    t0 = time.perf_counter()
    try:
        with tracing.trace("http.ask", question=req.question[:120]):
            out = P.ask(req.question, top_k=req.top_k)
        out["latency_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        return out
    except BudgetExceeded as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail="upstream unavailable",
                            headers={"Retry-After": "30"}) from exc


@app.post("/ask/stream")
async def ask_stream(req: AskRequest) -> EventSourceResponse:
    async def gen():
        # ask() performs CPU-bound adjudication + retrieval; run it off the
        # event loop so /ask/stream cannot stall concurrent requests.
        out = await asyncio.to_thread(ask, req)
        yield {"event": "verdict",
               "data": f"{out['decision']}/{out['sub_code']}"}
        words = out["answer"].split()
        for i in range(0, len(words), 8):
            await asyncio.sleep(0)
            yield {"event": "token", "data": " ".join(words[i:i + 8])}
        yield {"event": "citations", "data": str(out["sources"])}
        yield {"event": "done", "data": out["trace_id"]}

    return EventSourceResponse(gen())


@app.post("/analyze")
def analyze(req: AskRequest) -> dict:
    """Run Vidhi Guardian Policy Analyst Agent (multi-claim decomposition & synthesis)."""
    from vidhi.agent import run_agent
    briefing = run_agent(req.question)
    return briefing.model_dump()


@app.get("/demo", response_class=HTMLResponse)
def demo() -> str:
    """Zero-dependency demo webapp (Streamlit has no win-arm64 wheels)."""
    return (ROOT / "vidhi" / "demo.html").read_text(encoding="utf-8")


def _index_stats() -> dict:
    exc = [p for p in (ROOT / "data" / "excerpts").glob("*.md")
           if p.name != "README.md" and "ADVERSARIAL" not in p.name]
    truth = json.loads((ROOT / "vidhi" / "store.json")
                       .read_text(encoding="utf-8"))
    manifest = truth.get("manifest", {}) or {}
    # Lab7 freshness: scheduled rebuild + staleness alert on manifest age.
    staleness_days: float | None = None
    try:
        import datetime

        built = manifest.get("built_at")
        if built:
            dt = datetime.datetime.fromisoformat(str(built).replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=datetime.timezone.utc)
            now = datetime.datetime.now(datetime.timezone.utc)
            staleness_days = round((now - dt).total_seconds() / 86400, 1)
    except Exception:
        staleness_days = None
    return {"excerpts": len(exc),
            "verified_rows": sum(1 for r in truth.get("rows", [])
                                 if r.get("verification_status") == "verified"),
            "store_built_at": manifest.get("built_at"),
            "store_staleness_days": staleness_days,
            "store_stale": bool(staleness_days is not None and staleness_days > 90)}


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "uptime_s": round(time.time() - _STARTED, 1),
            "cache": cache.stats(), "rules": P.firewall().rule_version,
            "index": _index_stats()}


@app.get("/metrics")
def metrics() -> dict:
    b = global_budget()
    return {**b.as_dict(), "p99_latency_ms": round(b.percentile(99), 1),
            "index": _index_stats()}
