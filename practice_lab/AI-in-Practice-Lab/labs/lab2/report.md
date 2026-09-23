# Lab 2 report — The Prompt Lab

## 1. Grid results (dev split, n=60)

One row per configuration:

| configuration | record_acc | field_acc | schema_valid | repair_rate | cost_usd | cost/1k tickets | p50 ms | p95 ms |
|---|---|---|---|---|---|---|---|---|
| zero_shot (SMALL) | | | | | | | | |
| zero_shot_main (MAIN) | | | | | | | | |
| few_shot (SMALL) | | | | | | | | |
| few_shot_main (MAIN) | | | | | | | | |
| few_shot_reasoned (SMALL) | | | | | | | | |
| few_shot_reasoned_main (MAIN) | | | | | | | | |
| cascade (SMALL→MAIN) | | | | | | | | |

Answers:

1. Which axis moved the numbers most — prompt, or model tier?
2. What did the reasoning field cost in output tokens, and what did it buy?
   Express it as accuracy points per rupee.
3. Is any configuration dominated (worse on every axis)? Name it.

**Cost of the best configuration:** $ per 1,000 tickets · $ per year at 10k/day.

## 2. Few-shot selection (Part A)

### A1 — the six examples

| ticket id | what it teaches that prose cannot |
|---|---|
| | |
| | |
| | |
| | |
| | |
| | |

### A4 — leakage and your fix

The examples came from dev; you measured on dev. Name the problem, say what
you did about it, and what you report as the honest number.

### Result

zero_shot vs few_shot: Δ record accuracy = ?, paired b/c/p = ?

## 3. Cascade (Part C)

- Trigger(s) you implemented:
- Escalation rate:
- Blended cost (vs pure SMALL, vs pure MAIN):
- Blended accuracy (vs pure SMALL, vs pure MAIN):
- Signal check — agreement when correct vs when wrong:
- Interpretation:

## 4. Is your difference real? (Part D)

**Wilson 95% CIs** for your two main configurations:

- A: [ , ]
- B: [ , ]

Do they overlap? What can you conclude from the intervals alone?

**Paired test (McNemar):**

| comparison | b | c | p | verdict |
|---|---|---|---|---|
| | | | | |
| | | | | |

Conclusion (including "no significant difference" if that is what you got):

## 5. Error analysis and recommendation (Part E)

### E1 — top three failure clusters (best configuration)

1. — count:
2. — count:
3. — count:

### E2 — confusion matrix, worst field

(rows = gold, cols = predicted)

| | | | | | |
|---|---|---|---|---|---|
| | | | | | |
| | | | | | |
| | | | | | |
| | | | | | |
| | | | | | |

What systematic confusion does this reveal?

### E3 — recommendation

One paragraph. Configuration · three numbers · annual cost at 10k tickets/day ·
one condition that would change your mind.

## 6. Negative results (required — at least one)

1.
2.
