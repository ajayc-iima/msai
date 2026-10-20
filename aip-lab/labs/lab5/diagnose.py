#!/usr/bin/env python3
"""Lab 5 - the failure classifier.

    python labs/lab5/diagnose.py --input reports/lab4.json
    python labs/lab5/diagnose.py --input reports/lab4.json --pareto
    python labs/lab5/diagnose.py --input reports/lab5_v1.json --save reports/lab5_diagnosis_v1.json

Implements the T4 s5 diagnostic tree. Everything that can be decided by code
is decided by code; mode 2 needs your eyes and the script says so.

--------------------------------------------------------------------------
WHAT I CHANGED IN THE SHIPPED `classify`, AND WHY (Lab 5, Part A)
--------------------------------------------------------------------------
The shipped version asked the gold-context question and returned mode 6 on
"gold context does not fix it" BEFORE it ever asked whether the gold document
reached the generator. On our Lab 4 run that produced 17 failures out of 17
in mode 6 - a flat distribution, which the lab handout itself flags as the
symptom of mis-classification.

The tree in CONCEPTS.md reads the other way round, and the important
distinction is not "did gold context help" but "**was the material already in
front of the generator?**":

  * material ABSENT from the delivered context  -> retrieval failed. The
    gold-context probe fixing it is a *symptom* of that, not a generation
    verdict. Then: was the gold doc in the final k (mode 4/5), not even in
    the top 30 (mode 3/2)?
  * material PRESENT in the delivered context and the answer still wrong
    -> generation failed (mode 6). The probe corroborates: gold context
    fixing it here proves the generator was capable and was distracted.
  * material absent, right document delivered, but the answer-carrying chunk
    of that document is not in the window -> mode 2 (chunk boundary), which
    is the branch the script cannot fully automate and hands to you.

So the load-bearing addition is `answer_span_in_context`: a deterministic
check of whether the gold answer's own numbers and content words survive
into the exact context the generator was given. It costs nothing, it is
reproducible, and it is what lets modes 2/3/4/5 and mode 6 stop being
mutually exclusive by accident.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from aip.chunking import markdown_chunks
from labs.lab3.search import load_corpus, load_questions

MODES = {
    1: "missing_content",
    2: "chunk_boundary",
    3: "embedding_mismatch",
    4: "ranking",
    5: "reranker",
    6: "generation",
    7: "presentation",
}

_STOP = frozenset(
    ["the", "and", "for", "with", "that", "this", "from", "are", "was", "were", "have", "has", "not", "but", "any", "all", "can", "may", "will", "its", "their", "there", "here", "which", "what", "when", "who", "whom", "how", "why", "into", "onto", "than", "then", "also", "such", "some", "more", "most", "other", "same", "only", "over", "under", "out", "up", "down", "do", "does", "did", "done", "been", "being", "be", "to", "of", "in", "on", "at", "by", "as", "if", "or", "nor", "a", "an"]
)
_TOKEN = re.compile(r"[a-z0-9]+(?:\.[a-z0-9]+)?")
_NUM = re.compile(r"\d+(?:[.,]\d+)*%?")
_REFUSE_PREFIX = re.compile(
    r"^\s*(?:PARTIAL\s+)?REFUSE(?:\s+on\s+[^.]+)?\.\s*", re.IGNORECASE
)


def _norm(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^\w\s.%₹$]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _content_tokens(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(_norm(text)) if len(t) > 2 and t not in _STOP]


def _numbers(text: str) -> list[str]:
    return [n.replace(",", "") for n in _NUM.findall(text)]


def _num_present(num: str, hay: str) -> bool:
    """Match 30 / 30.0 / 1,00,000 style numbers with light normalisation."""
    variants = {num, num.lstrip("0") or "0"}
    if "." in num:
        variants.add(num.rstrip("0").rstrip("."))
    return any(v and v in hay for v in variants)


def answer_in_corpus(gold_answer: str, corpus: dict[str, str],
                     relevant_docs: list[str]) -> bool:
    """Mode 1 test: is the gold answer's content actually in the relevant docs?

    Improvements over the shipped substring/overlap check:
      - REFUSE / PARTIAL REFUSE markers are handled explicitly: a full REFUSE
        means the needed content is absent by definition (mode 1); PARTIAL
        only checks the supported remainder.
      - numbers are extracted and required to appear (insurance answers turn
        on 30 days / Rs 5 lakh / 80%, which whole-string matching misses when
        the corpus writes them differently).
      - content tokens use normalised containment against a windowed corpus
        string, so punctuation and light rewording do not flip the verdict.
    """
    raw = gold_answer or ""
    full_refuse = bool(re.match(r"^\s*REFUSE\b", raw, re.IGNORECASE))
    partial_refuse = bool(re.match(r"^\s*PARTIAL\s+REFUSE\b", raw, re.IGNORECASE))
    if full_refuse and not partial_refuse:
        return False

    body = _REFUSE_PREFIX.sub("", raw) if partial_refuse else raw
    text = _norm(" ".join(corpus.get(d, "") for d in relevant_docs))
    if not text:
        return False

    ans = _norm(body)
    if not ans:
        return True

    for n in _numbers(ans):
        if not _num_present(n, text):
            return False

    tokens = _content_tokens(body)
    if not tokens:
        return True
    # Significant coverage: most content words must appear somewhere in the
    # relevant documents. 0.5 on len>2 tokens is stricter than the old 0.4
    # on len>4, after stopword removal.
    hits = sum(1 for t in tokens if t in text)
    return hits / len(tokens) >= 0.5


# ---------------------------------------------------------------------------
# the deterministic check the shipped classifier was missing
# ---------------------------------------------------------------------------
def answer_span_in_context(gold_answer: str, context: str,
                           *, num_threshold: float = 1.0,
                           token_threshold: float = 0.8) -> tuple[bool, str]:
    """Did the gold answer's own content survive into the delivered context?

    Returns (present, evidence). "present" means: every number in the gold
    answer appears in the context AND at least `token_threshold` of its
    content words do.

    Why numbers are all-or-nothing and words are 80%: a number is the part a
    reader acts on, so one missing figure is a missing answer. Content words
    get slack because the corpus and the gold answer legitimately word the
    same fact differently ("eligibility ratio" vs "proportionate deduction").

    A PARTIAL REFUSE gold answer is checked on its supported part only - the
    declined part is *supposed* to be missing, and demanding it would report
    every refusal as a retrieval failure.
    """
    raw = gold_answer or ""
    partial_refuse = bool(re.match(r"^\s*PARTIAL\s+REFUSE\b", raw, re.IGNORECASE))
    if re.match(r"^\s*REFUSE\b", raw, re.IGNORECASE) and not partial_refuse:
        # Nothing to find: the corpus is *supposed* not to contain it.
        return False, "gold answer is a full REFUSE; nothing to look for"

    body = _REFUSE_PREFIX.sub("", raw) if partial_refuse else raw
    hay = _norm(context)
    nums = _numbers(_norm(body))
    missing_nums = [n for n in nums if not _num_present(n, hay)]
    toks = _content_tokens(body)
    missing_toks = [t for t in toks if t not in hay]
    coverage = 1.0 if not toks else 1 - len(missing_toks) / len(toks)

    present = (not missing_nums) and coverage >= token_threshold
    bits = [f"{coverage:.0%} of {len(toks)} content words"]
    if missing_nums:
        bits.append(f"missing numbers {missing_nums}")
    if missing_toks:
        bits.append(f"missing words {sorted(set(missing_toks))[:8]}")
    if not toks:
        bits.append("no content words to check")
    return present, "; ".join(bits)


# ---------------------------------------------------------------------------
# probes
# ---------------------------------------------------------------------------
_RETRIEVER_CACHE: dict = {}
_GOLD_FIX_CACHE: dict[str, bool | None] = {}
_GOLDWINDOW_CACHE: dict[str, bool | None] = {}


def _retriever():
    if "r" not in _RETRIEVER_CACHE:
        from labs.lab4.evaluate import build_retriever
        _RETRIEVER_CACHE["r"] = build_retriever()
    return _RETRIEVER_CACHE["r"]


def _gold_passage(q: dict, corpus: dict[str, str]) -> str:
    """Best single chunk from the gold docs for the mode-3 self-retrieval test."""
    ans_tokens = set(_content_tokens(q.get("gold_answer") or ""))
    best, best_score = "", -1.0
    for d in q.get("relevant_docs") or []:
        text = corpus.get(d, "")
        if not text:
            continue
        for chunk in markdown_chunks(text, d, size=400):
            toks = set(_content_tokens(chunk.text))
            if not toks:
                continue
            score = len(ans_tokens & toks) / max(len(ans_tokens), 1)
            if score > best_score:
                best_score, best = score, chunk.text
    if not best:
        for d in q.get("relevant_docs") or []:
            if corpus.get(d):
                return corpus[d][:600]
    return best


def _gold_context_fixes(q: dict, corpus: dict[str, str]) -> bool | None:
    """One generate + one judge: does gold context recover correctness >= 2?"""
    key = q["id"]
    if key in _GOLD_FIX_CACHE:
        return _GOLD_FIX_CACHE[key]
    docs = [corpus[d] for d in q.get("relevant_docs") or [] if d in corpus]
    if not docs:
        _GOLD_FIX_CACHE[key] = False
        return False
    try:
        from labs.lab4.evaluate import judge_correctness
        from labs.lab4.rag import answer_with_gold_context

        g = answer_with_gold_context(q["question"], docs)
        score = judge_correctness(q["question"], g.text, q["gold_answer"])
        fixed = score is not None and score >= 2
    except Exception:  # noqa: BLE001 - probe failure means "unknown", not crash
        fixed = None
    _GOLD_FIX_CACHE[key] = fixed
    return fixed


_VARIANT = {"name": "v1"}


def _window_hits(question: str) -> list:
    """The chunks the named arm actually hands the generator.

    D3 re-classifies the failures of a v2 arm, so the window has to be rebuilt
    with that arm's retrieval -- a reranked window is not the dense one, and
    re-classifying a reranked run against dense windows would be measuring the
    wrong system. v2a has no second stage, so its window is the dense one.
    """
    from labs.lab5.pipeline import VARIANTS

    if not VARIANTS.get(_VARIANT["name"], {}).get("rerank", False):
        return _retriever().search(question, k=12)[:5]
    from labs.lab5.pipeline import _reranker
    return _reranker().rerank(question, _retriever().search(question, k=30), k=5)


def _delivered_context(question: str, k: int = 12, final_k: int = 5) -> tuple[str, int]:
    """Rebuild the exact context the generator was handed.

    Retrieval here is exact (numpy matmul, no ANN) and the embedding model is
    unchanged, so recomputing from the question reproduces the window
    deterministically. The run files store document ids only, so the chunk text
    has to be rebuilt.

    Returns (context_text, n_chunks). The chunk count is NOT the number of
    distinct documents: Q04's window is five chunks of ONE document, and
    reporting "1" there would read as though the generator had been given a
    single passage.
    """
    from aip.retrieval import format_context

    try:
        window = _window_hits(question)
    except Exception:  # noqa: BLE001 - no index -> no span evidence
        return "", 0
    return format_context(window), len(window)


def _answer_from_hits(question: str, hits) -> str:
    """Generate + validate + repair from an explicit hit list.

    Same contract as labs/lab4/rag.answer_question -- imported rather than
    reimplemented, so a probe cannot disagree with the system it probes.
    """
    from labs.lab4.rag import _generate, _repair_note, validate_answer

    text, finish = _generate(question, list(hits), tier="MAIN")
    v = validate_answer(text, len(hits), finish)
    if not v["valid"] and not v["refused"]:
        text, finish = _generate(question, list(hits), tier="MAIN",
                                 max_tokens=1200 if v["truncated"] else 600,
                                 correction=_repair_note(v, len(hits)))
        v2 = validate_answer(text, len(hits), finish)
        if not v2["valid"]:
            from labs.lab4.rag import REFUSAL
            text = REFUSAL
    return text


def _gold_docs_window_fixes(q: dict) -> bool | None:
    """THE CONFOUND-CONTROL PROBE. Same experiment as _gold_context_fixes, but
    holding the context SIZE fixed.

    `answer_with_gold_context` (Lab 4 E2) feeds the generator every chunk of
    every gold document at size=800 -- for Q04 that is 11 chunks where the
    pipeline would have shown 5 at size=400. So when that probe fails to fix an
    answer you cannot tell "the generator cannot do this" from "the generator
    cannot do this with twice the context it is used to".

    This probe keeps the pipeline's own geometry and changes one thing: the
    retriever is not allowed to return anything from a non-gold document. If
    THIS fixes the answer, the generator is capable and the delivered window
    was the problem -- whether because the window was short (mode 4) or
    because the extra length of the gold context was itself the obstacle.
    """
    key = q["id"]
    if key in _GOLDWINDOW_CACHE:
        return _GOLDWINDOW_CACHE[key]
    try:
        hits = [h for h in _retriever().search(q["question"], k=30)
                if h.doc_id in set(q.get("relevant_docs") or [])][:5]
        if not hits:
            _GOLDWINDOW_CACHE[key] = None
            return None
        from labs.lab4.evaluate import judge_correctness
        text = _answer_from_hits(q["question"], hits)
        score = judge_correctness(q["question"], text, q["gold_answer"])
        fixed = score is not None and score >= 2
    except Exception:  # noqa: BLE001
        fixed = None
    _GOLDWINDOW_CACHE[key] = fixed
    return fixed


# ---------------------------------------------------------------------------
# the tree
# ---------------------------------------------------------------------------
def _doc_ranks(question: str, relevant: set[str], k: int = 30,
               probe: bool = True) -> dict[str, int | None]:
    """Best (lowest) rank each gold document reaches in the top-k.

    Generalises the tree's "is it in the top 30?" to multi-document questions.
    Q20 needs four documents; asking only whether *one* of them was in the top
    30 flatters the retriever, because one of four being found is not the same
    as the answer being findable. So we track every gold document and let the
    deepest miss decide the mode.

    Ranks are taken from the arm's own stage-1 pool (dense k=30), which is what
    both the reranker and final_k draw from -- so the number means the same thing
    before and after the fix.
    """
    if not probe or not relevant:
        return {d: None for d in relevant}
    try:
        hits = _retriever().search(question, k=k)
    except Exception:  # noqa: BLE001 - no probe -> unknown, not "buried"
        return {d: None for d in relevant}
    out: dict[str, int | None] = {}
    for d in relevant:
        ranks = [h.rank + 1 for h in hits if h.doc_id == d]
        out[d] = min(ranks) if ranks else None
    return out


def _never_retrieved(q: dict, ranks: dict[str, int | None]) -> list[str]:
    """Gold docs that no chunk of reached even the top 30."""
    return sorted(d for d, r in ranks.items() if r is None)


def _buried(ranks: dict[str, int | None], final_docs: set[str]) -> list[str]:
    """Gold docs that made the top 30 but never made the final k."""
    return sorted(d for d, r in ranks.items() if r is not None and d not in final_docs)


def _self_retrieves(q: dict, doc_id: str, corpus: dict[str, str]) -> bool:
    """Mode-3 test, scoped to one document: does its own text retrieve itself?"""
    sub = {doc_id: corpus[doc_id]} if doc_id in corpus else {}
    if not sub:
        return False
    one = dict(q)
    one["relevant_docs"] = [doc_id]
    passage = _gold_passage(one, sub)
    if not passage:
        return False
    try:
        return any(h.doc_id == doc_id for h in _retriever().search(passage, k=10))
    except Exception:  # noqa: BLE001
        return False


def classify(row: dict, q: dict, corpus: dict[str, str], *,
             gold_context_fixes_it: bool | None = None,
             in_top_30: bool | None = None,
             dropped_by_reranker: bool | None = None,
             probe: bool = True) -> tuple[int, str]:
    """Walk the T4 s5 diagnostic tree. Returns (mode, evidence).

    THREE SIGNALS, AND THE ORDER THEY ARE ASKED IN IS THE WHOLE ARGUMENT:

      can_full    every gold chunk, size 800 (Lab 4's E2 gold-context probe).
                  This is the generator's capability CEILING.
      can_window  5 chunks drawn only from gold documents, size 400 -- the
                  pipeline's own geometry with the retriever hobbled.
                  This asks a different question: is a five-slot window ENOUGH?
      span_ok     do the gold answer's numbers and content words survive into
                  the delivered window? Deterministic, free, no sampling.

      1. can_full is False            -> mode 6. The generator cannot do this
         even handed everything. No retrieval fix can recover the question.
      2. span_ok and can_window       -> mode 6. The window was good enough and
                                            the generator under-used it.
      3. span_ok and not can_window   -> mode 4. The window is too SMALL. Q34 is
         the proof case and the reason probe 2 exists: its span check looks
         fine, yet filling all five slots with the best gold chunks still
         fails, while more gold material succeeds. That is a context budget,
         not a ranking-quality problem and not a generation problem.
      4. not span_ok                  -> retrieval failed. The tree's branches,
         decided by how deep the missing material sat: never in the top 30 and
         it self-retrieves -> 3; never in the top 30 and it does not -> 2; in
         the top 30 but cut by final_k -> 4 (or 5 with a reranker); right
         document delivered, wrong chunk of it -> 2.

    Why not the gold-context probe alone: it asks "would MORE context have
    helped", which is not the same question as "was the context sufficient".
    On Q06 the entire gold answer sat in window slot 1 and the model still
    dropped half of it; the probe reports "fixes it", and reading that as proof
    that retrieval failed would send the fix to the wrong stage.
    """
    relevant = set(q.get("relevant_docs") or [])
    final_docs = set(row.get("retrieved") or [])

    # Mode 7 first: right answer, wrong citation. Not a retrieval failure at all.
    if row.get("correctness", 0) >= 2 and not row.get("citations_valid", True):
        return 7, f"correct answer, invalid citations {row.get('invalid_citations')}"

    # Mode 1: is the answer even in the corpus?
    if not answer_in_corpus(q["gold_answer"], corpus, q["relevant_docs"]):
        return 1, "gold answer content not found in the relevant documents"

    ctx, n_chunks = _delivered_context(q["question"])
    span_ok, span_ev = answer_span_in_context(q["gold_answer"], ctx)

    # --- three signals ----------------------------------------------------
    # can_full   : every gold chunk at size 800     -> the capability CEILING
    # can_window : 5 chunks, gold documents only     -> is a 5-slot window enough?
    # span_ok    : was the gold span already there? -> deterministic and free
    if probe:
        can_window = _gold_docs_window_fixes(q)
        if gold_context_fixes_it is None:
            gold_context_fixes_it = _gold_context_fixes(q, corpus)
        can_full = gold_context_fixes_it
    else:
        can_window, can_full = None, gold_context_fixes_it

    notes = (f"all-gold-material fixes it: {can_full}; "
             f"5 gold-only chunks fix it: {can_window}; "
             f"answer span {'PRESENT' if span_ok else 'ABSENT'} in the delivered "
             f"{n_chunks}-chunk window ({span_ev})")

    # --- Q1: is the generator capable at all? ------------------------------
    capable = can_full if can_full is not None else can_window
    if capable is False:
        return 6, ("the generator cannot produce this answer even handed every "
                   f"gold chunk -- {notes}")

    # --- Q2: capable. Was the delivered window good enough? ----------------
    if span_ok and can_window is not False:
        extra = ("the delivered window was sufficient and the generator "
                 "under-used it" if can_full is True else
                 "more context would not have helped either")
        return 6, f"{notes} -> {extra}"

    if span_ok and can_window is False:
        # The case that justifies the third probe. The span check looks fine,
        # yet filling the same five slots with the BEST chunks from gold
        # documents still fails while more gold material succeeds. So the
        # binding constraint is the size of the window -- neither the quality of
        # its contents nor the generator.
        return 4, (f"{notes} -> a 5-chunk window cannot hold this answer even "
                   f"when every slot is filled with a gold-document chunk, while "
                   f"more gold material fixes it. Context budget: not a ranking "
                   f"quality problem and not a generation problem")

    # --- Q3: the window was short of material. How deep did it sit? --------
    ranks = _doc_ranks(q["question"], relevant, probe=probe)
    never = _never_retrieved(q, ranks)
    buried = _buried(ranks, final_docs)

    if never:
        if not probe:
            return 2, (f"needs_human_check: gold doc(s) {never} absent from the "
                       "top 30 (no self-retrieval probe offline)")
        if _self_retrieves(q, never[0], corpus):
            return 3, (f"generator could do it ({notes}) but gold doc "
                       f"{never[0]} never reached the top 30, while its own text "
                       "retrieves it by its own text -> query/embedding mismatch")
        return 2, (f"generator could do it ({notes}) but gold doc {never[0]} "
                   "never reached the top 30 AND its own text does not retrieve "
                   "it -> needs_human_check (boundary vs index)")

    if buried:
        if dropped_by_reranker:
            return 5, (f"gold doc(s) {buried} were in the top 30 "
                       f"(best ranks {[ranks[d] for d in buried]}) and the reranker "
                       "dropped them")
        return 4, (f"generator could do it ({notes}), but gold doc(s) {buried} "
                   f"were in the top 30 (best ranks {[ranks[d] for d in buried]}) "
                   f"and never reached the {n_chunks}-chunk window")

    return 2, (f"generator could do it ({notes}) and every gold doc reached "
               f"the window, but the answer span did not ({span_ev}) -- the "
               "answer-carrying chunk inside the right document lost the cut")


def pareto(tally: Counter) -> str:
    total = sum(tally.values()) or 1
    lines, cum = ["failure mode          n    share   cumulative"], 0
    for mode, n in tally.most_common():
        cum += n
        bar = "█" * round(30 * n / total)
        lines.append(f"{MODES[mode]:<20} {n:>3}   {n/total:>5.1%}   "
                     f"{cum/total:>5.1%}  {bar}")
    return "\n".join(lines)


def tally_table(tally: Counter) -> str:
    """The A1 block: every one of the seven modes, including the zeroes."""
    total = sum(tally.values()) or 1
    out = [f"mode 1  missing content     n = {tally.get(1, 0)}",
           f"mode 2  chunk boundary      n = {tally.get(2, 0)}",
           f"mode 3  embedding mismatch  n = {tally.get(3, 0)}",
           f"mode 4  ranking             n = {tally.get(4, 0)}",
           f"mode 5  reranker            n = {tally.get(5, 0)}",
           f"mode 6  generation          n = {tally.get(6, 0)}",
           f"mode 7  presentation        n = {tally.get(7, 0)}",
           f"{'':<26}     --------",
           f"{'total':<26}     {total:>3}"]
    return "\n".join(out)


def _is_failure(r: dict) -> bool:
    c = r.get("correctness")
    return (c is not None and c < 2) or not r.get("citations_valid", True)


HAND_LABELS = ROOT / "labs/lab5/hand_labels.json"


def load_hand_labels(basis: str | None = None,
                      input_name: str = "reports/lab4.json") -> dict[str, dict]:
    """My Part A2 (and D3) judgements. Optional, keyed by question id.

    The v1-based labels live under "labels" and apply to reports/lab4.json;
    the v2b re-classification labels live under "labels_v2b" and apply to
    reports/lab5_v2b.json. Keeping them separate is what makes the D3
    comparison honest: the same question can (and does) change modes between
    arms, and one shared label set would hide that.
    """
    if not HAND_LABELS.exists():
        return {}
    data = json.loads(HAND_LABELS.read_text(encoding="utf-8"))
    key = "labels_v2b" if input_name == "reports/lab5_v2b.json" else "labels"
    labels = data.get(key, {})
    if basis and data.get("basis") and data["basis"] != basis:
        return {}
    return labels


def diagnose(rows: list[dict], *, probe: bool = True,
             use_lab4_pipeline: bool = True,
             input_name: str = "reports/lab4.json",
             use_hand_labels: bool = True,
             args_v2_variant: str = "v2b") -> tuple[list[dict], Counter]:
    """Classify every failing row. Returns (records, tally)."""
    questions = {q["id"]: q for q in load_questions(include_unanswerable=True)}
    corpus = load_corpus()
    if probe:
        # 429s must not silently become refusals inside a probe either.
        from labs.lab5.pipeline import harden_transport
        harden_transport()
    if not use_lab4_pipeline:
        from labs.lab5 import pipeline
        pipeline.activate("v2a" if args_v2_variant == "v2a" else "v2b")
        _VARIANT["name"] = args_v2_variant
    labels = load_hand_labels(input_name=input_name) if use_hand_labels else {}

    out: list[dict] = []
    tally: Counter = Counter()
    failures = [r for r in rows if _is_failure(r)]
    print(f"{len(failures)} failures out of {len(rows)}\n")

    for r in failures:
        q = questions[r["id"]]
        try:
            mode, evidence = classify(r, q, corpus,
                                     dropped_by_reranker=False,
                                     probe=probe)
        except Exception as exc:  # noqa: BLE001 - one bad probe != dead diagnosis
            mode, evidence = 2, f"needs_human_check: probe error {type(exc).__name__}"
        script_mode = mode

        # Part A2: my judgement wins over the script's, and the disagreement
        # is recorded rather than hidden -- an override with no reason is just
        # a second opinion.
        label = labels.get(r["id"])
        human = ""
        if label:
            mode = int(label["mode"])
            human = label.get("reason", "")
            if "looked_at" in label:
                human = f"LOOKED AT: {label['looked_at']}\n    JUDGEMENT: {human}"
        rec = {
            "id": r["id"], "kind": q["kind"], "mode": mode,
            "mode_name": MODES[mode],
            "script_mode": script_mode,
            "overrode_script": bool(label and mode != script_mode),
            "needs_human_check": not bool(label) and (
                evidence.startswith("needs_human_check") or mode == 2),
            "gold_docs": q.get("relevant_docs", []),
            "retrieved_docs": r.get("retrieved", []),
            "evidence": evidence,
            "human_note": human or None,
            "question": q["question"],
            "gold_answer": q.get("gold_answer", ""),
            "lab4_correctness": r.get("correctness"),
            "answer": r["answer"][:300],
        }
        tally[mode] += 1
        out.append(rec)
        flag = " [HAND]" if rec["overrode_script"] else ""
        print(f"  {r['id']:<5} {MODES[mode]:<20} {evidence}{flag}", flush=True)

    n_human = sum(1 for r in out if r["needs_human_check"])
    n_over = sum(1 for r in out if r["overrode_script"])
    print(f"\n{n_over} hand label(s) override the script; "
          f"{n_human} case(s) still need a human look (Part A2).")
    return out, tally


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="reports/lab4.json")
    ap.add_argument("--pareto", action="store_true")
    ap.add_argument("--save", default="reports/lab5_diagnosis.json")
    ap.add_argument("--summary", default="",
                    help="also write the tally + pareto as JSON here")
    ap.add_argument("--v2", action="store_true",
                    help="rebuild the delivered context with the Lab 5 v2 pipeline")
    ap.add_argument("--variant", default="v2b", choices=["v1", "v2a", "v2b"],
                    help="which arm's retrieval to rebuild the window with "
                         "(only meaningful with --v2)")
    ap.add_argument("--ignore-hand-labels", action="store_true",
                    help="report the script's own verdict, before my Part A2 "
                         "overrides -- use this to check what the probes alone say")
    ap.add_argument("--no-llm", action="store_true",
                    help="skip gold-context / top-30 probes (offline triage)")
    args = ap.parse_args()

    rows = json.loads((ROOT / args.input).read_text(encoding="utf-8"))
    out, tally = diagnose(rows, probe=not args.no_llm,
                          use_lab4_pipeline=not args.v2,
                          input_name=args.input,
                          use_hand_labels=not args.ignore_hand_labels,
                          args_v2_variant=args.variant)

    print("\n" + tally_table(tally))
    print("\n" + pareto(tally))
    n_human = sum(1 for r in out if r["needs_human_check"])
    print(f"\n{n_human} case(s) need a human look (Part A2). "
          "Open the chunks around the gold answer and record the judgement.")

    p = ROOT / args.save
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nsaved -> {p}")

    if args.summary:
        s = ROOT / args.summary
        s.parent.mkdir(parents=True, exist_ok=True)
        s.write_text(json.dumps({
            "input": args.input,
            "n_rows": len(rows),
            "n_failures": sum(tally.values()),
            "tally": {MODES[m]: tally.get(m, 0) for m in sorted(MODES)},
            "tally_by_id": {MODES[r["mode"]]: r["id"] for r in out},
            "script_tally": {MODES[m]: sum(1 for r in out if r["script_mode"] == m)
                             for m in sorted(MODES)},
            "overridden": [r["id"] for r in out if r["overrode_script"]],
            "needs_human_check": [r["id"] for r in out if r["needs_human_check"]],
            "pareto": pareto(tally),
        }, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"saved -> {s}")


if __name__ == "__main__":
    main()
