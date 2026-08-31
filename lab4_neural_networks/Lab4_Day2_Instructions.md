# Lab 4, Day 2 — Classification (3 hours)

Build a Fashion-MNIST classifier with proper validation tracking and early stopping, then read a confusion matrix as an error-analysis tool rather than decoration. This continues directly from day 1's `lab4_neural_networks/` folder in a new notebook (`day2_classification_starter.ipynb`).

---

## Step 1: Load Fashion-MNIST and Prepare Loaders (`stage_b_classification.py`)

```python
from torchvision import datasets, transforms
datasets.FashionMNIST(root="./data", train=True, download=True, transform=transforms.ToTensor())
```

This should already be cached in `data/` from day 1. If it isn't, run it now.

Split off a validation set from the training data (don't touch the real test set until the very end), and build `DataLoader`s for train/val/test. **Shuffle the training loader only** — shuffling validation or test data changes nothing about your metrics, it just wastes a little time.

## Look at the Data Before You Model It

Before writing a single line of model code, plot a few example images — one or a few per class. `train_set.classes` gives you the human-readable label names to put on them.

Step 4 is going to ask you whether the model's confusion between certain classes is reasonable, and you cannot honestly answer that question about images without looking at them. Looking now, before you have a model with an opinion, also means your judgment about what's confusable isn't retroactively shaped by already knowing which mistakes it made.

## Step 2: The Classifier

Think about the dimensions carefully.

Flatten the 28×28 images into a 784-length vector as your first layer, then a small MLP down to 10 output classes. The outputs are just the raw scores, **no softmax to be applied here** (though you could experiment with this and see what it leads to).

`nn.CrossEntropyLoss` applies log-softmax internally; adding a softmax layer on top of that gives you broken behavior. It runs and reports a loss but learns badly, with no error telling you why. This makes the "no softmax" warning from lecture more clear, and motivates tracking the validation carefully. Without it, you can't tell a model that's learning badly from one that's just learning slowly. Always double check your final layer.

## Step 3: Train With Validation Tracking and Early Stopping

Each epoch: train on the training loader, then evaluate accuracy on the validation loader (remember to toggle `model.train()` before the training pass and `model.eval()` before the validation pass, every single epoch). Track both the training loss and validation accuracy per epoch so you can plot them.

1. **Training pass**: loop over every batch in `train_loader`, and for each batch do the full `zero_grad → forward → loss → backward → step sequence` — this is the only part of the epoch that actually changes the weights. Accumulate the loss from each batch, and at the end of the epoch, average it and append that single number to `train_losses`.

2. **Validation pass**: after all training batches for that epoch are done, switch to eval mode, loop over `val_loader` with no gradient tracking, and compute one accuracy number for the whole validation set. Append that single number to `val_accuracies`.

Implement early stopping with **patience**, not a single bad epoch: keep a counter of how many consecutive epochs have passed without a new best validation accuracy, and stop once that counter hits some threshold (e.g. 3). Stopping on the very first non-improving epoch will stop on ordinary training noise, not a real plateau.

When you save your "best" model state, **clone the tensors**, don't just keep a reference to them (`{k: v.clone() for k, v in model.state_dict().items()}`). Without cloning, what you think is a snapshot of the best epoch is actually a live reference that keeps changing as training continues — so your "best" model silently becomes identical to your final model, and early stopping accomplishes nothing.

Restore the best saved state (not the final state) once training ends with `model.load_state_dict(best_state)`.

Reuse (or extend) the training-loop pattern you wrote in `train.py` on day 1 (if you refactored it).

## Step 4: Confusion Matrix

Finally, run the trained model over the test set, build a confusion matrix, and display it (`sklearn.metrics.confusion_matrix` + `ConfusionMatrixDisplay`).

**You should land somewhere around 87–89% test accuracy.** Look at where the model gets confused — on Fashion-MNIST, shirts, coats, pullovers, and t-shirts tend to get mixed up with each other. Ask yourself whether that's a reasonable place for a model to struggle, given what those classes actually look like at low resolution.

## Written Prompt

Answer this in a markdown cell, in your own words:

> Look at your training curves: validation accuracy flattens while training loss keeps falling. Describe what the model is doing in that gap, and explain what your early stopping rule actually protected you from.

## Closing Reflection

This is the last cell of your notebook. Answer in your own words:

> Across both days you used a framework to do things you had previously done by hand. Name one thing PyTorch genuinely did for you, and one thing it did *not* do — something you still had to get right yourself.

---

## Deliverable Checklist

- [ ] One notebook per day (or one combined notebook), running top to bottom after a full kernel restart
- [ ] Day 1: training loss curve, test MSE reported, explicit comparison against your Lab 2 code, written prompt answered
- [ ] Day 2: training loss and validation accuracy curves, early stopping with a patience mechanism, confusion matrix displayed and briefly interpreted, written prompt answered
- [ ] Closing reflection answered as the last cell of the lab
- [ ] All plots labeled — axes, title, and a legend wherever more than one series appears
- [ ] Code refactored into functions rather than repeated across cells — a reusable training function in `train.py` used by both days is the clearest sign of this
- [ ] A `README.md` explaining what your program does and how to run it

## Grading Rubric (Lab 4 = 7% of course grade)

| Category | Weight | Criteria |
|---|---|---|
| Day 1 — Regression | 30% | Correct training loop with `zero_grad` called each step + preprocessing done properly, features standardized and target reshaped + loss curve plotted and test MSE reported + explicit comparison against your own Lab 2 code. |
| Day 2 — Classification | 40% | Working classifier with `CrossEntropyLoss` and no softmax in the model + validation tracked per epoch and plotted alongside training loss + early stopping with a genuine patience mechanism, not a single-epoch check + confusion matrix displayed and briefly interpreted. |
| Written analysis | 15% | Three prompts, equally weighted. |
| Code quality and notebook hygiene | 15% | Refactored into functions rather than repeated cells + notebook runs top to bottom after a kernel restart + plots labeled. |

---

## How to Submit

1. Push your final code to a **GitHub repository**. Make sure the repository is **public** so it can be reviewed.
2. Your repo should include at minimum: `train.py`, `stage_a_regression.py`, `stage_b_classification.py`, your final notebook(s), `requirements.txt`, and a `README.md`.
3. Add a `.gitignore` that excludes `data/` and `__pycache__/`.
4. Submit the **link to your public GitHub repository** on Moodle. That link is your submission — nothing else needs to be uploaded separately.

Before you submit, restart your kernel and run every cell top to bottom one more time.

---

## Troubleshooting Quick Reference

| Symptom | Likely cause | Fix |
|---|---|---|
| Stage B accuracy stuck near 10% | Softmax applied in the model on top of `CrossEntropyLoss`, or labels aren't integer class indices | Remove the softmax; check `y.dtype` is an integer type |
| "Best" saved model performs identically to the final model | `state_dict()` saved by reference instead of cloned | Clone each tensor when saving: `{k: v.clone() for k, v in model.state_dict().items()}` |
| Early stopping never triggers, or triggers immediately | Patience counter reset/incremented in the wrong branch, or comparing with `>=` vs `>` inconsistently | Trace through one non-improving epoch by hand against your own logic |
| Fashion-MNIST download hangs or times out | Downloading live during the session on shared wifi | Should already be cached from Day 1 — check `data/` before assuming you need to redownload |
| `RuntimeError: Expected all tensors to be on the same device` | Model moved to GPU but batch wasn't, or vice versa | Move both consistently: `X.to(device)`, `model.to(device)` |
