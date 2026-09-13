"""Build Gold B probe file: 2 blinded candidates/query (Gold-A member + BM25 top-1
non-member), with answer-side excerpts pre-extracted. ~200 judgments total.
Deviation note: PLAN specifies hybrid/dense top-1 as candidate 2; dense-full is
pending (20h on this box), so BM25 top-1 stands in. Discovery rate then measures
lexical blind spots; extend probes when dense-full lands."""
import json
import random
import re
from pathlib import Path

SEED = 7
ANS = re.compile(r"\bANSWER\b", re.IGNORECASE)


def answer_excerpt(text, limit=600):
    spans = list(ANS.finditer(text or ""))
    body = text[spans[-1].start():] if spans else (text or "")
    body = " ".join(body.split())
    return body[:limit]


def main():
    rng = random.Random(SEED)
    gold_b = [json.loads(l) for l in open("data/gold_b_queries.jsonl", encoding="utf-8")]
    runs = {}
    with open("data/runs/bm25.jsonl", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            runs[r["query_id"]] = [it["doc_id"] for it in r["ranked_list"]]
    corpus = {}
    with open("data/corpus.jsonl", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            corpus[r["qslno"]] = r
    probes = []
    for q in gold_b:
        qid = q["query_id"]
        gold = list(q["gold"])
        member = rng.choice(gold)
        cand2, src = None, "none-available"
        for d in runs.get(qid, [])[:100]:
            if d not in set(gold):
                cand2, src = d, "bm25-top1-nonmember"
                break
        cands = [("A-member", member)]
        if cand2:
            cands.append((src, cand2))
        rng.shuffle(cands)
        for src_label, doc in cands:
            rec = corpus.get(doc, {})
            probes.append({
                "query_id": qid,
                "query_title": q["title"],
                "style": q.get("style"),
                "qslno": doc,
                "source": src_label,  # blinded at judging time (helper hides this)
                "ministry": rec.get("ministry"),
                "answer_date": rec.get("answer_date"),
                "excerpt": answer_excerpt(rec.get("text", "")),
            })
    with open("data/gold_b_probes.jsonl", "w", encoding="utf-8") as f:
        for p in probes:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    print(f"probes: {len(probes)} for {len(gold_b)} queries -> data/gold_b_probes.jsonl")


if __name__ == "__main__":
    main()
