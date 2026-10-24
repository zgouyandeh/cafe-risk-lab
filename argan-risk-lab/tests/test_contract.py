"""Purchase contract: prepayment / settlement on delivery, unpaid balance at the horizon, fixed-quantity vs fixed-USD budget,
permanent non-delivery, wealth identity."""
import numpy as np
import pytest

from argan_engine.config import Scenario
from argan_engine.sim import apply_shock, build_market, simulate_policy
from conftest import det_scenario


def _run(cal, orders, n=200, **kw):
    s = det_scenario(**kw)
    m = build_market(s, cal, n, np.random.default_rng(1))
    return s, m, simulate_policy(m, s, orders)


def test_prepay_100_is_the_old_behaviour(cal):
    s, m, r = _run(cal, [(0, 1000.0)])
    assert np.allclose(r.paid, 1000.0 * m.RC[:, 0]) and np.allclose(r.paid_order, r.paid) and np.allclose(r.paid_arrival, 0)


def test_prepay_zero_pays_nothing_until_delivery(cal):
    s, m, r = _run(cal, [(0, 1000.0)], prepay_fraction_pct=0.0)
    assert np.allclose(r.paid_order, 0)
    L = s.lead_weeks
    # the whole invoice is settled at the arrival-week rate, USD price fixed at the order date
    assert np.allclose(r.paid_arrival, 1000.0 * m.P[:, 0] * m.X[:, L])


def test_balance_settled_on_arrival_before_horizon(cal):
    s, m, r = _run(cal, [(0, 1000.0)], prepay_fraction_pct=30.0)
    L = s.lead_weeks
    assert np.allclose(r.paid_order, 0.3 * 1000.0 * m.P[:, 0] * m.X[:, 0])
    assert np.allclose(r.paid_arrival, 0.7 * 1000.0 * m.P[:, 0] * m.X[:, L])
    assert np.allclose(r.ap_end, 0)


def test_arrival_after_horizon_leaves_unpaid_balance_in_wealth(cal):
    s, m, r = _run(cal, [(12, 1000.0)], prepay_fraction_pct=30.0, lead_time_days=28)     # arrives after week 13
    H = m.H
    assert np.allclose(r.paid_arrival, 0)
    assert np.allclose(r.ap_end, 0.7 * 1000.0 * m.P[:, 12] * m.X[:, H])
    # wealth = cash + stock in transit at replacement cost - unpaid balance
    assert np.abs(r.profit_nom - (r.acct_profit - r.shrink_cost - r.lost_cost + r.holding_gain)).max() < 1.0


def test_permanent_non_delivery(cal):
    s = det_scenario(prepay_fraction_pct=30.0, initial_inventory_kg=100.0, weekly_demand_kg=50.0)
    m = build_market(s, cal, 100, np.random.default_rng(2))
    ok = simulate_policy(m, s, [(0, 1000.0)])
    bad = simulate_policy(apply_shock(m, s, delay_weeks=2, loss_share=1.0), s, [(0, 1000.0)])
    assert np.allclose(bad.paid_arrival, 0) and np.allclose(bad.ap_end, 0)             # the balance is never paid
    assert np.allclose(bad.lost_cost, 0.3 * 1000.0 * m.P[:, 0] * m.X[:, 0])           # prepayment is a loss
    assert np.allclose(bad.end_stock_kg, 0.0) and ok.end_stock_kg.min() > 0           # lost goods are neither in stock nor in transit
    assert (bad.unmet_kg > ok.unmet_kg).all()
    assert np.abs(bad.profit_nom - (bad.acct_profit - bad.shrink_cost - bad.lost_cost + bad.holding_gain)).max() < 1.0


def test_fixed_quantity_vs_fixed_usd(cal):
    s = Scenario(n_paths=500, purchase_mode="fixed_quantity")
    m = build_market(s, cal, 500, np.random.default_rng(3))
    kg = 2000.0
    land = 1 + s.landing_cost_pct / 100
    s2 = s.model_copy(update={"purchase_mode": "fixed_usd_budget"})
    fq, fu = simulate_policy(m, s, [(0, kg)]), simulate_policy(m, s2, [(0, kg)])
    assert np.allclose(fq.paid, kg * m.P[:, 0] * m.X[:, 0] * land)                       # fixed kg: rial paid follows the price
    assert np.allclose(fu.paid, kg * m.meta["P_ref_usd_kg"] * m.X[:, 0] * land)           # fixed USD: only the exchange rate moves it
    assert fq.paid.std() > fu.paid.std() * 0.99 and abs(fq.paid.mean() / fu.paid.mean() - 1) < 0.05


@pytest.mark.parametrize("alpha", [100.0, 50.0, 0.0])
def test_wealth_identity_with_prepay(cal, alpha):
    s = Scenario(n_paths=800, prepay_fraction_pct=alpha, import_delay_prob_pct=30, import_delay_days=42, import_loss_prob_pct=40,
                 purchase_mode="fixed_usd_budget")
    m = build_market(s, cal, 800, np.random.default_rng(9))
    r = simulate_policy(m, s, [(0, 1500.0), (4, 1500.0), (8, 1000.0)])
    assert np.abs(r.profit_nom - (r.acct_profit - r.shrink_cost - r.lost_cost + r.holding_gain)).max() < 1e-6 * np.abs(r.profit_nom).mean() + 1.0
