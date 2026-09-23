# Lab 1 report

## Part A — failure table

| Failure mode | Count in 40 | Example ticket id |
|---|---|---|
| Not valid JSON at all | |
| JSON wrapped in a markdown fence | |
| Extra prose before or after the JSON | |
| Valid JSON, missing a required field | |
| Valid JSON, category outside the allowed set | |
| Urgency as a string instead of an int | |
| Policy number invented (not present in the text) | |
| Unhandled exception | |

The arc: 0/40 parsed → 40/40 parsed after a one-line fix → still ~0/40 clean.

## Variant comparison (v0 / B / C)

| variant | schema_valid | field_acc | record_acc | cost | p95 ms |
|---|---|
| v0 | |
| B | |
| C | |

## Per-field accuracy (worst first)

(paste the harness output — the deterministic fields should be 1.000 in C)

## Category confusion matrix

(rows = gold, cols = predicted)

## Top three error clusters + proposed fix

1.
2.
3.

## D5 — economic argument

cost/ticket × 10,000 tickets/day vs 40 s of agent time at ₹300/hour.
State the break-even accuracy and show the arithmetic.

## One thing I tried that did not work
