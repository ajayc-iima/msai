# Class Summary: Lab 2 — The Prompt Lab
**Course:** AI in Practice — 1 (MSAI)  
**Student:** Ajay Choudhary | **Date:** September 2026  
**Lab Topic:** Evaluation-Driven Development, Grid Benchmarking & Statistical Honesty  

---

### 1. What Was the Task?
In Lab 1, I built a structured information extractor for Aurora Health Insurance support tickets. It felt solid, but "feeling good about your code" isn't an engineering metric. 

In Lab 2, the goal was to stop guessing and build a rigorous **evaluation harness** to test whether that extractor was actually the best version of itself. I set up a 7-way experimental grid testing:
- **Prompt Styles:** Zero-shot vs. Few-shot (6 hand-picked edge cases) vs. Few-shot with Chain-of-Thought reasoning.
- **Model Tiers:** A cheap, fast `SMALL` model vs. a heavy, capable `MAIN` model.
- **Routing:** Direct single-call vs. a cost-saving **Cascade** (try the cheap model first, escalate to the big model if uncertain or validation fails).

Instead of obsessing over accuracy alone, the mandate was to evaluate the complete engineering triangle: **Quality × Cost (Tokens) × Latency**.

---

### 2. Errors, Traps & What Went Wrong
This lab threw several realistic, humbling curveballs that forced me to think like a practitioner rather than a student hoping for clean numbers:

- **The Sudden EOL Small Model:** The `SMALL` tier model (`nemotron-3-nano-30b`) reached end-of-life right before running the grid and returned API errors for every call. All small-tier runs dropped to 0 accuracy.
- **The Cascade Trap:** Because the small model failed completely, the cascade triggered its safety fallback and escalated 100% of tickets to the `MAIN` model. It ended up being an exact, redundant copy of `zero_shot_main`. Even theoretically, self-consistency checks at temperature 0.7 only caught variance (sampling jitter), not model bias (systematic blind spots).
- **The Data Leakage Mistake (Part A4):** When picking 6 tricky few-shot examples, I took them directly from the `dev` split. But evaluating on that same split meant the model was being tested on questions it had already seen. I had to acknowledge this leakage and treat the numbers as an optimistic ceiling, recognizing that real validation requires a strictly disjoint test set.
- **The False Win (The 3% Illusion):** On paper, `few_shot_reasoned_main` scored 53.3% record accuracy compared to 46.7% for `zero_shot_main`. In a naive demo, you'd celebrate a +6.7% gain. But when I ran Wilson confidence intervals and paired McNemar tests, the intervals overlapped heavily and the $p$-value was **0.424**. The "improvement" was pure statistical noise.
- **Token Bloat for Zero Gain:** That reasoned few-shot configuration consumed **+55% more tokens** and added 20% latency to every single ticket without delivering any verifiable accuracy boost.

---

### 3. What Did I Actually Learn? (The Big Takeaways)

1. **Statistical Honesty Beats Intuition:**  
   On small sample sets ($n=60$), small percentage changes mean almost nothing. If $p > 0.05$, two models are statistically indistinguishable. Claiming one is better without a confidence interval is just wishful thinking.
2. **Cost and Latency Are the Real Tie-Breakers:**  
   When two models perform identically within margin of error, you don't pick the fancy one—you pick the cheap, fast one. At 10,000 tickets a day, shipping zero-shot saves **4.5 billion tokens a year** compared to the reasoned prompt.
3. **Pydantic Schemas Do the Heavy Lifting:**  
   Few-shot examples bought us almost nothing because our zero-shot Pydantic field `description` tags were already explicit and well-crafted. If your rules are clearly defined in the schema, you don't need to burn tokens repeating them through examples.
4. **Negative Results Are Great Engineering Results:**  
   I didn't produce a magical model with 95% accuracy, and that was the point. Proving that an expensive cascade and heavy few-shot prompt aren't worth the money is just as valuable as finding an optimization that works.
5. **The Real-World Recommendation:**  
   **Ship `zero_shot_main`.** It gives 90% field accuracy, handles edge cases cleanly, and runs at 2,268 tokens/ticket. The only thing that would change my mind is if a working, low-cost small model becomes available that can reliably handle ≥40% of routine tickets before escalating.

