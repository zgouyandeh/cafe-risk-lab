"""Proper scoring rules and coverage tests."""
from __future__ import annotations

import numpy as np
from scipy import stats


def crps_samples(x: np.ndarray, y: float) -> float:
    """CRPS of an ensemble forecast x for outcome y: E|X−y| − ½E|X−X'| (Gneiting & Raftery 2007)."""
    x = np.sort(np.asarray(x, float))
    n = len(x)
    t1 = np.abs(x - y).mean()
    i = np.arange(1, n + 1)
    t2 = (2 * (2 * i - n - 1) * x).sum() / (n * n)       # = E|X-X'| via sorted formula
    return float(t1 - 0.5 * t2)


def kupiec_pof(violations: int, n: int, p: float) -> dict:
    """Kupiec (1995) proportion-of-failures likelihood-ratio test, LR ~ chi2(1)."""
    x = violations
    if x in (0, n):
        ll1 = 0.0
    else:
        ll1 = x * np.log(x / n) + (n - x) * np.log(1 - x / n)
    ll0 = x * np.log(p) + (n - x) * np.log(1 - p)
    lr = -2 * (ll0 - ll1)
    return {"violations": int(x), "n": int(n), "rate": x / n, "expected": p, "lr": float(lr),
            "p": float(1 - stats.chi2.cdf(lr, 1))}


def christoffersen_ind(v: np.ndarray) -> dict:
    """Christoffersen (1998) independence test of the hit sequence, LR ~ chi2(1)."""
    v = np.asarray(v, int)
    a, b = v[:-1], v[1:]
    n00 = int(((a == 0) & (b == 0)).sum()); n01 = int(((a == 0) & (b == 1)).sum())
    n10 = int(((a == 1) & (b == 0)).sum()); n11 = int(((a == 1) & (b == 1)).sum())

    def ll(k, n):
        return 0.0 if k in (0, n) or n == 0 else k * np.log(k / n) + (n - k) * np.log(1 - k / n)
    pi = (n01 + n11) / max(n00 + n01 + n10 + n11, 1)
    l0 = (n00 + n10) * np.log(1 - pi) + (n01 + n11) * np.log(pi) if 0 < pi < 1 else 0.0
    l1 = ll(n01, n00 + n01) + ll(n11, n10 + n11)
    lr = max(-2 * (l0 - l1), 0.0)
    return {"lr": float(lr), "p": float(1 - stats.chi2.cdf(lr, 1))}


def diebold_mariano(l1: np.ndarray, l2: np.ndarray, h: int) -> dict:
    """Diebold–Mariano (1995) test on loss differentials with Newey–West variance (lag h−1) and the
    Harvey–Leybourne–Newbold small-sample correction. Negative mean => model 1 better."""
    d = np.asarray(l1) - np.asarray(l2)
    n = len(d)
    dm = d.mean()
    g0 = ((d - dm) ** 2).mean()
    var = g0
    for k in range(1, h):
        w = 1 - k / h
        var += 2 * w * ((d[k:] - dm) * (d[:-k] - dm)).mean()
    var = max(var, 1e-18) / n
    stat = dm / np.sqrt(var)
    corr = np.sqrt((n + 1 - 2 * h + h * (h - 1) / n) / n)
    stat *= corr
    return {"mean_diff": float(dm), "stat": float(stat), "p": float(2 * (1 - stats.t.cdf(abs(stat), n - 1)))}
