"""Function parsing, evaluation, and scoring engine."""
import math
import warnings
import numpy as np
from sympy import symbols, sympify, lambdify
from sympy.core.sympify import SympifyError

x = symbols("x")


def parse_function(expr_str: str):
    """Parse an expression string into a numpy-callable and its sympy form.

    Returns (callable, sympy_expr). Raises ValueError on bad input.
    """
    try:
        expr = sympify(expr_str)
        # lambdify with numpy so sin/exp/etc. work on arrays
        f = lambdify(x, expr, modules=["numpy"])
        return f, expr
    except (SympifyError, TypeError, ValueError) as e:
        raise ValueError(f"Cannot parse '{expr_str}': {e}")


def evaluate_safe(f, xs: np.ndarray) -> np.ndarray:
    """Evaluate f on xs; replace non-finite values with NaN."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            ys = np.asarray(f(xs), dtype=float)
            if ys.shape == ():
                ys = np.full(xs.shape, float(ys))
            return np.where(np.isfinite(ys), ys, np.nan)
        except Exception:
            return np.full(xs.shape, np.nan)


def compute_rmse(f_true, f_guess, a: float, b: float, n: int = 5000) -> float:
    """Compute RMSE between f_true and f_guess on [a, b] using n sample points."""
    xs = np.linspace(a, b, n)
    yt = evaluate_safe(f_true, xs)
    yg = evaluate_safe(f_guess, xs)
    mask = np.isfinite(yt) & np.isfinite(yg)
    if mask.sum() < 10:
        return float("inf")
    return float(np.sqrt(np.mean((yt[mask] - yg[mask]) ** 2)))


def function_std(f, a: float, b: float, n: int = 5000) -> float:
    """Compute the standard deviation of f on [a, b] (used for RMSE normalization)."""
    xs = np.linspace(a, b, n)
    ys = evaluate_safe(f, xs)
    ys = ys[np.isfinite(ys)]
    return float(np.std(ys)) if len(ys) > 1 else 1.0


def compute_score(rmse: float, f_std: float, hints_revealed: int, hint_cost: int = 50) -> int:
    """Convert RMSE to a game score (0–1000) minus hint penalties.

    Score = floor(1000 * exp(-2 * rmse/std)) - hints_revealed * hint_cost
    """
    if not math.isfinite(rmse):
        return 0
    normalized = rmse / max(f_std, 1e-10)
    accuracy = round(1000 * math.exp(-2 * normalized))
    penalty = hints_revealed * hint_cost
    return max(0, accuracy - penalty)
