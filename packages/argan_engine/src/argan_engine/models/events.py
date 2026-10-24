"""Event overlay: extra escalation (up) / de-escalation (down) jumps on top of the fitted model.

Jump *sizes* are bootstrapped from the empirical tails of observed weekly FX moves; jump
*probabilities* are user judgment (default 0 = history only, to avoid double counting jumps that
are already inside the fitted regime model)."""
from __future__ import annotations

import numpy as np


def apply_event_overlay(r_fx: np.ndarray, p_esc: float, p_deal: float, up_sizes: np.ndarray,
                        down_sizes: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    n, w = r_fx.shape
    out = r_fx.copy()
    rows = np.arange(n)
    if p_esc > 0 and len(up_sizes):
        hit = rng.random(n) < p_esc
        wk = rng.integers(0, w, n)
        sz = rng.choice(up_sizes, n)
        out[rows[hit], wk[hit]] += sz[hit]
    if p_deal > 0 and len(down_sizes):
        hit = rng.random(n) < p_deal
        wk = rng.integers(0, w, n)
        sz = rng.choice(down_sizes, n)
        out[rows[hit], wk[hit]] += sz[hit]
    return out
