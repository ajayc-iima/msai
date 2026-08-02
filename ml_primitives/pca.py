"""
pca.py — PCA via SVD, implemented from scratch in NumPy.
"""

import numpy as np


def pca_via_svd(data, n_components):
    """
    Principal Component Analysis via SVD.

    Steps:
      1. Center the data (subtract each column's mean) — required, or
         the recovered "principal direction" will be tilted away from
         the true axis of variance and instead point toward the origin.
      2. Run np.linalg.svd on the centered data.
      3. Take the top n_components rows of Vt as the principal components.
      4. Project the centered data onto those components.
    """
    data = np.asarray(data, dtype=float)
    mean = data.mean(axis=0)
    centered = data - mean

    # full_matrices=False -> economy SVD, cheaper and all we need here.
    U, S, Vt = np.linalg.svd(centered, full_matrices=False)

    components = Vt[:n_components]                 # (n_components, n_features)
    projected = centered @ components.T             # (n_samples, n_components)

    return components, projected, mean
