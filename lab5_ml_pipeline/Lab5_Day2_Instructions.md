# Lab 5, Day 2 — Pipeline, Features, and Model Selection (3 hours)

Build a leak-free preprocessing pipeline, get a cross-validated baseline, engineer features with a stated hypothesis, compare models honestly, tune once, and touch the test set exactly one time. This continues directly from Day 1's `lab5_ml_pipeline/` folder in a new notebook (`day2_pipeline_modeling_starter.ipynb`) — not a restart.

---

## Before You Start: Watch Leakage Happen

Fit a `StandardScaler` on your **full** dataset (`X`, before any split) and print `scaler.mean_`. Then fit a fresh `StandardScaler` on `X_train` alone and print its `.mean_`. The two sets of numbers differ.

Sit with that for a second before moving on: which numbers were influenced by data your model should never have had access to at fit time? That difference is the entire argument for wrapping every fitted preprocessing step inside a `Pipeline` — a `Pipeline` gets refit from scratch on each cross-validation fold's training portion, so it structurally cannot see the fold's held-out data. That's what you're about to build, and it's worth understanding *why* before writing it.

## Step 1: The ColumnTransformer (`pipeline.py`)

Build a preprocessing step that treats your numeric and categorical columns differently:

- **Numeric columns:** impute missing values (median is a reasonable default), then scale.
- **Categorical columns:** impute missing values (most-frequent is a reasonable default), then one-hot encode.

**`handle_unknown="ignore"` on the encoder is not optional.** If a category shows up only in your test set (or only at prediction time on new data later), the encoder will raise an error without it — and that's not a lab technicality, it's a real production failure mode. Combine both column-type pipelines with a `ColumnTransformer`, then wrap that together with a model inside one outer `Pipeline`.

## Step 2: Cross-Validated Baseline

Run cross-validation on your training set only, using a metric that actually fits this problem's class balance (think about whether plain accuracy is the right choice here, or whether something else better reflects what you care about).

**Report the standard deviation alongside the mean, not just the mean.** On a dataset this size, fold-to-fold variance is large enough to matter — reporting a bare mean hides real uncertainty in your estimate. This isn't pedantry: a 0.02 difference between two numbers that each have a standard deviation of 0.03 isn't a meaningful difference at all.

## Step 3: Engineer Features, With a Stated Hypothesis First

For each feature you engineer, write the hypothesis in a comment or markdown cell **before** you write the code that builds it — this stops you from rationalizing after the fact why a feature you already built must obviously help. Two reasonable starting points on Titanic: something capturing family size / traveling alone, and something extracted from the passenger's name or title.

**Then actually test whether each feature helped**, by comparing cross-validated scores with and without it, and **report the result honestly either way.** A feature that didn't help, reported clearly, earns full credit here — quietly dropping features that didn't pan out and only showing the ones that did does not. If you engineer something from a column you dropped in Day 1 (title from `Name`, for instance), that's a completely normal and expected reason to go back and un-drop it — not a sign you did Day 1 wrong.

## Step 4: Compare at Least Three Models

Cross-validate at least three different model types through the same preprocessing pipeline, and report mean and standard deviation for each.

**Expect the differences between them to be small — often smaller than one standard deviation.** That's not a disappointing result, it's the actual finding worth reporting: on a dataset this size, a 0.01 difference in score across noisy folds is not evidence that one model is genuinely better than another. If your numbers come out this way, say so directly in your analysis rather than picking a "winner" the data doesn't actually support.

## Step 5: Tune the Best Model, Then Evaluate the Test Set Exactly Once

Use `GridSearchCV` on your training data to tune whichever model performed best in Step 4. **Watch the parameter naming** — a parameter that lives inside a named pipeline step needs a `stepname__paramname` prefix (e.g. `model__n_estimators`), not the bare parameter name; this trips almost everyone up the first time.

Once tuning is done, evaluate on your held-out test set **exactly once**, with an appropriate metric, and stop there.

