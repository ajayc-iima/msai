"""
Stage A: California Housing Regression
Loads, preprocesses data (StandardScaler fit on train only, target reshaped to (n, 1)),
and defines a small MLP regression model in PyTorch.
"""

import torch
import torch.nn as nn
from sklearn.datasets import fetch_california_housing
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler


def load_and_preprocess_data(test_size: float = 0.2, random_state: int = 42):
    """
    Loads the California Housing dataset and applies preprocessing:
    - Train/Test split
    - StandardScaler fit on train data only, then used to transform test data
    - Target reshaped to (n, 1) to prevent silent MSELoss broadcasting bugs
    - Tensors returned with torch.float32 dtype
    """
    # 1. Fetch data
    housing = fetch_california_housing()
    X = housing.data
    y = housing.target

    # 2. Split train/test
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state
    )

    # 3. Fit scaler on train only, transform both train and test
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    # 4. Explicitly reshape target to (n, 1)
    y_train_reshaped = y_train.reshape(-1, 1)
    y_test_reshaped = y_test.reshape(-1, 1)

    # 5. Convert to PyTorch float32 tensors
    X_train_t = torch.tensor(X_train_scaled, dtype=torch.float32)
    X_test_t = torch.tensor(X_test_scaled, dtype=torch.float32)
    y_train_t = torch.tensor(y_train_reshaped, dtype=torch.float32)
    y_test_t = torch.tensor(y_test_reshaped, dtype=torch.float32)

    return X_train_t, X_test_t, y_train_t, y_test_t, scaler


def build_mlp(input_dim: int = 8, hidden_dim: int = 32) -> nn.Module:
    """
    Builds a small MLP regressor: Linear -> ReLU -> Linear
    """
    return nn.Sequential(
        nn.Linear(input_dim, hidden_dim),
        nn.ReLU(),
        nn.Linear(hidden_dim, 1),
    )


if __name__ == "__main__":
    X_train, X_test, y_train, y_test, scaler = load_and_preprocess_data()
    print("X_train shape:", X_train.shape)
    print("X_test shape :", X_test.shape)
    print("y_train shape:", y_train.shape)
    print("y_test shape :", y_test.shape)

    model = build_mlp(input_dim=X_train.shape[1])
    print("\nModel architecture:\n", model)
