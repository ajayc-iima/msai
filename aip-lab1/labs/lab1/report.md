# Lab 1 Technical Report: The Reliable Extractor

**Course**: AI in Practice — 1  
**Module**: T2 Structured Output & Deterministic Ensembling  
**System Evaluated**: Aurora Health Insurance Customer Support Extractor  

---

## 1. Part A: Characterisation of Naive Prompting (`v0_naive.py`)

A baseline evaluation of naive prompting (`v0_naive.py`) on 40 samples from `data/eval/extraction_dev.jsonl` demonstrated why unconstrained text generation cannot be deployed directly into production workflows.

### Failure Mode Breakdown (n = 40)

| Phase | Observed Failure Mode | Count | % of n | Taxonomy Mapping (T2 §1.2) |
|---|---|:---:|:---:|---|
| **Part 1: Strict `json.loads`** | Markdown code block formatting (` ```json ... ``` `) | 40 | 100.0% | **Surface Syntax (Envelope)**: Output enclosed in markdown prose wrapper instead of raw JSON byte-stream. |
| **Part 2: Salvaged Cleanliness** | Unsanitized urgency type (`"urgency": "high"`) | 40 | 100.0% | **Schema Type Mismatch**: Model outputs qualitative strings instead of integer scale `[1, 5]`. |
| **Part 2: Salvaged Cleanliness** | Out-of-set category values (e.g. `"Claim Query"`, `"Refund"`) | 40 | 100.0% | **Contract Invalidation**: Categorical values violate the closed enumerated set `CATEGORIES`. |
| **Summary** | Strictly Valid JSON Records | 0 | 0.0% | Complete pipeline failure for automated consumers. |
| **Summary** | Schema-Compliant Clean Records | 0 | 0.0% | Zero usable records without downstream heuristic repair. |

### Discussion of Unmapped Failure Modes
1. **Markdown Envelope Wrap (`markdown_fence`)**: Naive LLMs are conversational instruction-followers trained on chat datasets where code/JSON blocks are conventionally wrapped in triple backticks. In a headless pipeline, this represents an unprompted schema envelope violation that crashes standard deserializers (`json.loads`).
2. **Schema Drift & Free-form Invented Labels (`category_out_of_set`)**: Without a formal JSON Schema contract provided to the model during sampling, the LLM hallucinates domain labels (e.g. `"Claim Status"`, `"Billing Dispute"`). This breaks relational database foreign keys and automated ticket routing rules.

---

## 2. Quantitative System Comparison

Across all experimental iterations on the `dev` split (60 items) and the final test evaluation (120 items), our architecture evolved from unconstrained prompting (v0) to schema-constrained extraction (Variant B) and hybrid deterministic ensembling (Variant C).

| System Variant | Split | n | Field Accuracy | Record Accuracy | Schema Valid | Cost / 1k Calls | Latency p95 |
|---|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **`v0_naive`** | dev | 40 | 0.00%* | 0.00% | 0.00% | ~$0.35 | ~1,850 ms |
| **Variant B (Pure Model)** | dev | 60 | 90.24% | 51.67% | 100.00% | $0.265 | 1,952 ms |
| **Variant C (Hybrid)** | dev | 60 | 91.04% | 58.33% | 100.00% | $0.190 | 1,498 ms |
| **Variant C (Final Test)** | test | 120 | **91.67%** | **57.50%** | **100.00%** | **$0.233** | **1,211 ms** |

*\*Note: v0 strict accuracy is 0% due to JSON parse failure; salvaged field accuracy suffered from ~100% categorical and type errors.*

---

## 3. Test Set Performance & Diagnostic Analysis

### Per-Field Accuracy on Test Split (n = 120)

| Field | Accuracy | Extraction Mechanism | Notes / Root Cause |
|---|:---:|---|---|
| `policy_number` | **100.0%** | Deterministic Regex + Quoted Header Filter | Perfect rejection of stale thread history. |
| `contains_pii` | **100.0%** | Deterministic Regex + Domain Whitelist | Correct exclusion of Aurora corporate emails. |
| `language` | **100.0%** | Schema-Constrained Model | Robust Hindi/Hinglish code-mixing detection. |
| `product` | **97.5%** | Schema-Constrained Model | Accurate plan tier identification; strictly defaults to `unknown`. |
| `category` | **94.2%** | In-Context Reasoning via Prior `evidence` | High fidelity across 6 categories. |
| `escalate` | **92.5%** | Deterministic Code Business Rule | Function of `urgency >= 4` and `ombudsman` keyword. |
| `sentiment` | **81.7%** | Schema-Constrained Model | Minor boundary confusion between `frustrated` and `neutral`. |
| `urgency` | **67.5%** | Schema-Constrained Model | Subjective boundary tension between levels 2 and 3. |

### Test Split Confusion Matrix: `category`

```
                      Predicted:
Actual Gold:     billing   claims   complaint   information   policy_change   technical
billing               15        .           .             1               .           .
claims                 .       21           .             .               .           .
complaint              .        5          11             .               .           .
information            .        .           .            22               .           .
policy_change          .        .           .             .              22           .
technical              .        .           .             1               .          22
```

