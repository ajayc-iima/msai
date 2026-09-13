# Rajya Sabha Question-Hour QA — Master Plan (single file)

**What this is.** The complete capstone plan in one document: scope, corpus, benchmark, architecture, policy, metrics, pseudocode, repo layout, results templates, schedule, and build order. Hand this file to an AI (or follow it yourself) to complete the project. Nothing else is needed except the dataset (downloaded by script) and an NVIDIA API key (answer stage only, cached).

**System in one line.** Retrieval-augmented QA over the complete public corpus of Rajya Sabha parliamentary questions (306,400 records, 1995–2024): given a question it finds the record containing the ministry's official answer, generates a reply from that text only, cites ministry/session/answer-date — and abstains when evidence is insufficient. Its purpose is measurement, not demo.

**Research question (frames everything):** *When does semantic retrieval improve parliamentary QA, and when does evidence-grounding policy prevent retrieval improvements from becoming unsafe answers?* This splits the work into two experiments: **Experiment 1 = retrieval quality** (BM25 vs dense vs hybrid), **Experiment 2 = answer reliability under policy** (no-policy vs evidence-policy vs evidence+abstention).

**Constraints.** 6 graded hours across 2 days · CPU-only + NVIDIA API key · full corpus, no sampling · own-idea track · plan date 2026-09-11.

---

## 0. How to use this file (read this first)

1. **Today (before the session):** send §1 as the approval pitch. Save the reply as `APPROVAL.md`. Approval must be requested before the session — deciding on the spot costs the first hour.
2. **Tonight (prep, ungraded):** follow §12's prep list in order — environment, corpus build, query construction, Gold B annotation sittings, API probe + caching. Do not compress this list; the lab is not where to discover a corpus problem.
3. **Graded hours:** follow §12's hour table. Build order for the AI is in §15 with acceptance criteria (asserts that must pass).
4. **Conventions in this file:** *verified* = measured by direct access on plan date; `<FILL>` = a number only your run may supply — never copy a template digit; `Rev.2` notes mark the evidence-grounding upgrades (Gold B, MER gates, error-budget waterfall, policies A–D, two-experiment framing).

---

## 1. Pitch to send today

> **Own-idea pitch — Rajya Sabha question-hour QA with measured retrieval over the complete public corpus**
>
> **1. What are you building?** A retrieval-augmented QA system over the complete public corpus of Rajya Sabha parliamentary questions (306,400 question-and-answer records, 1995–2024): given a question, it finds the record containing the ministry's official answer, generates a reply from that text only, and cites ministry, session and answer date. It exists to measure how much a dense/hybrid retriever adds over tuned keyword search at real corpus scale, and to report honestly where it adds nothing — and whether evidence-grounding policy prevents retrieval gains from becoming unsafe answers.
>
> **2. What data, and do you already have access?** Yes — verified today by direct API access, and I have removed every network dependency from the lab hours. `anudit/rajyasabha-qa` on Hugging Face: 306,400 rows, MIT, one 509 MB parquet (`download_size` 508,851,734 B), **no token required** — schema fetched, 3,500 rows sampled across 35 blocks, parquet endpoint returns 200 with `accept-ranges: bytes` (resumes with plain `curl -C -`). I build the corpus **once, tonight, in prep**: full parquet → `data/corpus.jsonl` + metadata index + `manifest.json` with sha256s, pinned to commit `508b2411283162fdd52ee2c3e8ccaefbabfe9581`. The lab reads local files only. Two verified findings I am designing around: **28.0%** of rows have empty English text (all still carry `qtitle/status/qtype/adate`, 155 carry Hindi instead — Hindi-only and metadata-only records, not corruption), and **~93%** of documents exceed a 512-token encoder window, so chunking is mandatory.
>
> **3. Smallest end-to-end version in hour 1?** The lexical index over the whole corpus, a title-derived query, top-5 retrieval printed in full with citations, and an extractive answer — one loop, no embeddings, no LLM. Indexing a ~218k-document corpus in 2–4 minutes is the only part I cannot make smaller, so "hour 1" means *one command run once and its output persisted*.
>
> **4. What will you measure, and what's your baseline?** **Baseline = tuned BM25-style lexical retrieval**, built first, tuned on dev, frozen before any other system is scored. Retrieval and generation are scored separately as two experiments answering: *when does semantic retrieval improve parliamentary QA, and when does evidence-grounding policy prevent retrieval improvements from becoming unsafe answers?* Retrieval is scored twice: **Gold A** (title-equivalent sets, census-scale) for statistical power and **Gold B** (n≤100 human-judged pools, prep-annotated) for semantic validity. The query set is constructed automatically from the corpus — every row's `qtitle` is a query whose **gold is the set of documents sharing that normalised title** (titles are not unique; a single-gold assumption would score correct retrieval as failure). Split: dev 2011–2018 tunes, test 2019–2024 is seen once, no train split (nothing is trained), the index holds all 306k rows, and the one rule is **no test-derived tuning**. Metrics: **Recall@1/3/5/10, MRR, nDCG@10**, plus a difficulty statistic reported *before* results. Systems: BM25 → dense head-only baseline + chunked pilot → hybrid (RRF) → + cross-encoder rerank → oracle. Answer stage: extractive control beside an LLM variant (NVIDIA endpoint, every response cached and committed so a grader without a key reproduces identical numbers), compared across **policies A–D** (free → evidence-instructed → +evidence gate → +verification+abstention) on coverage, faithfulness, citation P/R, abstention P/R. **Policy: every factual claim must trace to evidence; an untraceable claim demotes the answer to abstention** — enforced by deterministic code, not a second model's opinion. The answer stage is **tiered**: 24 hand-written queries (qualitative) plus n=200 auto-scored (quantitative: citation P/R, trace rate, abstention, coverage F1 against the gold answer's own `(a)/(b)/(c)` clauses, verified extractable from 94.9% of documents). I will state plainly that auto-constructed queries are easier than human ones, and I will not use an LLM to write queries *and* answer them *and* judge them.
>
> **5. Which course tools does this draw on?** L1–L2: pure functions, `try/except` around load/parse, manifest validation, `.strip()` normalisation with counts. L3: `huggingface_hub` download, JSONL corpus, JSON manifest, argparse CLI, JSONL predictions. L4–L5: sparse TF-IDF matrices and the 384-d dense matrix, L2 normalisation, cosine as matmul, RRF as array algebra, 187k×384 float16 = 144 MB fitting in RAM because matrix arithmetic was the plan. L6: per-system bar chart, Recall@k-vs-corpus-size curve, chunking ablation, error-budget stacked bar. L7: dense pass as a forward-only loop with measured throughput; optional fine-tune on 500 mined pairs. L8–L9: staged pipeline, temporal held-out evaluation, version-pinned data, honest reporting including null results.
>
> **Deliberately left out:** no vector database, no LangChain/LlamaIndex, no dashboard, no deployment, no ingestion pipeline, no multilingual model. Hindi is present in 23.6% of rows — that is the cross-lingual follow-up, not a capstone feature.

---

## 2. Why this scope (rubric mapping + load-bearing rules)

| Rubric line | What it forces |
|---|---|
| "Too much ambition" is the failure mode; scope fit is scored | Full **corpus**, narrow **method**: no UI, no deploy, no ingestion |
| "Someone else can clone, follow README, reproduce" | Reproducibility = **90-second script + pinned commit sha**, not 535 MB of committed text |
| Evidence 30% = measured, sound, one baseline | Tens of thousands of auto-annotated test queries; BM25 frozen first on dev; answer stage tiered (n=24 qualitative + n=200 quantitative carrying the CI) |
| Analysis & honesty 20% | Pre-registered predictions; published negatives; failure modes separated (retrieval vs evidence vs generation), never one blended number |
| Communication 20% | README answers exactly four questions; 5-minute talk has "one thing I'd do differently" |

**Four load-bearing rules** (each corrects a first-draft error):

