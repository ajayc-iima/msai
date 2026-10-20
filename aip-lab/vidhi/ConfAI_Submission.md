# ConfAI 2026 Submission — Project Info (250 words)

**Title:** Refuse to Hallucinate: A Deterministic Validity Firewall for Indian Official Survey Statistics

**Author:** Ajay Choudhary, MSAI, Plaksha University (AI in Practice – 1, Policy Track)
**Conference:** ConfAI 2026, Plaksha University, Mohali, 30 Oct – 1 Nov 2026


## Abstract (250 words)

Generative AI fails at governance over sovereign statistics, not at retrieval. Unconstrained RAG is unstable there: MoSPI's own StatsDoc pilot (archived transcripts, chats 2472–2480) quoted urban MPCE as both 3,158 and 5,589 in one response, could not resolve the short code "mp", and compared survey rounds that are not comparable without warning. We present a deterministic validity firewall that adjudicates questions about Indian official survey data before any document is retrieved. Every question is parsed into a typed claim; five versioned rule stages (Safety-A, Scope, Comparability, Metadata, Numeric) fire in fixed order, and the verdict is frozen into a SHA-256 hash before retrieval. Safety-A runs first and blocks prompt injection in English, Hindi and Hinglish. Only verified rows may PASS; uncovered questions return WARN_NO_DATA with a coverage note, never a guess.

Measured offline: 100/100 golden verdicts [0.963–1.000] and reason codes, 60/60 numeric exact match, abstention recall 1.000 / hallucination rate 0.000 (36 must-abstain goldens) with an answer rate of 1.000 on the 64 answerable goldens (0 wrongly refused), Safety-A P/R/F1 1.000 on a 28-case multilingual red-team, Safety-B hash unchanged under corpus injection, typed-claim accuracy 20/21 on typos, codes, paraphrases and Hindi, and 1400/1400 page-anchored rows re-verified on their source PDF page (82% of the 1708 rows are anchored). $0.00 marginal model cost per query (p50 ≈ 150–190 ms warm, CPU-only). Every one of the 1708 verified rows is answerable through the live pipeline with its exact figure, source row and page (`scripts/coverage_probe.py`, `scripts/store_reaudit.py`).

MoSPI StatsDoc Assistant — `https://statsdoc.ai.mospi.gov.in/`