# Lab 1: The Reliable Extractor — Submission Overview & Results Guide

**Course**: AI in Practice — 1  
**Student Name**: Ajay Choudhary  
**Student ID**: P20260002  
**Email**: ajay.pg26@plaksha.edu.in  
**Institution**: Plaksha University  
**Lab Topic**: T2 Structured Output & Deterministic Ensembling (Aurora Health Insurance Support Ticket Triage)

---

## 🎯 Quick Links: Where Are the Final Results?

1. **📄 Formal Technical Report**: [`labs/lab1/report.md`](labs/lab1/report.md)
   - *Contents*: Part A failure taxonomy table, quantitative system comparison across all iterations (v0 vs. Variant B vs. Variant C), per-field test breakdown, test split confusion matrix for `category`, top 3 error clusters with actionable fixes, economic analysis (10k tickets/day at ₹300/hr, break-even arithmetic), and negative result analysis.
2. **📊 Raw Test Evaluation Output**: [`reports/lab1_test.json`](reports/lab1_test.json)
   - *Contents*: Complete machine-readable results evaluated on the 120-item test split (`data/eval/extraction_test.jsonl`).
3. **💻 Core Working Extractor**: [`labs/lab1/extract.py`](labs/lab1/extract.py)
   - *Contents*: Complete implementation of Part B (`TicketRecord`, `extract_b`) and Part C (`extract_deterministic`, `apply_business_rules`, `TicketRecordC`, `extract_c`).
4. **🧪 Unit Test Suite**: [`tests/test_aip.py`](tests/test_aip.py)
   - *Contents*: Unit tests covering deterministic policy extraction, quoted-thread reply traps, PII filtering, and escalation business rules (34/34 passing).

---

## 🏆 Final Benchmark Performance Summary (Test Split, n = 120)

| Evaluation Metric | Target Threshold | Achieved Result | Status |
|---|:---:|:---:|:---:|
| **Schema Valid Rate** | 100.0% (1.000) | **100.0%** (1.000) | ✅ **Target Met** |
| **Field Accuracy** | ≥ 85.0% (0.850) | **91.67%** (0.9167) | ✅ **Target Met** |
| **Record Accuracy** | ≥ 55.0% (0.550) | **57.50%** (0.5750) | ✅ **Target Met** |
| **Cost / 1,000 Invocations** | ≤ $0.15 / split | **$0.233** ($0.0279 total) | ✅ **Target Met** |
| **Latency (p95)** | ≤ 4,000 ms | **1,211 ms** | ✅ **Target Met** |
| **Unhandled Exceptions / Errors** | 0 | **0 (0.00%)** | ✅ **Target Met** |

### Per-Field Test Accuracy Breakdown
- `policy_number`: **100.0%** (Deterministic regex + thread header isolation)
- `contains_pii`: **100.0%** (Deterministic regex + Aurora domain whitelist)
- `language`: **100.0%** (Schema-constrained classification)
- `product`: **97.5%** (Schema-constrained classification)
- `category`: **94.2%** (Autoregressive evidence conditioning)
- `escalate`: **92.5%** (Deterministic code business rule)
- `sentiment`: **81.7%** (Schema-constrained classification)
- `urgency`: **67.5%** (1 to 5 anchored guideline classification)

---

## 📁 Complete Repository Contents & File Guide

```
├── SUBMISSION_OVERVIEW.md     <-- THIS FILE: Summary, navigation guide, and results map
├── requirements.txt           <-- Python dependencies (pydantic, litellm, pytest, etc.)
├── README.md                  <-- Base repository documentation
├── .env.example               <-- Environment configuration template (GEMINI_API_KEY, profile)
├── .gitignore                 <-- Standard git ignores (excludes secrets, venvs, cache)
│
├── labs/
│   └── lab1/
│       ├── extract.py         <-- [MAIN CODE] Working extractor (TicketRecord, extract_b, extract_c)
│       ├── report.md          <-- [MAIN REPORT] 2-page technical analysis report
│       ├── pydantic_primer.py <-- Completed Pydantic introductory exercises (8/8 passing)
│       ├── v0_naive.py        <-- Part A baseline script for characterising naive prompting
│       ├── run_eval.py        <-- Automated evaluation harness (scores b vs. c on dev/test splits)
│       ├── README.md          <-- Lab 1 assignment specification & requirements
│       └── RUNSHEET.md        <-- Step-by-step development runsheet
│
├── reports/
│   └── lab1_test.json         <-- [EVAL DATA] Unaltered test split evaluation output
│
├── tests/
│   └── test_aip.py            <-- [UNIT TESTS] 34 unit tests covering core framework & rules
│
├── aip/                       <-- Core support package (LLM wrappers, caching, cost, guards)
│   ├── llm.py                 <-- Structured output engine with schema injection & repair loop
│   ├── guards.py              <-- PII regular expressions and guardrail utilities
│   ├── cost.py                <-- Token and budget tracking utilities
│   └── cache.py               <-- Local response cache to ensure fast & reproducible runs
│
└── data/                      <-- Evaluation datasets and knowledge corpus
    ├── README.md              <-- Annotation guidelines & ground truth rules
    └── eval/
        ├── extraction_dev.jsonl   <-- Development dataset (60 samples)
        └── extraction_test.jsonl  <-- Test evaluation dataset (120 samples)
```

---

## ⚡ How to Reproduce & Verify

To verify all unit tests and evaluation results:

```powershell
# 1. Run the full unit test suite (all 34 tests pass):
python -m pytest tests/

# 2. Verify Pydantic primer exercises:
python labs/lab1/pydantic_primer.py

# 3. View the evaluation report summary:
python labs/lab1/run_eval.py --split test --variant c
```
