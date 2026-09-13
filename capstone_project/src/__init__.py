"""Rajya Sabha QA — consolidated package.

Modules:
    common       — shared IO, text, threading, math utilities
    build_corpus — corpus download + meta/manifest construction
    make_queries — Gold A/B query construction
    retrieval    — BM25 / dense / hybrid / rerank unified pipeline
    gating       — MER pre-gate + claim verification
    answer       — policy A-D answer generation (LLM + extractive)
    evaluate     — Exp-1 retrieval + Exp-2 answer metrics
    plots        — paper figures
    app          — FastAPI web interface
"""