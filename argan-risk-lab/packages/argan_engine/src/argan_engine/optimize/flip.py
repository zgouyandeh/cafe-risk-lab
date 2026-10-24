"""'What would change the answer?' – re-solve the whole problem along a one-dimensional belief axis."""
from __future__ import annotations

import numpy as np

from ..calibrate import Calibration
from ..config import Scenario
from ..sim import build_market
from .policy_search import evaluate_grid, select_best


def flip_curve(base: Scenario, cal: Calibration, field: str, values: list[float], W: np.ndarray,
               n_paths: int = 3000) -> list[dict]:
    rows = []
    for v in values:
        scn = base.model_copy(update={field: float(v)})
        rng = np.random.default_rng(base.seed + 31)          # same seed along the axis (smooth curve)
        mkt = build_market(scn, cal, n_paths, rng)
        ev = evaluate_grid(mkt, scn, W, keep_profit=False)
        sel = select_best(ev, scn)
        i = sel["idx"]
        rows.append({"value": float(v), "weights": ev.weights[i].tolist(), "feasible": bool(sel["feasible"]),
                     "mean": float(ev.mean[i]), "cvar": float(ev.cvar[i]), "w_first": float(ev.weights[i][0]),
                     "w_unconstrained_first": float(ev.weights[int(np.argmax(ev.J))][0])})
    return rows


def crossing(rows: list[dict], key: str = "w_first", level: float = 0.5) -> float | None:
    """First value where the optimal first-tranche share crosses `level` (linear interpolation)."""
    xs = [r["value"] for r in rows]
    ys = [r[key] for r in rows]
    for a in range(len(xs) - 1):
        y0, y1 = ys[a] - level, ys[a + 1] - level
        if y0 == 0:
            return xs[a]
        if y0 * y1 < 0:
            return xs[a] + (xs[a + 1] - xs[a]) * (0 - y0) / (y1 - y0)
    return None
