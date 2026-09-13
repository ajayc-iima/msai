"""query.py — Interactive single query runner for Rajya Sabha QA.

Supports both:
1. Compiled LLM mode (synthesizes evidence into a clean, cited answer).
2. Extractive mode (verbatim parliamentary spans).
"""
import os
import sys
import argparse
from pathlib import Path

# Load environment variables from .env if present
env_file = Path(".env")
if env_file.exists():
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

from src.app import _retrieve, _to_chunks, _answer
from src.gating import evidence_gate, verify_answer_claims

def run_compiled_rag(question: str, system: str = "bm25", tau: float = 0.80):
    """Retrieve documents, compile a synthesized answer with Gemini, and verify claims."""
    from google import genai

    # 1. Retrieve top candidates
    ranked = _retrieve(question, k=5, system=system)
    chunks = _to_chunks([r["doc_id"] for r in ranked], k=5)

    # 2. Evidence Gate Check
    gate = evidence_gate(chunks)
    if not gate["pass"]:
        print(f"\n[GATE STATUS]: {gate['reason']}")
        print(f"[ABSTAINED]  : True (Insufficient valid evidence in top retrieved documents)")
        return

    # 3. Format context for synthesis
    context_blocks = []
    citations_ref = []
    for i, ch in enumerate(chunks[:4], 1):
        m = ch.get("meta", {})
        qslno = m.get("qslno")
        ministry = m.get("ministry")
        adate = m.get("answer_date")
        ses_no = m.get("ses_no")
        text = ch.get("text", "")[:1500]
        context_blocks.append(f"--- [Doc ID {qslno} | Ministry of {ministry} | Date: {adate} | Session: {ses_no}] ---\n{text}\n")
        citations_ref.append({
            "doc_id": qslno,
            "ministry": ministry,
            "date": adate,
            "session": ses_no,
            "span": text[:300]
        })

    context_str = "\n".join(context_blocks)

    # 4. Generate compiled answer
    client = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY"))
    prompt = f"""You are an expert parliamentary researcher. Answer the following question by compiling and synthesizing a clear, factual answer based ONLY on the provided official Rajya Sabha records.

Question: {question}

Evidence Documents:
{context_str}

Instructions:
1. Synthesize a concise, well-structured answer (use 2-4 bullet points).
2. For each key point, cite the source document ID, Ministry, and Date.
3. If the specific numbers asked are not mentioned in the text, explicitly state what is covered.
4. Do not speculate or invent numbers.
"""
    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=prompt
    )
    compiled_text = response.text.strip()

    # 5. Display output
    print(f"\n{'='*75}")
    print(f"QUESTION : {question}")
    print(f"RETRIEVER: {system.upper()} | MODE: Compiled LLM Synthesis (Policy D)")
    print(f"{'='*75}\n")

    print(f"[GATE STATUS]: {gate['reason']}")
    print(f"[ABSTAINED]  : False\n")

    print(f"--- TOP RETRIEVED PARLIAMENTARY DOCUMENTS ---")
    for ev in ranked[:3]:
        print(f"  • Rank {ev['rank']}: Doc ID {ev['doc_id']} (Relevance Score: {ev['score']:.4f})")

    print(f"\n--- COMPILED PARLIAMENTARY ANSWER ---")
    print(compiled_text)

    print(f"\n--- PRIMARY SOURCE CITATIONS ---")
    for c in citations_ref[:3]:
        print(f"  • Doc ID {c['doc_id']} | Ministry: {c['ministry']} | Date: {c['date']} (Session {c['session']})")

    print(f"\n{'='*75}\n")


def run_extractive_rag(question: str, system: str = "bm25", policy: str = "D"):
    """Run extractive baseline that pulls verbatim clauses directly."""
    res = _answer(question, policy=policy, system=system)

    print(f"\n{'='*75}")
    print(f"QUESTION : {question}")
    print(f"RETRIEVER: {system.upper()} | MODE: Extractive Verbatim (Policy {policy})")
    print(f"{'='*75}\n")

    print(f"[GATE STATUS]: {res['gate_reason']}")
    print(f"[ABSTAINED]  : {res['abstained']}\n")

    print(f"--- TOP RETRIEVED EVIDENCE (Top 3) ---")
    for ev in res.get("evidence", []):
        print(f"  • Rank {ev['rank']}: Doc ID {ev['doc_id']} (Score: {ev['score']:.4f})")

    print(f"\n--- EXTRACTED VERBATIM CLAIMS ---")
    if res.get("claims"):
        for i, claim in enumerate(res["claims"], 1):
            print(f"  [{i}] {claim}")
    else:
        print("  (No claims emitted — system safely abstained)")

    print(f"\n--- CITATIONS ---")
    if res.get("citations"):
        for i, cite in enumerate(res["citations"], 1):
            print(f"  [{i}] Doc {cite.get('doc_id')} | Ministry: {cite.get('ministry')} | Date: {cite.get('date')} (Session {cite.get('session')})")

    print(f"\n{'='*75}\n")


def main():
    parser = argparse.ArgumentParser(description="Query the Rajya Sabha QA RAG system.")
    parser.add_argument("question", nargs="?", default="funds allocated under Jal Jeevan Mission",
                        help="The question to ask.")
    parser.add_argument("--mode", choices=["compile", "extract"], default="compile",
                        help="Answer mode: 'compile' (synthesized narrative) or 'extract' (verbatim quotes).")
    parser.add_argument("--system", default="bm25", choices=["bm25", "dense", "hybrid"],
                        help="Retriever to use (default: bm25).")
    args = parser.parse_args()

    # If compile mode is requested and Google API key is available, run compiled RAG
    if args.mode == "compile" and os.environ.get("GOOGLE_API_KEY"):
        try:
            run_compiled_rag(args.question, system=args.system)
            return
        except Exception as e:
            print(f"[Notice: Falling back to extractive mode due to: {e}]")

    run_extractive_rag(args.question, system=args.system)


if __name__ == "__main__":
    main()
