"""Auto-generate ordered hints from a sympy expression."""
from typing import List, Dict
import numpy as np
from sympy import (
    symbols, diff, integrate, solve, N, simplify,
    Poly, degree, oo,
)
from sympy.core.sympify import SympifyError

x = symbols("x")


def _is_even(expr) -> bool:
    try:
        return simplify(expr.subs(x, -x) - expr) == 0
    except Exception:
        return False


def _is_odd(expr) -> bool:
    try:
        return simplify(expr.subs(x, -x) + expr) == 0
    except Exception:
        return False


def _detect_family(expr) -> str:
    s = str(expr)
    has_trig = any(t in s for t in ["sin", "cos", "tan", "sec", "csc", "cot"])
    has_exp  = any(t in s for t in ["exp", "E**"])
    has_log  = any(t in s for t in ["log"])

    try:
        p = Poly(expr, x)
        d = int(degree(p))
        names = {1: "linear", 2: "quadratic", 3: "cubic", 4: "quartic", 5: "quintic"}
        label = names.get(d, f"degree-{d}")
        return f"{label} polynomial"
    except Exception:
        pass

    if has_trig and has_exp:
        return "combination of trigonometric and exponential terms"
    if has_trig:
        return "trigonometric function"
    if has_exp:
        return "exponential function"
    if has_log:
        return "logarithmic function"
    return "algebraic function"


def generate_hints(expr, a: float, b: float) -> List[Dict]:
    """Return a list of hint dicts ordered from least to most informative."""
    hints: List[Dict] = []
    midpoint = (a + b) / 2.0

    # --- Hint: function family (weakest, difficulty 1) ---
    family = _detect_family(expr)
    hints.append({
        "type": "family",
        "difficulty": 1,
        "text": f"The function belongs to the family: {family}.",
    })

    # --- Hint: symmetry (difficulty 1) ---
    if _is_even(expr):
        sym_text = "The function is even — f(−x) = f(x) — symmetric about the y-axis."
    elif _is_odd(expr):
        sym_text = "The function is odd — f(−x) = −f(x) — has rotational symmetry about the origin."
    else:
        sym_text = "The function has no special symmetry (neither even nor odd)."
    hints.append({"type": "symmetry", "difficulty": 1, "text": sym_text})

    # --- Hint: definite integral (difficulty 2) ---
    try:
        val = float(N(integrate(expr, (x, a, b)), 6))
        hints.append({
            "type": "integral",
            "difficulty": 2,
            "text": f"The definite integral  ∫f(x)dx  over [{a}, {b}]  ≈  {val:.4f}.",
        })
    except Exception:
        pass

    # --- Hint: zeros in [a, b] (difficulty 2) ---
    try:
        raw_roots = solve(expr, x)
        real_roots = []
        for r in raw_roots:
            try:
                rv = complex(N(r))
                if abs(rv.imag) < 1e-8:
                    rf = rv.real
                    if a <= rf <= b:
                        real_roots.append(rf)
            except Exception:
                pass
        if real_roots:
            root_str = ",  ".join(f"{r:.4f}" for r in sorted(real_roots))
            hints.append({
                "type": "roots",
                "difficulty": 2,
                "text": f"Within [{a}, {b}], the function has zeros at  x ≈ {root_str}.",
            })
        else:
            hints.append({
                "type": "roots",
                "difficulty": 2,
                "text": f"The function has no zeros within [{a}, {b}].",
            })
    except Exception:
        pass

    # --- Hint: derivative at midpoint (difficulty 3) ---
    try:
        deriv = diff(expr, x)
        dval = float(N(deriv.subs(x, midpoint), 6))
        hints.append({
            "type": "derivative",
            "difficulty": 3,
            "text": f"The derivative at x = {midpoint}:  f′({midpoint}) ≈ {dval:.4f}.",
        })
    except Exception:
        pass

    # --- Hint: local extrema (difficulty 3) ---
    try:
        deriv = diff(expr, x)
        deriv2 = diff(expr, x, 2)
        crit_pts = solve(deriv, x)
        extrema = []
        for p in crit_pts:
            try:
                pv = complex(N(p))
                if abs(pv.imag) > 1e-8:
                    continue
                pf = pv.real
                if not (a < pf < b):
                    continue
                fv = float(N(expr.subs(x, p)))
                d2 = float(N(deriv2.subs(x, p)))
                kind = ("local maximum" if d2 < 0
                        else "local minimum" if d2 > 0
                        else "saddle point")
                extrema.append(f"{kind} at ({pf:.4f},  {fv:.4f})")
            except Exception:
                pass
        if extrema:
            hints.append({
                "type": "extrema",
                "difficulty": 3,
                "text": "Within the interval: " + ";  ".join(extrema) + ".",
            })
        else:
            hints.append({
                "type": "extrema",
                "difficulty": 3,
                "text": f"The function is monotone on [{a}, {b}] — no local extrema inside the open interval.",
            })
    except Exception:
        pass

    # --- Hint: concavity at midpoint (difficulty 3, most technical) ---
    try:
        deriv2 = diff(expr, x, 2)
        d2val = float(N(deriv2.subs(x, midpoint), 6))
        direction = ("concave up (∪)" if d2val > 0
                     else "concave down (∩)" if d2val < 0
                     else "has an inflection point")
        hints.append({
            "type": "concavity",
            "difficulty": 3,
            "text": (
                f"At the midpoint x = {midpoint}:  f″({midpoint}) ≈ {d2val:.4f}.  "
                f"The function is {direction} near the midpoint."
            ),
        })
    except Exception:
        pass

    hints.sort(key=lambda h: h["difficulty"])
    return hints
