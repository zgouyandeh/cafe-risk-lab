import numpy as np

from argan_engine.models import FXRegime
from argan_engine.sim import build_market
from conftest import det_scenario
from argan_engine.config import Scenario


def test_regime_parameter_recovery():
    """Simulate from known parameters, refit, and recover them (parameter-recovery test)."""
    true = FXRegime(np.array([0.004, 0.015]), np.array([0.02, 0.065]), np.array([[0.9, 0.1], [0.35, 0.65]]),
                    np.array([1.0, 0.0]))
    rng = np.random.default_rng(11)
    z = rng.standard_normal((1, 2500))
    r = true.simulate(z, rng)[0][0]
    fit, _ = FXRegime.fit(r, k=2, n_starts=4)
    assert np.allclose(fit.sigma, true.sigma, rtol=0.2)
    assert abs(fit.P[0, 0] - 0.9) < 0.06 and abs(fit.P[1, 1] - 0.65) < 0.15
    assert fit.mu[1] > fit.mu[0] - 0.005


def test_coffee_is_martingale(cal):
    scn = Scenario(coffee_spot_c_lb=300.0, robust=False, flip_analysis=False)
    m = build_market(scn, cal, 60000, np.random.default_rng(1))
    ratio = m.P[:, -1] / m.P[:, 0]
    se = ratio.std() / np.sqrt(len(ratio))
    assert abs(ratio.mean() - 1) < 4 * se + 1e-3


def test_fx_drift_override_hits_target(cal):
    for kind in ("regime", "t", "gbm"):
        scn = Scenario(fx_model=kind, fx_drift_annual_pct=30.0, robust=False, flip_analysis=False)
        m = build_market(scn, cal, 40000, np.random.default_rng(2))
        lg = np.log(m.X[:, -1] / m.X[:, 0])
        target = 0.30 * m.H / 52
        assert abs(lg.mean() - target) < 4 * lg.std() / np.sqrt(len(lg)) + 1e-3, kind


def test_events_move_distribution(cal):
    base = Scenario(fx_drift_annual_pct=0.0, robust=False, flip_analysis=False)
    up = base.model_copy(update={"event_p_escalation": 50.0})
    dn = base.model_copy(update={"event_p_deal": 50.0})
    mb, mu, md = (build_market(s, cal, 20000, np.random.default_rng(5)) for s in (base, up, dn))
    f = lambda m: np.log(m.X[:, -1] / m.X[:, 0]).mean()
    assert f(mu) > f(mb) + 0.01 and f(md) < f(mb) - 0.01
