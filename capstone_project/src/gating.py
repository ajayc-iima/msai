"""src/gating.py — Evidence gates: MER pre-generation + post-generation claim verification.

Merged from evidence_gate.py (MER-1/2/3) and verify_claims.py (trace + numeric check).
Both are pure functions — no API, no model.
"""
import difflib
import re
from typing import List, Dict, Any, Optional, Tuple, Set


# ── Pre-generation: Minimum Evidence Requirements (MER) ─────────────────────

MER_MIN_SPAN_CHARS = 200


def first_missing_requirement(topk_chunks: List[Dict[str, Any]], k: int = 8) -> str:
    """Determine which MER requirement fails first (only called when no doc passes all).

    Order of failure: NO_DOC (no usable doc) → NO_SPAN (docs too short)
    → NO_METADATA (missing source fields).
    """
    docs = [
        ch for ch in (topk_chunks or [])[:k]
        if ch.get("meta", {}).get("retrievable")
        and ch.get("meta", {}).get("lang") == "en"
        and ch.get("meta", {}).get("status_is_answered")
    ]
    if not docs:
        return "NO_DOC"
    span_ok = [ch for ch in docs if len((ch.get("text") or "").strip()) >= MER_MIN_SPAN_CHARS]
    if not span_ok:
        return "NO_SPAN"
    for ch in span_ok:
        m = ch.get("meta", {})
        if all(m.get(f) for f in ("ministry", "ses_no", "answer_date")) and (m.get("qslno") or m.get("qno")):
            return "MER_PASS"  # would have passed evidence_gate; unreachable in practice
    return "NO_METADATA"


def evidence_gate(topk_chunks: List[Dict[str, Any]], k: int = 8) -> Dict[str, Any]:
    """
    Pre-generation evidence gate (MER-1/2/3). Pure function.

    Returns:
        {"pass": bool, "reason": str (MER_PASS|NO_DOC|NO_SPAN|NO_METADATA), "best": dict|None}
    """
    for ch in (topk_chunks or [])[:k]:
        m = ch.get("meta", {})
        if not (m.get("retrievable") and m.get("lang") == "en" and m.get("status_is_answered")):
            continue
        if len((ch.get("text") or "").strip()) < MER_MIN_SPAN_CHARS:
            continue
        if not all(m.get(f) for f in ("ministry", "ses_no", "answer_date")):
            continue
        if not (m.get("qslno") or m.get("qno")):
            continue
        return {"pass": True, "reason": "MER_PASS", "best": ch}

    return {"pass": False, "reason": first_missing_requirement(topk_chunks), "best": None}


def log_gate_decision(query_id: str, policy: str, gate_result: Dict[str, Any],
                      rrf_top1_score: float = None, theta_ref: float = None) -> Dict[str, Any]:
    return {
        "query_id": query_id,
        "policy": policy,
        "gate": "evidence",
        "pass": gate_result["pass"],
        "reason": gate_result["reason"],
        "best_doc": gate_result["best"]["meta"].get("qslno") if gate_result["best"] else None,
        "rrf_top1_score": rrf_top1_score,
        "theta_ref": theta_ref,
    }


# ── Post-generation: claim verification ──────────────────────────────────────

def norm(text: str) -> str:
    """Normalize: lowercase, alphanumeric only, hyphens to spaces."""
    if not text:
        return ""
    return " ".join(re.findall(r"[a-z0-9]+", text.lower().replace("-", " ")))


def trigrams(text: str) -> Set[str]:
    text = norm(text)
    if len(text) < 3:
        return {text} if text else set()
    return {text[i:i+3] for i in range(len(text) - 2)}


def trace_score(claim: str, chunk: str) -> float:
    """max(LCS-ratio, trigram-overlap) on identically-normalized text."""
    c, n = norm(claim), norm(chunk)
    if not c:
        return 0.0
    matcher = difflib.SequenceMatcher(None, c, n, autojunk=False)
    lcs_ratio = matcher.find_longest_match(0, len(c), 0, len(n)).size / len(c)
    tc, tn = trigrams(c), trigrams(n)
    trigram_overlap = len(tc & tn) / len(tc) if tc else 0.0
    return max(lcs_ratio, trigram_overlap)


