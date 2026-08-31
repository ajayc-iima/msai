# Lab 4, Day 1 — Regression (3 hours)

Build a small MLP regressor in PyTorch, then compare it head-to-head against your own Lab 2 NumPy gradient descent on the exact same data. This is your first framework lab after a few weeks of NumPy-only work. The goal is understanding what PyTorch is automating for you.

Work in the `lab4_neural_networks/` folder shared with you. Today you need `train.py`, `stage_a_regression.py`, and `day1_regression_starter.ipynb` — all blank/shell files for you to fill in.

---

## 0. Before You Touch Any Code

**This should already be done before you start the lab work**: `pip install torch torchvision scikit-learn matplotlib` (or `pip install -r requirements.txt`). `torch` is a large download — if you haven't installed it yet, do that first, since it eats real time out of an already-tight three hours.

---

## Step 1: Load and Preprocess (`stage_a_regression.py`)

Load the California Housing dataset (`sklearn.datasets.fetch_california_housing`), split into train/test, and get two preprocessing details right:

- **Standardize features:** fit a `StandardScaler` on the training data only, then use that same fitted scaler to transform the test data. Fitting on the test set too leaks information from data your model shouldn't have seen yet — worth internalizing now, since it's a concept the course covers properly in a couple weeks.
- **Reshape your target to `(n, 1)`.** If you leave `y_train` as shape `(n,)` while your model outputs shape `(n, 1)`, `MSELoss` will silently broadcast them into an `(n, n)` matrix instead of erroring. The loss still computes, still decreases, and is completely meaningless. This is the easiest bug in the whole lab to miss, because nothing crashes — check your shapes explicitly.

## Step 2: Model, Loss, Optimizer

Build a small MLP: one hidden layer is enough (e.g. `Linear -> ReLU -> Linear`, hidden size around 32). Use `nn.MSELoss()` and `optim.Adam`.

## Step 3: The Training Loop (`train.py`)

Write a training loop that, each epoch: computes predictions, computes loss, zeros gradients, backpropagates, and steps the optimizer. Record the loss **value**, not the loss tensor itself — pulling out a plain float (rather than keeping the tensor object) matters, because the tensor keeps its entire computation graph alive in memory for as long as you hold onto it. Holding 200 epochs' worth of full computation graphs is a real memory leak, not just untidy code.

Write this as a reusable function in `train.py` rather than a one-off loop in the notebook — you'll want the exact same shape of loop again tomorrow, just with mini-batches instead of the whole dataset at once. Building that reusability now is exactly what the "code quality" rubric criterion is checking for, and it saves you real work tomorrow.

## Step 4: Evaluate and Plot

Switch the model to evaluation mode and disable gradient tracking before computing test loss. These do two different jobs and both matter here: eval mode toggles the behavior of certain layer types (no visible effect on this particular model, but the habit matters if you ever add dropout or batchnorm), while disabling gradients skips unnecessary computation and memory use at inference time.

Plot your training loss curve and report the final test MSE.

## Step 5: Compare Against Your Own Lab 2 Code

This is the point of today. Take your Lab 2 gradient descent implementation (or rewrite the same idea: a linear model, hand-derived gradients, a manual update loop) and fit it on the exact same preprocessed data. Compare test MSE between the two approaches.

**Set your expectations honestly:** California Housing is close to linear, so don't expect the MLP to dramatically outperform your Lab 2 linear model — a modest win is the correct, honest result, not a sign something's wrong. The actual point of this comparison isn't "MLP wins," it's noticing exactly what PyTorch replaced: the two lines where you derived `grad_w` and `grad_b` by hand. Those two lines are exactly the ones that become impossible to write out by hand once you have more than one layer — that's the whole argument for using a framework at all, and it's worth stating explicitly in your written answer below.

## Written Prompt

Answer this in a markdown cell at the end of your Day 1 work, in your own words:

> Your MLP barely beats the linear model, and might lose to it. What would have to be true about this data for the MLP to win decisively — and what does that tell you about when a neural network is the right tool?

Aim for a short paragraph, not a one-liner. Think about non-linearity and feature interactions: a neural network can only exploit structure that's actually there, and if the true relationship between features and target is close to linear, extra capacity has little to work with — and can even hurt, by giving the model more room to overfit. "More data" alone isn't a complete answer; more data helps a model that's already the right shape for the problem, and does little for one that isn't.

---

## Before You Leave Today

Three things, in order:

1. **Save your trained model:** `torch.save(model.state_dict(), "stage_a.pt")`. Tomorrow is a different session.
2. **Pre-download Fashion-MNIST**, so it's cached before Day 2 needs it:
   ```python
   from torchvision import datasets, transforms
   datasets.FashionMNIST(root="./data", train=True, download=True, transform=transforms.ToTensor())
   datasets.FashionMNIST(root="./data", train=False, download=True, transform=transforms.ToTensor())
   ```
   Run this once now. A room of people downloading this simultaneously at the start of Day 2 costs everyone time.
3. **Keep your notebook and folder as-is.** Day 2 is a new notebook in this same folder — it is not a restart, and it does not repeat today's setup.

---

## Troubleshooting Quick Reference

| Symptom | Likely cause | Fix |
|---|---|---|
| Loss never decreases | `optimizer.zero_grad()` missing from the loop | Add it before `loss.backward()` |
| Loss becomes `nan` after a few steps | Learning rate too high, or features weren't standardized | Drop the learning rate by 10×; confirm `StandardScaler` was applied |
| Loss decreases but the number looks meaningless | Target shape `(n,)` vs. prediction shape `(n, 1)` — `MSELoss` silently broadcast them | Reshape your target: `y = y.reshape(-1, 1)` before training |
| `RuntimeError: Expected all tensors to be on the same device` | Model moved to GPU but batch wasn't, or vice versa | Move both consistently: `X.to(device)`, `model.to(device)` |
