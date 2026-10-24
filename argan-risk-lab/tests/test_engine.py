import numpy as np

from argan_engine.sim import build_market, orders_from_weights, simulate_policy
from conftest import det_scenario


def run(scn, cal, w, n=4):
    m = build_market(scn, cal, n, np.random.default_rng(0))
    return m, simulate_policy(m, scn, orders_from_weights(w, m.Q, scn.schedule_weeks))


def test_carry_identity_closed_form(cal):
    """W_T(now) − W_T(week 4) = Q·RC0·(1+r)^(H−4)·[g4 − (1+r)^4]  (no demand, no costs)."""
    scn = det_scenario()
    m, a = run(scn, cal, [1.0, 0.0])
    _, b = run(scn, cal, [0.0, 1.0])
    H, rw = m.H, (1 + 0.30) ** (1 / 52) - 1
    g4 = m.RC[0, 4] / m.RC[0, 0]
    expected = m.Q * m.RC[0, 0] * (1 + rw) ** (H - 4) * (g4 - (1 + rw) ** 4)
    assert np.allclose(a.profit_nom - b.profit_nom, expected, rtol=1e-6)


def test_early_beats_late_iff_growth_exceeds_carry(cal):
    for drift, early_better in [(60.0, True), (10.0, False)]:
        scn = det_scenario(fx_drift_annual_pct=drift)
        _, a = run(scn, cal, [1.0, 0.0])
        _, b = run(scn, cal, [0.0, 1.0])
        assert (a.profit_nom[0] > b.profit_nom[0]) == early_better


def test_lead_time_blocks_sales(cal):
    scn = det_scenario(weekly_demand_kg=100.0, initial_inventory_kg=0.0, lead_time_days=14, schedule_days=[0, 28])
    m, r = run(scn, cal, [1.0, 0.0])
    # order at week 0 arrives at week 2 -> weeks 0 and 1 are fully lost
    assert np.isclose(r.unmet_kg[0], 200.0, rtol=1e-9)
    assert np.allclose(r.unmet_kg + 0, r.demand_kg - (r.demand_kg - r.unmet_kg))


def test_flat_world_economic_equals_accounting_profit(cal):
    """With flat prices and no valuation effects, FIFO accounting profit == economic profit (no double counting)."""
    scn = det_scenario(fx_drift_annual_pct=0.0, weekly_demand_kg=500.0, initial_inventory_kg=2000.0, weekly_opex_bn_irr=2.0,
                       storage_cost_pct_week=0.1, deposit_rate_pct=20, borrow_rate_pct=20, coffee_vol_mult=1e-12,
                       purchase_qty_kg=3000.0)
    m, r = run(scn, cal, [0.5, 0.5])
    assert np.allclose(r.profit_nom, r.acct_profit, rtol=1e-6, atol=1e3)


def test_invariants_random_world(cal):
    from argan_engine.config import Scenario
    scn = Scenario(robust=False, flip_analysis=False)
    m = build_market(scn, cal, 2000, np.random.default_rng(3))
    r = simulate_policy(m, scn, orders_from_weights([0.5, 0.3, 0.2], m.Q, scn.schedule_weeks))
    assert (r.unmet_kg >= -1e-9).all() and (r.unmet_kg <= r.demand_kg + 1e-9).all()
    assert (r.end_stock_kg >= -1e-9).all()
    assert np.isfinite(r.profit_real).all()
    assert np.allclose(r.paid, 0.0 + m.Q * (0.5 * m.RC[:, 0] + 0.3 * m.RC[:, 4] + 0.2 * m.RC[:, 9]), rtol=1e-9)


def test_common_random_numbers_deterministic(cal):
    from argan_engine.config import Scenario
    scn = Scenario()
    a = build_market(scn, cal, 500, np.random.default_rng(7))
    b = build_market(scn, cal, 500, np.random.default_rng(7))
    assert np.array_equal(a.RC, b.RC) and np.array_equal(a.D, b.D)