**If the tuned model does no better than your untuned baseline on the test set, that's a result, not a bug.** Report it honestly. Going back to tune again because the test-set number wasn't what you hoped for is itself a form of leakage — you'd be letting the test set influence your modeling decisions, which defeats the entire purpose of holding it out in the first place.

## Closing Analysis

Write up what worked, what didn't, and what you'd try next. This is graded and it's worth being specific rather than vague: name the feature that helped (or didn't), name whether your model comparison found a real winner or genuine noise, and say what you'd try with more time. Honest negative results, clearly reported, are worth more here than a tidier-sounding story that overstates what the data actually showed.

---

## Deliverable Checklist

- [ ] Notebook runs top to bottom after a kernel restart
- [ ] Data quality report: missingness, types, outliers, class balance — including the missingness-vs-target check
- [ ] Cleaning decisions documented in markdown, with reasons
- [ ] Split performed before any preprocessing is fitted
- [ ] `ColumnTransformer` + `Pipeline` handling numeric and categorical columns separately
- [ ] Cross-validated baseline, reported with standard deviation
- [ ] At least one engineered feature, with a stated hypothesis and a tested (and honestly reported) result
- [ ] At least three models compared under cross-validation
- [ ] One final evaluation on the held-out test set, with an appropriate metric
- [ ] Closing analysis: what worked, what didn't, what's next

## Grading Rubric (Lab 5 = 8% of course grade)

| Category | Weight | Criteria |
|---|---|---|
| Stage A — Exploration and cleaning (Day 1) | 25% | Quality report covering missingness, types, outliers, and class balance + the missingness-vs-target check, not just a missing-value count + cleaning decisions documented with reasons in markdown. |
| Stage B — Pipeline and baseline (Day 1–2) | 30% | Split performed before any fitting — no leakage + working `ColumnTransformer` handling both column types + cross-validated baseline reported with standard deviation, not a bare mean + metric appropriate to class imbalance, with the choice justified. |
| Stage C — Features and selection (Day 2) | 25% | At least one engineered feature with a stated hypothesis + three models compared under cross-validation + tuning done on training data only + exactly one final test-set evaluation, reported honestly. |
| Analysis and narrative | 20% | Markdown explaining decisions throughout, not just code + closing analysis covering what worked, what didn't, and what's next. |

---

## How to Submit

1. Push your final code to a **GitHub repository**. Make sure the repository is **public** so it can be reviewed.
2. Your repo should include at minimum: `data.py`, `pipeline.py`, your final notebook(s), `requirements.txt`, and a `README.md`.
3. Add a `.gitignore` that excludes `__pycache__/` and any local dataset cache directories.
4. Submit the **link to your public GitHub repository** on Moodle. That link is your submission — nothing else needs to be uploaded separately.

Before you submit, restart your kernel and run every cell top to bottom one more time.

---

## Troubleshooting Quick Reference

| Symptom | Likely cause | Fix |
|---|---|---|
| Suspiciously high score (accuracy or F1 above ~0.95 on Titanic) | A leaked column, or the test set was involved in fitting something | Check for a feature that encodes the outcome; check that nothing was fit before the split |
| `ValueError: Found unknown categories` at predict time | `OneHotEncoder` built without `handle_unknown` | `OneHotEncoder(handle_unknown="ignore")` |
| `ColumnTransformer` errors referencing column names | `X` got converted to a plain NumPy array somewhere upstream | Keep `X` a DataFrame all the way through; pass column name lists, not positions |
| CV scores vary a lot across folds | Small dataset — this is genuine variance, not a bug | Report the standard deviation; don't chase individual fold numbers |
| `Pclass` (or similar) being scaled like a continuous number | dtype-based column selection swept it into the numeric group | Move it to the categorical group manually |
| `GridSearchCV` raises a parameter-name error | Missing the `stepname__paramname` prefix | Use `model__n_estimators`, not `n_estimators` |
| A saved model fails to run on new data later | Only the bare estimator was saved, not the fitted `Pipeline` | Save the whole `Pipeline` object, not just the model step |
