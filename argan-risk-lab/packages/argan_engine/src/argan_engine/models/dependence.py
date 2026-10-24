"""Gaussian-copula dependence between coffee, FX and demand shocks."""
from __future__ import annotations

import numpy as np


def kendall_to_pearson(tau: float) -> float:
    """For elliptical copulas ρ = sin(π τ / 2) (Lindskog, McNeil & Schmock 2003)."""
    return float(np.sin(np.pi * tau / 2.0))


def nearest_psd_corr(C: np.ndarray, eps: float = 1e-8) -> np.ndarray:
    w, v = np.linalg.eigh((C + C.T) / 2)
    w = np.clip(w, eps, None)
    A = v @ np.diag(w) @ v.T
    d = np.sqrt(np.diag(A))
    return A / np.outer(d, d)


def correlated_normals(n: int, w: int, rho_cf: float, rho_fd: float, rho_cd: float,
                       rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return (z_coffee, z_fx, z_demand), each (n, w), with the given pairwise correlations."""
    C = np.array([[1, rho_cf, rho_cd], [rho_cf, 1, rho_fd], [rho_cd, rho_fd, 1]], float)
    C = nearest_psd_corr(C)
    L = np.linalg.cholesky(C)
    g = rng.standard_normal((3, n, w))
    z = np.tensordot(L, g, axes=(1, 0))
    return z[0], z[1], z[2]
