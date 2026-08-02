# ML Primitives in NumPy

Three ML building blocks implemented from scratch in NumPy: a k-NN classifier,
gradient descent (1D and 2D), and PCA via SVD.

## Files

| File | Contents |
|---|---|
| `knn.py` | `euclidean_distance`, `cosine_similarity`, `distances_to_all` (vectorized distance from one query point to every training point), `knn_predict` (majority-vote k-NN classifier), `predict_grid` (classifies a meshgrid for decision-boundary plotting). |
| `gradient_descent.py` | `f`/`grad_f` and `gradient_descent_1d` for `f(x) = (x-3)^2`; `f2`/`grad_f2` and `gradient_descent_2d` for `f(x,y) = x^2 + 5y^2`. |
| `pca.py` | `pca_via_svd(data, n_components)` — centers the data, runs `np.linalg.svd`, returns the top principal components and the projected data. |
| `run_demo.py` | Generates synthetic data, calls all of the above, and saves plot into `plots/`. |
| `ml_primitives_starter.ipynb` | Completed notebook — Imports the same functions from `knn.py`, `gradient_descent.py`, and `pca.py`; functionally equivalent to `run_demo.py`. |
| `requirements.txt` | `numpy`, `matplotlib`. |

## How to run

```bash
pip install -r requirements.txt
python run_demo.py
```

This prints a short summary of each part's results to stdout and writes four
PNGs to `plots/`:

- `knn_decision_boundary.png` — two-class decision boundary with training
  points overlaid.
- `gd_1d_learning_rates.png` — loss vs. step for three learning rates on
  `f(x) = (x-3)^2`; one of them (`lr=1.05`) is deliberately past the stable
  range and diverges, the other two converge.
- `gd_2d_contour_path.png` — the path taken by 2D gradient descent on
  `f(x,y) = x^2 + 5y^2`, plotted over a contour map. The path curves rather
  than moving in a straight line to the minimum, because the two coefficients
  (1 and 5) are unequal.
- `pca_direction_projection.png` — a synthetic `y = 2x + noise` dataset with
  its recovered principal direction and 1D projection.

Alternatively, open `ml_primitives_starter.ipynb`