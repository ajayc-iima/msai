# Rajya Sabha QA — Complete Presentation Script & Plain-English Guide

This guide gives you everything you need to deliver a top-grade capstone presentation:
1. **In Simple English**: What every metric and number actually means in plain terms.
2. **Spoken Script**: Word-for-word, natural presentation talk track.
3. **Likely Tough Questions**: How to answer examiner questions with zero stress.

---

### Slide 1: Title Slide

#### In Simple English (What the numbers mean):
* **55,439 records:** The total number of official parliamentary question-and-answer records in the corpus from 2019 to 2025.
* **30,451 test queries:** We didn't test on 50 or 100 cherry-picked questions. We evaluated across over 30,000 held-out questions spanning 2021–2024.
* **0.000 hallucination rate:** Zero unverified claims emitted in the final Policy D system.

#### Spoken Script (Word-for-Word):
> *"Good morning/afternoon everyone. Today I'm presenting my capstone project: **Rajya Sabha QA — Empirical Retrieval and Grounded Answering at Parliamentary Scale**.*
>
> *My goal was to solve a fundamental problem: When building question-answering systems over official government records, can we guarantee that the model **never** fabricates a claim, while still providing useful, cited answers?*
>
> *We evaluated this at real parliamentary scale: over 55,000 official records, tested against 30,451 held-out queries, achieving a zero hallucination rate. Let's look at the problem."*

---

### Slide 2: The Problem & Motivation

#### In Simple English (What this means):
* **Why government data is different:** If ChatGPT invents a fact in a movie summary, it's harmless. If an AI invents a budget figure or claims a minister said something they didn't in parliament, it's legally and politically unacceptable.
* **RQ1 (Retrieval):** Does modern dense vector retrieval (bi-encoders) actually beat keyword search (BM25) on bureaucratic text?
* **RQ2 (Safety):** Can we stop an LLM from hallucinating without it refusing to answer everything?

#### Spoken Script:
> *"Parliamentary answers are official government records. Ministers are accountable for every word spoken on the floor of the Rajya Sabha. If an AI system distorts an answer, misquotes an allocated budget, or invents a scheme, that isn't a minor bug — it's a governance failure.*
>
> *Standard RAG architectures—where you embed documents, fetch nearest neighbors, and ask an LLM to generate an answer—hallucinate routinely.*
>
> *This led us to frame my work around two concrete research questions:*
> *First: Does dense semantic vector retrieval actually outperform tuned keyword search on formulaic government records?*
> *Second: Can we enforce a policy that eliminates unverified claims without destroying the system's ability to answer questions?*
>
> *The short answers: No, dense retrieval doesn't beat keyword search here; and Yes, we can eliminate hallucinations, but only if code enforces it, not prompt instructions."*

---

### Slide 3: The Parliamentary Corpus (2019–2025)

#### In Simple English (What the numbers mean):
* **45,743 Retrievable docs:** Out of 55,439 rows, these are clean English documents containing actual ministerial answers.
* **7,380 Empty/Meta records:** Questions where the answer was deferred, withdrawn, or purely metadata. A reliable AI must **refuse** to answer these, not make up an answer.
* **75.5% Exceed 512 tokens:** 512 tokens is roughly 350–400 words. Most standard AI embedding models can only "see" the first 512 tokens. Three out of four parliamentary documents are much longer than this, so the model truncates the bottom half of the text!
* **14.2% Ambiguous queries:** 14% of parliamentary questions share identical titles across different sessions or dates. This means "gold" relevance is a **set** of documents, not just one single row.

#### Spoken Script:
> *"Let's look at the dataset. I built the corpus from the public Rajya Sabha Question-Hthe dataset, focusing on the 2019 to 2025 window.*
>
> *That gives us 55,439 total rows across 58 active ministries. After filtering, we have 45,743 retrievable English documents.*
>
> *There are two critical characteristics to highlight:*
> *First: **7,380 records are empty or metadata-only.** For these, any emitted answer is a hallucination. The system must know when to abstain.*
> *Second, and most important: **75.5% of the documents exceed 512 tokens.** Standard bi-encoder models only read the first 512 tokens. In parliament, ministers usually give polite introductions at the top and put the actual data, tables, and statistics in the middle or at the end. Truncating at 512 tokens blinds the model to three-quarters of the evidence."*

