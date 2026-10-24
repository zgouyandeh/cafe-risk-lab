"""Model-free historical replay: what would purchase timing have cost on REALISED prices?

For every start week with a full horizon of data, landed replacement cost RC_t = P_t · X_t · (1+landing)
is read from the real weekly series. For a weight vector w over order weeks:
    extra_cost(w)  = Σ w_k RC_{k}/RC_0 − 1             (rial cost vs buying everything at week 0)
    carry(w)       = Σ w_k [(1+r)^{k/52}(1+hold)^k − 1] (financing + storage of buying earlier)
    advantage_now  = extra_cost(w) − carry(w)           (net saving from buying earlier than w)
Blocks of overlapping windows are strongly dependent, hence a stationary bootstrap for the CI."""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..config import Scenario
from ..data import cents_lb_to_usd_kg


def stationary_bootstrap_ci(x: np.ndarray, mean_block: int = 13, B: int = 2000, seed: int = 0) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    n = len(x)
    p = 1.0 / mean_block
    means = np.empty(B)
    for b in range(B):
        idx = np.empty(n, int)
        idx[0] = rng.integers(n)
        for i in range(1, n):
            idx[i] = rng.integers(n) if rng.random() < p else (idx[i - 1] + 1) % n
        means[b] = x[idx].mean()
    return float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))


def run(cal_series: dict, scn: Scenario, coffee_weekly: pd.Series, fx_weekly: pd.Series) -> dict:
    land = 1 + scn.landing_cost_pct / 100
    df = pd.concat([coffee_weekly.rename("c").ffill(limit=2), fx_weekly.rename("x")], axis=1).dropna()
    RC = (cents_lb_to_usd_kg(df["c"]) + scn.coffee_differential_usd_kg) * df["x"] * land
    H = scn.horizon_weeks
    sw = scn.schedule_weeks
    hold = scn.storage_cost_pct_week / 100 + scn.shrink_pct_week / 100
    rate = {"deposit": scn.deposit_rate_pct / 100, "borrow": scn.borrow_rate_pct / 100}
    pols = {"all_now": [1, 0, 0], "equal_split": [1 / 3] * 3, "late_heavy": [0.2, 0.3, 0.5], "all_late": [0, 0, 1]}
    pols = {k: v[:len(sw)] if len(sw) <= 3 else v for k, v in pols.items()}
    pols = {k: np.array(v) / sum(v) for k, v in pols.items() if len(v) == len(sw)}
    starts = range(0, len(RC) - H)
    rows = []
    for s in starts:
        r0 = RC.iloc[s]
        row = {"date": RC.index[s]}
        for name, w in pols.items():
            extra = sum(wk * RC.iloc[s + k] / r0 for wk, k in zip(w, sw)) - 1
            for rn, rv in rate.items():
                carry = sum(wk * ((1 + rv) ** (k / 52) * (1 + hold) ** k - 1) for wk, k in zip(w, sw))
                row[f"{name}|{rn}"] = extra - carry
            row[f"{name}|extra"] = extra
        rows.append(row)
    d = pd.DataFrame(rows).set_index("date")
    out = {"n_windows": int(len(d)), "start": str(d.index[0].date()), "end": str(d.index[-1].date()),
           "horizon_weeks": H, "policies": {}}
    for name in pols:
        if name == "all_now":
            continue
        entry = {}
        for rn in ("deposit", "borrow"):
            x = d[f"{name}|{rn}"].values
            lo, hi = stationary_bootstrap_ci(x)             # advantage of buying all now vs `name`
            entry[rn] = {"advantage_of_earlier_mean": float(x.mean()), "ci": [lo, hi],
                         "share_windows_earlier_better": float((x > 0).mean())}
        entry["extra_cost_mean"] = float(d[f"{name}|extra"].mean())
        by_year = d.groupby(d.index.year)[f"{name}|deposit"].mean()
        entry["by_year_advantage_deposit"] = {int(k): float(v) for k, v in by_year.items()}
        out["policies"][name] = entry
    fxr = fx_weekly.reindex(df.index)
    chg = (fxr.shift(-H) / fxr - 1).dropna()
    out["fx_13w_change"] = {"mean": float(chg.mean()), "share_down": float((chg < 0).mean()),
                            "p5": float(chg.quantile(0.05)), "p95": float(chg.quantile(0.95))}
    return out
