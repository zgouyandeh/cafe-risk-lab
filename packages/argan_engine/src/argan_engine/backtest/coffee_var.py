"""Out-of-sample VaR backtest for weekly coffee returns (expanding window, 1-week and 13-week horizons)."""
from __future__ import annotations

import numpy as np
from scipy import stats

from .scores import christoffersen_ind, kupiec_pof


def run(r: np.ndarray, min_train: int = 260) -> dict:
    r = np.asarray(r, float)
    out = {"n_forecasts": int(len(r) - min_train), "models": {}}
    for name in ("historical", "normal"):
        res = {}
        for level in (0.95, 0.99):
            hits = []
            for t in range(min_train, len(r)):
                tr = r[:t]
                q = np.quantile(tr, 1 - level) if name == "historical" else tr.mean() + tr.std(ddof=1) * stats.norm.ppf(1 - level)
                hits.append(int(r[t] < q))
            hits = np.array(hits)
            k = kupiec_pof(int(hits.sum()), len(hits), 1 - level)
            k["independence_p"] = christoffersen_ind(hits)["p"]
            res[f"{int(level * 100)}"] = k
        out["models"][name] = res
    # 13-week horizon on non-overlapping windows (independence is then not an issue)
    h = 13
    hits = {"95": [], "99": []}
    for t in range(min_train, len(r) - h, h):
        tr = r[:t]
        # historical simulation of 13-week sums via bootstrap
        rng = np.random.default_rng(t)
        sums = rng.choice(tr, (4000, h)).sum(axis=1)
        y = r[t:t + h].sum()
        for lv, key in ((0.95, "95"), (0.99, "99")):
            hits[key].append(int(y < np.quantile(sums, 1 - lv)))
    out["h13"] = {k: kupiec_pof(int(np.sum(v)), len(v), 1 - int(k) / 100) for k, v in hits.items()}
    return out