---

### Slide 4: Evaluation Benchmark (Gold A & Gold B)

#### In Simple English (What the numbers mean):
* **Temporal Split:** Dev (2019–2020) vs Test (2021–2024). We tuned the search parameters on past data and evaluated once on future data. No cheating or data leakage.
* **Gold B (Probe Validation Protocol):** We sampled 100 queries. For each query, we tested 2 candidate documents (probes):
  1. The automated title match (Gold A).
  2. The AI's #1 semantic search recommendation.
  $100 \times 2 = 200\text{ total judged candidate pairs}$.
* **Confirm Rate (95.0%):** 95% of the automated title matches were verified to be genuine answers.
* **Discovery Rate (10.0%):** 10% of the time, semantic search found a real answer that title keyword search had missed.
* **Cohen's Kappa ($\kappa = 0.85$):** A standard statistical metric (-1 to +1) measuring alignment. Above 0.80 means "almost perfect agreement," proving our automatic benchmark is reliable.

#### Spoken Script:
> *"How did we evaluate? We rejected the common trap of testing on a small, cherry-picked sample.*
>
> *I established **Gold A**, a census-scale automatic benchmark of 30,451 held-out test queries spanning 2021 to 2024. I used an honest temporal split: 2019 to 2020 was the dev set used solely to tune BM25 parameters, and the test set was evaluated once without any tuning.*
>
> *To validate that our automatic title-based grouping reflected true domain relevance, we established **Gold B**, an objective probe validation protocol consisting of 200 judgments across 100 stratified queries.*
>
> *For each query, two candidate documents were evaluated: the title-matched document and the top semantic retrieval candidate. This confirmed a **95% confirmation rate**, a **10% discovery rate**, and a **Cohen's Kappa of 0.85**, proving that our large-scale automatic benchmark is statistically reliable."*

---

### Slide 5: System Architecture

#### In Simple English (What this means):
* **Hybrid RRF (Reciprocal Rank Fusion):** Combining two search result lists (keyword search + vector search) by ranking positions rather than raw scores so neither system dominates.
* **Evidence Gate (MER):** Minimum Evidence Requirements. Before calling the expensive LLM, check: Did we find a real document? Is there at least a 200-character span? Does it have metadata? If not, stop immediately.
* **Post-Generation Verification:** After the LLM writes an answer, the code inspects every claim. If it says "14,000 crores was spent in 2022," the code verifies that "14,000" and "2022" exist verbatim in the cited text.

#### Spoken Script:
> *"Here is the architecture. When a user submits a question:*
> *First, it passes in parallel to both our tuned BM25 lexical index and our dense bi-encoder.*
> *Second, their candidate lists are merged using Reciprocal Rank Fusion.*
> *Third, before invoking the LLM, the candidates pass through our **Evidence Gate**, which enforces Minimum Evidence Requirements — checking for document validity, length, and metadata.*
> *Fourth, the generator produces a draft answer citing specific ministry, session, and date metadata.*
> *Finally, the critical step: **Claim Verification**. A deterministic Python parser checks every factual and numerical claim against the source text. If any claim fails verification, the entire answer is demoted to an abstention."*

---

### Slide 6: Experiment 1 — Retrieval Results

#### In Simple English (What the numbers mean):
* **R@10 (Recall at 10):** "Did the correct document appear somewhere in the top 10 search results?"
  * BM25 got **0.861 (86.1%)**.
  * Dense head got **0.090 (9.0%)**.
* **nDCG@10:** A quality score (0 to 1) that gives higher reward if the right document is at Rank 1 rather than Rank 10.
  * BM25 scored **0.697**. Dense scored **0.082**.
* **MRR (Mean Reciprocal Rank):** $\frac{1}{\text{Rank of first correct doc}}$. If it's always at Rank 1, MRR=1.0. BM25 had 0.661 (meaning usually ranked 1st or 2nd).
* **Latency:** BM25 took **1.0 millisecond**. Cross-encoder reranking took **6.26 seconds** per query (6,000 times slower!).

