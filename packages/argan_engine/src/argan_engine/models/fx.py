"""USD/IRR weekly log-return models.

* FXGBM      – constant drift/vol Gaussian random walk (benchmark)
* FXStudentT – constant drift/vol Student-t random walk
* FXRegime   – k-state Markov-switching mean/variance model (Hamilton 1989), fitted by ML

All models expose simulate(z, rng) where z are standard-normal scores injected by the dependence
layer (Gaussian copula); regime paths additionally use their own uniforms for state transitions.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy import stats

WEEKS_PER_YEAR = 52.0


@dataclass
class FXGBM:
    mu: float
    sigma: float
    kind: str = "gbm"

    def mean_weekly(self) -> float:
        return self.mu

    def with_drift(self, annual_log_drift: float) -> "FXGBM":
        return FXGBM(annual_log_drift / WEEKS_PER_YEAR, self.sigma)

    def with_vol_mult(self, m: float) -> "FXGBM":
        return FXGBM(self.mu, self.sigma * m)

    def simulate(self, z: np.ndarray, rng: np.random.Generator) -> tuple[np.ndarray, None]:
        return self.mu + self.sigma * z, None

    def to_dict(self) -> dict:
        return {"kind": self.kind, "mu": self.mu, "sigma": self.sigma}

    @classmethod
    def fit(cls, r: np.ndarray) -> "FXGBM":
        return cls(float(np.mean(r)), float(np.std(r, ddof=1)))


@dataclass
class FXStudentT:
    mu: float
    sigma: float          # standard deviation (not scale)
    nu: float
    kind: str = "t"

    def mean_weekly(self) -> float:
        return self.mu

    def with_drift(self, annual_log_drift: float) -> "FXStudentT":
        return FXStudentT(annual_log_drift / WEEKS_PER_YEAR, self.sigma, self.nu)

    def with_vol_mult(self, m: float) -> "FXStudentT":
        return FXStudentT(self.mu, self.sigma * m, self.nu)

    def simulate(self, z: np.ndarray, rng: np.random.Generator) -> tuple[np.ndarray, None]:
        u = np.clip(stats.norm.cdf(z), 1e-12, 1 - 1e-12)
        t = stats.t.ppf(u, self.nu) / np.sqrt(self.nu / (self.nu - 2.0))   # unit variance
        return self.mu + self.sigma * t, None

    def to_dict(self) -> dict:
        return {"kind": self.kind, "mu": self.mu, "sigma": self.sigma, "nu": self.nu}

    @classmethod
    def fit(cls, r: np.ndarray) -> "FXStudentT":
        nu, loc, scale = stats.t.fit(r)
        nu = float(np.clip(nu, 3.0, 60.0))
        sd = float(scale * np.sqrt(nu / (nu - 2.0)))
        return cls(float(loc), sd, nu)


@dataclass
class FXRegime:
    mu: np.ndarray            # (k,) weekly mean log-return per state (ordered by sigma ascending)
    sigma: np.ndarray         # (k,)
    P: np.ndarray             # (k,k) row-stochastic: P[i,j] = Pr(next=j | now=i)
    p_now: np.ndarray         # (k,) filtered state probabilities at the last observation
    kind: str = "regime"

    @property
    def k(self) -> int:
        return len(self.mu)

    def stationary(self) -> np.ndarray:
        w, v = np.linalg.eig(self.P.T)
        s = np.real(v[:, np.argmin(np.abs(w - 1))])
        s = np.abs(s)
        return s / s.sum()

    def mean_weekly(self) -> float:
        return float(self.stationary() @ self.mu)

    def with_drift(self, annual_log_drift: float) -> "FXRegime":
        shift = annual_log_drift / WEEKS_PER_YEAR - self.mean_weekly()
        return FXRegime(self.mu + shift, self.sigma, self.P, self.p_now)

    def with_vol_mult(self, m: float) -> "FXRegime":
        return FXRegime(self.mu, self.sigma * m, self.P, self.p_now)

    def filter_last(self, r: np.ndarray) -> np.ndarray:
        """Hamilton filter with fixed parameters: Pr(state | data) at the last observation."""
        p = self.stationary()
        for i, x in enumerate(np.asarray(r, float)):
            pred = p if i == 0 else p @ self.P
            lik = stats.norm.pdf(x, self.mu, self.sigma)
            post = pred * lik + 1e-300
            p = post / post.sum()
        return p

    def expected_durations(self) -> np.ndarray:
        return 1.0 / (1.0 - np.diag(self.P))

    def simulate(self, z: np.ndarray, rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
        n, w = z.shape
        cum_p = np.cumsum(self.P, axis=1)
        p1 = self.p_now @ self.P                     # state distribution for the first simulated week
        s = (rng.random(n)[:, None] > np.cumsum(p1)[None, :]).sum(1).clip(0, self.k - 1)
        states = np.empty((n, w), dtype=np.int8)
        for t in range(w):
            states[:, t] = s
            u = rng.random(n)
            s = (u[:, None] > cum_p[s]).sum(1).clip(0, self.k - 1)
        r = self.mu[states] + self.sigma[states] * z
        return r, states

    def to_dict(self) -> dict:
        return {"kind": self.kind, "mu": self.mu.tolist(), "sigma": self.sigma.tolist(),
                "P": self.P.tolist(), "p_now": self.p_now.tolist()}

    @classmethod
    def from_dict(cls, d: dict) -> "FXRegime":
        return cls(np.array(d["mu"]), np.array(d["sigma"]), np.array(d["P"]), np.array(d["p_now"]))

    @classmethod
    def fit(cls, r: np.ndarray, k: int = 2, n_starts: int = 5, seed: int = 0
            ) -> tuple["FXRegime", dict]:
        """ML fit of a Markov-switching model with switching mean and variance (statsmodels).
        Returns the model and fit info (llf, bic, smoothed probabilities)."""
        import statsmodels.api as sm
        y = pd.Series(np.asarray(r, float) * 100.0)       # percent units: better conditioning
        best = None
        for i in range(n_starts):
            np.random.seed(seed + i)
            try:
                res = sm.tsa.MarkovRegression(y, k_regimes=k, trend="c", switching_variance=True
                                              ).fit(search_reps=10, disp=False)
            except Exception:                              # pragma: no cover - rare numerical failures
                continue
            if best is None or res.llf > best.llf:
                best = res
        if best is None:
            raise RuntimeError("regime model failed to converge")
        names = list(best.params.index)
        mu = np.array([best.params[f"const[{i}]"] for i in range(k)]) / 100.0
        sig = np.sqrt(np.array([best.params[f"sigma2[{i}]"] for i in range(k)])) / 100.0
        rt = np.asarray(best.regime_transition)[:, :, 0]        # rt[i,j] = Pr(S_t=i | S_{t-1}=j)
        P = rt.T.copy()
        filt = np.asarray(best.filtered_marginal_probabilities)
        smooth = np.asarray(best.smoothed_marginal_probabilities)
        order = np.argsort(sig)
        mu, sig = mu[order], sig[order]
        P = P[np.ix_(order, order)]
        filt, smooth = filt[:, order], smooth[:, order]
        n_obs = len(y)
        llf = float(best.llf) + n_obs * np.log(100.0)      # back to decimal-return units (comparable with gbm/t)
        n_par = int(len(names))
        info = {"llf": llf, "bic": -2 * llf + n_par * np.log(n_obs), "aic": -2 * llf + 2 * n_par, "k": k,
                "n_params": n_par, "smoothed": smooth, "filtered": filt}
        return cls(mu, sig, P, filt[-1]), info


def fx_model_from_dict(d: dict):
    if d["kind"] == "regime":
        return FXRegime.from_dict(d)
    if d["kind"] == "t":
        return FXStudentT(d["mu"], d["sigma"], d["nu"])
    return FXGBM(d["mu"], d["sigma"])