1. **Gold is a set.** Group rows on normalised title tokens first (§4). Changes the metric (any-of vs all-of Recall@10), makes `same-topic-multi` the default case, and exposes the out-of-split-gold leak (fixed by recording `n_gold_out_of_split` per query).
2. **Dense is a labelled baseline, not the claim.** "Head-only 512 tokens over 93%-longer documents" is named `dense-head-only` and priced against a chunked pilot. The limitation becomes the evidence.
3. **Answerability ≠ retrievability.** Retrieval failure and "no answer exists" are different bugs (§6 waterfall); scored apart.
4. **Verification is post-generation and enforced.** Prompt wording is instructional (requests behaviour); `verify_claims` on the generated string with demote-to-abstain is enforced (guarantees the invariant). Exp. 2 measures control, not wording.

**Accepted trade (stated, not hidden):** auto-derived title queries are easier than human ones, so Recall@1 will be high for every system. Mitigation is a harder task at full scale, not a smaller corpus: graded gold sets, `title-subset`/`cross-ministry` styles, Gold B validation, and **Recall@10/nDCG@10 as headlines**. If dense cannot beat lexical even at ~187k documents, that is a legitimate finding about formulaic bureaucratic language.

---

## 3. Full-corpus build (prep, tonight — not in graded window)

```bash
python src/build_corpus.py            # 509 MB download, ~4 min on a good link, resumable
```

**What it must do, in order, printing numbers at every stage** (this printout is the L1–L2 evidence):

1. `hf_hub_download(repo_type="dataset")` with pinned `revision` sha.
2. Read the parquet **once** with `columns=[...]` (no `datasets` dependency).
3. Normalise `qtype/status/min_name` → `strip().upper()`; count changes.
4. Dedupe on `qslno`; count duplicates (expect ~0; else a finding). **Fail with exit 1 before writing anything.**
5. **Keep every row in `corpus.jsonl`.** Tag empties (`lang: en | hi | meta_only`), don't drop them; expose `retrievable`.
6. **Group rows into queries** on normalised `title_tokens` (Gold A sets) at build time; manifest carries `title_group_sizes_1_2_3_4_5plus`, `n_unique_queries_after_grouping`.
7. Chunk `english` into ~300-word spans (1,800 chars, 300-char overlap) for `lang != meta_only`; also write `head512` (first 512 tokens) for the full-scale dense pass.
8. Write `meta.jsonl` (one line/doc: ids, ministry, date, session, status, `status_is_answered`, title, `title_tokens`, chars, n_chunks, retrievable), then `manifest.json` (counts + sha256s + revision + all §4 statistics — **meta first, because the manifest records its sha256**), then `corpus.jsonl` last (plain JSONL, not gzip: evaluation re-opens top docs by line number and gzip is not seekable). Keep `corpus.parquet` on disk for verifiers, not in git.

**Expected magnitudes** (from the 3,500-row measurement — sanity-check the build against these): **61.3%** usable English (~**187,800** docs), ~**3.5 chunks each** → ~650k chunk vectors or ~187k head vectors. Wildly different output = parsing bug, not data.

`.gitignore` `data/` **except** `manifest.json` (+ tiny `gold_b_*.jsonl`).

**`status_is_answered` rule:** `status.startswith("ANSWER")` after normalisation AND answer-marker present — a heuristic; the manifest's `status_census` (top 25 values) lets you correct it in one line before trusting the `no_answer_in_corpus` class.

**Reference implementation** (tested against a 6-row fixture: duplicate `qslno`, Hindi-only row, missing `ANSWER` marker, `strip/upper` noise — five defects found and fixed: `zlib.open` nonexistence; gzip non-seekability; doubled RSS from holding text twice; manifest hashed before writing meta; `--verify-only` truncating `corpus.jsonl` to 0 bytes. Keep all five guards):

  Fixture acceptance (6 rows: duplicate `qslno`, Hindi-only row, missing `ANSWER` marker, `strip/upper` noise):

  | check | result |
  |---|---|
  | `--verify-only` writes only `manifest_verify.json` (`"full_corpus": false`) | `data/` byte-identical after a real build |
  | build writes corpus + meta + manifest | `sha256_meta` = digest of the file on disk |
  | duplicate `qslno` | exit 1 BEFORE any file is written |
  | `strip/upper` noise | `"unstarred "` → `UNSTARRED` |
  | title grouping → gold sets | 6 rows → 2 queries, sizes `[1×1, 3×1]` |
  | `status_is_answered` discriminates | deferred → false while the row stays indexed |
  | ambiguity stat pre-scoring | 3 of 4 retrievable share a title → 75.0% |

```python
"""src/build_corpus.py — complete corpus, no sampling. Stdlib + pyarrow + huggingface_hub."""
import argparse, hashlib, json, re, time
from collections import Counter
from pathlib import Path
import pyarrow.parquet as pq
from huggingface_hub import hf_hub_download

REVISION = "508b2411283162fdd52ee2c3e8ccaefbabfe9581"
REPO     = "anudit/rajyasabha-qa"
COLS     = ["english","hindi","qslno","qtitle","qtype","adate","shri","qno",
            "name","min_name","ses_no","status","mp_code","P_flag"]
ANSWERED_PREFIX = "ANSWER"
STOP     = set("the a an of to in and for is on by that with as be from are was it not has have been will "
               "per govt india government ministry minister be pleased state answer answers".split())
QNO      = re.compile(r"QUESTION NO\s*[0-9]{1,2}\.[0-9]{2}")
ANS      = re.compile(r"\bANSWER\b|उत्तर")   # Hindi alternative UNVERIFIED — check a Hindi row first
WORDS    = re.compile(r"[A-Za-z']{4,}")

def sha(p):  return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def norm(s): return (s or "").strip().upper()
def toks(s): return {w.lower() for w in WORDS.findall(s or "")} - STOP

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dest", default="data"); ap.add_argument("--verify-only", action="store_true")
    a = ap.parse_args(); d = Path(a.dest); d.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    f = d / "corpus.parquet"
    if not f.exists():
        src = hf_hub_download(repo_id=REPO, repo_type="dataset", filename="train-00000-of-00000.parquet",
                              revision=REVISION, local_dir=str(d))
        Path(src).rename(f)
    print(f"parquet: {f.stat().st_size/1e6:.0f} MB  sha256={sha(f)[:16]}  {time.time()-t0:.0f}s")
    tbl = pq.read_table(f, columns=COLS)
    cols = {c: tbl.column(c).to_pylist() for c in COLS}
    n = len(cols["qslno"]); print(f"rows: {n:,}")
    # recs stays metadata-only; texts is a parallel list (holding both doubles RSS past 2 GB boxes).
    ids, dupes, seen, texts = [], 0, set(), []
    for q in cols["qslno"]:
        if q in seen: dupes += 1
        seen.add(q); ids.append(q)
    stats = Counter(); recs = []; n_scanned = 0; status_census = Counter()
    for i in range(n):
        if a.verify_only and i >= 20000: break
        n_scanned = i + 1
        e = (cols["english"][i] or "").strip(); h = (cols["hindi"][i] or "").strip()
        lang = "en" if e else ("hi" if h else "meta_only")
        stats[lang] += 1
        text = e or h
        has_ans = bool(ANS.search(text))
        ok = bool(text) and has_ans
        stats["usable_" + lang] += int(ok)
        stats["mangled"] += int(bool(QNO.search(e)))
        stats["over512"] += int(len(text) > 2000)   # chars proxy — recount with a real tokenizer before quoting
        st = norm(cols["status"][i]); status_census[st] += 1
        answered = st.startswith(ANSWERED_PREFIX) and ok
        toks_ = toks(cols["qtitle"][i])
        chunks = [text[j:j+1800] for j in range(0, len(text), 1500)] if ok else []
        recs.append({"qslno": cols["qslno"][i], "lang": lang, "retrievable": ok,
                     "ministry": norm(cols["min_name"][i]), "qtype": norm(cols["qtype"][i]),
                     "status": st, "status_is_answered": answered,
                     "answer_date": (cols["adate"][i] or "")[:10],
                     "ses_no": cols["ses_no"][i], "qno": cols["qno"][i], "member": cols["name"][i],
                     "title": (cols["qtitle"][i] or "").strip(), "title_tokens": sorted(toks_),
                     "chars": len(text), "n_chunks": len(chunks)})
        if not a.verify_only: texts.append(text)
    if dupes:
        print(f"FAIL: {dupes} duplicate qslno -> refusing to build")
        return 1
    groups = Counter(tuple(r["title_tokens"]) for r in recs if r["retrievable"])
    gsizes = Counter(min(v, 5) for v in groups.values())
    over2 = sum(v for v in groups.values() if v >= 2)
    yrs = Counter(r["answer_date"][:4] for r in recs if r["answer_date"])
    mins = Counter(r["ministry"] for r in recs if r["retrievable"])
    out = {"built_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "repo": REPO, "revision": REVISION,
           "rows": n, "dup_qslno": dupes, "lang": dict(stats),
           "usable": {k: v for k, v in stats.items() if k.startswith("usable")},
           "ocr_mangled_qno": stats["mangled"], "docs_over_512_tokens": stats["over512"],
           "min_years": min(yrs), "max_years": max(yrs), "n_years": len(yrs),
           "n_ministries": len(mins), "largest_ministries": mins.most_common(10),
           "title_group_sizes_1_2_3_4_5plus": [gsizes.get(k,0) for k in (1,2,3,4,5)],
           "n_unique_queries_after_grouping": len(groups),
           "status_census": dict(status_census.most_common(25)),
           "status_census_truncated": len(status_census) > 25,
           "queries_with_2plus_same_title": over2,
           "pct_retrievable_queries_ambiguous": round(100*over2/max(1,sum(groups.values())),2),
           "build_seconds": round(time.time()-t0,1), "sha256_meta": None,
           "census_rows_scanned": n_scanned, "full_corpus": not a.verify_only}
    if a.verify_only:   # EARLY RETURN — never opens corpus/meta for writing
        (d/"manifest_verify.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
        print(json.dumps(out, indent=1)); return 0
    (d/"meta.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in recs), encoding="utf-8")
    out["sha256_meta"] = sha(d/"meta.jsonl")
    (d/"manifest.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    with (d/"corpus.jsonl").open("w", encoding="utf-8") as fh:
        for r, t in zip(recs, texts):
            fh.write(json.dumps({**r, "text": t}, ensure_ascii=False) + "\n")
    print(json.dumps(out, indent=1)); print("OK: qslno unique")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
```

