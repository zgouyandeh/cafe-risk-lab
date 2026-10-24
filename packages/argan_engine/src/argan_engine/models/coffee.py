"""Arabica weekly log-return model: filtered/empirical historical simulation, mean-corrected so the
futures price is a martingale (E[P_T] = P_0, no risk premium, roll yield ignored).

Why not GARCH: on weekly data the ARCH-LM test does not reject constant variance
(see Calibration.coffee['arch_lm']); the engine therefore uses constant weekly volatility with a
user-controlled multiplier, and the diagnostics are shown in the expert UI."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import stats


@dataclass
class CoffeeModel:
    std_resid: np.ndarray       # sorted, standardised (mean 0, sd 1) weekly log-returns
    sigma_week: float           # weekly sd of log returns

    @classmethod
    def fit(cls, r: np.ndarray) -> "CoffeeModel":
        r = np.asarray(r, float)
        sigma = float(r.std(ddof=1))
        e = np.sort((r - r.mean()) / sigma)
        return cls(std_resid=e, sigma_week=sigma)

    def _kappa(self, s: float) -> float:
        return float(np.log(np.mean(np.exp(s * self.std_resid))))

    def log_returns(self, z: np.ndarray, vol_mult: float = 1.0) -> np.ndarray:
        """z: standard-normal scores (dependence is injected through them, i.e. a Gaussian copula)."""
        s = self.sigma_week * vol_mult
        n = len(self.std_resid)
        u = stats.norm.cdf(z)
        grid = (np.arange(n) + 0.5) / n
        e = np.interp(u, grid, self.std_resid)
        return s * e - self._kappa(s)

    def to_dict(self) -> dict:
        return {"std_resid": self.std_resid.tolist(), "sigma_week": self.sigma_week}

    @classmethod
    def from_dict(cls, d: dict) -> "CoffeeModel":
        return cls(np.asarray(d["std_resid"]), float(d["sigma_week"]))
