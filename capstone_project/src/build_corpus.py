"""src/build_corpus.py — 2019+ corpus (default) or full-scale; no sampling except the year window.

`--since 2019` keeps only rows whose answer date is >= 2019 (undated rows kept).
`--refilter` trims an already-built corpus.jsonl in place (no re-download).
"""
import argparse
import hashlib
import json
import re
import time
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional

import duckdb
from huggingface_hub import hf_hub_download

REVISION = "508b2411283162fdd52ee2c3e8ccaefbabfe9581"
REPO     = "anudit/rajyasabha-qa"
COLS     = ["english","hindi","qslno","qtitle","qtype","adate","shri","qno",
            "name","min_name","ses_no","status","mp_code","P_flag"]
ANSWERED_PREFIX = "ANSWER"
STOP     = set("the a an of to in and for is on by that with as be from are was it not has have been will "
               "per govt india government ministry minister be pleased state answer answers".split())
QNO      = re.compile(r"QUESTION NO\s*[0-9]{1,2}\.[0-9]{2}")
ANS      = re.compile(r"\bANSWER\b|उत्तर")
WORDS    = re.compile(r"[A-Za-z']{4,}")

def sha(p):  return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def norm(s): return (s or "").strip().upper()
def toks(s): return {w.lower() for w in WORDS.findall(s or "")} - STOP

def year_of(r: Dict[str, Any]) -> str:
    return (r.get("answer_date") or "")[:4]

def in_window(ans_date: str, since: str) -> bool:
    return not ans_date or ans_date[:4] >= since

def _summarize(recs: List[Dict[str, Any]], texts: List[str], since: str, t0: float,
               repo: str, revision: str, n_scanned: int, dupes: int,
               full_corpus: bool) -> Dict[str, Any]:
    """Recompute the full manifest census from (already-filtered) records."""
    stats = Counter()
    status_census = Counter()
    for r, t in zip(recs, texts):
        stats[r["lang"]] += 1
        ok = r["retrievable"]
        stats["usable_" + r["lang"]] += int(ok)
        stats["mangled"] += int(bool(QNO.search(t)))
        stats["over512"] += int(len(t) > 2000)
        status_census[r["status"]] += 1

    groups = Counter(tuple(r["title_tokens"]) for r in recs if r["retrievable"])
    gsizes = Counter(min(v, 5) for v in groups.values())
    over2 = sum(v for v in groups.values() if v >= 2)
    yrs = Counter(year_of(r) for r in recs if r["answer_date"])
    mins = Counter(r["ministry"] for r in recs if r["retrievable"])
    years = sorted(yrs)

    return {"built_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "repo": repo, "revision": revision,
            "since_year": since, "rows": len(recs), "dup_qslno": dupes,
            "lang": dict(stats), "usable": {k: v for k, v in stats.items() if k.startswith("usable")},
            "ocr_mangled_qno": stats["mangled"], "docs_over_512_tokens": stats["over512"],
            "min_years": years[0] if years else None, "max_years": years[-1] if years else None,
            "n_years": len(years),
            "n_ministries": len(mins), "largest_ministries": mins.most_common(10),
            "title_group_sizes_1_2_3_4_5plus": [gsizes.get(k, 0) for k in (1, 2, 3, 4, 5)],
            "n_unique_queries_after_grouping": len(groups),
            "status_census": dict(status_census.most_common(25)),
            "status_census_truncated": len(status_census) > 25,
            "queries_with_2plus_same_title": over2,
            "pct_retrievable_queries_ambiguous": round(100 * over2 / max(1, sum(groups.values())), 2),
            "build_seconds": round(time.time() - t0, 1), "sha256_meta": None,
            "census_rows_scanned": n_scanned, "full_corpus": full_corpus}


