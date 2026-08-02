"""
gradient_descent.py — gradient descent from scratch in NumPy, 1D and 2D.
"""

import numpy as np


# ---------------------------------------------------------------------------
# Part 1: 1D optimization
#   f(x) = (x - 3)^2, minimum at x = 3
#   f'(x) = 2(x - 3)
# ---------------------------------------------------------------------------

def f(x):
    return (x - 3) ** 2


def grad_f(x):
    return 2 * (x - 3)


def gradient_descent_1d(start, lr, steps):
    """
    Run gradient descent on f(x) = (x - 3)^2 starting at `start`,
    with learning rate `lr`, for `steps` iterations.
    """
    x = start
    history = [x]     #list of x values visited
    for _ in range(steps):
        x = x - lr * grad_f(x)
        history.append(x)
    return x, history


# ---------------------------------------------------------------------------
# Part 2: 2D extension
#   f2(x, y) = x^2 + 5y^2, minimum at (0, 0)
#   grad f2(x, y) = (2x, 10y)
# ---------------------------------------------------------------------------

def f2(x, y):
    return x ** 2 + 5 * y ** 2


def grad_f2(x, y):
    return np.array([2 * x, 10 * y])


def gradient_descent_2d(start, lr, steps):
    """
    Run gradient descent on f2(x, y) = x^2 + 5y^2 starting at `start`
    (a length-2 array-like), with learning rate `lr`, for `steps`
    iterations.

   """
    point = np.array(start, dtype=float)
    path = [point.copy()]
    for _ in range(steps):
        g = grad_f2(point[0], point[1])
        point = point - lr * g
        path.append(point.copy())
    return point, np.array(path)
