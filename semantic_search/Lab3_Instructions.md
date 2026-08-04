# Lab 3 — Semantic Search (Capstone, Part 1)

Build a small semantic search engine: turn a corpus of short text documents into embeddings, search it by meaning (not just keyword matching) using cosine similarity, and visualize the resulting embedding space with PCA.

Everything below is required, and everything below should comfortably fit in a single 3-hour session.

Work in this `semantic_search/` folder. It already has empty files to fill in (`search.py`, `requirements.txt`, `README.md`), a placeholder `documents.json` showing the expected format, and `semantic_search_starter.ipynb` — a blank notebook shell with a section and `# TODO` per step, structure only, no logic. `embeddings.py` is **not** blank — see Step 1, it comes partly pre-written.

```bash
pip install -r requirements.txt
```

---

## 0. Before You Touch Any Code: Reuse Your Lab 1 API Key

This lab uses the **same NVIDIA NIM key** from Lab 1 — no new signup. If you still have it, you're set; if you lost it, regenerate one at [build.nvidia.com/settings/api-keys](https://build.nvidia.com/settings/api-keys).

Key facts you'll need:
- **Endpoint:** `https://integrate.api.nvidia.com/v1/embeddings`
- **Auth header:** `Authorization: Bearer <NVIDIA_API_KEY>`
- **Model:** `nvidia/nv-embedqa-e5-v5`

**Two things that are different from Lab 1's chat endpoint** — easy to miss if you're copying patterns from memory instead of reading the docs carefully:
1. The request body's `input` field must be a **list** of strings (`["some text"]`), not a bare string.
2. This model is asymmetric and requires an `input_type` field: `"passage"` when embedding a document going into your index, `"query"` when embedding the search query itself. Get this backwards and your search will still run without erroring, but results will be worse — this is a good example of a bug that doesn't crash, only quietly underperforms.

**You do not need a working API key to build most of this lab.** `embeddings.py` ships with a working `offline` mode (see Step 1) that runs with no key and no network at all — build and test your entire pipeline in offline mode first, and only switch to the real API once everything works end to end. This mirrors Lab 1's advice to prove the riskiest unknown works before building on top of it, just inverted: here, the riskiest unknown is your own logic, so isolate that from the API dependency instead of the other way around.

---

## 1. Embeddings (`embeddings.py`)

Open `embeddings.py`. Most of it is already written for you:

