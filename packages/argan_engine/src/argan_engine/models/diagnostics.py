"""Standard time-series diagnostics used to justify (or reject) model components."""
from __future__ import annotations

import warnings

import numpy as np
from scipy import stats
warnings.filterwarnings('ignore', category=FutureWarning, module='statsmodels')
from statsmodels.stats.diagnostic import acorr_ljungbox, het_arch


def arch_lm(r: np.ndarray, lags: int = 8) -> dict:
    lm, p, _, _ = het_arch(np.asarray(r) - np.mean(r), nlags=lags)
    return {"stat": float(lm), "p": float(p), "lags": lags}


def ljung_box(r: np.ndarray, lags: int = 10, squared: bool = False) -> dict:
    x = np.asarray(r) - np.mean(r)
    x = x ** 2 if squared else x
    out = acorr_ljungbox(x, lags=[lags], return_df=True)
    return {"stat": float(out["lb_stat"].iloc[0]), "p": float(out["lb_pvalue"].iloc[0]), "lags": lags}


def variance_ratio(r: np.ndarray, q: int) -> dict:
    """Lo–MacKinlay (1988) variance ratio with heteroskedasticity-robust z statistic.
    VR(q) = Var(q-period return) / (q Var(1-period)); 1 under a random walk."""
    r = np.asarray(r, float)
    n = len(r)
    mu = r.mean()
    d = r - mu
    s1 = (d ** 2).sum() / (n - 1)
    rq = np.convolve(r, np.ones(q), mode="valid")
    m = q * (n - q + 1) * (1 - q / n)
    sq = ((rq - q * mu) ** 2).sum() / m
    vr = sq / s1
    theta = 0.0
    for j in range(1, q):
        num = (d[j:] ** 2 * d[:-j] ** 2).sum()
        den = ((d ** 2).sum()) ** 2
        delta = n * num / den
        theta += (2 * (q - j) / q) ** 2 * delta
    z = (vr - 1) / np.sqrt(theta / n)
    return {"q": q, "vr": float(vr), "z": float(z), "p": float(2 * (1 - stats.norm.cdf(abs(z))))}


def moments(r: np.ndarray) -> dict:
    r = np.asarray(r, float)
    return {"n": int(len(r)), "mean": float(r.mean()), "std": float(r.std(ddof=1)),
            "skew": float(stats.skew(r)), "excess_kurtosis": float(stats.kurtosis(r)),
            "min": float(r.min()), "max": float(r.max())}