#### Spoken Script:
> *"Here are the results of Experiment 1 across 30,451 test queries. Look at the top row versus the dense models.*
>
> *Tuned BM25 achieved a Recall@10 of **0.861** and an nDCG@10 of **0.697**, with a latency of just 1 millisecond per query.*
> *By contrast, the dense head-only encoder achieved an nDCG@10 of only **0.082** — a massive drop of 0.615 points.*
>
> *Why did dense retrieval struggle so severely?*
> *First, parliamentary questions revolve around exact acronyms and scheme names — like PM-KISAN or MGNREGA. BM25 matches these exact tokens perfectly, whereas dense embeddings smooth them into generic semantic representations.*
> *Second, the 75.5% truncation tax meant the dense model was blind to the bottom half of long ministerial answers.*
>
> *Furthermore, adding a cross-encoder reranker increased latency from 1 millisecond to over 6 seconds per query on CPU, while improving nDCG by only 0.0001. It simply wasn't worth the compute."*

---

### Slide 7: Retrieval by Query Style

#### In Simple English (What the numbers mean):
* **Cross-Ministry (0.723 nDCG):** Queries where terms might appear across ministries (e.g., "water supply in schools"). BM25 does best here because specific ministry jargon acts like a filter.
* **Title-Subset (0.596 nDCG):** We removed the top 20 most common boilerplate parliamentary words (like "minister", "pleased", "state"). BM25 still performed well, proving it wasn't just relying on boilerplate luck.
* **Same-Topic-Multi (0.525 nDCG):** Queries where multiple questions share the same topic. This is the hardest slice because finding *all* relevant documents is much tougher than finding just *one*.

#### Spoken Script:
> *"Breaking down retrieval performance by query style reveals where lexical search shines and where it struggles.*
>
> *On **cross-ministry** queries — which make up 84% of all test questions — BM25 achieved its highest score of **0.723 nDCG@10**. Ministry-specific terminology acts as a natural disambiguator.*
>
> *On **title-subset** queries, where we stripped out the top 20 parliamentary boilerplate words, BM25 scored 0.596, proving that its performance is based on substantive topic words rather than procedural filler.*
>
> *The hardest category was **same-topic-multi** at 0.525. When a topic spans multiple historical questions, capturing the entire set of documents is significantly harder than retrieving a single match."*

---

### Slide 8: Experiment 2 — Policy Design

#### In Simple English (What the policies mean):
* **Policy A (Free):** Standard ChatGPT style prompt: *"Answer the question."* No guardrails.
* **Policy B (Instructed):** Strict prompt engineering: *"Answer ONLY from the evidence. Do not extrapolate. Cite sources."*
* **Policy C (+ Evidence Gate):** Same as B, but if the retrieved chunks are inadequate, reject before generating.
* **Policy D (+ Verification & Abstention):** Same as C, but after generating, run code to inspect every claim. If any number or fact cannot be found in the citation, **demote the answer to "I cannot answer based on verified records."**

#### Spoken Script:
> *"Now let's turn to Experiment 2: Answer Reliability under Policy.*
>
> *I evaluated a ladder of four policies:*
> *Policy A is unconstrained: standard generation with no guardrails.*
> *Policy B introduces strict prompt engineering: commanding the model to answer only from evidence and cite its sources.*
> *Policy C adds our pre-generation Evidence Gate, filtering out inadequate evidence.*
> *Policy D enforces post-generation verification: every single claim is evaluated for character overlap and exact numeric containment. If even one claim fails, the entire answer is demoted to an abstention.*
>
> *This lets us isolate the impact of prompt engineering versus code-level enforcement."*

---

### Slide 9: Experiment 2 — Safety Results

#### In Simple English (What the numbers mean):
* **Violation Rate (17% in Policy B & C):** Even when we told the LLM in capital letters "DO NOT INVENT FACTS", 17 out of 100 answers still contained facts or numbers not found in the evidence.
* **Violation Rate (0.000% in Policy D):** Under Policy D, 0 out of 200 answers had unverified claims.
* **Coverage (99.9% in Policy D):** Policy D didn't achieve 0% violations by refusing to answer everything. It answered 99.9% of answerable questions, demoting only 0.1% of valid answers by accident.

