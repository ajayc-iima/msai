# Statistical Evidence & Validity Firewall: Concept Note (Policy Track)
**Project Title:** Statistical Evidence & Validity Firewall — Deterministic Statistical Evidence & Validity Firewall for Indian Official Survey Statistics  
**Author:** Ajay Choudhary (MSAI @ Plaksha University, `ajay.pg26@plaksha.edu.in`)  
**Course:** AI in Practice – 1 (Term Final Track Assignment — Policy Track)  
**Instructor:** Subrat  
**Associated Deliverables:** 4-Slide Executive Deck (`decks/Vidhi_Guardian_Demo.pptx`), Evaluation Report (`vidhi/EVALUATION_REPORT.md`), Interactive Web Portal (`localhost:8001/demo`)  

---

## 1. Executive Summary & Core One-Liner

> **"MoSPI's tools help you FIND the number. Statistical Evidence & Validity Firewall checks whether you are ALLOWED TO SAY what you want to say with it — and stops you, with a cited rule, when you are not."**

In the deployment of generative AI across official sovereign data, search and retrieval are solved problems, but statistical governance is not. Official government AI pilots—exemplified by the Ministry of Statistics and Programme Implementation's (MoSPI) StatsDoc AI Assistant (`statsdoc.ai.mospi.gov.in`)—retrieve textual document chunks via semantic embeddings, leaving synthesis and interpretation to probabilistic Large Language Models. 

In high-stakes public policy, this creates dangerous vulnerabilities: LLMs hallucinate statutory definitions (e.g., expanding MPCE as *"Mean Per Capita..."*), compare non-comparable survey rounds across radical methodological revisions without warning, and can be easily subverted by adversarial text chunks.

**Statistical Evidence & Validity Firewall** introduces a deterministic validity firewall placed *ahead* of generation. Natural language inquiries are mapped to a strictly typed `StructuredStatisticalClaim`. Adjudication is executed entirely by versioned, transparent rules across five sequential stages. The final verdict is cryptographically frozen into a SHA-256 hash *before* retrieval runs, guaranteeing that untrusted context chunks cannot alter the verdict (Safety-B guarantee).

---

## 2. Epistemological Grounding: VERIFIED vs. INFERENCE vs. CONTRIBUTION

To maintain the rigorous scientific and policy standards required in national statistics:

1. **VERIFIED (Empirical Ground Truth):**
   - MoSPI officially publishes primary survey reports, press notes, metadata definitions, unit-level microdata layouts, and the eSankhyiki data portal.
   - The official 2025 revamp of the Periodic Labour Force Survey (PLFS) transitioned from an agricultural-year cycle (July–June) to a calendar-year cycle (January–December) with a re-stratified 2011 Census sampling frame and redesigned schedules.
   - The Household Consumption Expenditure Survey (HCES) 2022-23 and 2023-24 introduced a radical 3-visit CAPI (Computer Assisted Personal Interviewing) canvassing method with restructured item lists, breaking direct backward comparability with the paper-canvassed NSS 68th Round (2011-12).

