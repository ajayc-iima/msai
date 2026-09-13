"""src/make_queries.py — Build query sets (Gold A + 5 styles + Gold B sampling)."""
import argparse
import json
import random
import re
from collections import Counter, defaultdict
from pathlib import Path

from src.common import load_jsonl, write_jsonl, sha256_file, extract_subparts


STOP = set("the a an of to in and for is on by that with as be from are was it not has have been will "
           "per govt india government ministry minister be pleased state answer answers".split())


def normalize_title(title: str) -> tuple:
    """Normalize title to STOP-filtered token set."""
    tokens = [w.lower() for w in title.split() if w.lower() not in STOP and len(w) > 2]
    return tuple(sorted(tokens))


def build_queries(meta_path: Path, queries_path: Path, gold_b_path: Path = None,
                  gold_b_n: int = 100, seed: int = 7) -> dict:
    """Build query sets from meta.jsonl."""
    random.seed(seed)
    recs = load_jsonl(meta_path)
    
    # Build top 20 boilerplate tokens across corpus
    token_counts = Counter()
    for r in recs:
        if r.get("retrievable"):
            token_counts.update(r.get("title_tokens", []))
    top20_boilerplate = set(w for w, _ in token_counts.most_common(20))

    # Build group stats
    groups = defaultdict(list)
    ministry_tokens = defaultdict(set)
    for r in recs:
        if r["retrievable"]:
            groups[tuple(r["title_tokens"])].append(r["qslno"])
            distinctive = set(r["title_tokens"]) - top20_boilerplate
            ministry_tokens[r["ministry"]].update(distinctive)
    
    # Build reverse index: distinctive token -> ministries that use it
    token_to_ministries = defaultdict(set)
    for ministry, tokens in ministry_tokens.items():
        for token in tokens:
            token_to_ministries[token].add(ministry)
    
    corpus_stats = {
        "group_sizes": {k: len(v) for k, v in groups.items()},
        "token_to_ministries": token_to_ministries,
    }
    
    # Build qslno -> record mapping for fast lookup
    rec_by_qslno = {r["qslno"]: r for r in recs}
    
    # Build queries (one per group)
    queries = []
    for title_tokens, qslno_list in groups.items():
        # Get representative record
        rep = rec_by_qslno[qslno_list[0]]
        title_text = rep["title"]
        
        # Assign style
        if not rep["retrievable"]:
            style = "answer-unavailable"
        elif rep["status"] != "ANSWERED":
            style = "answer-unavailable"
        else:
            group_size = len(qslno_list)
            if group_size >= 2:
                style = "same-topic-multi"
            else:
                has_boilerplate = bool(set(rep["title_tokens"]) & top20_boilerplate)
                has_distinctive = bool(set(rep["title_tokens"]) - top20_boilerplate)
                distinctive = set(rep["title_tokens"]) - top20_boilerplate
                is_cross = any(len(corpus_stats["token_to_ministries"].get(t, set())) > 1 for t in distinctive)
                
                # Assign title-subset to singletons with boilerplate, stripping boilerplate from title
                if has_boilerplate and has_distinctive and (hash(rep["qslno"]) % 4 == 0):
                    style = "title-subset"
                    words = title_text.split()
                    remaining = [w for w in words if w.lower().strip(",.()[]{}:;\"'") not in top20_boilerplate]
                    if remaining:
                        title_text = " ".join(remaining)
                elif is_cross:
                    style = "cross-ministry"
                else:
                    style = "title"
        
        # Determine split by answer_date year (2019+ corpus: dev 2019-2020 tunes, test 2021-2024 evaluated)
        year = int(rep["answer_date"][:4]) if rep["answer_date"] else 0
        if 2019 <= year <= 2020:
            split = "dev"
        elif 2021 <= year <= 2024:
            split = "test"
        else:
            split = "train"
        
        # Gold set (all qslno in this group)
        gold = qslno_list
        
        # Count gold outside split
        n_gold_out_of_split = 0
        for qslno in gold:
            gold_rec = rec_by_qslno[qslno]
            gyear = int(gold_rec["answer_date"][:4]) if gold_rec["answer_date"] else 0
            if split == "dev" and not (2019 <= gyear <= 2020):
                n_gold_out_of_split += 1
            elif split == "test" and not (2021 <= gyear <= 2024):
                n_gold_out_of_split += 1
        
        query = {
            "query_id": f"q_{rep['qslno']}",
            "qslno": rep["qslno"],
            "title": title_text,
            "title_tokens": list(title_tokens),
            "style": style,
            "split": split,
            "gold": gold,
            "n_gold": len(gold),
            "n_gold_out_of_split": n_gold_out_of_split,
            "ministry": rep["ministry"],
            "answer_date": rep["answer_date"],
            "status": rep["status"],
            "retrievable": rep["retrievable"],
        }
        queries.append(query)
    
    # Write all queries
    write_jsonl(queries_path, queries)
    
    # Print collision stats
    group_sizes = Counter(len(v) for v in groups.values())
    print(f"Total groups: {len(groups)}")
    print(f"Group size distribution: {dict(group_sizes.most_common(10))}")
    print(f"Ambiguous queries (size>=2): {sum(v for k,v in group_sizes.items() if k>=2)}")
    print(f"Queries written to {queries_path}")
    
    # Gold B sampling
    if gold_b_path and gold_b_n > 0:
        test_queries = [q for q in queries if q["split"] == "test" and q["retrievable"]]
        by_style = defaultdict(list)
        for q in test_queries:
            by_style[q["style"]].append(q)
        
        # Stratified sampling: 40 title, 20 title-subset, 20 same-topic-multi, 20 cross-ministry
        style_targets = {
            "title": 40,
            "title-subset": 20,
            "same-topic-multi": 20,
            "cross-ministry": 20,
        }
        
        gold_b = []
        for style, target in style_targets.items():
            pool = by_style.get(style, [])
            if not pool:
                continue
            sampled = random.sample(pool, min(target, len(pool)))
            gold_b.extend(sampled)
        
        # If we don't have enough, fill from other styles
        if len(gold_b) < gold_b_n:
            remaining = [q for q in test_queries if q not in gold_b]
            random.shuffle(remaining)
            gold_b.extend(remaining[:gold_b_n - len(gold_b)])
        
        gold_b = gold_b[:gold_b_n]
        write_jsonl(gold_b_path, gold_b)
        print(f"Gold B queries ({len(gold_b)}) written to {gold_b_path}")
    
    return {"n_queries": len(queries), "n_test": len([q for q in queries if q["split"] == "test"])}


