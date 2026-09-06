"""Dataset loading for Lab 5. PROVIDED - you don't need to write or modify this file.

Uses the real Titanic dataset when it can be reached, and otherwise falls back to a
deterministic synthetic dataset with the *same schema and the same quality problems*
(missing Age, mostly-missing Cabin, a couple of missing Embarked, a Name column with
extractable titles). Every teaching point in the lab - missingness that predicts the
target, family_size, title extraction, leakage discipline - works on either.

This is infrastructure, not something you're being asked to learn: generating a
realistic synthetic dataset isn't itself a lab skill, it just guarantees the notebook
runs even with no network on lab day. Skim it if you're curious, but the actual lab
starts at load_titanic() - call that and move on to Stage A.
"""
import numpy as np
import pandas as pd

RANDOM_STATE = 0


def _synthetic_titanic(n=891, seed=RANDOM_STATE):
    """Titanic-shaped data with realistic structure and missingness."""
    rng = np.random.default_rng(seed)

    pclass = rng.choice([1, 2, 3], n, p=[0.24, 0.21, 0.55])
    sex = rng.choice(["male", "female"], n, p=[0.65, 0.35])
    # fare tracks class, with a long right tail
    base_fare = {1: 84.0, 2: 21.0, 3: 13.0}
    fare = np.array([abs(rng.normal(base_fare[c], base_fare[c] * 0.6)) for c in pclass]).round(4)
    age = np.clip(rng.normal(29.7, 14.5, n), 0.42, 80).round(1)
    sibsp = rng.choice([0, 1, 2, 3, 4], n, p=[0.68, 0.23, 0.05, 0.02, 0.02])
    parch = rng.choice([0, 1, 2, 3], n, p=[0.76, 0.13, 0.09, 0.02])
    embarked = rng.choice(["S", "C", "Q"], n, p=[0.72, 0.19, 0.09])

    # survival: women and higher classes far more likely, young children helped
    logit = (-1.4
             + 2.5 * (sex == "female")
             + 0.9 * (pclass == 1) + 0.3 * (pclass == 2)
             - 0.02 * (age - 30)
             + 0.4 * ((sibsp + parch) == 1)
             - 0.35 * ((sibsp + parch) >= 4))
    survived = (rng.random(n) < 1 / (1 + np.exp(-logit))).astype(int)

    # titles, drawn to correlate with sex and age as they really do
    def title_for(s, a):
        if s == "male":
            return "Master" if a < 13 else rng.choice(["Mr", "Dr", "Rev"], p=[0.94, 0.04, 0.02])
        return rng.choice(["Miss", "Mrs"], p=[0.45, 0.55]) if a >= 18 else "Miss"

    titles = [title_for(s, a) for s, a in zip(sex, age)]
    surnames = rng.choice(["Smith", "Brown", "Andersson", "Sage", "Panula", "Carter",
                           "Goodwin", "Rice", "Johnson", "Skoog", "Ford", "Palsson"], n)
    name = [f"{sn}, {t}. Passenger {i}" for i, (sn, t) in enumerate(zip(surnames, titles))]

    df = pd.DataFrame({
        "PassengerId": np.arange(1, n + 1),
        "Survived": survived,
        "Pclass": pclass,
        "Name": name,
        "Sex": sex,
        "Age": age,
        "SibSp": sibsp,
        "Parch": parch,
        "Ticket": [f"T{rng.integers(10000, 99999)}" for _ in range(n)],
        "Fare": fare,
        "Cabin": pd.Series([f"{rng.choice(list('ABCDE'))}{rng.integers(1, 120)}"
                            for _ in range(n)], dtype="object"),
        "Embarked": embarked,
    })

    # --- inject the real dataset's missingness pattern ---
    # Cabin ~77% missing, and recorded far more often in first class (this is the
    # signal that makes a has_cabin indicator worth engineering).
    p_cabin_missing = np.where(pclass == 1, 0.19, np.where(pclass == 2, 0.86, 0.975))
    df.loc[rng.random(n) < p_cabin_missing, "Cabin"] = np.nan
    # Age ~20% missing, slightly more often in third class
    p_age_missing = np.where(pclass == 3, 0.26, 0.14)
    df.loc[rng.random(n) < p_age_missing, "Age"] = np.nan
    # Embarked: two rows, as in the original
    df.loc[rng.choice(n, 2, replace=False), "Embarked"] = np.nan
    return df


def load_titanic(csv_path=None, verbose=True):
    """Return (DataFrame, source_label). Never raises on a missing network.

    This is the one function you actually call - see Day 1, Step 1.
    """
    if csv_path:
        df = pd.read_csv(csv_path)
        if verbose:
            print(f"Loaded Titanic from {csv_path}  {df.shape}")
        return df, "csv"

    try:
        from sklearn.datasets import fetch_openml
        raw = fetch_openml("titanic", version=1, as_frame=True, parser="auto")
        df = raw.frame.rename(columns={
            "pclass": "Pclass", "name": "Name", "sex": "Sex", "age": "Age",
            "sibsp": "SibSp", "parch": "Parch", "ticket": "Ticket", "fare": "Fare",
            "cabin": "Cabin", "embarked": "Embarked", "survived": "Survived",
        })
        df["Survived"] = df["Survived"].astype(int)
        if verbose:
            print(f"Loaded real Titanic from OpenML  {df.shape}")
        return df, "openml"
    except Exception as e:
        df = _synthetic_titanic()
        if verbose:
            print(f"OpenML unavailable ({type(e).__name__}); using the synthetic "
                  f"Titanic-shaped fallback  {df.shape}")
        return df, "synthetic"


if __name__ == "__main__":
    df, src = load_titanic()
    print("source:", src)
    print(df.head())
    print("\nmissing %:")
    print((df.isna().mean() * 100).round(1).sort_values(ascending=False).head())
