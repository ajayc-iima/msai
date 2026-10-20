#!/usr/bin/env python3
"""Lab 7 — the observability dashboard, read from local traces.

    streamlit run labs/lab7/dashboard.py

`aip.tracing` writes one JSONL file per run to .aip_traces/. This page reads
them back. It is a teaching-scale stand-in for Langfuse / LangSmith / Phoenix;
the concept -- structured spans with a run id and a parent id -- is identical.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from aip.config import settings

st.set_page_config(page_title="Aurora Assistant — Ops", layout="wide")
st.title("Aurora Policy Assistant — operations")

runs = sorted(settings.trace_dir.glob("*.jsonl"), reverse=True)
if not runs:
    st.info(f"No traces yet in {settings.trace_dir}. Run some queries first.")
    st.stop()

chosen = st.sidebar.multiselect("runs", [p.stem for p in runs],
                                default=[runs[0].stem])
rows = [json.loads(l) for p in runs if p.stem in chosen
        for l in p.open(encoding="utf-8") if l.strip()]
if not rows:
    st.stop()

df = pd.DataFrame(rows)
df["ts"] = pd.to_datetime(df["ts"], unit="s")

c = st.columns(5)
c[0].metric("spans", len(df))
c[1].metric("total cost", f"${df.get('cost_usd', pd.Series([0])).fillna(0).sum():.4f}")
llm = df[df["name"] == "llm.call"]
c[2].metric("model calls", len(llm))
if len(llm):
    c[3].metric("cache hit rate", f"{llm.get('cached', pd.Series([False])).fillna(False).mean():.0%}")
c[4].metric("errors", int((df.get("status") == "error").sum()))

st.subheader("Latency by stage")
# C3: p50/p95 per span name — the table that answers "which stage should I
# optimise?" (Part B4). Generation-equivalent stages dominate; retrieval and
# validation are noise beside them.
stage = (df.groupby("name")["duration_ms"]
         .agg(n="count", p50="median",
              p95=lambda s: s.quantile(0.95), total="sum")
         .sort_values("total", ascending=False))
st.dataframe(stage, use_container_width=True)

st.subheader("Cost over time")
if "cost_usd" in df:
    cum = df.sort_values("ts").assign(cum=lambda d: d["cost_usd"].fillna(0).cumsum())
    st.line_chart(cum.set_index("ts")["cum"])

st.subheader("Errors")
errs = df[df.get("status") == "error"]
st.dataframe(errs[["ts", "name", "error"]] if len(errs) else pd.DataFrame(),
             use_container_width=True)

# C4: one alert condition with its runbook. Refusal-rate doubling is the
# alert worth having on this system: a broken index throws no errors, raises
# no latency and costs nothing — it just stops finding things, and a correct
# pipeline responds by declining. WHEN IT FIRES: freeze deploys, check /health
# index counts vs the committed corpus, diff the corpus/excerpts, re-run the
# gate; if the index shrank, restore it and re-warm the cache.
st.subheader("Alerts")
ask_spans = df[df["name"].isin(["http.ask", "vidhi.ask"])]
n_ask = len(ask_spans)
n_refused = int(((ask_spans.get("decision") == "REFUSE")).sum()) if n_ask else 0
refusal_rate = (n_refused / n_ask) if n_ask else 0.0
http_lat = df[df["name"] == "http.ask"]["duration_ms"]
p95_http = float(http_lat.quantile(0.95)) if len(http_lat) else 0.0
SLO_P95_MS, REFUSAL_BASELINE = 6000.0, 0.30
ac = st.columns(3)
ac[0].metric("refusal rate", f"{refusal_rate:.0%}", f"{n_refused}/{n_ask} asks")
ac[1].metric("p95 /ask", f"{p95_http:.0f} ms", f"SLO {SLO_P95_MS:.0f} ms")
alert = refusal_rate >= 2 * REFUSAL_BASELINE or p95_http > SLO_P95_MS
ac[2].metric("alert", "FIRING" if alert else "clear",
             "refusal 2x baseline or p95 > SLO")
if alert:
    st.error("Action: freeze deploys → check /health index counts → diff "
             "corpus/excerpts → re-run gate → restore index, re-warm cache.")
else:
    st.caption("Fires when refusal rate doubles vs baseline (broken-index "
               "signal) or p95 /ask breaches the 6,000 ms SLO.")
