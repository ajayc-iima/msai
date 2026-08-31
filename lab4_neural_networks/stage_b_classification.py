"""
Stage B: Iris Classification
Loads the Iris dataset, trains a PyTorch classification model,
and evaluates accuracy on a held-out test set.
"""

import torch
import torch.nn as nn
from sklearn.datasets import load_iris
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler


def load_and_preprocess_data(test_size: float = 0.2, random_state: int = 42):
    data = load_iris()
    X = data.data
    y = data.target

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state, stratify=y
    )

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    X_train_t = torch.tensor(X_train_scaled, dtype=torch.float32)
    X_test_t = torch.tensor(X_test_scaled, dtype=torch.float32)
    y_train_t = torch.tensor(y_train, dtype=torch.long)
    y_test_t = torch.tensor(y_test, dtype=torch.long)

    return X_train_t, X_test_t, y_train_t, y_test_t


class IrisClassifier(nn.Module):
    def __init__(self, input_dim: int = 4, hidden_dim: int = 16, num_classes: int = 3):
        super().__init__()
        self.model = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, num_classes),
        )

    def forward(self, x):
        return self.model(x)


def train_model(
    model: nn.Module,
    X_train: torch.Tensor,
    y_train: torch.Tensor,
    epochs: int = 200,
    lr: float = 1e-3,
) -> nn.Module:
    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)

    model.train()
    for _ in range(epochs):
        optimizer.zero_grad()
        logits = model(X_train)
        loss = criterion(logits, y_train)
        loss.backward()
        optimizer.step()

    return model


def evaluate_model(
    model: nn.Module,
    X_test: torch.Tensor,
    y_test: torch.Tensor,
) -> float:
    model.eval()
    with torch.no_grad():
        logits = model(X_test)
        preds = torch.argmax(logits, dim=1)
        accuracy = (preds == y_test).float().mean().item()
    return accuracy


if __name__ == "__main__":
    X_train, X_test, y_train, y_test = load_and_preprocess_data()
    print(f"X_train shape: {X_train.shape}, y_train shape: {y_train.shape}")
    print(f"X_test shape: {X_test.shape}, y_test shape: {y_test.shape}")

    model = IrisClassifier(input_dim=X_train.shape[1])
    model = train_model(model, X_train, y_train, epochs=300)
    accuracy = evaluate_model(model, X_test, y_test)
    print(f"Test accuracy: {accuracy:.4f}")