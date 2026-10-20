# Poster Abstract — ConfAI 2026

## Title
Refuse to Hallucinate: A Deterministic Validity Firewall for Indian Official Survey Statistics

## One-liner
MoSPI's tools help you FIND the number. This firewall checks whether you are ALLOWED TO SAY what you want with it — and stops you, with a cited rule, when you are not.

## The Problem
Generative AI over sovereign statistics fails at governance, not retrieval:
- **Definitional hallucination:** MPCE expanded as "Mean Per Capita Expenditure" instead of "Monthly Per Capita Consumption Expenditure"
- **Unguided cross-round arithmetic:** ~40% MPCE growth quoted across the HCES paper-to-3-visit-CAPI break with no warning
- **Adversarial vulnerability:** Retrieved document chunks can override system guardrails

Per `evaluation/statsdoc_audit/PROTOCOL.md`, these MoSPI StatsDoc observations (session `https://statsdoc.ai.mospi.gov.in/c/2402`) are anecdotal (live tests without archived transcripts) and are not presented as a measured baseline.

## The Solution: A Deterministic Validity Firewall

Five versioned rule stages adjudicate in **fixed order**, first rule wins:
1. **Safety-A** — refuse prompt injections (English, Hindi, Hinglish) first, so an injection is always refused *as* an injection
2. **Scope** — refuse forecasts, causality, politics, microdata
3. **Comparability** — warn on HCES-CAPI and PLFS-revamp breaks
4. **Metadata** — warn on unsupported disaggregations
5. **Numeric** — PASS only on a `verified` store row

## Key Innovation: Pre-Retrieval Freeze (Safety-B)

The SHA-256 verdict hash is computed **before any document is retrieved**. Poisoned chunks cannot move the verdict — byte-identical hash with or without injected corpus text.

## Key Innovation: Field-Guarded Cache

Danger pairs embed at cosine 0.93–0.99 (inseparable from paraphrases). No cosine threshold is safe. Cache reuses answers **only** when all critical fields match exactly. Measured: 0 collisions across 19 pairs.

## Results (measured offline, no API key, no GPU)

| Metric | Result |
|---|---|
| Verdict accuracy | 100/100 = 1.000 |
| Reason-code accuracy | 100/100 = 1.000 |
| Numeric exact match | 59/59 = 1.000 |
| Danger-pair collisions | 0 (19 pairs) |
| Safety-B (freeze before retrieval) | unchanged under injection |
| Abstention recall (must-abstain → abstained) | 37/37 = 1.000 |
| Hallucination rate (must-abstain → answered) | 0/37 = 0.000 |
| Safety-A P/R/F1 (n=28: en · hi · hi-en red-team) | 1.000 — 0 misses, 0 false positives |
| Verified store rows | 173/173 |
| Row utilization (verified rows touched) | 54/173 = 31.2% |
| Stages exercised | 5/5 |
| Decisions exercised | 3/3 |
| Surveys covered | 4/4 (PLFS/HCES/TUS/MIS) |
| In-process p50 latency | ≈150–190 ms (CPU-only; exact-cache ≈0 ms) |
| Cost per query | $0.0000 |

## Honest Limits
Coverage is the limit, not logic: 173 verified rows cover HCES state MPCE both imputation legs, PLFS national LFPR/WPR/UR, TUS minutes; measured coverage is 54/173 (31.2%). Uncurated slices return WARN_NO_DATA — never a guess. All five YAML comparability rules are active with verbatim caveat quotes and PDF provenance.

## Demo
`localhost:8001/demo` — offline, no API key, no GPU. Six live scenarios including refusal of "urban female LFPR in PLFS 2025" with honesty, not a guess.

**Author:** Ajay Choudhary, MSAI @ Plaksha University  
**Track:** Track 06 — Responsible and Ethical AI
