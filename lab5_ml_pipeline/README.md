# Lab 5 - Titanic ML Pipeline (Days 1 + 2)

Leak-free Titanic survival modeling: exploration/cleaning (Day 1) → `ColumnTransformer` + `Pipeline`,
cross-validated baseline, hypothesis-first feature engineering, 3-model comparison, one tuning run,
and exactly one held-out test evaluation (Day 2).

## Files

- `data.py` - dataset loading (OpenML Titanic, synthetic fallback). Provided; unmodified.
- `pipeline.py` - `FareGroupMedianImputer`, `engineer()` (`FamilySize`/`IsAlone`/`Title`),
  `build_preprocessor()` (median+scale / mode+one-hot with `handle_unknown="ignore"`),
  `build_pipeline()` (Fare fix inside the outer `Pipeline`, refit per CV fold).
- `day1_exploration_starter.ipynb` - quality report, cleaning decisions, stratified split → `split.joblib`.
- `day2_pipeline_modeling_starter.ipynb` - Day 2 work; runs top-to-bottom (executed, outputs saved).
- `split.joblib` - stratified split (`test_size=0.2`, `random_state=0`, `stratify=y`).
- `requirements.txt`

## Run

```bash
pip install -r requirements.txt
python data.py                      # optional: verify dataset loads
# then open the notebooks in order: day1, day2 (kernel restart → run all)
```

Day 2 rebuilds `X` from the raw frame with identical cleaning plus `engineer()` and the same
split seed, verified to reproduce the saved split indices exactly.

## Results (5-fold stratified CV, F1; test touched once)

| Setting | CV F1 mean ± std |
|---|---|
| Baseline (Day-1 cols, LogReg) | 0.701 ± 0.037 |
| + FamilySize/IsAlone | 0.712 ± 0.031 (+0.011, within noise) |
| + Title | 0.746 ± 0.027 |
| + family + Title | **0.754 ± 0.032** |
| RandomForest (full feats) | 0.729 ± 0.031 |
| SVC (full feats) | 0.747 ± 0.023 |

Model gaps are < 1 std: no data-supported winner; LogReg tuned (`GridSearchCV`,
`model__C=0.5`, best CV 0.756 vs untuned 0.754 - null gain, honestly reported).
Final test (once): **F1 0.754, accuracy 0.821**, matching the CV estimate.
