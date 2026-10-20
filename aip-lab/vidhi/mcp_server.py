#!/usr/bin/env python3
"""Statistical Evidence & Validity Firewall — Official Model Context Protocol (MCP) Server.

Exposes the deterministic statistical firewall and verified
ground truth as standard Model Context Protocol (MCP) tools over JSON-RPC stdio.

Compatible with:
- Claude Desktop (`claude_desktop_config.json`)
- Cursor / Windsurf / VS Code
- Any MCP-compliant client or agent (e.g. MoSPI assistant copilots)

Usage:
    python -m vidhi.mcp_server
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from vidhi import pipeline as P

# Lab6 L3: strict arg schemas validated BEFORE any tool runs.
# Loose matching (substring survey/indicator) is replaced by exact
# allowlists; invalid args raise synchronously and are returned as
# MCP isError instead of silently returning zero matches.
try:
    from pydantic import BaseModel, Field

    class AdjudicateArgs(BaseModel):
        question: str = Field(min_length=3, max_length=1000)
        top_k: int = Field(default=3, ge=1, le=10)

    class ComparabilityArgs(BaseModel):
        survey_a: str = Field(min_length=3, max_length=32)
        survey_b: str = Field(min_length=3, max_length=32)
        indicator: str | None = Field(default=None, max_length=32)

    class LookupArgs(BaseModel):
        survey: str = Field(
            pattern=r"^(PLFS_2025|PLFS_2023_24|HCES_2023_24|TUS_2024|NSS78_MIS_2020_21)$"
        )
        indicator: str = Field(
            pattern=r"^(LFPR|WPR|UR|MPCE|average_time|participation_rate|drinking_water)$"
        )
        residence: str = Field(default="all", pattern=r"^(all|rural|urban)$")
        sex: str = Field(default="all", pattern=r"^(all|male|female)$")

    class MetadataArgs(BaseModel):
        survey_id: str = Field(min_length=3, max_length=32)

    _SCHEMAS: dict[str, Any] = {
        "adjudicate_statistical_claim": AdjudicateArgs,
        "check_survey_comparability": ComparabilityArgs,
        "lookup_verified_ground_truth": LookupArgs,
        "get_survey_metadata": MetadataArgs,
    }
except Exception:  # pragma: no cover - pydantic is a hard dep
    _SCHEMAS = {}

# Initialize firewall
_FW = P.firewall()

TOOLS = [
    {
        "name": "adjudicate_statistical_claim",
        "description": (
            "Adjudicate whether a claim or inquiry about Indian official statistics (PLFS, HCES, TUS, MIS) "
            "is methodologically defensible, comparable across rounds, and backed by verified ground truth. "
            "Returns decision (PASS/WARN/REFUSE), official figures, citations, and a SHA-256 frozen verdict hash."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "The statistical question or claim to verify (e.g. 'What was rural MPCE in HCES 2023-24?' or 'Compare MPCE 2011-12 vs 2023-24')"
                },
                "top_k": {
                    "type": "integer",
                    "description": "Number of supporting official document excerpts to retrieve",
                    "default": 3
                }
            },
            "required": ["question"]
        }
    },
    {
        "name": "check_survey_comparability",
        "description": (
            "Verify whether two Indian survey rounds or methodologies can be legitimately compared "
            "without violating official MoSPI comparability caveats (e.g. HCES 2011-12 paper vs 2023-24 CAPI break, "
            "or PLFS 2023-24 vs PLFS 2025 calendar revamp)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "survey_a": {
                    "type": "string",
                    "description": "First survey identifier (e.g. 'HCES_2011_12' or 'PLFS_2023_24')"
                },
                "survey_b": {
                    "type": "string",
                    "description": "Second survey identifier (e.g. 'HCES_2023_24' or 'PLFS_2025')"
                },
                "indicator": {
                    "type": "string",
                    "description": "Indicator being compared (e.g. 'MPCE', 'LFPR', 'UR')"
                }
            },
            "required": ["survey_a", "survey_b"]
        }
    },
    {
        "name": "lookup_verified_ground_truth",
        "description": (
            "Retrieve verified statutory statistics directly from MoSPI primary tables. "
            "Guarantees 100% exact match against verified press notes and annual reports."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "survey": {
                    "type": "string",
                    "description": "Survey code (PLFS_2025, PLFS_2023_24, HCES_2023_24, TUS_2024, NSS78_MIS_2020_21)"
                },
                "indicator": {
                    "type": "string",
                    "description": "Statistical indicator (LFPR, WPR, UR, MPCE)"
                },
                "residence": {
                    "type": "string",
                    "enum": ["all", "rural", "urban"],
                    "description": "Sector disaggregation"
                },
                "sex": {
                    "type": "string",
                    "enum": ["all", "male", "female"],
                    "description": "Gender disaggregation"
                }
            },
            "required": ["survey", "indicator"]
        }
    },
    {
        "name": "get_survey_metadata",
        "description": (
            "Retrieve official metadata, survey dates, sampling design, and statutory definitions "
            "for an Indian national survey."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "survey_id": {
                    "type": "string",
                    "description": "Survey identifier (e.g. 'PLFS_2025', 'HCES_2023_24', 'TUS_2024')"
                }
            },
            "required": ["survey_id"]
        }
    }
]


def handle_adjudicate_claim(args: dict[str, Any]) -> dict[str, Any]:
    question = args.get("question", "")
    top_k = args.get("top_k", 3)
    out = P.ask(question, top_k=top_k)
    return {
        "decision": out["decision"],
        "sub_code": out["sub_code"],
        "reason_code": out["reason_code"],
        "answer": out["answer"],
        "value": out.get("value"),
        "unit": out.get("unit"),
        "verdict_frozen_hash": out.get("verdict_frozen_hash"),
        "verdict_attestation": out.get("verdict_attestation"),
        "rule_version": out.get("rule_version"),
        "citations": [{"doc_id": c.get("doc_id"), "text": c.get("text", "")[:400]} for c in out.get("citations", [])],
        "citations_valid": out.get("citations_valid", True)
    }


def handle_check_comparability(args: dict[str, Any]) -> dict[str, Any]:
    from vidhi.claims import StructuredStatisticalClaim
    sa = args.get("survey_a", "").lower()
    sb = args.get("survey_b", "").lower()

    claim = StructuredStatisticalClaim(
        claim_type="comparative",
        comparison_surveys=[sa, sb],
        indicator=args.get("indicator")
    )
    v = _FW.comparability(claim)
    if v is not None:
        # Surface the versioned YAML provenance for the fired rule: the
        # verbatim MoSPI caveat travels with the decision (comparability
        # verdicts carry no retrieval hits, so the rule's own source_doc /
        # caveat_quote is the citation).
        prov = _FW.caveat_for(v.reason_code, v.sub_code) or {}
        return {
            "comparable": False,
            "status": v.sub_code,
            "reason_code": v.reason_code,
            "message": v.message,
            "citations": [
                {
                    "doc_id": prov.get("source_doc"),
                    "page": prov.get("source_page"),
                    "rule_id": prov.get("rule_id"),
                    "text": prov.get("caveat_quote", ""),
                }
            ]
            if prov.get("caveat_quote")
            else [],
        }
    return {
        "comparable": True,
        "status": "PERMITTED_WITH_CAUTION",
        "reason_code": "R_OK",
        "note": "No active rule prohibits this comparison, but standard standard-error pooling applies."
    }


def handle_lookup_ground_truth(args: dict[str, Any]) -> dict[str, Any]:
    survey = args.get("survey", "")
    indicator = args.get("indicator", "")
    residence = args.get("residence", "all")
    sex = args.get("sex", "all")

    truth_file = ROOT / "vidhi" / "store.json"
    rows = json.loads(truth_file.read_text(encoding="utf-8")).get("rows", [])

    matched = []
    for r in rows:
        if r.get("verification_status") != "verified":
            continue
        # Exact allowlisted match only (Lab6): substring matching leaks
        # neighbouring surveys (e.g. PLFS_2025 vs PLFS_2023_24).
        if survey.lower() != str(r.get("survey", "")).lower():
            continue
        if indicator.lower() != str(r.get("indicator", "")).lower():
            continue
        # A specific request must never be answered with an aggregate row
        # (rural != all). "all" means no filter, so every slice is returned.
        if residence and residence != "all":
            if str(r.get("residence") or "all").lower() != residence.lower():
                continue
        if sex and sex != "all":
            if str(r.get("sex") or "all").lower() != sex.lower():
                continue
        matched.append(r)

    return {
        "query": args,
        "match_count": len(matched),
        "results": matched
    }


def handle_get_metadata(args: dict[str, Any]) -> dict[str, Any]:
    import yaml
    survey_id = args.get("survey_id", "").lower()
    meta_path = ROOT / "data" / "vidhi" / "survey_metadata.yaml"
    catalog = {}
    if meta_path.exists():
        raw_cat = yaml.safe_load(meta_path.read_text(encoding="utf-8")) or {}
        for item in raw_cat.get("in_corpus", []) + raw_cat.get("reference_only", []):
            catalog[item["id"].lower()] = item

    meta = catalog.get(survey_id)
    if meta:
        return {"survey_id": survey_id, "metadata": meta}
    return {
        "error": f"Survey {survey_id} not found in metadata catalog.",
        "available_surveys": list(catalog.keys())
    }


def dispatch_tool(name: str, args: dict[str, Any]) -> Any:
    # Schema check before call (Lab6 LLM02): invalid args never reach the function.
    if name in _SCHEMAS:
        args = _SCHEMAS[name].model_validate(args or {}).model_dump()
    if name == "adjudicate_statistical_claim":
        return handle_adjudicate_claim(args)
    elif name == "check_survey_comparability":
        return handle_check_comparability(args)
    elif name == "lookup_verified_ground_truth":
        return handle_lookup_ground_truth(args)
    elif name == "get_survey_metadata":
        return handle_get_metadata(args)
    else:
        raise ValueError(f"Unknown tool: {name}")


def main() -> None:
    """Run JSON-RPC 2.0 stdio loop for Model Context Protocol."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except Exception:
            continue

        req_id = req.get("id")
        method = req.get("method")
        params = req.get("params", {})

        # Handle MCP Protocol Methods
        if method == "initialize":
            resp = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {"listChanged": False}
                    },
                    "serverInfo": {
                        "name": "vidhi-guardian-mcp",
                        "version": "2.0.0",
                        "description": "Sovereign Statistical Evidence & Validity Firewall for Indian Official Data"
                    }
                }
            }
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()

        elif method == "notifications/initialized":
            # Client acknowledge, no response needed
            pass

        elif method == "tools/list":
            resp = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "tools": TOOLS
                }
            }
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()

        elif method == "tools/call":
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})
            try:
                result_data = dispatch_tool(tool_name, tool_args)
                resp = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps(result_data, indent=2)
                            }
                        ],
                        "isError": False
                    }
                }
            except Exception as e:
                resp = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": f"Error executing {tool_name}: {str(e)}"
                            }
                        ],
                        "isError": True
                    }
                }
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()

        elif req_id is not None:
            # Fallback for unhandled method
            resp = {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32601,
                    "message": f"Method {method} not found"
                }
            }
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
