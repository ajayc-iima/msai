# Lab 5, Day 1 — Exploration and Cleaning (3 hours)

Build a documented data-quality report for the Titanic dataset, make and justify a series of cleaning decisions, then split your data and check your column groups. **No model building today**, we are only working on getting the data in good shape.

Here, the models are three lines each. Today is two hours of pandas, and the judgement calls you make is where most of this lab's actual grading weight sits — a notebook full of correct code with no documented reasoning is a weak submission for this lab specifically.

Work in the `lab5_ml_pipeline/` folder shared with you. Today you need `pipeline.py` (blank, you'll add to it in Steps 5–6) and `day1_exploration_starter.ipynb`. `data.py` is fully provided — open it if you're curious, but it's only infrastructure (dataset loading with an offline fallback), not something you're being asked to write or learn from.

---

## Step 1: Load and Profile

```python
from data import load_titanic
df, source = load_titanic()
```

This tries the real Titanic dataset from OpenML first, and falls back to a synthetic dataset with the same schema and the same quality problems if there's no network. Either way, run `df.info()`, `df.describe(include="all").T`, and compute the percentage missing per column, sorted descending.

You should see roughly: `Cabin` ~77% missing, `Age` ~20% missing, `Embarked` ~0.2% missing (two rows). Those three numbers should drive three *different* decisions, not one blanket approach — that's the driving point of this step, not just producing the numbers.

## Step 2: The Most Skipped Checks

Missingness itself can carry information. Compare the survival rate between rows where a column is missing and rows where it isn't — at minimum, do this for `Age` and `Cabin`.

Think about `Cabin` specifically before you look at the number: passengers with a recorded cabin tend to be a different population (wealthier, higher class) than those without one. If the survival rates differ noticeably between the two groups, that's a real signal — and it means blindly dropping the column, or blindly imputing it, throws information away. It doesn't necessarily mean you have to keep the raw column; it might mean the *fact of having a cabin recorded* is worth keeping even if the specific cabin number isn't.

## Step 3: Look for Impossible Values and Placeholders

`isna()` only catches missingness that's actually stored as null. Real datasets often hide missing values as placeholder strings or nonsense numbers that `isna()` walks right past. Check unique values in your object (string) columns, look for zero or negative fares, check whether `Age` has any impossible values.

If you're working with a different dataset than Titanic, be especially suspicious here — placeholder markers like `"?"` or `999` are common, and `describe()` alone will not save you from them.

## Step 4: Decide, and Write It Down

For every column where you found a problem in Steps 1–3, write a markdown cell (or a row in a table) stating what you did and *why*. This is not optional decoration — a silent `fillna(0)` with no explanation earns much less credit than the identical code with one sentence of justification next to it, because the rubric is explicitly grading your reasoning, not just whether the final numbers look right.

Before moving on, do one more check regardless of what dataset you're using: **look for target leakage** — a column that encodes the outcome directly or near-directly. An impressively high score later that turns out to come from a leaked column hides every other problem in your pipeline, so it's worth ruling out now while you're already looking closely at every column.

## Step 5: Split First, Before Fitting Anything (`pipeline.py`)

```python
from sklearn.model_selection import train_test_split
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=0, stratify=y
)
```

Do this **before** you fit anything — not just the model, anything: no scaler, no imputer, no encoder should see the full dataset before this split exists. `stratify=y` matters here specifically because survival is imbalanced; without it, an unlucky split can leave your test set with a noticeably different class balance than your training set, which quietly distorts everything you measure afterward.

## Step 6: Column Groups — and Check Them by Eye

Split your feature columns into numeric and categorical, most simply by dtype. Then **actually look at both lists** rather than trusting the automatic split blindly — this is the single most common silent mistake in this stage. Ask yourself: does every column that dtype selection called "numeric" actually behave like a number, where being bigger genuinely means "more" of something? A passenger class stored as `1`, `2`, `3` is stored as an integer, but treating class 3 as though it's "more" than class 1 in a mathematical sense is not what that column means.

---

## Before You Leave Today

Four things, in order:

1. **Save your cleaned frame and your split** so Day 2 resumes instead of re-deriving it: `joblib.dump({"X_train": X_train, "X_test": X_test, "y_train": y_train, "y_test": y_test}, "split.joblib")`. If tomorrow re-runs the split with even a different `random_state`, every comparison made against today's numbers is silently invalidated.
2. **Confirm your split used `stratify=y` and a fixed `random_state`.** Double-check this now — it matters more than usual across a day's gap.
3. **Make sure Step 4's decisions are actually written down**, while the reasoning is still fresh. Reconstructing your justifications tomorrow morning produces visibly thinner reasoning than writing them down today.
4. **Check your column groups one more time.** If `Pclass` (or anything like it) is sitting in your numeric list, tomorrow's pipeline will build on top of that mistake without necessarily giving you any error to notice it by.

Keep your notebook and this folder exactly as they are — Day 2 is a new notebook here, not a restart.

---

## Troubleshooting Quick Reference

| Symptom | Likely cause | Fix |
|---|---|---|
| `isna()` reports zero missing but the data looks wrong | Placeholder markers like `?` or `999` used instead of a real null | Inspect `.unique()` per column; convert placeholders to `NaN` before profiling further |
| Suspiciously high correlation between one column and the target | Possible leaked column — one that encodes the outcome directly | Read that column's meaning carefully before including it |
| `groupby(...).mean()` on a missingness check throws an error | Comparing against a column with its own missing values, or a dtype mismatch | Check the dtypes of both sides of the comparison |
| Class balance looks different between train and test | Split wasn't stratified | Add `stratify=y` to `train_test_split` |
