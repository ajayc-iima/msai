"""
knn.py — k-Nearest Neighbors classifier implemented from scratch in NumPy.

All distance computations are vectorized: no `for point in X_train` loops.
"""

import numpy as np


def euclidean_distance(a, b):
    """
    Euclidean distance between two 1D vectors a and b.

    a, b: shape (d,)
    returns: scalar float
    """
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    return np.sqrt(np.sum((a - b) ** 2))


def cosine_similarity(a, b):
    """
    Cosine similarity between two 1D vectors a and b.

    a, b: shape (d,)
    returns: scalar float in [-1, 1] (0 if either vector has zero norm)
    """
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return np.dot(a, b) / (norm_a * norm_b)


def distances_to_all(query, X_train):
    """
    Vectorized Euclidean distance from a single query point to every
    row of X_train, computed in one broadcasted call (no Python loop
    over training points).

    This reuses `euclidean_distance`'s formula rather than rewriting a
    new one: it's the same sqrt(sum((a - b)**2)), just applied to every
    row of X_train at once via broadcasting instead of to a single
    pair (a, b). Calling `euclidean_distance` inside a
    `for point in X_train:` loop would produce identical numbers, but
    would reintroduce the very loop this function exists to avoid —
    so the broadcasting below is that same formula generalized across
    rows, not a differently-written one.

    query:   shape (d,)
    X_train: shape (n, d)
    returns: shape (n,) — distances[i] == euclidean_distance(query, X_train[i])
    """
    query = np.asarray(query, dtype=float)
    X_train = np.asarray(X_train, dtype=float)
    # Same formula as euclidean_distance: sqrt(sum((a - b)**2)).
    # Broadcasting: (n, d) - (d,) -> (n, d); square, sum over axis 1 -> (n,)
    diffs = X_train - query
    sq_dists = np.sum(diffs ** 2, axis=1)
    return np.sqrt(sq_dists)


def knn_predict(query, X_train, y_train, k):
    """
    Classify a single query point by majority vote among its k nearest
    neighbors in X_train (by Euclidean distance).

    query:   shape (d,)
    X_train: shape (n, d)
    y_train: shape (n,) integer/label array
    k:       number of neighbors to consider

    returns: predicted label (same dtype as y_train's elements)
    """
    y_train = np.asarray(y_train)
    dists = distances_to_all(query, X_train)

    # Indices of the k smallest distances. argpartition is O(n) vs
    # O(n log n) for a full argsort, and we don't need the k neighbors
    # sorted amongst themselves for a majority vote.
    k = min(k, len(dists))
    nearest_idx = np.argpartition(dists, k - 1)[:k]
    nearest_labels = y_train[nearest_idx]

    # Majority vote. bincount requires non-negative ints, which is the
    # normal case for class labels (0..C-1). We use it because it's
    # the cleanest vectorized "mode" for that case.
    if np.issubdtype(nearest_labels.dtype, np.integer) and nearest_labels.min() >= 0:
        counts = np.bincount(nearest_labels)
        return np.argmax(counts)

    # Fallback for non-integer / negative labels: unique + counts.
    values, counts = np.unique(nearest_labels, return_counts=True)
    return values[np.argmax(counts)]


def predict_grid(X_train, y_train, k, xx, yy):
    """
    Classify every point on a meshgrid (xx, yy) using knn_predict, and
    return the predictions reshaped to the grid's 2D shape so they can
    be passed directly to plt.contourf.

    xx, yy: shape (m, n), as returned by np.meshgrid
    returns: shape (m, n) array of predicted labels
    """
    grid_points = np.column_stack([xx.ravel(), yy.ravel()])  # shape (m*n, 2)
    preds = np.array([
        knn_predict(pt, X_train, y_train, k) for pt in grid_points
    ])
    return preds.reshape(xx.shape)
