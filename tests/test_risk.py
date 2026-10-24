import numpy as np
from scipy import stats

from argan_engine.backtest.scores import christoffersen_ind, crps_samples, diebold_mariano, kupiec_pof
from argan_engine.optimize import pareto_front, weight_grid
from argan_engine.risk import cvar_lower, ssd_relation, var_lower


def test_cvar_exact_small_sample():
    assert cvar_lower(np.arange(1, 21), 0.9) == 1.5          # worst 10% of 20 = {1,2}
    assert abs(cvar_lower(np.arange(1, 11), 0.85) - (1 + 0.5 * 2) / 1.5) < 1e-9   # k=1.5: weights 1 and 0.5


def test_cvar_normal_closed_form():
    x = np.random.default_rng(0).standard_normal(1_000_000)
    exact = -stats.norm.pdf(stats.norm.ppf(0.05)) / 0.05
    assert abs(cvar_lower(x, 0.95) - exact) < 0.02
    assert abs(var_lower(x, 0.95) - stats.norm.ppf(0.05)) < 0.01


def test_ssd_shift_and_spread():
    rng = np.random.default_rng(1)
    a = rng.normal(0, 1, 20000)
    assert ssd_relation(a + 0.5, a) == "A"
    spread = a + rng.normal(0, 0.8, 20000)                 # mean-preserving spread
    assert ssd_relation(a, spread) == "A"


def test_kupiec_and_independence():
    k = kupiec_pof(5, 100, 0.05)
    assert abs(k["lr"]) < 1e-9 and abs(k["p"] - 1) < 1e-9
    assert kupiec_pof(20, 100, 0.05)["p"] < 0.001
    clustered = np.array([1, 1, 1, 1, 1] + [0] * 95)
    assert christoffersen_ind(clustered)["p"] < 0.05


def test_crps_properties():
    rng = np.random.default_rng(0)
    sharp = rng.normal(0, 1, 4000)
    assert crps_samples(sharp, 0.0) < crps_samples(sharp, 3.0)
    # Gaussian closed form: CRPS(N(0,1), 0) = (sqrt(2)-1)/sqrt(pi)
    assert abs(crps_samples(sharp, 0.0) - (np.sqrt(2) - 1) / np.sqrt(np.pi)) < 0.02


def test_diebold_mariano_detects_difference():
    rng = np.random.default_rng(0)
    l1 = rng.normal(1.0, 0.2, 300)
    l2 = l1 + 0.3 + rng.normal(0, 0.1, 300)
    assert diebold_mariano(l1, l2, 1)["p"] < 0.01 and diebold_mariano(l1, l1 + rng.normal(0, 0.1, 300), 1)["p"] > 0.01


def test_grid_and_pareto():
    W = weight_grid(3, 0.1)
    assert W.shape[0] == 67 and np.allclose(W.sum(1), 1) and (W >= 0).all()
    m, c = np.array([1.0, 2.0, 3.0, 2.5]), np.array([3.0, 2.0, 1.0, 0.5])
    assert pareto_front(m, c).tolist() == [0, 1, 2]
