# Lab 2 — ML Primitives in NumPy

Implement three core ML building blocks from scratch in NumPy: a k-NN classifier, gradient descent, and PCA via SVD. Everything in this lab runs offline.

Work in this `ml_primitives/` folder. It already has empty files for you to fill in (`knn.py`, `gradient_descent.py`, `pca.py`, `requirements.txt`, `README.md`) plus a `plots/` folder to save your output figures into.

```bash
pip install -r requirements.txt
```

There's also `ml_primitives_starter.ipynb` — a blank notebook shell with a section and import cell per part, and `# TODO` comments marking what goes where. It saves you from having to build the notebook structure by hand, but it does **not** contain any data generation, plotting, or test code — that's still yours to write, per the steps below. You're also free to skip the notebook entirely and just call your functions from your own script.

---

## Part A — k-NN Classifier (`knn.py`)

### Step 1: Distance functions

Implement `euclidean_distance(a, b)` and `cosine_similarity(a, b)` — the same two functions from lecture. Reuse them, don't rewrite from scratch.

### Step 2: Vectorize the distance to every training point

Write a function that takes one query point and the full training set, and returns the distance from the query to *every* training point in a single vectorized call — no loop over training points. Looping point-by-point works but defeats the point of the exercise, and it's slow. If you find yourself writing `for point in X_train:`, stop and look for the broadcasting-based version instead.

### Step 3: The classifier itself