---

## 4. Top Three Error Clusters & Actionable Fixes

### Cluster 1: Urgency Boundary Off-by-One (Levels 2 vs. 3)
- **Error Pattern**: Tickets asking about existing in-flight requests or delays are occasionally scored as 2 rather than 3, or general status checks are scored as 1 instead of 2.
- **Root Cause**: The transition between "requiring an account lookup" (Level 2) and "customer waiting after something went wrong/delayed" (Level 3) is subtle when customer phrasing is polite.
- **Proposed Fix**: Provide two explicit few-shot contrastive pairs in the system prompt clarifying that any explicit mention of elapsed waiting time without resolution automatically promotes the score to Level 3.
- **Estimated Impact**: +8–12% urgency accuracy (~+0.04 record accuracy).

### Cluster 2: Complaint vs. Claims Boundary Confusion
- **Error Pattern**: 5 instances where customer complaints regarding delayed claims handling were categorized as `claims` rather than `complaint`.
- **Root Cause**: The model's attention was drawn to claim-specific vocabulary (e.g. deductions, pre-auth, hospital bills) rather than the meta-grievance regarding service quality.
- **Proposed Fix**: Two-stage hierarchical classification: classify primary intent (transaction execution vs. service conduct redress) using regex cues for grievance escalation terms.
- **Estimated Impact**: +4.2% category accuracy (~+0.035 record accuracy).

### Cluster 3: Subtle Frustration vs. Neutral Sentiment
- **Error Pattern**: Customers reporting broken portal functionality or minor delays with formal language were classified as `neutral` instead of `frustrated`.
- **Root Cause**: In the absence of exclamation marks or negative adjectives, the model interprets polite phrasing as neutral even when reporting an obstacle.
- **Proposed Fix**: Add explicit schema instruction: *"Reporting a functional defect or unresolved prior attempt is intrinsically 'frustrated' regardless of polite vocabulary."*
- **Estimated Impact**: +6–8% sentiment accuracy (~+0.025 record accuracy).

---

## 5. Economic & Business Analysis (Section 4.5)

### Operational Parameters
- **Daily Inbound Volume**: 10,000 tickets / day (3.65 million tickets / year).
- **Human Triage Baseline**: 40 seconds per ticket @ ₹300 / hour (~₹3.333 per ticket).
- **Current Annual Human Triage Cost**: **₹12,166,667 / year** (~$146,500 USD).

### Automated Pipeline Costs (Variant C)
- **Model Call Cost**: $0.000233 per ticket (₹0.0193 per ticket).
- **Total Annual LLM API Cost**: **₹70,445 / year** (~$848 USD).

### Break-Even Record Accuracy Arithmetic
Let $A$ be the record accuracy, $C_{\text{human}} = ₹3.333$ the human triage cost saved on a perfect record, $C_{\text{api}} = ₹0.0193$ the model invocation cost, and $C_{\text{err}}$ the cost to remediate an imperfect record:

1. **Autonomous Straight-Through Processing (Zero-Penalty Review)**:
   If imperfect records are flagged for standard human review with no extra penalty ($C_{\text{err}} = 0$):
   $$\text{Net Daily Savings} = 10,000 \times (A \times ₹3.333 - ₹0.0193)$$
   $$\text{Break-even Accuracy } A_{\text{break-even}} = \frac{₹0.0193}{₹3.333} = \mathbf{0.58\%}$$
   At our current record accuracy of **57.50%**, net annual savings are **₹6,925,000 / year** ($83,400 USD).

2. **Downstream Rerouting Penalty Scenario**:
   If an imperfect extraction causes downstream misrouting that requires 60 seconds of agent time to correct ($C_{\text{err}} = ₹5.00$):
   $$\mathbb{E}[\text{Value}] = A \times ₹3.333 - (1 - A) \times ₹5.00 - ₹0.0193 \ge 0$$
   $$8.333 \times A \ge 5.0193 \implies A_{\text{break-even}} = \mathbf{60.2\%}$$
   Routing all high-confidence predictions autonomously and sending the remaining ~42% to human triage generates immediate net positive ROI while eliminating misrouting risk.

---

## 6. What Did Not Work (Negative Result & Rationale)

### Experiment: Attempting to Extract `policy_number` via LLM Schema Validator
- **What Was Attempted**: In early iterations of Variant B, we relied on the LLM to locate and extract the policy number, backed by a Pydantic `@field_validator` regex.
- **Why It Failed**:
  1. **Quoted History Traps (C3)**: When a customer forwarded an email thread containing an older policy number in the header quote (`> Reference: AUR-9999999`) alongside their current issue, the model frequently grabbed the quoted policy number.
  2. **Token Inefficiency**: Forcing the LLM to output 7-digit IDs increased output token count by ~15% and slowed p95 latency.
- **Resolution**: Shifting policy number extraction and PII detection to pure Python regex (`extract_deterministic`) completely eliminated policy hallucinations, delivered **100.0% accuracy**, reduced prompt/completion tokens, and cut p95 latency from 1,952 ms to 1,211 ms.
