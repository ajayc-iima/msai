# ConfAI 2026 Submission — Project Info (250 words)

**Title:** Refuse to Hallucinate: A Deterministic Validity Firewall for Indian Official Survey Statistics

**Author:** Ajay Choudhary, MSAI, Plaksha University (AI in Practice – 1, Policy Track)
**Conference:** ConfAI 2026, Plaksha University, Mohali, 30 Oct – 1 Nov 2026


## Abstract (250 words)

Generative AI fails at governance when it comes to sovereign statistics rather than at retrieval. Unconstrained RAG hallucinates definitions (MoSPI's StatsDoc expands MPCE to mean "Mean Per Capita Expenditure" rather than the statutory "Monthly Per Capita Consumption Expenditure"), will compare survey rounds that are not in any way comparable without warning and will allow a poisoned document chunk to override a verdict. We present a deterministic validity firewall that adjudicates questions about Indian official survey data before any document is retrieved. Every question is parsed into a typed claim; five versioned rule stages (Safety-A, Scope, Comparability, Metadata, Numeric) fire in fixed order, and the verdict is frozen into a SHA-256 hash before retrieval. Safety-A runs first and blocks prompt injection in English, Hindi and Hinglish. Only verified ground-truth rows may PASS; uncovered questions return WARN_NO_DATA with a coverage note rather than a guess.

Measured offline: 100/100 golden verdicts [0.963–1.000], 100/100 reason codes, 59/59 numeric exact match [0.939–1.000], 0 collisions across 19 danger pairs [floor 0.83], refusal tp=8 fp=0 fn=0 raw (n=8, floor 0.68), Safety-B hash unchanged under corpus injection, abstention recall 1.000 / hallucination rate 0.000 (37 must-abstain goldens), Safety-A P/R/F1 1.000 on a 28-case multilingual red-team (0 misses, 0 false positives), 173/173 verified store rows with provenance, 54/173 (31.2%) row utilization, $0.00 marginal model cost per query on the deterministic path plus hosting (p50 ≈ 150–190 ms warm, CPU-only; the one-time cold model load is paid at service startup).

MoSPI StatsDoc Assistant — `https://statsdoc.ai.mospi.gov.in/`