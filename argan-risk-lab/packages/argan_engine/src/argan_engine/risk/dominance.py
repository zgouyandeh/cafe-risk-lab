"""Second-order stochastic dominance (SSD) between outcome samples.

A SSD B  <=>  E[(x-A)^+] <= E[(x-B)^+] for all x  <=>  every risk-averse expected-utility maximiser
(any increasing concave utility) weakly prefers A. This is a preference-free filter: it needs no λ.
(Hadar & Russell 1969; Rothschild & Stiglitz 1970.)"""
from __future__ import annotations

import numpy as np


def ssd_gap(a: np.ndarray, b: np.ndarray, n_grid: int = 400) -> dict:
    """Returns max_x [E(x-A)^+ - E(x-B)^+] (>0 means A fails to dominate somewhere) and its mirror."""
    pooled = np.concatenate([a, b])
    xs = np.quantile(pooled, np.linspace(0.0, 1.0, n_grid))
    ea = np.array([np.maximum(x - a, 0).mean() for x in xs])
    eb = np.array([np.maximum(x - b, 0).mean() for x in xs])
    scale = float(np.std(pooled)) or 1.0
    d = (ea - eb) / scale
    return {"a_minus_b_max": float(d.max()), "b_minus_a_max": float((-d).max()),
            "frac_a_better": float((d < 0).mean())}


def ssd_relation(a: np.ndarray, b: np.ndarray, tol: float = 2e-3) -> str:
    """'A', 'B' or 'none': which sample (if any) SSD-dominates, up to a tolerance of `tol` sd."""
    g = ssd_gap(a, b)
    a_dom = g["a_minus_b_max"] <= tol and g["b_minus_a_max"] > tol
    b_dom = g["b_minus_a_max"] <= tol and g["a_minus_b_max"] > tol
    return "A" if a_dom else "B" if b_dom else "none"
