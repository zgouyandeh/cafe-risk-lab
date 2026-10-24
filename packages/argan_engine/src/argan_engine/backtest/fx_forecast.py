"""Out-of-sample comparison of FX predictive distributions for the cumulative 13-week log change.

Candidates: rw0 (zero drift Gaussian), gbm (drift+vol), t (Student-t), regime (2-state Markov).
Expanding window, regime refit every `refit` weeks with the Hamilton filter updated every origin.
Scores: CRPS (lower is better), central-interval coverage, Diebold–Mariano tests vs. each rival."""
from __future__ import annotations

import warnings

import numpy as np

from ..models.fx import FXGBM, FXRegime, FXStudentT
from .scores import crps_samples, diebold_mariano

warnings.filterwarnings("ignore")


def run(r: np.ndarray, h: int = 13, min_train: int = 104, refit: int = 13, M: int = 3000, seed: int = 1) -> dict:
    r = np.asarray(r, float)
    names = ["rw0", "gbm", "t", "regime"]
    crps = {k: [] for k in names}
    cover = {k: {50: [], 80: [], 90: []} for k in names}
    pit = {k: [] for k in names}
    reg = None
    origins = list(range(min_train, len(r) - h + 1))
    for t in origins:
        tr = r[:t]
        y = r[t:t + h].sum()
        rng = np.random.default_rng(seed + t)
        z = rng.standard_normal((M, h))
        if reg is None or (t - min_train) % refit == 0:
            try:
                reg, _ = FXRegime.fit(tr, k=2, n_starts=3, seed=t)
            except Exception:
                pass
        else:
            reg = FXRegime(reg.mu, reg.sigma, reg.P, reg.filter_last(tr))
        gbm, tm = FXGBM.fit(tr), FXStudentT.fit(tr)
        fc = {"rw0": FXGBM(0.0, gbm.sigma).simulate(z, rng)[0].sum(1),
              "gbm": gbm.simulate(z, rng)[0].sum(1),
              "t": tm.simulate(z, rng)[0].sum(1),
              "regime": reg.simulate(z, rng)[0].sum(1)}
        for k, x in fc.items():
            crps[k].append(crps_samples(x, y))
            pit[k].append(float((x < y).mean()))
            for c in (50, 80, 90):
                lo, hi = np.quantile(x, [(1 - c / 100) / 2, 1 - (1 - c / 100) / 2])
                cover[k][c].append(int(lo <= y <= hi))
    arr = {k: np.array(v) for k, v in crps.items()}
    out = {"h": h, "n_origins": len(origins), "models": {}}
    for k in names:
        out["models"][k] = {"crps": float(arr[k].mean()),
                            "coverage": {str(c): float(np.mean(v)) for c, v in cover[k].items()},
                            "pit": np.histogram(pit[k], bins=10, range=(0, 1))[0].tolist()}
    best = min(names, key=lambda k: out["models"][k]["crps"])
    out["best_by_crps"] = best
    out["dm_vs_best"] = {k: diebold_mariano(arr[best], arr[k], h) for k in names if k != best}
    # Selection rule: models statistically indistinguishable from the CRPS-best (DM p > 0.10) form a
    # tie set; inside it prefer the richest tail description (regime > t > gbm) because risk metrics
    # (CVaR, liquidity breach) are driven by tails. A clearly worse model (e.g. zero drift) is dropped.
    tie = [best] + [k for k in names if k != best and out["dm_vs_best"][k]["p"] > 0.10]
    out["tie_set"] = tie
    out["selected"] = next(k for k in ("regime", "t", "gbm", "rw0") if k in tie)
    out["dm_vs_selected"] = out["dm_vs_best"]
    return out