Write `knn_predict(query, X_train, y_train, k)` that:
1. Gets distances from the query to all training points (Step 2's function).
2. Finds the indices of the `k` smallest distances.
3. Looks up those neighbors' labels.
4. Returns the majority label among them.

Think about how to find "the k smallest" and "the majority label" using NumPy functions rather than manual loops and counters — both have a clean vectorized answer.

### Step 4: Decision boundary plot

Reuse the meshgrid + `contourf` recipe from lecture: build a grid of points covering your data's range, classify every grid point with `knn_predict`, and shade the grid by predicted class. Overlay your actual training points on top.

**Common failure mode:** if your boundary plot renders as a single solid color, you likely forgot to reshape your flat array of grid predictions back into the grid's 2D shape before passing it to `contourf`.

---

## Part B — Gradient Descent (`gradient_descent.py`)

### Step 1: 1D optimization

Pick a simple function with a known minimum, e.g. `f(x) = (x - 3)^2`, and write its derivative by hand. Implement `gradient_descent_1d(start, lr, steps)` that repeatedly steps `x` in the direction that decreases `f`, and returns both the final `x` and the full history of values visited (you'll need the history for the next step's plot).

### Step 2: Learning rate comparison

Run your 1D gradient descent with at least three different learning rates and plot how the loss changes over steps for each on the same chart. You should see one rate converge cleanly, and — if you push a learning rate high enough — one that oscillates or diverges instead of converging. Finding that unstable rate and showing it is part of the point of this exercise, not an edge case to avoid.

### Step 3: 2D extension

Extend the same idea to a function of two variables, e.g. `f(x, y) = x^2 + 5y^2`, with its gradient as a 2-element vector. Track the full path taken across steps (not just the endpoint), and plot that path over a contour plot of the function. If your two coefficients aren't equal, the path should visibly curve rather than move in a straight line toward the minimum — that's a more realistic picture of what gradient descent looks like outside of toy circular examples.

---

## Part C — PCA via SVD (`pca.py`)

### Step 1: Generate data with an obvious principal direction

Create a 2D dataset where one variable is a noisy linear function of the other (e.g. `y = 2x + noise`), so there's a clear dominant direction of variance to recover.

### Step 2: Center, then apply SVD

Write `pca_via_svd(data, n_components)` that:
1. **Centers the data** (subtract the mean of each column) — this is crucial, skipping it will visibly tilt your result away from the actual axis of the data.
2. Runs `np.linalg.svd` on the centered data.
3. Takes the top `n_components` rows of `Vt` as your principal component(s).
4. Projects the centered data onto those components.

### Step 3: Plot it

Plot the original scattered points, the recovered principal direction as a line through the data, and the 1D projection — together, on one chart. The direction line should visibly run along the long axis of the scatter.

---

## Deliverable Checklist

- [ ] `knn_predict` implemented with vectorized distance computation (no loop over training points)
- [ ] Decision boundary plot, axes labeled, points overlaid
- [ ] Gradient descent convergence comparison across at least three learning rates, including one that visibly diverges or oscillates
- [ ] 2D gradient descent path plotted over a contour plot
- [ ] PCA via SVD, including the centering step, with original data / principal direction / projection all plotted together
- [ ] All plots have axis labels, a title, and a legend where more than one series appears
- [ ] A `README.md` explaining what each file does and how to run it

## Grading Rubric (Lab 2 = 8% of course grade)

Slightly more rigorous than Lab 1's rubric — this lab is more algorithmic than mechanical — but still graded per-criterion as working/not-working rather than deducted for style.

| Category | Weight | Criteria |
|---|---|---|
| Part A — k-NN | 30% | `euclidean_distance` / `cosine_similarity` correct (5%) + distance-to-all-points function genuinely vectorized, no loop over training points (10%) + `knn_predict` majority-vote logic correct (10%) + decision boundary plot, correctly reshaped and labeled (5%). |
| Part B — Gradient Descent | 35% | 1D gradient descent correct (10%) + convergence comparison across at least three learning rates, plotted (10%) + at least one learning rate shown diverging or visibly misbehaving, not just three that all converge nicely (5%) + 2D extension implemented with the path plotted over a contour plot (10%). |
| Part C — PCA via SVD | 25% | Centering step present before SVD (5%) + `np.linalg.svd` correctly applied to extract the principal direction (10%) + visualization showing original data, direction, and projection together (10%). |
| Plot quality (cross-cutting) | 10% | Every required plot has axis labels, a title, and a legend where more than one series appears — graded once across the whole submission rather than per-part. |

A few things worth knowing about how this gets graded:
- **k-NN vectorization is checked directly in your code**, not just your output — a `for` loop over `X_train` in your distance function is an automatic miss on that 10%, even if the final answer is correct.
- **The learning-rate comparison needs at least one curve that clearly diverges or oscillates.** Three flat, nicely-converging lines suggests you only tried "safe" rates and missed the point of the comparison — push a rate high enough to break it.
- **A tilted or clearly-wrong PCA direction is almost always a missing centering step** — this is checked directly.
- **A single solid-color decision boundary is an automatic sign the grid predictions weren't reshaped** before `contourf` — an easy one-line fix, but it will cost you the 5% if left in.

---

## How to Submit

1. Push your final code to a **GitHub repository**. Make sure the repository is **public** so it can be reviewed.
2. Your repo should include at minimum: `knn.py`, `gradient_descent.py`, `pca.py`, `requirements.txt`, a `README.md`, and your generated plot images (or the notebook/script that produces them).
3. Submit the **link to your public GitHub repository** on Moodle. That link is your submission — nothing else needs to be uploaded separately.

Before you submit, double check that your repo actually runs cleanly if someone clones it fresh — no dependence on variables or state left over from your own notebook session.

---

## Troubleshooting Quick Reference

| Symptom | Likely cause | Fix |
|---|---|---|
| Decision boundary is one solid color | Grid predictions not reshaped to the grid's 2D shape before `contourf` | Reshape your flat predictions array to `xx.shape` before plotting |
| Gradient descent loss increases instead of decreasing | Learning rate too high, or a sign error in your gradient | Double check your derivative by hand; try a much smaller `lr` first to confirm the rest of the loop is correct |
| PCA direction looks wrong or tilted | Forgot to center the data before SVD | Subtract `data.mean(axis=0)` before calling `np.linalg.svd` |
| `ValueError: operands could not be broadcast together` | Shape mismatch, often `(n,)` vs `(n,1)` | Print `.shape` on every array involved; reshape explicitly rather than guessing |
| k-NN prediction is slow | Looping over training points instead of vectorizing | Replace the loop with the broadcasting-based distance function from Part A, Step 2 |