def _record(cols: Dict[str, List], i: int, text: str, since: str) -> Optional[Dict[str, Any]]:
    e = text.strip()
    lang = "en" if e else ("hi" if (cols["hindi"][i] or "").strip() else "meta_only")
    has_ans = bool(ANS.search(e))
    ok = bool(e) and has_ans
    ans_date = (cols["adate"][i] or "")[:10]
    if not in_window(ans_date, since):
        return None
    return {"qslno": cols["qslno"][i], "lang": lang, "retrievable": ok,
            "ministry": norm(cols["min_name"][i]), "qtype": norm(cols["qtype"][i]),
            "status": norm(cols["status"][i]),
            "status_is_answered": norm(cols["status"][i]).startswith(ANSWERED_PREFIX) and ok,
            "answer_date": ans_date,
            "ses_no": cols["ses_no"][i], "qno": cols["qno"][i], "member": cols["name"][i],
            "title": (cols["qtitle"][i] or "").strip(), "title_tokens": sorted(toks(cols["qtitle"][i])),
            "chars": len(e), "n_chunks": len(e) // 1500 + 1}


def _build_from_parquet(d: Path, since: str, scan: Optional[int] = None) -> int:
    t0 = time.time()
    f = d / "corpus.parquet"
    if not f.exists():
        src = hf_hub_download(repo_id=REPO, repo_type="dataset", filename="train-00000-of-00000.parquet",
                              revision=REVISION, local_dir=str(d))
        Path(src).rename(f)
    print(f"parquet: {f.stat().st_size/1e6:.0f} MB  sha256={sha(f)[:16]}  {time.time()-t0:.0f}s")

    con = duckdb.connect()
    query = f"SELECT {', '.join(COLS)} FROM read_parquet('{f}')"
    if scan:
        query += f" LIMIT {scan}"
    result = con.execute(query).fetchall()
    cols = {c: [row[i] for row in result] for i, c in enumerate(COLS)}
    n = len(result)
    print(f"raw rows: {n:,}")

    seen, dupes = set(), 0
    for q in cols["qslno"]:
        if q in seen:
            dupes += 1
        seen.add(q)
    if dupes:
        print(f"FAIL: {dupes} duplicate qslno -> refusing to build")
        return 1

    recs, texts = [], []
    text_col = cols["english"]
    for i in range(n):
        e = (text_col[i] or "").strip()
        rec = _record(cols, i, e, since)
        if rec is None:
            continue
        recs.append(rec)
        texts.append(e or (cols["hindi"][i] or "").strip())

    full = scan is None
    out = _summarize(recs, texts, since, t0, REPO, REVISION, n, dupes, full_corpus=full)
    if scan:
        (d / "manifest_verify.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
        print(json.dumps(out, indent=1))
        return 0
    _write_artifacts(d, recs, texts, out)
    size_mb = f.stat().st_size / 1e6
    f.unlink()
    print(f"removed raw {f.name} ({size_mb:.0f} MB) — kept only >= {since} rows")
    print(json.dumps(out, indent=1))
    print("OK: qslno unique")
    return 0


def _refilter_corpus(d: Path, since: str) -> int:
    """Trim an existing corpus.jsonl (+meta.jsonl, +manifest) to the year window, in place."""
    f = d / "corpus.jsonl"
    if not f.exists():
        print(f"FAIL: {f} not found (build the corpus first)")
        return 1
    t0 = time.time()
    mpath = d / "manifest.json"
    old = json.loads(mpath.read_text(encoding="utf-8")) if mpath.exists() else {}
    recs, texts = [], []
    before = 0
    for line in f.open(encoding="utf-8"):
        r = json.loads(line)
        before += 1
        text = r.pop("text")
        if not in_window(r.get("answer_date") or "", since):
            continue
        recs.append({k: v for k, v in r.items()})
        texts.append(text)
    if len(recs) == before:
        print(f"No rows dropped (all {before} already >= {since}); nothing written. Done.")
        return 0
    out = _summarize(recs, texts, since, t0,
                     old.get("repo", REPO), old.get("revision", REVISION), before, 0,
                     full_corpus=old.get("full_corpus", False))
    _write_artifacts(d, recs, texts, out)
    print(f"refiltered {before:,} -> {len(recs):,} rows (>= {since})   {time.time()-t0:.1f}s")
    print(json.dumps(out, indent=1))
    return 0


def _write_artifacts(d: Path, recs: List[Dict], texts: List[str], out: Dict[str, Any]) -> None:
    (d / "meta.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in recs), encoding="utf-8")
    out["sha256_meta"] = sha(d / "meta.jsonl")
    (d / "manifest.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    with (d / "corpus.jsonl").open("w", encoding="utf-8") as fh:
        for r, t in zip(recs, texts):
            fh.write(json.dumps({**r, "text": t}, ensure_ascii=False) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dest", default="data")
    ap.add_argument("--since", default="2019", help="Keep rows with answer_date >= YEAR")
    ap.add_argument("--refilter", action="store_true", help="Trim an existing corpus.jsonl instead of re-downloading")
    ap.add_argument("--verify-only", action="store_true")
    a = ap.parse_args()
    d = Path(a.dest)
    d.mkdir(parents=True, exist_ok=True)

    if a.verify_only:
        return _build_from_parquet(d, a.since, scan=20000)
    if a.refilter:
        return _refilter_corpus(d, a.since)
    return _build_from_parquet(d, a.since)


if __name__ == "__main__":
    raise SystemExit(main())