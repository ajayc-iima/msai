"""
Training Utilities for PyTorch Models
Provides modular training and evaluation functions.
"""

from typing import List, Tuple
import torch
import torch.nn as nn
import torch.optim as optim


def train_full_batch(
    model: nn.Module,
    X_train: torch.Tensor,
    y_train: torch.Tensor,
    epochs: int = 500,
    lr: float = 1e-3,
    criterion: nn.Module = None,
    optimizer: optim.Optimizer = None,
) -> List[float]:
    """
    Trains a model using full-batch gradient descent.

    Crucial implementation details:
    - optimizer.zero_grad() called before loss.backward()
    - loss.item() recorded as a float to prevent memory leaks from retaining computational graphs
    """
    if criterion is None:
        criterion = nn.MSELoss()
    if optimizer is None:
        optimizer = optim.Adam(model.parameters(), lr=lr)

    losses: List[float] = []

    model.train()
    for epoch in range(epochs):
        # 1. Forward pass
        predictions = model(X_train)

        # 2. Compute loss
        loss = criterion(predictions, y_train)

        # 3. Zero gradients, backpropagate, and step optimizer
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

        # 4. Record loss float value (not the tensor graph!)
        losses.append(loss.item())

    return losses


def evaluate(
    model: nn.Module,
    X_test: torch.Tensor,
    y_test: torch.Tensor,
    criterion: nn.Module = None,
) -> float:
    """
    Evaluates the model on test data in evaluation mode with gradient tracking disabled.
    """
    if criterion is None:
        criterion = nn.MSELoss()

    model.eval()
    with torch.no_grad():
        predictions = model(X_test)
        test_loss = criterion(predictions, y_test)

    return test_loss.item()