---

## 4. Benchmark: Gold A (scale) + Gold B (quality)

### 4.1 Gold A — title-equivalent, automatic, census-scale

1. Normalise every `qtitle` to STOP-filtered token set (`title_tokens` in `meta.jsonl`).
2. **Group rows by token set.** One query per group; gold = whole `qslno` set. Singleton = common case; size>1 = hard case (`same-topic-multi`), not an error.
3. **Relevance graded by construction**: Recall@k any-of (≥1 member in top-k) + all-of (fraction retrieved); nDCG@10 with gain 1 per relevant doc.
4. **Out-of-split leak fix:** per query record `n_gold_out_of_split` (group members outside the query's split count as relevant for nDCG, excluded from the clean `title` subset); report the share.

**Split: dev 2011–2018 tunes, test 2019–2024 seen once. No train split** (nothing is trained; BM25/dense are *configured*). Index holds everything 1995–2024 (as deployed). **Only rule: no test-derived tuning** — nothing selected from test numbers. Sensitivity check: swap windows, rerun two headline rows; if the conclusion flips, the split was doing the work.

**Query styles** (separate result rows):

| style | construction | tests |
|---|---|---|
| `title` | verbatim `qtitle`; groups of size 1 only | ceiling; every system looks great |
| `title-subset` | drop 20 most corpus-frequent terms | how much lexical recall is boilerplate luck |
| `same-topic-multi` | groups with ≥2 gold docs | retrieving *all* of a topic (nDCG earns its place) |
| `cross-ministry` | title terms also occur in another ministry's docs | whether ministry vocabulary dominates |
| `answer-unavailable` | `status` not Answered, or empty/Hindi-only text | correct output = refusal, not a guess |

**Pre-register before scoring:** "`title` saturates above 0.9 for BM25; dense advantage appears only in `title-subset`/`cross-ministry`; `same-topic-multi` loses most Recall@10 (full-set ≫ any-of difficulty)." Inputs already measured: title Jaccard 0.011 mean / 0.000 p90; 764 title terms in ≥3 docs — ranking matters, top-1 doesn't.

**`n_test` is an output:** `(#retrievable docs ≥2019) ÷ (group collapse)`; estimate 30–60k unique groups, printed by `make_queries.py`. Power holds across the range (0.5-pt gap at n=30k → SE ≈ 0.04 pts).

**Corpus statistics to report (free from the build — what makes a reviewer believe you touched full data, not a sample):** per-ministry counts, per-year counts, empty-text rate by year, `hindi` coverage by year, chunk-length distribution, share of docs >512 tokens, title-collision distribution (groups of size 1/2/3/≥4), out-of-split-gold rate, `status` value census (sizes the answer-unavailable class).

Random splits are never used (the same ministry repeats vocabulary for years — a time boundary is the honest split); still report the MinHash/`title_tokens` overlap rate between tuning and test vocab (one line of code) to justify the split instead of asserting it.

### 4.2 Gold B — manually validated relevance, n≤100 (prep, ~1.5–2 h)

Gold A measures title-token equality, not relevance. Gold B is the construct check: **statistical power from A, semantic validity from B. Every retrieval claim names its gold; if they disagree in direction, B wins the interpretation.**

**Protocol** (`make_queries.py --gold-b 100 --seed 7` → `data/gold_b_queries.jsonl`, committed, tiny):

- **Sample (stratified, test window, `answerable` only):** 40 `title` + 20 `title-subset` + 20 `same-topic-multi` + 20 `cross-ministry`.
- **Probe (2 judgments/query, ~200 total — full pooling at ~1,000 judgments costs ~8–14 h and is rejected):** (1) one Gold A member — *is the title construct correct?* (2) the hybrid top-1 if it differs, else dense top-1 — *is semantic retrieval finding real relevance the construct misses?*
- **Judge (blinded to source system; excerpts pre-extracted, ~30–45 s each):** `2` = answers the query · `1` = on-topic but doesn't answer · `0` = off-topic · + `reason` ≤5 words (`wrong-year`, `wrong-subpart-c`, … — free failure taxonomy). Retrieval-relevant = `2` (strict); `≥1` as sensitivity row.
- **Report:** confirm rate (Gold A member judged relevant), discovery rate (non-A top-1 judged relevant), 2×2 agreement table + Cohen's κ (A-vs-human, single annotator — state it). Pre-registered: confirm ≥0.8 on singletons, ≤0.6 on `same-topic-multi`.
- **Cap:** hard 2 h in two sittings; fallback **n=60** with identical protocol (CI widens ±10→±12.6 pts; report achieved n). Below 60 the construct claim evaporates — never cut entirely.

**Judgment format** (`data/gold_b_judgments.jsonl`, one line each): `{query_id, qslno, label_0_1_2, reason, annotator, seconds}`. A `--judge` helper prints query + answer-side excerpt and appends your keystroke.

---

## 5. Architecture: gates before generate, verification after

### 5.1 Canonical pipeline

```
             ┌─────────────┐
             │ User Query  │
             └──────┬──────┘
                    ↓
              Query Parser (normalise, style tag)
                    ↓
          ┌──────────────────┐
          │ Retrieval Layer  │  BM25 ∪ dense → RRF → (rerank)
          └────────┬─────────┘
                   ↓
             Top-k Evidence (chunks + metadata)
                   ↓
          ┌──────────────────┐
          │ Evidence Gate    │  PRE-generation: MER on retrieved k (§5.2)
          │ (retrieval-level)│  fail → ABSTAIN{reason}
          └────────┬─────────┘
                   ↓ pass
          ┌──────────────────┐
          │ Answerability    │  PRE-generation: corpus-level (§5.3)
          │ Gate             │  unanswerable → ABSTAIN{reason}
          └────────┬─────────┘
                   ↓ answerable
          ┌──────────────────┐
          │ Generate         │  extractive OR llm (--policy A–D)
          └────────┬─────────┘
                   ↓ draft {claims[], citations[]}
          ┌──────────────────┐
          │ Claim            │  POST-generation: verify_claims on the
          │ Verification     │  generated text vs quoted chunks (§5.4).
          └────────┬─────────┘  any unsupported claim → demote WHOLE
                   ↓            answer to ABSTAIN (Policy D only)
              Citations (doc_id, span, ministry/session/date)
                   ↓
        ┌─────────────────────┐
        │ Answer  /  Abstain  │
        └─────────────────────┘
```

**Why this order.** Evidence Gate first because it's cheap and per-query (*did retrieval return anything usable?*); Answerability Gate second because it's authoritative (*does the corpus contain an answer?*). Same abstain decision either way — this order yields cleaner failure logs for the error budget. **Claim Verification must run after Generate, on the generated string, across a process boundary** (`answer.py` emits draft → calls verifier → attaches citations only to surviving claims). Prompt wording ("answer only from evidence") is *instructional* (requests behaviour); verify-then-demote is *enforced* (guarantees "no emitted answer contains an untraced claim", modulo the checker's measured error rate). If verification runs before/during generation or is skipped for the LLM arm, Exp. 2 measures prompt wording, not control. **Negative control (hour 4):** bypass the gate once on one query and confirm violation rate goes nonzero — proves D's 0.000 is live.

### 5.2 Evidence Gate — Minimum Evidence Requirements (MER)

> **An answer is emitted only if ALL hold on the retrieved top-k, else ABSTAIN:**
> - **MER-1 — relevant retrieved document:** ≥1 chunk whose doc has `retrievable=true`, `lang=en`, `status_is_answered=true` → else `NO_DOC`
> - **MER-2 — supporting text span:** quotable span ≥200 chars answer-side text with `doc_id/chunk_idx/offsets` recorded → else `NO_SPAN`
> - **MER-3 — identifiable source metadata:** non-null `ministry`, `ses_no`, `answer_date`, `qslno`/`qno` → else `NO_METADATA`

**The fused-score threshold θ is demoted to a logged reference feature** (kept for a sensitivity plot only). A high similarity score does not mean the text supports the claim — three counterexamples for the report: (1) high score, right doc, *wrong sub-part chunk*; (2) high score on a deferred/unanswered record sharing title terms; (3) high score on header/boilerplate matching query terms. MER-1/2/3 abstain on all three; θ passes all three. *Ranking scores measure "looks similar"; evidence requirements measure "can support a claim". Only the second licenses an answer.*

```python
# src/evidence_gate.py — pre-generation. Pure function. No API, no model.
MER_MIN_SPAN_CHARS = 200
def evidence_gate(topk_chunks, k=8):
    for ch in (topk_chunks or [])[:k]:
        m = ch.get("meta", {})
        if not (m.get("retrievable") and m.get("lang") == "en" and m.get("status_is_answered")): continue
        if len((ch.get("text") or "").strip()) < MER_MIN_SPAN_CHARS: continue
        if not all(m.get(f) for f in ("ministry","ses_no","answer_date")): continue
        if not (m.get("qslno") or m.get("qno")): continue
        return {"pass": True, "reason": "MER_PASS", "best": ch}
    return {"pass": False, "reason": first_missing_requirement(topk_chunks), "best": None}
# Log every decision: {query_id, policy, gate:"evidence", pass, reason, best_doc, rrf_top1, theta_ref}
```

### 5.3 Answerability Gate — corpus-level routing (metadata only)

| condition | class | correct behaviour |
|---|---|---|
| gold non-empty, indexed, English | `answerable` | retrieve + cite; retrieval & generation metrics apply |
| `status` not answered/deferred | `no_answer_in_corpus` | ABSTAIN (`NO_ANSWER_IN_CORPUS`) — not a retrieval failure |
| Hindi-only / metadata-only | `unanswerable_en` | ABSTAIN (`UNANSWERABLE_EN`) — not a retrieval failure |

### 5.4 Claim Verification — post-generation trace check (the enforced policy)

A claim is supported iff **some quoted chunk passes BOTH**: (a) `max(LCS-ratio, trigram-overlap) ≥ 0.80` on identically-normalised text (character-level — immune to hyphen/morphology splits); (b) **numeric check**: every number in the claim (digits + spelled 0–99, word-boundaried; compounds on the glued copy) appears in the chunk. One unsupported claim demotes the **whole answer**. Claims with <5 content tokens skip the audit and are counted (`skipped_short_claims`).

Measured on six adversarial cases: supported `1.00/0.93/0.83`, demoted `0.56/0.45/0.40` — real margin, but 0.83 vs 0.80 threshold is uncomfortable, which is the finding. Catches: fabricated `999 crore` (0.45 + missing number), non-sequiturs (0.00), shared-vocabulary contradictions (0.56), **year flips** (trace 0.93 SUPPORTED — only the numeric check blocks it; the whole argument for pairing the two). Cannot catch: spelled numbers ≥100, negation-by-word-order (0.71 demoted by accident of phrasing) — those go to the LLM judge as a second axis, never to this rule.

History worth keeping in DECISIONS: v1 (token overlap ≥0.8) demoted a verbatim copy (`thirty-two` tokenisation) AND supported an invented `40` (numerals ignored); v2 (content containment) broke on `inspected`/`inspection`. The kept rule is v3. "I wrote a plausible rule and tested it" is the lesson.

```python
# src/verify_claims.py — POST-generation. Runs on the emitted string. No API, no model.
import difflib, re
norm = lambda t: " ".join(re.findall(r"[a-z0-9]+", (t or "").lower().replace("-", " ")))
tri  = lambda s: {s[i:i+3] for i in range(len(s)-2)} if len(s) > 3 else {s}
def trace_score(claim, chunk):
    c, n = norm(claim), norm(chunk)
    if not c: return 0.0
    lcs = difflib.SequenceMatcher(None, c, n, autojunk=False).find_longest_match(0, len(c), 0, len(n)).size / len(c)
    tc, tn = tri(c), tri(n)
    return max(lcs, len(tc & tn) / max(1, len(tc)))
def claim_supported(claim, chunks, tau=0.80):   # + numeric_check: claim_numbers(claim) ⊆ claim_numbers(chunk)
    scored = [(trace_score(claim, ch), ch) for ch in chunks]
    s, ch = max(scored, key=lambda x: x[0])
    return (s >= tau) and numeric_check(claim, ch), round(s, 3)
```

---

## 6. Error budget + failure analysis (connects retrieval to policy)

Every **answerable** query lands in exactly one bucket (**assert the identity in code**):

```
1.000 = P(A retrieval fail: gold ∩ top-k = ∅)
      + P(B evidence fail: gold retrieved BUT MER fails on top-k)
      + P(C generation fail: MER passes BUT answer demoted OR coverage-F1 = 0)
      + P(success: emitted and scores > 0)
```

Unanswerables get a separate row (`correct_abstain` vs `wrong_answer`); `false_demote_rate` (= P(abstain | answerable)) prices the policy's cost. Pre-registered: A dominates `title-subset`/`cross-ministry` (fix *ranking*); B dominates `same-topic-multi` — right doc, wrong sub-part chunk (fix *chunking/span selection*; split B by MER-1/2/3 — each implies a different fix); C smallest except Policy A (fix *generator/τ*; split verifier-demotions = policy working, from zero-coverage emissions = generator failing).

**Report as a stacked bar (A/B/C/success × style)** — the single best figure in the talk. **Analysis routine:** (1) largest bucket first; (2) 3 examples per non-empty bucket with full chunks; (3) one sentence per bucket naming the module to fix. A failure table without example queries is a summary, not an analysis.

**Per-query log schema (what makes each bucket fixable):**

| bucket | reason codes | log with it |
|---|---|---|
| A | `GOLD_ABSENT_TOPK` | qid, style, gold set, top-k ids, system |
| B | `NO_DOC` / `NO_SPAN` / `NO_METADATA` | + best-chunk doc, span length, missing metadata fields, top-1 RRF score (reference only) |
| C | `UNTRACED_CLAIM` (+ claim text, trace score) / `ZERO_COV` | + per-claim verifier verdicts |
| wrong_answer | `EMITTED` on unanswerable | + the gate reason that *should* have fired |
| false_demote | answerable + abstained | + would-have-been-correct flag (tier-A read) |

```python
# failure_analysis.py — pseudocode
def classify(q, ranked, gate, answer_row, k=10):
    if not q.answerable: return "correct_abstain" if answer_row.abstained else "wrong_answer"
    if not (set(q.gold) & set(ranked[:k])): return "A"          # GOLD_ABSENT_TOPK
    if not gate.pass: return "B"                                 # NO_DOC / NO_SPAN / NO_METADATA
    if answer_row.abstained or answer_row.cov_f1 <= 0: return "C" # UNTRACED_CLAIM / ZERO_COV
    return "success"
```

---

## 7. The two experiments

### Experiment 1 — Retrieval: does semantics help at full-corpus scale?

| # | system | notes |
|---|---|---|
| 1 | `bm25` | **Baseline.** Sweep `sublinear_tf, norm, min_df, max_features, ngram_range` on dev; freeze |
| 2 | `bm25+chunks` | chunk granularity, max-pooled to doc **before** fusion |
| 3 | `dense-head-only` (labelled baseline) | `BAAI/bge-small-en-v1.5` (33.4M, 133.5 MB), fp16, one 512-token head vector/doc; 187k×384 fp16 = 144 MB; cosine as `E @ q`, no FAISS |
| 3b | `dense-chunked` (pilot-or-full) | same model, ~3.5 spans/doc, max-pooled. Decision rule: measure `r` (seq/s); if `657300/r < 2 h` run full (replaces row 3), else 20k-doc pilot (`70000/r`) as ablation |
| 4 | `dense-head-only+instr` | + documented query instruction (`encode_query` since ST v5.0) — real ablation |
| 5 | `hybrid` | RRF of BM25 + dense top-100 lists, `k ∈ {20,60,100}` on dev. Rank-based (no score calibration); doc-granularity fusion |
| 6 | `hybrid+rerank` | `cross-encoder/ms-marco-MiniLM-L6-v2` (22.7M, 90.9 MB) rescores fused top-20 → top-10; generation reads top-8 **chunks**; report p95 latency |
| 7 | `oracle` | gold handed to answer stage; retrieval metrics must be exactly 1.000 (else table is void) |

- **Gold:** A (all test groups) + B (n≤100). **Metrics:** Recall@1/3/5/10 (any-of + all-of), MRR, **nDCG@10 headline**; paired bootstrap CIs (10k) on A, Wilson on B.
- **Dense-as-retriever vs cross-encoder-as-reranker** are different mechanisms (matmul vs per-pair attention) — rows 3 and 6 are not two versions of "rerank".
- **Cost is `N_passes / r`** with `r` measured (`encode(200 docs)`, wall-clock): head-only 187.8k, chunked ~657.3k, rerank n_test×20 pairs (pessimistic bound — cross-encoder pass costs more than bi-encoder).

  Cost table (hours at r = 50 / 100 / 190 / 400 seq/s — illustrative; YOUR measured r decides):

  | step | inference passes | hours |
  |---|---|---|
  | head-only, full corpus | 187,800 | 1.04 / 0.52 / 0.27 / 0.13 |
  | chunked, full corpus (~3.5×) | ~657,300 | 3.65 / 1.83 / 0.96 / 0.46 |
  | chunked, 20k-doc pilot | ~70,000 | 0.39 / 0.20 / 0.10 / 0.05 |
  | rerank, all test queries × 20 | ~0.6–1.2M pairs | 4.4 / 2.2 / 1.2 / 0.6 (pessimistic) |
  | dense scoring of all test queries | n_test × 187k dots | minutes; 144 MB RAM (499 MB chunked) |

  Two corrected conclusions: (1) full-scale chunked dense is NOT automatically off the table — at r≥150 seq/s it is under an hour, i.e. free next to the rest of the evening; (2) the first draft kept an ~800k-pair rerank while "rejecting" the cheaper 657k bi-encoder pass — both are now `N/r` from the same single measurement, not competing guesses. Pre-registered: `hybrid ≥ max(bm25, dense)` on nDCG@10 with non-overlapping CIs; three failure modes worth reporting — bge-small OOD on OCR'd bureaucratic text (dense loses outright = finding), RRF ignoring margin (why row 6 exists — report 5/6 separately), fusion can't recover recall (top-100 of 187k = 0.05% cut; Recall@10 exposes it).

### Experiment 2 — Reliability: does policy prevent unsafe answers?

All four share **ONE frozen retriever** (Exp-1 winner; if none, BM25 — the experiment is valid regardless). `answer.py --policy {A,B,C,D,extractive}`; scoring-only over cached contexts (no new retrieval).

| Policy | prompt | pre-gen MER | post-gen verify | measures |
|---|---|---|---|---|
| **A** free | "Answer the question." (context present, no evidence instruction) | OFF | OFF | — |
| **B** evidence-instructed | "Answer **only** from evidence; cite ministry/session/date per claim." | OFF | OFF | A→B = prompt effect |
| **C** + evidence gate | same as B | **ON** | OFF | B→C = gate effect |
| **D** + verify + abstain | same as B | **ON** | **ON** (any untraced claim demotes whole answer) | C→D = post-check value; **B→D = instructional→enforced (headline)**; A→D = safety story |

Plus `extractive` (spans only — satisfies D trivially; ceiling on faithfulness). **Metrics:** coverage (`P(emitted)` overall/answerable/unanswerable), faithfulness, citation P/R, abstention P/R, violation rate (D must be 0.000). Pre-registered: coverage A>B>C>D, faithfulness/abstention-precision reverse, B→D gap > A→B gap. If C already hits 0 violations, the post-check bought nothing — a null result for placement, still a finding.

**Answer tiers** (compute is not the wall — human time is; 4.3 min/query measured over 82 docs):

| tier | n | gold | CI @ p=0.7 | role |
|---|---|---|---|---|
| A · human-written (qualitative) | 24 (+2 unanswerable) | hand expected sub-parts | ±15.6 → ranks nothing | case inspection + demo; failure taxonomy > aggregates |
| B · auto-scored quantitative | 200 (seeded) | none (regex/judged) | ±6.3 | reportable numbers: citation P/R, trace rate, abstention |
| C · auto-derived coverage | 200 | gold answer's own `(a)/(b)/(c)` clauses (94.9% extractable, median 3; split at **last** `\bANSWER\b`; 70 question-only → span overlap, 22 unusable) | ±6.3 | coverage F1 at scale, labelled reference-based |
| D · LLM + judge | 24→60 (quota-batched) | tier-C gold + trace check | ±15.6→±12.3 | API-bound arm; batches of 12, hard stop at 75% credits |

**Why tiered (the cost table that settled it, at n=200):** extractive answers 1.0 min · auto metrics 16.7 min · human query-writing **14.2 h** (4.3 min/query measured over 82 real docs, range 2m45s–5m30s scaling with sub-part count; median 3 sub-parts). So 24 human + 200 auto = 1.7 h + 17 min, versus 200 human = a full day. Tier A stays qualitative by arithmetic, not by excuse: 1 query = 4.2 pts; ±10 pts needs n≈81 (≈3.5 h of writing); ±5 pts needs n≈323 (≈13 h). Tier-C extraction detail: 70 question-only docs (coverage degrades to whole-answer span overlap), 8 answer-only, 22 unusable.

No BLEU/ROUGE (translation metrics, not generation metrics). LLM judge = additional axis on tier A/D only, never the gate — a model cannot be the authority on whether a model hallucinated.

---

## 8. Metric reference (all 7 families — each with formula, denominator, question)

**Retrieval (Exp. 1)** — denominator: answerable queries with non-empty gold (unanswerables excluded — nothing to retrieve ≠ retrieval failure):

| metric | formula (gold G, ranked R) | answers |
|---|---|---|
| Recall@k any-of / all-of, k∈{1,3,5,10} | `1[G∩R[:k]≠{}]` / `|G∩R[:k]|/|G|` | reachable? / whole topic? |
| MRR | `1/rank(first relevant)` else 0 | how far down must the reader look? |
| nDCG@10 (headline) | binary DCG@10 / IDCG over `min(|G|,10)` | graded ranking quality |

**Answer (Exp. 2)** — correctness/coverage/faithfulness/citation denominators = emitted answers; abstention/coverage denominators = labelled sets:

| metric | formula | answers |
|---|---|---|
| Coverage F1 (correctness) | R = sub-parts `trace(sub,answer)≥0.80` / all; P = claims matching some sub-part / all; F1. Lexical by design — a year-flip still *covers* (that's why faithfulness exists) | what the ministry said, present? |
| Faithfulness | supported / judged claims (trace ≥0.80 AND numeric check; <5-token claims skipped + counted) | every claim traceable? (the invariant) |
| Citation P / R | supporting cited spans / cited claims; claims with supporting citation / judged claims | citations load-bearing or decorative? |
| Abstention P / R | `P(unans|abstain)` / `P(abstain|unans)`; + coverage splits + violation `P(≥1 untraced|emitted)` | refuses correctly, and at what coverage cost? |

```python
# retrieval metrics — pseudocode (gold is a SET)
recall_any  = lambda G,R,k: 1.0 if set(G) & set(R[:k]) else 0.0
recall_all  = lambda G,R,k: len(set(G) & set(R[:k]))/len(G)
mrr         = first i with R[i] in G → 1/i else 0.0
ndcg@10     = Σ_{i≤10} rel_i/log2(i+1) / Σ_{i≤min(|G|,10)} 1/log2(i+1)
# deltas: paired bootstrap, 10k resamples; Gold B proportions: Wilson interval
```

---

## 9. Repository layout + module contracts

```
rs-qa-retrieval/
├── README.md            ← EXACTLY four questions (§11.1)
├── APPROVAL.md          ← pitch + reply
├── DECISIONS.md         ← 16 entries (§11.2)
├── results.md           ← headline + tables (§11.3)
├── PLAN.md              ← this file
├── LICENSE-DATA.md      ← MIT terms; TCPD clause if member/minister tables kept
├── requirements.txt     ← numpy==2.5.3 pandas==3.0.5 pyarrow scikit-learn==1.9.1
│                          sentence-transformers==6.0.1 huggingface_hub openai matplotlib scipy
│                          (no faiss/langchain/llamaindex/FlagEmbedding/vector DB; torch CPU as needed)
├── .gitignore           ← data/* except manifest.json + gold_b_*.jsonl
├── data/                ← corpus.jsonl · meta.jsonl · manifest.json · gold_b_*.jsonl ·
│                          cache/{E.npy, tfidf.pkl, preds/*.jsonl, llm_responses.json}
├── src/
│   ├── build_corpus.py  ← §3 (given, tested)
│   ├── make_queries.py  ← corpus → 5 styles + collision stats + `--gold-b 100 --seed 7` → queries.jsonl
│   ├── index_lexical.py │ index_dense.py │ fusion.py (RRF) │ rerank.py
│   ├── retrieve.py      ← --print-chunks (MANDATORY: read retrieved text before touching prompts)
│   ├── evidence_gate.py ← §5.2 MER → ANSWER or ABSTAIN{reason}; ships hour 1 (no LLM needed)
│   ├── answer.py        ← extractive + --llm --policy {A,B,C,D}; emits {claims[], supports[]}; --no-llm replays cache
│   ├── verify_claims.py ← §5.4 POST-generation trace check; demote-to-abstain; bypass flag for neg. control
│   ├── evaluate.py      ← retrieval metrics + bootstrap CIs; --systems … --split test --gold {A,B}
│   ├── score_parts.py   ← Exp-2 metrics + waterfall assert (Σ=1.000) + skip counters
│   ├── plots.py         ← systems bar · error-budget stacked bar · Recall@10-vs-size (20k/60k/120k/187k) · chunking ablation · θ–τ panel
│   └── common.py        ← manifest validation, sha256, logging, argparse, CI helpers
└── notebooks/capstone.ipynb ← every number and figure (a description is not evidence)
```

**Every stage writes ranked lists to disk** (`data/runs/<system>.jsonl`); rows re-score free, metric bugs never cost a re-encode. `llm_responses.json` keyed on `sha256(model+prompt+temp+max_tokens)` — grader reproduces without a key.

---

## 10. Models, libraries, API budget

| purpose | pick | verified |
|---|---|---|
| dense | `BAAI/bge-small-en-v1.5` | 33.4M, 133.5 MB, 64.6M downloads |
| reranker | `cross-encoder/ms-marco-MiniLM-L6-v2` | 22.7M, 90.9 MB; short-span bias — report it |
| generator + judge | `nvidia/llama-3.1-nemotron-70b-instruct` via `integrate.api.nvidia.com/v1` | 401 live/key-gated on probe; fallback `nemotron-nano-3-30b-a3b`; `llama3-chatqa-1.5-70b` purpose-built for cited RAG |
| API rerank/embeddings at scale | **not available** | 404 on all rerank paths; catalog 404s even listed models |

**Rejected:** `bge-m3` (2,271 MB — too heavy for CPU overnight); `Qwen3-Reranker-0.6B` (1,192 MB — offline cached upper bound only); `nv-embedqa-e5-v5` (**retired, 410**); anything from the catalog list alone (still advertises models retired 2026-08-26 — **probe before depending**).

**API rails:** free tier ~1,000 credits (up to 5,000 on request), ~40 req/min per model (2026 write-ups; NVIDIA: limits model-specific/unpublished — budget in queries, not credits). Tier D = 24 queries ≈ 78–102 calls (answers + judge + relevance + ≤30 retries, exp. backoff on 429), `temperature=0`, **batches of 12 with a credits check between, hard stop at 75%** (one report of HTTP 402 when credits exhaust — the stop exists so you never discover it mid-run); unreadable check → cap at 24 and write "limited by account quota, n=<x>". Key never in code; API off the critical path (live demo = one query, `--live`).

---

## 11. Graded artifacts

### 11.1 `README.md` — four questions, only those four

```markdown
## 1. What does this do, in two sentences?
Answers questions about Rajya Sabha parliamentary records by retrieving the record containing the ministry's
official written answer, from the complete 306,400-document public corpus, and generating a reply only from
that text with ministry, session and answer date cited — abstaining when evidence is insufficient. It measures
how much semantic retrieval adds over tuned keyword search at full scale, and whether evidence-grounding policy
keeps retrieval gains from becoming unsafe answers.

## 2. How do I run it?
    python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
    python src/build_corpus.py            # 509 MB, resumable; writes data/manifest.json
    python src/make_queries.py            # Gold A sets + styles + split stats; --gold-b 100 --seed 7
    python src/evaluate.py --systems bm25,bm25_chunks,dense_head,dense_chunked,hybrid --split test
    python src/plots.py
    # then: notebooks/capstone.ipynb -> Kernel -> Restart and Run All
Python 3.11. Only network need: corpus download (sha256 in manifest). LLM answers replay from
data/cache/llm_responses.json — no key required. --no-llm runs extractive only. **Timings below are YOURS
from the run log** (dense encode = 187800/r min head-only, 657300/r chunked, r = your seq/s). A template
number that isn't yours is the easiest thing for a grader to catch.

## 3. What did you find — headline, stated plainly?
<FILL hour 5, one Exp-1 sentence + one Exp-2 sentence, every digit from your run:
"Over <n_test> held-out 2019–2024 query groups (gold=set, <g>% size≥2), tuned BM25 scored R@10 <a>/nDCG@10 <b>
and hybrid <c>/<d> (Gold A; Gold B confirm <x>/discovery <y>/κ <k>, n=<..>); dense gain confined to
<title-subset + cross-ministry>, <negative/flat> on same-topic-multi; chunking moved nDCG@10 by <±e>.
Freezing <retriever>, policy D held faithfulness <f> at coverage <c> with abstention P/R <p>/<r> and violation
0.000, vs policy B faithfulness <f2> at coverage <c2> (Exp.2, tiers B/C).">

## 4. What would you do next?
(a) human-written queries (titles overstate every system); (b) cross-lingual slice (Hindi in 23.6% rows,
155/3,500 Hindi-only — a real benchmark); (c) full-scale chunked dense (head-only labelled baseline because
~93% lose their tail; at my measured r it <does/does not> fit).
```

### 11.2 `DECISIONS.md` — 4–6 lines each, 16 entries

1. `[scope]` Full corpus, no sampling — ~150k held-out groups beat a hand-labelled dozen; paired bootstrap CIs become meaningful. Cost owned: repo not self-contained; reproducibility = pinned sha + verified sha256.
2. `[got it]` Gold is a set — grouping on `title_tokens` (metric any-of vs all-of; `same-topic-multi` default; out-of-split leak fixed). Numbers: `<g>` groups, `<x>%` size≥2, `<y>%` out-of-split gold.
3. `[got it]` No train split — configured, not trained; dev tunes, test seen once; reverse-split rerun checks principle-vs-convenience.
4. `[method]` Dense labelled head-only baseline — primary claim is "what throwing away 93% costs", measured on a `<20k>` pilot at `<h>` h.
5. `[did not work]` My cost estimates, twice — unmeasured 1–2k docs/s band (wrong 10×); kept 800k-pair rerank while rejecting cheaper 657k bi-encoder pass. Both rows now `N/r` formulas from measured `r=<..>`.
6. `[method]` Pre-registered predictions (§4/§7) — falsified by CIs, not preference.
7. `[negative result]` Dense vs BM25 at scale — whatever it says, with CIs; overlap → "indistinguishable", interesting for formulaic corpora.
8. `[got it]` Answerability ≠ retrievability — waterfall A/B/C/success = 1.000 (not a product); first draft would have chased retrieval fixes for corpus properties.
9. `[got it]` Policy enforced by code — `{doc_id,chunk_idx,span}` per claim; one unsupported claim demotes whole answer. Cost reported: `false_demote_rate=<x>%` at `τ=<v>` (dev).
10. `[did not work]` Two trace rules failed 6 adversarial cases before v3 passed — overlap ignored numerals + broke on `thirty-two`; containment broke on morphology. Kept: `max(LCS,trigram)≥0.80` + verbatim number check. Weakness: flipped year scores 0.93.
11. `[got it]` Answer stage tiered (after n=12 caught out) — citation/trace/abstention/coverage need no human (auto-gold 94.9%, median 3 sub-parts, n=1,973): 24 qualitative + 200 quantitative (±6.3, 17 min compute).
12. `[did not work]` Two measurement scripts lied — `re.search` boundary → 0.0% sub-parts (anchor on *last* occurrence); hyphen normalisation broke verbatim matches (normalise both sides identically).
13. `[scope]` No LLM claims without a control — `extractive` beside `llm` on identical context; API cached (flakiest component).
14. `[got it]` Score threshold demoted — similarity ≠ support (3 counterexamples; MER replaces θ; θ logged reference only). Observed case: `<FILL>`.
15. `[got it]` Gold B construct check — n=<..> blinded: confirm `<x>`, discovery `<y>`, κ `<k>`; single annotator = agreement, not inter-annotator reliability.
16. **What I'd do differently** — one process error + minutes cost (2-min talk). Pick: shipping two order-of-magnitude cost claims no measurement supported.

### 11.3 `results.md` template

```markdown
# Headline (≤25 words, digits, end of hour 4)
# Corpus (from manifest.json — reported, not assumed)
| rows | retrievable | empty-text | dup qslno | ministries | years | >512 tokens | ambiguous queries |
# Retrieval — test, n=<groups>, one pass/system, 95% bootstrap CIs (any-of + all-of R@10)
| system | R@1 | R@3 | R@5 | R@10(any) | R@10(all) | MRR | nDCG@10 | Δ vs BM25 (CI) | ms/query |
| bm25 | | | | | | | | | |
| bm25+chunks | | | | | | | | | |
| dense-head-only | | | | | | | | | |
| dense-chunked (pilot/full?) | | | | | | | | | |
| dense-head-only+instr | | | | | | | | | |
| hybrid (RRF) | | | | | | | | | |
| hybrid+rerank | | | | | | | | | |
| oracle | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | — | — |
# By style (gold A; gold B agreement alongside)
| style | n | BM25 | dense | hybrid |
| title (size-1) | | | | |
| title-subset | | | | |
| same-topic-multi (≥2) | | | | |
| cross-ministry | | | | |
# Error budget — answerable only, k=10/top-8 (WATERFALL, rows sum to 1.000)
| slice | n | A retrieval | B evidence (MER-1/2/3: / / ) | C generation | success | Σ |
| all (Gold A) | | | | | | 1.000 |
| title | | | | | | |
| title-subset | | | | | | |
| same-topic-multi | | | | | | |
| cross-ministry | | | | | | |
# Abstention — unanswerable (correct = abstain)
| slice | n | correct abstain | wrong answer | abstain P / R |
| no_answer_in_corpus | | | | |
| unanswerable_en | | | | |
# Exp.2 — policy comparison (frozen <retriever>, tiers B/C n=200; name policy in every sentence)
| policy | coverage (all/ans/unans) | faithfulness | citation P/R | abstain P/R | violation |
| A free | | | | | |
| B evidence-instructed | | | | | |
| C +evidence gate | | | | | |
| D +verify+abstain | | | | | 0.000 |
| extractive (ref) | | | | | 0.000 |
# Checker costs | violation D=0.000 (hard gate + neg. control) | numeric-payload rate | false_demote / false_support (gate's own budget, n=12) | policy cost = coverage lost at τ |
# Answer tiers: A QUALITATIVE n=24 (±16, ranks nothing) · B/C n=200 AUTO (±6.3, carries CI; gold = answer's own clauses, 94.9% derivable)
| answerer | coverage F1 | citation P | citation R | trace rate | demoted |
# Failure taxonomy (same 12 — worth more than aggregates at this n)
| retrieval miss | hit-but-no-span | unsourced-claim → demoted | correct abstain | wrong abstain (MER too strict) | count each |
# Chunking ablation (dev): size × overlap → nDCG@10
# Cost of compromises (measured, not admitted): head-only cost <±y> nDCG on <20k> pilot, full pass <h> h at r=<..> → <on/off table> · rerank +<z> at <s> s/q · dev-only tuning, reverse-split moved headline <±w>
# Caveats (≤5): titles overstate all systems · relevance = title-token equality (Gold A) + n=<..> human (Gold B) · <x>% out-of-split gold · 1995–2024 only · 3-line card provenance, P_flag undeciphered
```

**Sanity checks before pasting:** `R@1≤@3≤@5≤@10` · `MRR ≥ R@1` · **oracle exactly 1.000** · `dup_qslno = 0` · waterfall rows sum to 1.000 · D violation 0.000.

---

## 12. Schedule

**Tonight (prep, in order):**

1. `pip install -r requirements.txt`; note whether `torch` is cached (else 196 MB CPU wheel).
2. `build_corpus.py --verify-only` (20k census, ~1 min, writes only `manifest_verify.json`) → confirm §3 magnitudes → then the real build.
3. `make_queries.py` → 5 styles + collision stats + `--gold-b 100 --seed 7`.
4. **Measure `r` before deciding anything dense:** `encode(200 docs)`, 4 threads, wall-clock. `187800/r` = head-only pass, `657300/r` = chunked (`<2 h` → full, else 20k pilot). Fill `r=<measured>` in DECISIONS-5.
5. Write 24 human queries + gold `qslno`s + sub-parts + 2 unanswerables (~1.7 h at measured 4.3 min each; short evening → cut to 16, keep tier B/C which carry the numbers). Take deterministic 200-query auto tier (free). **Gold B sittings:** 2 × 50 queries (~1.5–2 h, source-blinded; hard cap 2 h, fallback n=60).
6. Probe key (chat 200, embeddings 200-or-403); cache first 24 answer + 24 judge calls; record credits-before/after (tier D ceiling becomes measured).
7. Public repo, push. Touch no pipeline code after.

| Hour | graded window | gate |
|---|---|---|
| **1** | `index_lexical` + `evidence_gate.py` + extractive `answer.py` + `verify_claims.py` (all deterministic — exist from hour 1); run on dev, **print chunks in full**; commit | crude end-to-end runs (Day-1 requirement) |
| **2** | `make_queries` on test; BM25 frozen config; bootstrap CI harness | baseline measured and frozen |
| **3** | `dense-head-only` (load-and-score — matrix is a file by now) + `+instr` + `fusion`; kick off `dense-chunked` pilot; persist every ranked list + vector file | nothing recomputes Day 2 |
| **4** | **Freeze.** Full test eval all rows; tier B/C scoring (17 min — not the thing to cut); launch `hybrid+rerank` (`n_test×20` pairs) as background job on committed fused lists (foreground-free; if >~2 h use deterministic 5k-query subset and say so); 2 unanswerables abstain; Exp-2 loop (A–D over cached contexts) + violation D=0.000 + bypass neg. control; headline line (Exp-1 + Exp-2 sentences); tier A under `qualitative (n=24)`, B/C with CI | no tuning on test, ever |
| **5** | 4 plots (systems bar · **error-budget stacked bar** · Recall@10-vs-size 20k/60k/120k/187k · chunking ablation · θ–τ secondary); fill `results.md` (waterfall + policy + Gold B), README Q3; **re-clone and run top to bottom** | the check they perform |
| **6** | Stop building. Rehearse: built 1 min (one live query, cached numbers noted) · found 2 min · would-do-differently 2 min | 10% of grade |

**Cut order (behind at hour 4):** Gold B 100→60 → reranker → dense-chunked beyond pilot → `+instr` → `bm25+chunks`. **Never cut:** evaluation, bootstrap CIs, plots, README, MER gate, policy D, waterfall assert, Gold B entirely (n=60 minimum).

---

## 13. Verified facts vs unverified (settle in this order)

**Verified by direct access, no credentials (plan date):** 306,400 rows, single `train` split, 15 fields; `english` holds the complete QA document incl. answer (docs read at 1,163/7,542/2,490 chars; 97.9% non-empty rows contain `ANSWER`); `qno` non-unique, `qslno` unique; 3,500 rows / 35 blocks — 28.0% empty English (all with metadata, 155 Hindi-instead), 61.3% usable, mean 2,857 / median 1,706 / max 45,596 chars, ~93% beyond 512 tokens, `hindi` 23.6%, years 1995–2024, 74 ministries (HOME AFFAIRS 164 / RAILWAYS 132 / HRD 131 / AGRICULTURE 129 / DEFENCE 120), title Jaccard 0.011 mean / 0.000 p90, 764 title terms in ≥3 docs; parquet 200 + `accept-ranges: bytes`; `/v1/models` 80 ids incl. retired (410: `nv-embedqa-e5-v5`); embeddings+chat exist (401 keyless); rerank 404 ×4 paths; `torch==2.4.1+cpu` unresolvable from CPU index; pinned versions §10; TCPD CSVs + codebooks checked (QH = Lok Sabha; second = elections, not questions); **tier-C auto-gold: 94.9%** of 1,973 live rows split at last `\bANSWER\b` with ≥2 markers both sides (median 3 answer-side; 70 question-only, 8 answer-only, 22 unusable); API limits: ~40 req/min per model + ~1,000 signup credits (three 2026 write-ups; NVIDIA: model-specific/unpublished — shape, not guarantee).

**Unverified — yours to settle:**

| item | why not | if wrong |
|---|---|---|
| Your throughput `r` (seq/s) | 2 cores / 1,938 MB here — a benchmark would be fiction | **sets scope**: r=190 → full chunked 0.96 h, worth it; r=20 → 9 h, pilot only |
| Peak RSS of `build_corpus.py` | can't hold 306k rows here | columnar read ~1.1 GB alone; on 2 GB the *build* is tight, not retrieval — drop `hindi` from COLS (−~90 MB) before anything else; confirm with `/usr/bin/time -v` |
| Your key's entitlements + tier-D spend | needs your key | tier D batched in 12s — stops at 24 queries worst case; tiers A–C unaffected; report "LLM arm limited to n=<x>" |
| Full-corpus census of §3 stats | API truncates >100 rows/request | 3,500-row figures are estimates; build replaces them in ~2 min |
| 94.9% auto-gold rate at full scale | API timeouts past ~2k rows | tier C n=200 either way; fallback share must be your census's, not 5.1% |
| True year span; empties Hindi-by-design? | only a census says | §11.3 caveats need census numbers |

First commands: `build_corpus.py --verify-only` + API probe (15 min) → every row above becomes your number in `manifest_verify.json` (`"full_corpus": false` — quote as census sample only).

---

## 14. Pre-registration summary (predictions to beat)

1. `title` saturates >0.9 for BM25; dense gain only in `title-subset`/`cross-ministry`; `same-topic-multi` loses most Recall@10.
2. `hybrid ≥ max(bm25, dense)` on nDCG@10, non-overlapping CIs.
3. Gold B confirm ≥0.8 singleton / ≤0.6 multi (construct degrades where grading matters).
4. Exp. 2: coverage A>B>C>D, faithfulness/abstention-precision reverse, B→D gap > A→B gap, violation D=0.000 with C>0.
5. Waterfall: A dominates `title-subset`/`cross-ministry`, B dominates `same-topic-multi`, C smallest except Policy A.

---

## 15. Build order for the AI (dependency order + acceptance criteria)

- [ ] 1. Env + `requirements.txt`; `./reproduce.sh` skeleton (fresh-clone runnable).
- [ ] 2. `build_corpus.py` (§3) → `--verify-only` writes only `manifest_verify.json`; full build: `dup_qslno=0`, magnitudes ≈ §3, `sha256_meta` matches file on disk.
- [ ] 3. `make_queries.py` → 5 styles, `n_gold_out_of_split` per query, collision stats; `--gold-b` emits 100-query file. Annotate Gold B (2 sittings, blinded).
- [ ] 4. `index_lexical.py` + BM25 sweep on dev → freeze config; persist ranked lists.
- [ ] 5. `evidence_gate.py` (§5.2) + `verify_claims.py` (§5.4) + `answer.py --policy` + extractive; **6-case adversarial suite passes** (supported ≥0.80 / demoted below; year-flip caught by numeric check only).
- [ ] 6. `retrieve.py --print-chunks` → read real chunks before any prompt work.
- [ ] 7. Measure `r`; `index_dense.py` head-only (+chunked per rule); `fusion.py` RRF (doc-granularity — max-pool chunks first); `rerank.py` (background, hour 4).
- [ ] 8. `evaluate.py` → Exp-1 tables on Gold A + B; **oracle row exactly 1.000**; bootstrap CIs; Gold B agreement + κ.
- [ ] 9. `score_parts.py` → Exp-2 A–D tables on tiers B/C (+A qualitative read); **D violation = 0.000 + bypass neg. control**; **waterfall Σ = 1.000 asserted**.
- [ ] 10. Tier-D LLM calls in batches of 12 (cache everything); judge axis on tier A only.
- [ ] 11. `plots.py` → 4 figures; `results.md` filled (§11.3); README Q3 digits; DECISIONS 16 entries.
- [ ] 12. Fresh-clone reproduce; rehearse talk.

**Global asserts (any failure voids the run):** oracle 1.000s · `R@1≤@3≤@5≤@10` · `MRR≥R@1` · waterfall sums · D violation 0.000 · every `results.md` digit printed by a repo script (else `<FILL>`) · every answer number names its tier · every retrieval claim names its gold.

*End of plan. Strongest improvement: policy comparison (§7 Exp. 2). Most load-bearing line: the MER rule (§5.2).*
