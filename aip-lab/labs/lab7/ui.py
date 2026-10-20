#!/usr/bin/env python3
"""Lab 7 — Streamlit front end.

    streamlit run labs/lab7/ui.py

Requires the service to be running:
    uvicorn labs.lab7.service:app --port 8000

The one non-negotiable UI requirement: **citations must be expandable to show
the source text.** Grounding the user cannot check is decoration.
"""
from __future__ import annotations

import requests
import streamlit as st

API = st.sidebar.text_input("Service URL", "http://localhost:8000")

st.title("Aurora Policy Assistant")
st.caption("Answers come only from Aurora's policy documents. "
           "Every claim is cited. When the documents do not cover a question, "
           "the assistant says so instead of guessing.")

q = st.text_input("Ask a question",
                  placeholder="How long do I have to file a reimbursement claim?")

if st.button("Ask", type="primary") and q:
    with st.spinner("thinking"):
        try:
            r = requests.post(f"{API}/ask", json={"question": q}, timeout=60)
            r.raise_for_status()
            st.session_state["last"] = {"question": q, **r.json()}
        except requests.HTTPError as exc:
            st.error(f"{exc.response.status_code}: {exc.response.text[:300]}")
            st.stop()
        except requests.RequestException as exc:
            st.error(f"service unreachable: {exc}")
            st.stop()

data = st.session_state.get("last")
if data:
    if data.get("refused"):
        st.warning(data["answer"])
    else:
        st.markdown(data["answer"])

    # A4: citations as expanders showing the source excerpt — grounding the
    # user cannot open is decoration.
    for c in data.get("citations", []):
        with st.expander(f"[{c['index']}] {c['doc_id']}"):
            st.text(c["excerpt"])

    cols = st.columns(4)
    cols[0].metric("latency", f"{data.get('latency_ms', 0):.0f} ms")
    cols[1].metric("cost", f"${data.get('cost_usd', 0):.5f}")
    cols[2].metric("cached", "yes" if data.get("cached") else "no")
    cols[3].metric("sources", len(data.get("citations", [])))
    st.caption(f"trace: `{data.get('trace_id', '')}`")

    # Stretch: thumbs-down writes the case into a review queue — the cheapest
    # real feedback loop, and how golden sets get built.
    if st.button("report a bad answer"):
        import json
        from pathlib import Path

        queue = Path(__file__).resolve().parent / "review_queue.jsonl"
        with queue.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"question": data.get("question", ""),
                                 "answer": data.get("answer", ""),
                                 "trace_id": data.get("trace_id", "")}) + "\n")
        st.success(f"logged to {queue.name} for golden-set review")

