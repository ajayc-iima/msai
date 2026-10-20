#!/usr/bin/env python3
"""Statistical Evidence & Validity Firewall — Sovereign Policy Analyst Agent (Lab 6 Extension).

An autonomous agent that breaks down multi-part policy inquiries, invokes
the deterministic statistical validity firewall as an unbypassable tool, and
synthesizes a verified, tamper-proof policy briefing with deep risk analysis
and statistically defensible phrasing recommendations.

Architecture (Lab 6 alignment):
- L1: Untrusted document delimiters (<RETRIEVED_EXCERPT>)
- L2: Safety-A Injection Detection on user query & tools
- L3: Typed Structured Output (PolicyBriefing schema)
- L4: ToolGuard privilege capping — firewall verdicts CANNOT be mutated by the agent
- L5: Output filtering & citation integrity validation

Runs 100% offline deterministically by default. Set VIDHI_USE_LLM=1 for live LLM reasoning.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from vidhi import pipeline as P

# ------------------------------------------------------------------------------
# Schemas (Lab 6 L3 Structured Output)
# ------------------------------------------------------------------------------
class RiskScorecard(BaseModel):
    temporal_comparability_risk: str = Field(description="LOW | MEDIUM | HIGH | CRITICAL")
    subpopulation_reification_risk: str = Field(description="LOW | MEDIUM | HIGH")
    hallucination_vulnerability: str = Field(description="LOW | MEDIUM | HIGH | CRITICAL")
    rationale: str


class AdjudicatedFinding(BaseModel):
    sub_query: str
    decision: str = Field(description="PASS | WARN | REFUSE")
    sub_code: str
    reason_code: Optional[str] = None
    official_figure: Optional[str] = None
    warning_or_caveat: Optional[str] = None
    frozen_hash: str
    primary_citation: Optional[str] = None
    survey_lineage: Optional[str] = None


class PolicyBriefing(BaseModel):
    executive_summary: str
    overall_governance_status: str = Field(description="VERIFIED | CONTAINS_CAVEATS | REJECTED")
    statistical_integrity_score: int = Field(default=100, ge=0, le=100)
    risk_scorecard: Optional[RiskScorecard] = None
    policy_phrasing_recommendation: Optional[str] = None
    findings: List[AdjudicatedFinding]
    methodological_warnings: List[str]
    audit_trace_ids: List[str]
    citation_index: List[str]


# ------------------------------------------------------------------------------
# Core Tool Executor
# ------------------------------------------------------------------------------
class VidhiAgent:
    def __init__(self, use_llm: bool = False):
        self.use_llm = use_llm or (os.getenv("VIDHI_USE_LLM", "0").strip().lower() in {"1", "true"})
        self.firewall = P.firewall()

    def adjudicate(self, question: str) -> dict:
        """Call Vidhi Guardian deterministic pipeline."""
        return P.ask(question, top_k=3)

    def analyze(self, complex_inquiry: str) -> PolicyBriefing:
        """Decompose query, adjudicate sub-claims, and synthesize policy briefing."""
        sub_questions = self._decompose(complex_inquiry)

        findings: List[AdjudicatedFinding] = []
        warnings: List[str] = []
        traces: List[str] = []
        citations: set[str] = set()

        has_warn = False
        has_refuse = False
        reason_codes = set()

        for sq in sub_questions:
            res = self.adjudicate(sq)
            dec = res.get("decision", "WARN")
            r_code = res.get("reason_code")
            if r_code:
                reason_codes.add(r_code)
            traces.append(res.get("trace_id", ""))

            if dec == "WARN":
                has_warn = True
                if res.get("answer"):
                    warnings.append(res["answer"])
            elif dec == "REFUSE":
                has_refuse = True
                if res.get("answer"):
                    warnings.append(res["answer"])

            for c in res.get("citations", []):
                citations.add(c.get("doc_id", "Unknown Document"))

            findings.append(AdjudicatedFinding(
                sub_query=sq,
                decision=dec,
                sub_code=res.get("sub_code", ""),
                reason_code=r_code,
                official_figure=f"{res.get('value')} {res.get('unit') or ''}".strip() if res.get("value") is not None else None,
                warning_or_caveat=res.get("answer") if dec != "PASS" else None,
                frozen_hash=res.get("verdict_frozen_hash", ""),
                primary_citation=res.get("citations", [{}])[0].get("doc_id") if res.get("citations") else None,
                survey_lineage=res.get("claim", {}).get("survey")
            ))

        # Overall Status & Integrity Score
        if has_refuse:
            status = "REJECTED"
            score = 15
        elif has_warn:
            status = "CONTAINS_CAVEATS"
            score = max(40, 75 - (len(warnings) * 10))
        else:
            status = "VERIFIED"
            score = 100

        # Risk Scorecard Computation
        risk = self._compute_risk_scorecard(reason_codes, has_warn, has_refuse)

        # Policy Phrasing Recommendations
        phrasing = self._compute_phrasing_recommendation(findings, status)

        # Synthesize Executive Summary
        if self.use_llm:
            try:
                summary = self._llm_synthesize(complex_inquiry, findings, status)
            except Exception:
                summary = self._deterministic_synthesize(complex_inquiry, findings, status, score)
        else:
            summary = self._deterministic_synthesize(complex_inquiry, findings, status, score)

        return PolicyBriefing(
            executive_summary=summary,
            overall_governance_status=status,
            statistical_integrity_score=score,
            risk_scorecard=risk,
            policy_phrasing_recommendation=phrasing,
            findings=findings,
            methodological_warnings=list(dict.fromkeys(warnings)),
            audit_trace_ids=traces,
            citation_index=sorted(list(citations))
        )

    def _decompose(self, text: str) -> list[str]:
        """Split multi-part policy inquiries into atomic statistical questions."""
        # Protect dates and coordinate pairs from accidental splitting (e.g. 2011-12 and 2023-24, rural and urban)
        protected = re.sub(r'(\b\d{4}(?:-\d{2,4})?)\s+and\s+(\d{4}(?:-\d{2,4})?\b)', r'\1__AND__\2', text, flags=re.IGNORECASE)
        protected = re.sub(r'\b(rural|urban|male|female|men|women|ps|ss)\s+and\s+(rural|urban|male|female|men|women|ps|ss)\b', r'\1__AND__\2', protected, flags=re.IGNORECASE)
        protected = re.sub(r'\bbetween\s+([^?;\n]+?)\s+and\s+([^?;\n]+?)\b', r'between \1__AND__\2', protected, flags=re.IGNORECASE)

        # Split on questions, semicolons, or major independent query conjunctions
        splits = re.split(r'\s*(?:\?|;|\band\s+also\b|\balso\b|\badditionally\b|\bfurthermore\b)\s*|\s+\band\s+(?=(?:what|how|will|compare|is|are|can|does)\b)', protected, flags=re.IGNORECASE)

        cleaned = []
        for s in splits:
            s_clean = s.replace('__AND__', ' and ').strip()
            s_clean = re.sub(r'^[\s.,;?!]+|[\s.,;?!]+$', '', s_clean)
            if len(s_clean) > 12:
                cleaned.append(s_clean + "?")

        # Contextual anaphora resolution: inherit metric/survey across clauses
        if len(cleaned) > 1:
            first_q = cleaned[0].lower()
            topic = ""
            if "mpce" in first_q or "consumption" in first_q:
                topic = "MPCE"
            elif "lfpr" in first_q or "labour" in first_q:
                topic = "LFPR"
            elif "unemployment" in first_q or "wpr" in first_q:
                topic = "PLFS"

            if topic:
                for i in range(1, len(cleaned)):
                    sub_low = cleaned[i].lower()
                    if ("compare" in sub_low or "how does" in sub_low or "what about" in sub_low) and topic.lower() not in sub_low:
                        cleaned[i] = re.sub(r'\b(it|this)\b', f"{topic}", cleaned[i], flags=re.IGNORECASE)
                        if topic.lower() not in cleaned[i].lower():
                            cleaned[i] = f"Compare average {topic} in " + cleaned[i]

        return cleaned if cleaned else [text]

    def _compute_risk_scorecard(self, reason_codes: set[str], has_warn: bool, has_refuse: bool) -> RiskScorecard:
        """Evaluate structural governance risks."""
        if any("COMPARABILITY" in r for r in reason_codes):
            temp_risk = "CRITICAL"
            temp_rat = "Structural survey design break (e.g. 3-visit CAPI or calendar revamp) violates raw longitudinal comparability."
        elif has_warn:
            temp_risk = "MEDIUM"
            temp_rat = "Methodological nuances or missing microdata require cautionary interpretation."
        else:
            temp_risk = "LOW"
            temp_rat = "Longitudinal series conforms to official survey standards."

        if any(r in {"R_NO_CURATED_ROW", "R_METADATA_UNSUPPORTED_DISAGGREGATION",
                     "R_METADATA_UNKNOWN_INDICATOR", "R_METADATA_UNKNOWN_SURVEY"}
               for r in reason_codes):
            sub_risk = "HIGH"
            sub_rat = "Extrapolating national figures to sub-geographies presents high risk of ecological fallacy."
        else:
            sub_risk = "LOW"
            sub_rat = "Aggregation level is aligned with survey sample design."

        if any(r in {"R_FORECAST", "R_CAUSAL", "R_POLITICAL", "R_PROMPT_INJECTION"} for r in reason_codes):
            hall_risk = "CRITICAL"
            hall_rat = "Inquiry solicits predictive or speculative reasoning ungrounded in official cross-sectional tables."
        elif has_warn:
            hall_risk = "MEDIUM"
            hall_rat = "Standard unconstrained RAG models frequently drop comparability caveats."
        else:
            hall_risk = "LOW"
            hall_rat = "Deterministic match against verified ground truth ensures zero hallucination."

        return RiskScorecard(
            temporal_comparability_risk=temp_risk,
            subpopulation_reification_risk=sub_risk,
            hallucination_vulnerability=hall_risk,
            rationale=f"Assessment: {temp_rat} {sub_rat} {hall_rat}".strip()
        )

    def _compute_phrasing_recommendation(self, findings: list[AdjudicatedFinding], status: str) -> str:
        """Provide statistically defensible phrasing for researchers, speechwriters, and journalists."""
        if status == "VERIFIED":
            quotes = [f"'{f.official_figure}' for {f.sub_query.replace('?', '')}" for f in findings if f.official_figure]
            return (
                "Statistically Defensible Phrasing: Citable directly as official statutory estimates. "
                f"Recommended wording: 'According to official survey estimates published by MoSPI, {', and '.join(quotes)}'."
            )
        elif status == "CONTAINS_CAVEATS":
            return (
                "Statistically Defensible Phrasing: Do NOT report direct percentage growth or level comparisons without explicit caveats. "
                "Recommended wording: 'While recent survey estimates provide headline values, MoSPI official methodology notes that "
                "questionnaire and sampling revisions prevent direct uninterrupted longitudinal chaining.'"
            )
        else:
            return (
                "Statistically Defensible Phrasing: Do NOT emit or endorse speculative figures under official MoSPI branding. "
                "Official position: 'MoSPI conducts retrospective cross-sectional statistical measurements; it does not issue "
                "speculative economic forecasts or causal political adjudications.'"
            )

    def _deterministic_synthesize(self, query: str, findings: list[AdjudicatedFinding], status: str, score: int) -> str:
        """Deterministic rule-based briefing synthesis."""
        parts = [f"Policy Executive Briefing [Statistical Integrity Index: {score}/100]:"]
        if status == "VERIFIED":
            parts.append("Status: FULLY VERIFIED. All statistical assertions are certified against primary statutory tables.")
        elif status == "CONTAINS_CAVEATS":
            parts.append("Status: CONDITIONAL / CONTAINS CAVEATS. Underlying survey series contain structural methodology breaks.")
        else:
            parts.append("Status: ADJUDICATION REJECTED. Query contains speculative predictive or out-of-bounds assertions.")

        for f in findings:
            if f.decision == "PASS":
                parts.append(f"• Verified Metric on '{f.sub_query}': {f.official_figure} (Lineage: {f.primary_citation or f.survey_lineage or 'MoSPI'}).")
            elif f.decision == "WARN":
                parts.append(f"• Governance Notice on '{f.sub_query}': {f.warning_or_caveat}.")
            else:
                parts.append(f"• Adjudication Block on '{f.sub_query}': {f.warning_or_caveat}.")

        return "\n".join(parts)

    def _llm_synthesize(self, query: str, findings: list[AdjudicatedFinding], status: str) -> str:
        """LLM-driven synthesis constrained strictly by the findings."""
        from aip.llm import chat
        prompt = (
            f"You are the Sovereign Policy Intelligence Analyst. Synthesize a concise 3-sentence policy executive summary "
            f"for the user inquiry: '{query}'.\n"
            f"Governance Status: {status}\n"
            f"Verified Findings:\n" +
            "\n".join([f"- Query: {f.sub_query} | Decision: {f.decision} | Figure: {f.official_figure} | Caveat: {f.warning_or_caveat}" for f in findings]) +
            "\n\nRules: Strictly cite verified figures. Never ignore caveats. Never invent numbers."
        )
        return chat(prompt, tier="SMALL")


def run_agent(question: str) -> PolicyBriefing:
    agent = VidhiAgent()
    return agent.analyze(question)


if __name__ == "__main__":
    test_q = "What was rural MPCE in HCES 2023-24 and will unemployment fall in 2027?"
    print(f"Analyzing: {test_q}\n")
    briefing = run_agent(test_q)
    print(briefing.model_dump_json(indent=2))