2. **INFERENCE (Observed failure modes of MoSPI AI pilot):**
   - Live probing of MoSPI StatsDoc (`statsdoc.ai.mospi.gov.in`) OBSERVED (anecdotal; Sessions #2402 & #2399; re-runnable prompts in `evaluation/statsdoc_audit/PROTOCOL.md`): unconstrained RAG-style answers can hallucinate definitions, compute unguided cross-round growth rates without methodological warnings, with hosted-RAG latency and per-query cost.

3. **CONTRIBUTION (Our Engineered System):**
   - A deterministic, 5-stage validity firewall that decouples translation from adjudication.
   - The *Verdict-Freezing Architecture*: Cryptographic SHA-256 hash computed before retrieval, eliminating prompt injection via RAG documents.
   - The *Semantic Danger-Pair Resolution*: Proof that cosine similarity (0.93–0.99) cannot isolate demographic sub-populations; replaced with deterministic field-guards.
   - Zero-cost ($0.0000/query) offline execution; 100/100 accuracy on golden policy benchmarks.

---

## 3. End-to-End Technical Progression (Course Sequence)

Statistical Evidence & Validity Firewall follows the complete pedagogical progression established in the course (Labs 1 through 7):

```
[User Query]
      │
      ▼
┌─────────────────────────┐
│ 1. Exact Cache Check    │ ──(Exact Match)──► Return Cached Adjudication (~0 ms)
└─────────────────────────┘
      │ (Miss)
      ▼
┌─────────────────────────┐
│ 2. Claim Extraction     │ ──► StructuredStatisticalClaim (Pydantic Schema)
└─────────────────────────┘
      │
      ▼
┌─────────────────────────┐
│ 3. Confidence Gate      │ ──(< 0.60 Structural)──► WARN: Ambiguous Phrasing
└─────────────────────────┘
      │ (≥ 0.60)
      ▼
┌─────────────────────────┐
│ 4. Semantic Cache Guard │ ──► Cosine Lookup + Field-Guard (Rejects Danger Pairs)
└─────────────────────────┘
      │
      ▼
┌────────────────────────────────────────────────────────────────────────┐
│ 5. Five-Stage Deterministic Firewall                                   │
│    [Stage 1: Scope Gate] ──► Intercepts Out-of-Scope Topics (R_SCOPE)  │
│    [Stage 2: Safety-A]   ──► Intercepts Injections & Politics (REFUSE) │
│    [Stage 3: Comparability] ──► Evaluates Cross-Round Shifts (WARN)    │
│    [Stage 4: Metadata Match] ──► Validates Indicator & Population     │
│    [Stage 5: Numeric Match] ──► Checks Verified Ground Truth (PASS)    │
└────────────────────────────────────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────┐
│ 6. Cryptographic Lock   │ ──► Compute & Lock SHA-256 Frozen Verdict Hash
└─────────────────────────┘
      │
      ▼
┌─────────────────────────┐
│ 7. Untrusted RAG        │ ──► Retrieve Document Chunks (Treated as Untrusted)
└─────────────────────────┘
      │
      ▼
┌─────────────────────────┐
│ 8. Templated Generation │ ──► Render Constrained Prose (WARN/REFUSE Locked)
└─────────────────────────┘
      │
      ▼
┌─────────────────────────┐
│ 9. Citation Validator   │ ──► Verify All Bracketed Citations Exist in Chunks
└─────────────────────────┘
      │
      ▼
[Emitted Official Verdict + Verified Numbers + Primary PDF Citations]
```

### 3.1 Data Sourcing & Canonical Ground Truth
Four distinct official surveys are curated into the initial proof-of-mechanism corpus:
1. **PLFS 2025 Calendar Year Revamp** (`mospi_PLFS_2025_F_REV_29052026.pdf`)
2. **PLFS 2023-24 Annual Report** (`mospi_PLFS_2023-24_AnnualReport.pdf`)
3. **HCES 2023-24 Factsheet & Press Note** (`mospi_HCES_2023-24_Factsheet.pdf`)
4. **Time Use Survey (TUS) 2024 & NSS 78th Multiple Indicator Survey (MIS)**

A curated ground truth dataset of 1708 verified numeric rows represents the absolute source of truth. Valid filtered questions outside this curated set honestly return `WARN_NO_DATA` rather than probabilistic guesses.

### 3.2 The Semantic Danger-Pair Trap & Cache Field-Guards
During caching experiments, queries differing only in sensitive sub-populations (e.g., *"urban Bihar female LFPR"* vs. *"rural Bihar female LFPR"* or *"all-India LFPR"*) were embedded using `bge-small`. 

**Critical Empirical Finding:** Danger pairs embed at cosine similarities of **0.93 to 0.99**. 
- If the cosine cache threshold is set to 0.95, danger pairs falsely collide, returning all-India statistics for state-level queries.
- If the threshold is raised to 0.99, legitimate paraphrases miss the cache.

**Solution:** No scalar cosine threshold is safe. Statistical Evidence & Validity Firewall implements a deterministic `field_compatible()` guard on canonical fields (`indicator`, `geography`, `residence`, `sex`, `round`). The cache permits reuse *only* if critical fields match identically, eliminating cache collisions (0 collisions across 19 danger pairs).

### 3.3 The 5-Stage Deterministic Firewall
The core decision engine executes in strict priority order. The first rule to fire terminates adjudication:
1. **Scope Gate:** Blocks topics outside MoSPI jurisdiction (CPI, RBI monetary policy, Union Budget). Reason: `R_SCOPE_OUT`.
2. **Safety-A Defense:** Rejects forward forecasts (`R_FORECAST`), political judgments (`R_POLITICAL`), causal attributions (`R_CAUSAL`), and prompt injections (`R_PROMPT_INJECTION`).
3. **Comparability Engine:** Reads YAML rules (`comparability_rules.yaml`). Enforces survey breaks (e.g., `R_COMPARABILITY_HCES_METHOD` and `R_COMPARABILITY_PLFS_REVAMP`). Emits mandatory methodological caveats.
4. **Metadata Validation:** Verifies whether survey round, demographic disaggregations, and indicators exist in the official taxonomy.
5. **Numeric Verification:** Queries `ground_truth_tables.json`. If an exact verified row exists, emits `PASS_WITH_NUMBER`. If unverified, emits `WARN_NO_DATA`.

### 3.4 Pre-Retrieval Verdict Freezing (Safety-B Guarantee)
Standard RAG architectures provide document chunks to the LLM during answer synthesis. If a malicious or contradictory chunk is retrieved (e.g., secondary analysis claiming the 2011-12 and 2023-24 rounds are directly comparable), the LLM is easily swayed.

Statistical Evidence & Validity Firewall calculates the verdict and generates a SHA-256 hash:
$$\text{Hash} = \text{SHA256}(\text{Claim JSON} + \text{Decision} + \text{SubCode} + \text{RuleVersion})$$
This hash is locked *before* retrieval. The answer generation uses templated scaffolds where WARN and REFUSE responses are fixed. Even under adversarial retrieval poisoning, the emitted response cannot be corrupted.

### 3.5 Model Context Protocol (MCP) Server & Autonomous Policy Agent (Lab 6 Extension)
To make Statistical Evidence & Validity Firewall fully interoperable across modern AI ecosystems, two key architectural extensions were implemented:
1. **Official Model Context Protocol (MCP) Server (`vidhi/mcp_server.py`):**
   - Implements the open JSON-RPC 2.0 stdio MCP specification.
   - Exposes four core governance tools: `adjudicate_statistical_claim`, `check_survey_comparability`, `lookup_verified_ground_truth`, and `get_survey_metadata`.
   - Allows external AI assistants (e.g., Claude Desktop, Cursor, or MoSPI's future copilots) to natively connect to Statistical Evidence & Validity Firewall as an external governance oracle via `claude_desktop_config.json`.
2. **Autonomous Policy Analyst Agent (`vidhi/agent.py`):**
   - Extends the Lab 6 multi-layer defense agent pattern (L1 untrusted delimiters, L2 injection detection, L3 typed `PolicyBriefing` schema, L4 tool privilege capping, L5 citation validation).
   - Decomposes compound policy inquiries (e.g. comparing HCES consumption trends and PLFS labor participation in a single prompt) into atomic claims.
   - Evaluates each sub-claim through the firewall and synthesizes an authoritative policy briefing that respects all frozen caveats.

---

## 4. Benchmark Audit: MoSPI StatsDoc vs. Statistical Evidence & Validity Firewall

| Audit Dimension | MoSPI StatsDoc (`statsdoc.ai.mospi.gov.in`) | Statistical Evidence & Validity Firewall (`vidhi/pipeline.py`) |
|---|---|---|
| **Definitional Precision** | Hallucinates *"Mean Per Capita..."* for MPCE | Enforces canonical *"Monthly Per Capita Consumption Expenditure"* |
| **Survey Breaks** | Outputs 40% growth without warning on 3-visit CAPI break | Fires `R_COMPARABILITY_HCES_METHOD`; halts unguided comparisons |
| **Comparative Arithmetic** | Quotes disjointed 40% & 4% figures; fails compound math | Refuses synthetic math without official chained series |
| **Adversarial Injection** | Susceptible to instruction override in retrieved text | **Immune:** Verdict frozen via SHA-256 before retrieval |
| **Query Cost** | ~$0.02 – $0.05 per query (LLM API inference) | **$0.0000 / query** on deterministic path |
| **p50 Latency** | 3,500 – 8,000 ms TTFT (hosted LLM) | **≈150–190 ms** in-process, CPU-only (20–50× faster) |
| **Auditability** | Non-deterministic natural language prose | Deterministic verdict with rule version & hash trace |

---

## 5. Quantitative Verification & Quality Gates

Statistical Evidence & Validity Firewall is evaluated using an automated offline battery (`python vidhi/eval.py` & `python labs/lab7/gate.py`):
- **Golden Test Battery (100 Queries):** 100/100 verdict accuracy, 100/100 reason-code match, 100% numeric exact match.
- **Danger Pair Battery (19 Pairs):** 0 collisions.
- **Safety-B Adversarial Battery:** Frozen SHA-256 hash matches clean query byte-for-byte under corpus poisoning.
- **Unit Test Battery:** offline unit + gate tests pass (`tests/test_vidhi.py` and `tests/test_aip.py`, no API key).
- **Cost & Speed:** $0.00 cost per query, in-process p50 ≈ 150–190 ms (SLO target <= 6,000 ms); exact-cache hit ≈ 0 ms.

---

## 6. Scope Boundaries & Scaling Roadmap

- **Proof of Mechanism vs Full Catalog:** The current build locks 1708 verified numeric rows (the full PLFS Highlights battery of both annual reports, the TUS 2024 tables battery and the HCES 2023-24 trend columns, including state-wise MPCE for all 36 states/UTs) to demonstrate architectural correctness. State questions resolve in any spelling ("mp", "up", "m.p.", "orissa", "maharastra") and an under-specified slice returns every published cell rather than one narrowed figure. Questions requesting non-curated rows (state-level labour figures, off-badge rounds, MIS numerics) honestly return `WARN_NO_DATA` rather than fabricating numbers.
- **Catalog Scaling:** Scaling to all 10,000+ MoSPI indicators requires running an automated tabular PDF ingestion pipeline to extract and verify factsheet tables into `ground_truth_tables.json`. No architectural modifications are required.
- **Newsroom & Policy Integration:** Statistical Evidence & Validity Firewall is designed as a sovereign drop-in API for journalists, fact-checkers, and legislative researchers to verify statistical claims before public dissemination.

---
*Authored by Ajay Choudhary | Master of Science in Artificial Intelligence (MSAI) @ Plaksha University*