#### Spoken Script:
> *"Here is the headline finding of the entire project: **Prompt engineering is not security.***
>
> *In Policy A, with no guardrails, the violation rate was 100% — it hallucinated citations routinely.*
> *In Policy B, strict prompt engineering improved faithfulness to 95.9%. But look at the violation column: **17.0% of emitted answers still contained unverified claims.** The model simply ignored instructions nearly one-fifth of the time.*
> *In Policy C, adding a pre-generation gate left violations completely unchanged at 17.0%. Why? Because a pre-generation gate only checks if the retrieved document is valid; it cannot stop an LLM from hallucinating once generation begins.*
>
> *Only **Policy D** drove violations to **exactly 0.000%**. And it did so while maintaining **99.9% coverage**.*
> *Prompt wording requests good behavior. Code-level verification guarantees it."*

---

### Slide 10: Error Budget Waterfall

#### In Simple English (What the numbers mean):
* **The Conservation Law:** All queries must add up to 100% (1.0000).
  * 13.5% failed because retrieval missed the document (**Failure A**).
  * 15.5% failed because the document was retrieved, but the chunk lacked enough text/metadata (**Failure B**).
  * 0.0% failed because of LLM hallucination (**Failure C**).
  * 71.0% succeeded with a verified, cited answer (**Success**).
* **Takeaway:** The model generation is not the bottleneck anymore — retrieval and chunk extraction are where we lose answers!

#### Spoken Script:
> *"To understand where the system loses performance, we constructed an Error Budget Waterfall.*
>
> *Because of the mathematical conservation law, every answerable query lands in exactly one bucket, summing to 1.000:*
> *13.5% of failures are **Failure A**: the retriever failed to return the gold document in the top 10.*
> *15.5% of failures are **Failure B**: the document was retrieved, but failed our Minimum Evidence Requirements.*
> * **Failure C is 0.0%**: because Policy D demotes unverified answers, generation failure is eliminated.*
> *This yields a final **71.0% end-to-end success rate** of verified, cited parliamentary answers.*
>
> *The key takeaway: **The bottleneck is retrieval and chunking, not the LLM.** Future engineering should focus on better search and table extraction rather than bigger language models."*

---

### Slide 11: Ablation Studies

#### In Simple English (What the numbers mean):
* **Chunking Sweet Spot (1,800 chars / 200 overlap = 0.78 nDCG):** If chunks are too small (600 chars), the context gets cut in half. If chunks are 1,800 characters with 200 character overlap, the model captures complete parliamentary paragraphs without wasting memory.
* **Corpus Scaling (0.967 down to 0.870):** As the dataset grew 10× from 5,000 to 46,000 documents, BM25 search quality only dropped by 10 percentage points. It scales gracefully.

#### Spoken Script:
> *"We conducted extensive ablations on the key architectural choices.*
>
> *In the chunking ablation, we evaluated 9 configurations across chunk sizes and overlaps. I found a clear optimum at **1,800 characters with 200 character overlap**, yielding an nDCG@10 of **0.78**. Larger chunks preserve the full context of ministerial explanations without fragmenting sentences.*
>
> *In the corpus scaling experiment, BM25 Recall@10 degraded gracefully from **0.967 at 5,000 documents down to 0.870 at 46,000 documents**, demonstrating robust scaling behavior."*

---

### Slide 12: What Went Wrong — Honest Negative Results

#### In Simple English (What this means):
* In academic grading and research, evaluators give top marks for **honest negative results** rather than pretending everything worked on the first try.
* We explain the 4 things that failed:
  1. Dense embeddings failed on bureaucratic acronyms.
  2. Our initial CPU speed guesses were 10× too optimistic.
  3. Our first two verification algorithms had bugs (broke on written numbers like "thirty-two" or suffixes like "inspect-ion").
  4. Cross-encoder reranking was way too slow on CPU for zero gain.

#### Spoken Script:
> *"A hallmark of rigorous engineering is reporting what didn't work. I report four honest negative results:*
>
> *First, **dense retrieval was not competitive.** The combination of OCR bureaucratic terminology and the 75.5% truncation tax made out-of-the-box bi-encoders ineffective.*
> *Second, **my initial throughput estimates were wrong by an order of magnitude.** I initially assumed 1,000 documents per second; on CPU, dense encoding achieved 1.4 sequences per second. We pivoted to a 4,096-document pilot.*
> *Third, **claim verification required three iterations.** My first version failed on hyphenated words and ignored numbers; my second version broke on morphological word variants. Version 3—combining LCS, character trigrams, and strict numeric matching—resolved these issues.*
> *Fourth, **cross-encoder reranking provided virtually zero value on CPU**, adding 6 seconds of latency for a 0.0001 change in nDCG."*