- `.env` loading is already wired up (`load_dotenv()`) — copy `.env.example` to `.env` and fill in your key, no manual `export` needed each terminal session.
- `_get_embedding_offline` is **fully implemented** — a hashed bag-of-words vector, a text representation technique you likely haven't seen elsewhere in this course. You don't need to write or deeply understand this function; it's provided purely as scaffolding so you can build and test your whole pipeline (search, ranking, visualization) with no API key and no network. Skim the docstring so you know roughly what it's doing, but don't spend time on it.
- `get_embedding(text, input_type)` is also written — it's just the switch between the two modes.
- **`_get_embedding_api` is the one function you write.** This is the actual new content of this step: call the NVIDIA NIM embeddings endpoint (same shape of work as Lab 1's `call_model`, different endpoint) and return the embedding as a plain list of floats.

**Fail loudly if the API mode is selected but no key is set** — same principle as Lab 1's `check_api_key`.

---

## 2. Load a Corpus and Build an Embedding Matrix (`search.py`)

### Step 1: Build your own corpus

Replace the placeholder entries in `documents.json` with your own. Each entry needs a `topic`, a `text` passage, and a unique `id`. Aim for **at least 20 documents spread across 4-6 clearly distinct topics** — distinct topics matter more than raw document count for getting a convincing result in Step 4's visualization. Pick topics that don't semantically overlap (e.g. astronomy, cooking, and sports separate cleanly; "cats" and "dogs" as separate topics probably won't).

**Keep each document to one or two sentences** — a single factual statement is enough (e.g. "A light-year measures distance, not time — it's the distance light travels in one year.") This is a coding lab, not a writing exercise; don't spend 45 minutes crafting polished paragraphs when a plain sentence does the job just as well for testing search and clustering. Topics you already know well (something from another course, a hobby, whatever) are usually faster to write than something you'd have to research.

### Step 2: Load documents and fetch embeddings

Write `load_documents(path)` to read your JSON file, and `build_embedding_matrix(documents)` to fetch (or compute, in offline mode) an embedding for every document and stack them into one NumPy matrix — one row per document.

**Cache your embeddings to a file** (e.g. `embeddings_cache.json`) the first time you fetch them, and load from that cache on subsequent runs instead of re-fetching. This isn't optional polish — without it, every re-run of your notebook re-calls the API for every document, which is slow and burns your rate limit for no reason. Think about what should trigger a cache miss (a corpus that's changed size is one obvious signal).

---

## 3. Cosine Similarity Search

Reuse `cosine_similarity` from Lab 2 unchanged. Write a `search(query, embedding_matrix, documents, top_k)` function that:
1. Embeds the query itself — remember, this call needs `input_type="query"`, not `"passage"`.
2. Computes the similarity between the query embedding and every document's embedding.
3. Returns the `top_k` highest-scoring documents, together with their scores.

The pattern for finding the top-k highest values is the mirror image of Lab 2's k-NN, which found the *smallest* k distances — same `argsort` idea, sorted the other direction.

**Test this with at least two different example queries** and sanity-check that the results are actually relevant to what you asked, not just that the code runs without error.

---

## 4. Visualize the Embedding Space With PCA

Reuse your Lab 2 PCA-via-SVD function, extended from one principal component to two so you can scatter-plot the result in 2D. Color each point by its document's `topic`. With a well-chosen corpus (distinct topics, reasonable document count per topic), you should see visibly separated clusters — more cleanly separated in real API mode than in offline mode, which is itself worth noticing and is a fine thing to mention in your README.

---

## Deliverable Checklist

- [ ] `_get_embedding_api` implemented in `embeddings.py` (offline mode is provided, no work needed there)
- [ ] `documents.json` replaced with your own corpus (20+ documents, 4-6 distinct topics)
- [ ] `search.py` with a working `search()` function, cosine similarity, and a persisted embeddings cache
- [ ] At least two example queries run and shown to return relevant results
- [ ] A PCA scatter plot of the embedding space, colored by topic, with visibly separated clusters
- [ ] A `README.md` explaining what your program does and how to run it (including how to switch between offline and API mode)

## Grading Rubric (Lab 3 = 12% of course grade)

The highest weight of the three labs, reflecting that this is the Part 1 capstone: it requires correctly integrating Lab 1's API-call pattern and Lab 2's cosine similarity and PCA-via-SVD into one working system, on top of the genuinely new pieces (embedding-based retrieval, top-k ranking, a corpus you design yourself, and a caching strategy). Graded per-criterion as working/not-working, same as Labs 1 and 2.

| Category | Weight | Criteria |
|---|---|---|
| Embeddings pipeline | 25% | `_get_embedding_api` correctly implemented — right endpoint, headers, list-wrapped `input`, correct `input_type` per call site (15%) + embeddings persisted to a cache and correctly reloaded rather than refetched every run (10%). |
| Search correctness | 30% | Cosine similarity reused correctly (5%) + `search()` correctly finds and ranks the top-k most similar documents (15%) + at least two example queries demonstrated returning relevant results (10%). |
| PCA visualization | 25% | Correct reuse of Lab 2's PCA-via-SVD, extended to 2 components (10%) + scatter plot colored by topic, with axis labels and a title (10%) + a corpus with topics distinct enough to show visibly separated clusters (5%). |
| Code organization & README | 20% | Code organized into functions across `embeddings.py` and `search.py`, not one script (10%) + README clearly explains what the program does and how to run it in both modes (10%). |

---

## How to Submit

1. Push your final code to a **GitHub repository**. Make sure the repository is **public** so it can be reviewed.
2. Your repo should include at minimum: `embeddings.py`, `search.py`, `documents.json` (your own corpus), `requirements.txt`, a `README.md`, and a `.gitignore` that excludes your `.env` file.
3. Submit the **link to your public GitHub repository** on Moodle. That link is your submission — nothing else needs to be uploaded separately.

Before you submit, double check that your repo runs cleanly if someone clones it fresh in offline mode (no key needed), and that switching to API mode is a one-line environment variable change, not a code edit.

---

## Troubleshooting Quick Reference

| Symptom | Likely cause | Fix |
|---|---|---|
| Clusters don't separate in the PCA plot | Too few documents per topic, or topics that overlap semantically | Use fewer, more clearly distinct topics; aim for 4-6 topics with several documents each |
| Search results seem irrelevant in offline mode | Expected — the provided hashed bag-of-words fallback matches on shared vocabulary, not meaning | Switch to API mode for real semantic results; this is a real limitation of the offline fallback, not a bug |
| `NotImplementedError` when calling `get_embedding` | `_get_embedding_api` hasn't been filled in yet | Implement it, or set `LAB3_EMBEDDING_MODE=offline` to keep building without it in the meantime |
| `422` or a malformed-request error calling the embeddings endpoint | Sent `input` as a bare string instead of a list, or omitted `input_type` | Body must include `"input": [text]` (a list) and `"input_type": "passage"` or `"query"` |
| `429` rate limit while fetching embeddings | Many documents fetched in a tight loop | Add a short delay between calls, or rely on your cache after the first successful run |
| Re-running your notebook re-fetches every embedding | Cache file missing, or your cache-loading logic isn't wired up | Confirm the cache file exists after a run and that you're actually checking for it before calling the API again |
| Search results look identical regardless of query | Query embedded with `input_type="passage"` instead of `"query"` | This won't crash, so it's easy to miss — check that call site specifically |