NUMBER_WORDS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
    "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20,
    "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70,
    "eighty": 80, "ninety": 90,
}

def extract_numbers(text: str) -> Set[str]:
    """All numbers from text (digits + spelled 0-99), normalized strings."""
    numbers = set()
    for match in re.finditer(r'\b\d[\d,.]*\b', text):
        num_str = match.group().replace(",", "")
        try:
            num_str = str(float(num_str)) if "." in num_str else str(int(num_str))
            numbers.add(num_str)
        except ValueError:
            pass
    words = re.findall(r'\b[a-z]+\b', text.lower())
    i = 0
    while i < len(words):
        word = words[i]
        if word in NUMBER_WORDS:
            val = NUMBER_WORDS[word]
            if val >= 20 and val % 10 == 0 and i + 1 < len(words):
                nxt = words[i + 1]
                if nxt in NUMBER_WORDS and NUMBER_WORDS[nxt] < 10:
                    val += NUMBER_WORDS[nxt]
                    i += 1
            numbers.add(str(val))
        i += 1
    return numbers


def numeric_check(claim: str, chunk: str) -> bool:
    claim_nums = extract_numbers(claim)
    if not claim_nums:
        return True
    return claim_nums.issubset(extract_numbers(chunk))


def claim_supported(claim: str, chunks: List[str], tau: float = 0.80) -> Tuple[bool, float, bool]:
    """(supported, best_trace_score, numeric_ok) — claim vs any chunk."""
    if not chunks:
        return False, 0.0, True
    best_score = 0.0
    best_chunk = None
    for chunk in chunks:
        score = trace_score(claim, chunk)
        if score > best_score:
            best_score, best_chunk = score, chunk
    trace_ok = best_score >= tau
    numeric_ok = numeric_check(claim, best_chunk) if best_chunk else False
    return trace_ok and numeric_ok, round(best_score, 3), numeric_ok


def verify_answer_claims(claims: List[str], citations: List[Dict[str, Any]],
                         tau: float = 0.80) -> Dict[str, Any]:
    """Post-generation verification. One unsupported claim fails the whole answer."""
    results = []
    skipped_short = 0
    unsupported = []

    for i, claim in enumerate(claims):
        content_tokens = len([w for w in norm(claim).split() if len(w) > 2])
        if content_tokens < 5:
            skipped_short += 1
            results.append({"claim": claim, "supported": True, "trace_score": 1.0,
                            "numeric_ok": True, "chunk_idx": -1, "skipped": True})
            continue

        claim_chunks = []
        if i < len(citations):
            span = citations[i].get("span", "")
            if span:
                claim_chunks.append(span)

        supported, score, numeric_ok = claim_supported(claim, claim_chunks, tau)
        results.append({"claim": claim, "supported": supported, "trace_score": score,
                        "numeric_ok": numeric_ok,
                        "chunk_idx": i if i < len(citations) else -1, "skipped": False})
        if not supported:
            unsupported.append(claim)

    return {
        "claims": results,
        "all_supported": len(unsupported) == 0,
        "unsupported_claims": unsupported,
        "skipped_short_claims": skipped_short,
    }


# ── Adversarial tests (component check) ──────────────────────────────────────

