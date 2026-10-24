import numpy as np

from argan_engine.optimize import convergence, run_worlds, weight_grid
from argan_engine.risk import STRESSES, stress_params
from argan_engine.risk.reverse_stress import reverse_stress
from argan_engine.sim import apply_shock, build_market, orders_from_weights, simulate_policy, subset
from conftest import det_scenario


def _mk(cal, **kw):
    scn = det_scenario(**kw)
    return scn, build_market(scn, cal, 50, np.random.default_rng(1))


def test_zero_shock_is_identity(cal):
    scn, m = _mk(cal, weekly_demand_kg=500.0, demand_price_elasticity=0.3, demand_cv=0.2, initial_inventory_kg=2000.0)
    m2 = apply_shock(m, scn)
    assert np.allclose(m2.RC, m.RC) and np.allclose(m2.S, m.S) and np.allclose(m2.D, m.D)


def test_fx_shock_scales_cost_exactly(cal):
    scn, m = _mk(cal)
    m2 = apply_shock(m, scn, fx=0.5)
    assert np.allclose(m2.RC[:, 0], m.RC[:, 0]) and np.allclose(m2.RC[:, 1:], m.RC[:, 1:] * 1.5)


def test_import_delay_moves_arrival_and_creates_unmet(cal):
    scn, m = _mk(cal, weekly_demand_kg=500.0, initial_inventory_kg=1000.0, schedule_days=[0], lead_time_days=14)
    orders = [(0, 5000.0)]
    base = simulate_policy(m, scn, orders)
    late = simulate_policy(apply_shock(m, scn, delay_weeks=6), scn, orders)
    assert late.unmet_kg.mean() > base.unmet_kg.mean() + 100          # stock-out while the shipment is late
    assert late.min_stock_kg.mean() <= base.min_stock_kg.mean()
    # goods still in transit at the horizon are counted in terminal wealth (no free disappearance)
    very_late = simulate_policy(apply_shock(m, scn, delay_weeks=60), scn, orders)
    assert np.allclose(very_late.end_stock_kg, 5000.0 + 0.0, atol=1e-6) or very_late.end_stock_kg.mean() >= 5000.0 - 1e-6


def test_all_stresses_resolve(cal):
    scn = det_scenario()
    for s in STRESSES:
        sp = stress_params(s, scn)
        assert "shock" in sp and sp["scn"] is not None
    sp = stress_params(next(s for s in STRESSES if s["id"] == "severe_crisis"), scn)
    assert sp["scn"].receivable_lag_weeks == scn.receivable_lag_weeks + 2 and sp["shock"]["delay_weeks"] == scn.delay_weeks


def test_reverse_stress_monotone_in_delay(cal):
    scn = det_scenario(weekly_demand_kg=500.0, initial_inventory_kg=1000.0, purchase_budget_usd=50_000, schedule_days=[0, 28])
    m = build_market(scn, cal, 40, np.random.default_rng(2))
    W = weight_grid(2, 0.5)
    r = reverse_stress(m, scn, cal, W, {"rec": 0})
    cells = {(c["fx"], c["coffee"], c["delay_weeks"]): c["rec"]["unmet"] for c in r["cells"]}
    for dw0, dw1 in zip(r["delay_grid"], r["delay_grid"][1:]):
        assert cells[(0.0, 0.0, dw1)] >= cells[(0.0, 0.0, dw0)] - 1e-9     # later shipment never reduces shortage
    assert r["units"]["fx"] > 0


def test_convergence_reports_stability(cal):
    scn = det_scenario(robust=True, n_worlds=12, paths_per_world=200, demand_cv=0.2)
    W = weight_grid(2, 0.25)
    wr = run_worlds(scn, cal, W)
    c = convergence(wr, scn, W, reps=8)
    assert c["n_full"] == 12 and all(0 <= r["close"] <= 1 for r in c["rows"])
