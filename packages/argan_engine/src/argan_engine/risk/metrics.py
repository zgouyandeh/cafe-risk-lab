"""Risk metrics on simulated outcome samples."""
from __future__ import annotations

import numpy as np


def var_lower(x: np.ndarray, alpha: float = 0.95) -> float:
    """Value-at-Risk of a PROFIT sample: the (1-alpha) quantile (loss is its negative)."""
    return float(np.quantile(x, 1 - alpha))


def cvar_lower(x: np.ndarray, alpha: float = 0.95) -> float:
    """Expected shortfall of a PROFIT sample: mean of the worst (1-alpha) fraction.

    Acerbi–Tasche estimator (exact fractional weight at the boundary). Equals the Rockafellar–Uryasev
    minimum  min_z { z + 1/((1-alpha)) E[(z - X)^+] } of the profit-side shortfall (sign-flipped)."""
    x = np.sort(np.asarray(x, float))
    n = len(x)
    k = round((1 - alpha) * n, 9)       # guard against float error in floor()
    m = int(np.floor(k))
    tot = x[:m].sum() + (k - m) * (x[m] if m < n else 0.0)
    return float(tot / k)


def mean_cvar_objective(x: np.ndarray, alpha: float, lam: float) -> float:
    """J = (1-λ) E[Π] + λ CVaR_α[Π]  — coherent for λ in [0,1] (convex combination of two coherent
    risk-adjusted measures). λ=0: risk neutral; λ→1: only the worst tail matters."""
    return float((1 - lam) * np.mean(x) + lam * cvar_lower(x, alpha))


def paired_diff(a: np.ndarray, b: np.ndarray) -> dict:
    """a-b on common random numbers: mean difference, standard error, 95% CI and P(a>b)."""
    d = np.asarray(a) - np.asarray(b)
    se = d.std(ddof=1) / np.sqrt(len(d))
    return {"mean": float(d.mean()), "se": float(se), "lo": float(d.mean() - 1.96 * se),
            "hi": float(d.mean() + 1.96 * se), "p_better": float((d > 0).mean())}


def bootstrap_ci(x: np.ndarray, fn, B: int = 300, seed: int = 0) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    n = len(x)
    vals = [fn(x[rng.integers(0, n, n)]) for _ in range(B)]
    return float(np.quantile(vals, 0.025)), float(np.quantile(vals, 0.975))