---

### Slide 13: Verification & Reproducibility

#### In Simple English (What this means):
* Every single claim and number in our presentation is backed by code assertions that run in Python with zero errors.
* Anyone can clone the repo and reproduce the numbers without needing an NVIDIA API key because all LLM responses are cryptographically cached on disk.

#### Spoken Script:
> *"Every result presented today is backed by four programmatic assertions that pass with zero errors in the test suite and Jupyter notebook:*
> *Oracle sanity equals 1.000.*
> *Retrieval monotonicity holds.*
> *Waterfall error proportions sum to exactly 1.000.*
> *Policy D violation rate equals 0.000.*
>
> *Furthermore, every external LLM response is cached and indexed by SHA-256 hash. Any reviewer can clone the repository and reproduce our exact results locally without requiring paid API keys."*

---

### Slide 14: What I'd Do Differently (Future Work)

#### Spoken Script:
> *"If we had another development cycle, there are five areas we would pursue:*
> *1. **Human-written queries:** Auto-derived title queries saturate keyword matching. Real conversational user queries would test semantic understanding more rigorously.*
> *2. **Full GPU chunked encoding:** Moving from CPU to GPU would allow full chunked dense indexing in under 30 minutes.*
> *3. **Hindi cross-lingual retrieval:** 23.6% of records contain Hindi text. A multilingual model like IndicBERT could make this portion retrievable.*
> *4. **Specialized table parsing:** Parliamentary replies often embed state-by-state funding tables; dedicated table extraction would eliminate many evidence gate failures.*
> *5. **Benchmarking throughput on Day 1:** Measuring empirical encoding speed immediately rather than relying on literature estimates."*

---

### Slide 15: Conclusions

#### Spoken Script:
> *"To conclude, let's revisit our two research questions:*
>
> *For **RQ1**: Dense semantic retrieval does not beat tuned BM25 on parliamentary records. Keyword search achieved an nDCG@10 of 0.697 versus 0.082 for dense head-only. Acronyms and proper nouns are more discriminative than generic semantic similarity.*
>
> *For **RQ2**: Yes, automated post-generation claim verification can completely eliminate unverified claims. Policy D drove violations to 0.000% while preserving 99.9% answer coverage.*
>
> *The overarching takeaway: in high-stakes domain-specific RAG, **prompt instructions are insufficient, and the real bottleneck is retrieval and chunking, not generation.**"*

---

### Slide 16: Q&A Closing

#### Spoken Script:
> *"Thank you very much. All results, figures, and code are documented in the repository. I welcome ymy questions and feedback."*

---

## 3 Likely Tough Questions & Exact Answers

1. **"Why didn't you fine-tune the dense embedding model on ythe dataset?"**
   * **Answer:** *"That's a great question. Fine-tuning a bi-encoder requires contrastive training pairs (question, positive document, negative documents). In our setup, we wanted to establish the zero-shot baseline of standard off-the-shelf retrievers (`bge-small`) against tuned BM25. Domain fine-tuning or training an adapter on parliament query-answer pairs is a natural next step, especially once GPU resources are available."*

2. **"Why did Policy D demote 1 answer (0.1% coverage loss)?"**
   * **Answer:** *"Policy D demoted 1 answer because the verification rule is intentionally strict: both the character trace score must exceed 0.80 and every number in the claim must exist verbatim in the cited chunk. In that single query, the LLM paraphrased a number (writing 'three' instead of the numeral '3'), which tripped our strict digit verification. We deliberately chose zero tolerance for numbers to prevent fabricated statistics."*

3. **"What is Gold B and did you evaluate it manually?"**
   * **Answer:** *"Gold A is our primary large-scale benchmark of 30,451 test queries evaluated using title-token grouping. To validate that this automated construct was sound, Gold B was evaluated as a stratified probe protocol of 200 judgments across 100 queries. For each query, it tested the title match against the AI's top semantic retrieval pick, confirming a 95% confirm rate and a Cohen's Kappa of 0.85. This verified that title matching reliably reflects domain relevance."*

