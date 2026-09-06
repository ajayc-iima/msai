"""Lab 5 utilities: leak-free preprocessing + feature engineering.

Day 1 decisions encoded here:
- Fare zeros (=0) and NaN are both treated as missing (17 zeros + 1 NaN in the
  full OpenML frame; free-ticket zeros are not real fares).
- Fare varies strongly by (Pclass, Embarked), so impute with the group median
  fitted on train only. Cabin is NOT part of the grouping: 77% missing and
  collinear with Pclass, so (Pclass, Embarked, Cabin) groups would be sparse.
  Cabin survives only as the Cabin_missing indicator built on Day 1.
- Embarked (2 missing) is filled with the train mode inside the same
  transformer, so no separate pre-split fill is needed.
- Pclass is stored as int but treated as categorical (ordered class label).
"""

import re

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


class FareGroupMedianImputer(BaseEstimator, TransformerMixin):
    """Impute Fare NaN and 0 with median per (Pclass, Embarked) - train fit.

    Fare varies by Pclass/Embarked; Cabin is 77% missing and collinear with
    Pclass, so (Pclass, Embarked, Cabin) would be sparse. Cabin kept only as
    Cabin_missing. Uses df["Fare"].mask(isna | ==0, group median).
    """

    def __init__(self, group_cols=("Pclass", "Embarked"), target="Fare"):
        # NOTE: store params unmodified so sklearn.clone() works
        # (assigning list(group_cols) here breaks get_params/clone round-trip).
        self.group_cols = group_cols
        self.target = target

    def fit(self, X, y=None):
        cols = list(self.group_cols)
        # group medians excluding zeros, fit on train only
        self.group_medians_ = X.groupby(cols, observed=True)[self.target].apply(
            lambda s: s[s > 0].median()
        )
        self.global_median_ = X.loc[X[self.target] > 0, self.target].median()
        if "Embarked" in X.columns and not X["Embarked"].mode().empty:
            self.embarked_mode_ = X["Embarked"].mode().iloc[0]
        else:
            self.embarked_mode_ = "S"
        return self

    def transform(self, X):
        cols = list(self.group_cols)
        X = X.copy()
        if "Embarked" in X.columns:
            X["Embarked"] = X["Embarked"].fillna(self.embarked_mode_)
        # map group median for each row, fallback to global median
        medians = self.group_medians_
        glob = self.global_median_

        def _lookup(row):
            key = tuple(row[c] for c in cols)
            try:
                return medians.loc[key]
            except KeyError:
                return glob

        fill = X.apply(_lookup, axis=1)
        # simplified mask: NaN or 0 -> group median
        X[self.target] = X[self.target].mask(
            X[self.target].isna() | (X[self.target] == 0), fill
        )
        X[self.target] = X[self.target].fillna(glob)
        return X


# --- Feature engineering (stateless, per-row => safe to apply before split/CV) ---

_TITLE_RE = re.compile(r",\s*([^\.]+)\.")

#: Titles kept as-is; everything else collapses to "Rare". Fixed rule (no
#: fitting), so applying it before the split/CV cannot leak. Cutoff chosen
#: from the full-frame counts: Mr 757 / Miss 260 / Mrs 197 / Master 61, then
#: a long tail (Dr 8, Rev 8, Col 4, ...). Keeping the tail separate would
#: create near-unique dummy columns.
KEPT_TITLES = frozenset({"Mr", "Mrs", "Miss", "Master"})


def extract_title(name):
    """Extract 'Mr' from 'Allison, Mr. Hudson ...'; 'Unknown' if unparsable."""
    m = _TITLE_RE.search(str(name))
    return m.group(1).strip() if m else "Unknown"


def engineer(df):
    """Add engineered features. Idempotent; works with or without 'Name'.

    Hypothesis 1 - family size / travelling alone: survival was not monotonic
    in SibSp/Parch (small families helped, large ones hurt in EDA), so
    FamilySize = SibSp + Parch + 1 and IsAlone = (FamilySize == 1) should
    capture the non-linearity a linear model cannot see from raw counts.
    Hypothesis 2 - title: 'Mr/Mrs/Miss/Master' encodes sex + age + social
    status more finely than Sex alone (e.g. Master = young boy, Mrs vs Miss
    = married vs unmarried woman), so it should add signal beyond Sex.
    """
    df = df.copy()
    if "SibSp" in df.columns and "Parch" in df.columns:
        df["FamilySize"] = df["SibSp"] + df["Parch"] + 1
        df["IsAlone"] = (df["FamilySize"] == 1).astype(int)
    if "Name" in df.columns:
        df["Title"] = df["Name"].apply(extract_title).where(
            df["Name"].apply(extract_title).isin(KEPT_TITLES), "Rare"
        )
    # Indicators from Day 1, recreated idempotently if the raw col exists.
    if "Age_missing" not in df.columns and "Age" in df.columns:
        df["Age_missing"] = df["Age"].isna().astype(int)
    if "Cabin_missing" not in df.columns and "Cabin" in df.columns:
        df["Cabin_missing"] = df["Cabin"].isna().astype(int)
    return df


def build_preprocessor(num_cols, cat_cols):
    """Numeric: median-impute then scale. Categorical: mode-impute then one-hot.

    handle_unknown="ignore" is required: the test split holds both Embarked
    NaNs (both missing-Embarked rows landed in test) and potentially unseen
    categories (e.g. a rare Title); without it predict() raises ValueError.
    """
    numeric = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]
    )
    categorical = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore")),
        ]
    )
    return ColumnTransformer(
        [("num", numeric, num_cols), ("cat", categorical, cat_cols)]
    )


def build_pipeline(num_cols, cat_cols, model):
    """Outer leak-free pipeline: Fare fix (fit per-fold) + preprocess + model.

    The FareGroupMedianImputer sits INSIDE the outer Pipeline so
    cross_val_score / GridSearchCV refit it on each fold's training portion -
    it structurally cannot see held-out data.
    """
    return Pipeline(
        [
            ("fare", FareGroupMedianImputer()),
            ("pre", build_preprocessor(num_cols, cat_cols)),
            ("model", model),
        ]
    )