MER_ADVERSARIAL = [
    ("verbatim_copy",
     [{"meta": {"retrievable": True, "lang": "en", "status_is_answered": True,
                "ministry": "HOME AFFAIRS", "ses_no": 250, "answer_date": "2020-03-15",
                "qslno": 12345}, "text": "The ministry has allocated 500 crore for the scheme." * 10}],
     True, "MER_PASS"),
    ("no_retrievable_doc",
     [{"meta": {"retrievable": False, "lang": "en", "status_is_answered": True,
                "ministry": "HOME AFFAIRS", "ses_no": 250, "answer_date": "2020-03-15",
                "qslno": 12345}, "text": "Some text." * 10}],
     False, "NO_DOC"),
    ("hindi_only",
     [{"meta": {"retrievable": True, "lang": "hi", "status_is_answered": True,
                "ministry": "HOME AFFAIRS", "ses_no": 250, "answer_date": "2020-03-15",
                "qslno": 12345}, "text": "Some text." * 10}],
     False, "NO_DOC"),
    ("unanswered_status",
     [{"meta": {"retrievable": True, "lang": "en", "status_is_answered": False,
                "ministry": "HOME AFFAIRS", "ses_no": 250, "answer_date": "2020-03-15",
                "qslno": 12345}, "text": "The question is pending." * 10}],
     False, "NO_DOC"),
    ("short_span",
     [{"meta": {"retrievable": True, "lang": "en", "status_is_answered": True,
                "ministry": "HOME AFFAIRS", "ses_no": 250, "answer_date": "2020-03-15",
                "qslno": 12345}, "text": "Short."}],
     False, "NO_SPAN"),
    ("missing_ministry",
     [{"meta": {"retrievable": True, "lang": "en", "status_is_answered": True,
                "ses_no": 250, "answer_date": "2020-03-15", "qslno": 12345},
       "text": "Text." * 100}],
     False, "NO_METADATA"),
]

# Known limitations (PLAN §5.4, kept honest not aspirational):
#   - minor_paraphrase / reordered_clauses score 0.74/0.78 (< 0.80) — below threshold,
#     so they are demoted; the tracer is conservative, not universal-paraphrase-proof.
#   - contradiction (negation-by-word-order) scores 0.90 — NOT caught by trace+numeric;
#     documented as the reason the LLM-judge axis exists. Expected=True (bypass) is the
#     honest contract of this deterministic rule.
VERIFY_ADVERSARIAL = [
    ("verbatim_copy",
     "The ministry has allocated 500 crore for the scheme.",
     ["The ministry has allocated 500 crore for the scheme." * 10], True),
    ("minor_paraphrase_below_tau",
     "The ministry has earmarked 500 crore for this scheme.",
     ["The ministry has allocated 500 crore for the scheme." * 10], False),
    ("reordered_clauses_below_tau",
     "For the scheme, 500 crore has been allocated by the ministry.",
     ["The ministry has allocated 500 crore for the scheme." * 10], False),
    ("fabricated_number",
     "The ministry has allocated 999 crore for the scheme.",
     ["The ministry has allocated 500 crore for the scheme." * 10], False),
    ("non_sequitur",
     "The weather is nice today and birds fly south.",
     ["The ministry has allocated 500 crore for the scheme." * 10], False),
    ("negation_by_word_order_known_gap",
     "The ministry has NOT allocated 500 crore for the scheme.",
     ["The ministry has allocated 500 crore for the scheme." * 10], True),
    ("year_flip",
     "In 2021, the ministry allocated 500 crore.",
     ["In 2020, the ministry allocated 500 crore." * 10], False),
    ("missing_number",
     "The ministry allocated 40 crore.",
     ["The ministry allocated thirty-two crore." * 10], False),
]


def run_gate_tests() -> bool:
    """Run both adversarial suites. Returns True if all pass."""
    all_pass = True
    for desc, chunks, expected_pass, expected_reason in MER_ADVERSARIAL:
        result = evidence_gate(chunks)
        ok = result["pass"] == expected_pass and result["reason"] == expected_reason
        print(f"  {'PASS' if ok else 'FAIL'} [MER] {desc} -> pass={result['pass']}, reason={result['reason']}")
        all_pass &= ok
    for desc, claim, chunks, expected in VERIFY_ADVERSARIAL:
        supported, score, numeric_ok = claim_supported(claim, chunks, tau=0.80)
        ok = supported == expected
        print(f"  {'PASS' if ok else 'FAIL'} [verify] {desc} -> supported={supported}, trace={score:.3f} (expected={expected})")
        all_pass &= ok
    return all_pass


if __name__ == "__main__":
    print("Running adversarial gate tests...")
    success = run_gate_tests()
    print(f"\nAll tests {'PASSED' if success else 'FAILED'}")
    raise SystemExit(0 if success else 1)