def build_coverage_gold(corpus_path: Path, queries_path: Path, out_path: Path) -> None:
    """Build coverage gold from answer's own (a)/(b)/(c) clauses."""
    corpus = {r["qslno"]: r for r in load_jsonl(corpus_path)}
    queries = load_jsonl(queries_path)
    
    coverage_gold = []
    for q in queries:
        if q["split"] != "test" or not q["retrievable"]:
            continue
        # Get gold documents
        gold_texts = []
        for g in q["gold"]:
            if g in corpus:
                gold_texts.append(corpus[g]["text"])
        
        all_parts = []
        for text in gold_texts:
            parts = extract_subparts(text)
            all_parts.extend(parts)
        
        if all_parts:
            coverage_gold.append({
                "query_id": q["query_id"],
                "gold_subparts": all_parts,
                "n_subparts": len(all_parts),
            })
    
    write_jsonl(out_path, coverage_gold)
    print(f"Coverage gold ({len(coverage_gold)} queries) written to {out_path}")


def judge_helper(queries_path: Path, judgments_path: Path) -> None:
    """Interactive helper for Gold B annotation (blinded: source hidden).

    Accepts either gold_b_queries rows {query_id, qslno, ...} or probe rows
    {query_id, query_title, qslno, excerpt, ...}. Shows excerpt, times each
    judgment, resumes where it left off.
    """
    import time
    rows = load_jsonl(queries_path)
    existing = {}
    if judgments_path.exists():
        for j in load_jsonl(judgments_path):
            key = (j["query_id"], j["qslno"])
            existing[key] = j

    todo = [r for r in rows if (r["query_id"], r["qslno"]) not in existing]
    print(f"Judgments done: {len(existing)}, remaining: {len(todo)}")
    print("Labels: 2=answers the query, 1=on-topic but doesn't answer, 0=off-topic")
    print("Press 'q' to quit (progress saved), 's' to skip")

    for i, r in enumerate(todo):
        print(f"\n[{len(existing)+1}/{len(existing)+len(todo)-i}] Query: {r.get('query_title', r.get('title'))}")
        print(f"Style: {r.get('style')}, Ministry: {r.get('ministry')}, Date: {r.get('answer_date')}")
        print(f"--- excerpt (doc {r['qslno']}) ---")
        print((r.get("excerpt") or "[no excerpt]")[:1200])
        print("--- end excerpt ---")
        t0 = time.time()
        label = input("Label (0/1/2): ").strip()
        secs = round(time.time() - t0, 1)
        if label == 'q':
            break
        if label == 's':
            continue
        if label not in ('0', '1', '2'):
            print("Invalid label")
            continue

        reason = input("Reason (<=5 words): ").strip()[:50]

        judgment = {
            "query_id": r["query_id"],
            "qslno": r["qslno"],
            "label_0_1_2": int(label),
            "label": int(label),
            "reason": reason,
            "annotator": "human",
            "seconds": secs,
        }
        write_jsonl(judgments_path, [judgment], append=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--meta", default="data/meta.jsonl")
    ap.add_argument("--queries", default="data/queries.jsonl")
    ap.add_argument("--gold-b", type=int, default=0)
    ap.add_argument("--gold-b-out", default="data/gold_b_queries.jsonl")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--coverage-gold", action="store_true")
    ap.add_argument("--corpus", default="data/corpus.jsonl")
    ap.add_argument("--coverage-out", default="data/coverage_gold.jsonl")
    ap.add_argument("--judge", action="store_true")
    ap.add_argument("--judgments", default="data/gold_b_judgments.jsonl")
    a = ap.parse_args()
    
    if a.judge:
        judge_helper(Path(a.gold_b_out), Path(a.judgments))
        return
    
    stats = build_queries(Path(a.meta), Path(a.queries),
                          Path(a.gold_b_out) if a.gold_b > 0 else None,
                          a.gold_b, a.seed)
    
    if a.coverage_gold:
        build_coverage_gold(Path(a.corpus), Path(a.queries), Path(a.coverage_out))
    
    print(json.dumps(stats, indent=1))


if __name__ == "__main__":
    main()