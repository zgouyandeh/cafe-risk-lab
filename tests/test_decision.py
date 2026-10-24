"""Shapley attribution, accounting identity with shrink / lost shipments, break-even beliefs, decision map."""
import numpy as np
import pytest

from argan_engine.calibrate import get_calibration
from argan_engine.config import Scenario
from argan_engine.risk import decision_map as dmap
from argan_engine.risk.shapley import shapley
from argan_engine.sim import apply_shock, build_market, orders_from_weights, simulate_policy


# ---------------------------------------------------------------- Shapley
def _game(S):
    base = {"a": 3.0, "b": 1.0, "c": 0.0}
    v = sum(base[p] for p in S)
    return v + (2.0 if {"a", "b"} <= set(S) else 0.0)           # a and b interact; c is a null player


def test_shapley_efficiency_null_symmetry():
    r = shapley(["a", "b", "c"], lambda S: _game(S))
    assert abs(r["efficiency_gap"]) < 1e-12 and abs(r["total"] - 6.0) < 1e-12
    assert abs(r["phi"]["c"]) < 1e-12                           # null player
    assert abs(r["phi"]["a"] - 4.0) < 1e-12 and abs(r["phi"]["b"] - 2.0) < 1e-12   # 3 + 2/2 and 1 + 2/2
    sym = shapley(["x", "y"], lambda S: 5.0 * len(S) ** 2)      # identical players
    assert abs(sym["phi"]["x"] - sym["phi"]["y"]) < 1e-12


# ---------------------------------------------------------------- accounting identity
@pytest.fixture(scope="module")
def cal():
    return get_calibration()


@pytest.mark.parametrize("upd", [
    {},
    dict(import_delay_prob_pct=40, import_delay_days=42, import_loss_prob_pct=60, shrink_pct_week=0.5),
    dict(pipeline_weeks=[2], pipeline_kg=[800.0], initial_receivables_bn_irr=30.0, terminal_haircut_pct=5.0, storage_cost_pct_week=0.3),
])
def test_wealth_change_identity(cal, upd):
    s = Scenario(n_paths=1500, **upd)
    m = build_market(s, cal, 1500, np.random.default_rng(5))
    r = simulate_policy(m, s, [(0, 1500.0), (4, 1500.0)])
    rhs = r.acct_profit - r.shrink_cost - r.lost_cost + r.holding_gain
    assert np.abs(r.profit_nom - rhs).max() < 1e-6 * np.abs(r.profit_nom).mean() + 1.0


def test_identity_holds_under_shock_and_loss(cal):
    s = Scenario(n_paths=1000)
    m = build_market(s, cal, 1000, np.random.default_rng(6))
    m2 = apply_shock(m, s, fx=0.4, coffee=0.2, delay_weeks=4, loss_share=0.5)
    r = simulate_policy(m2, s, [(0, 1000.0), (4, 2000.0)])
    assert np.abs(r.profit_nom - (r.acct_profit - r.shrink_cost - r.lost_cost + r.holding_gain)).max() < 1.0


# ---------------------------------------------------------------- lost shipments
def test_lost_shipment_loses_prepayment_and_creates_shortage(cal):
    s = Scenario(n_paths=800, initial_inventory_kg=500.0)
    m = build_market(s, cal, 800, np.random.default_rng(8))
    ok = simulate_policy(m, s, [(0, 3000.0)])
    lost = simulate_policy(apply_shock(m, s, loss_share=1.0), s, [(0, 3000.0)])
    assert np.allclose(ok.paid, lost.paid)                       # the money is still paid
    assert (lost.lost_cost > 0).all() and (lost.unmet_kg.mean() > ok.unmet_kg.mean())
    assert lost.profit_real.mean() < ok.profit_real.mean()


def test_loss_belief_does_not_disturb_other_random_streams(cal):
    a = build_market(Scenario(), cal, 500, np.random.default_rng(3))
    b = build_market(Scenario(import_delay_prob_pct=30, import_delay_days=28, import_loss_prob_pct=0.0), cal, 500, np.random.default_rng(3))
    c = build_market(Scenario(import_delay_prob_pct=30, import_delay_days=28, import_loss_prob_pct=50.0), cal, 500, np.random.default_rng(3))
    assert np.allclose(a.RC, b.RC) and np.allclose(b.RC, c.RC) and b.lost_w is None and c.lost_w.any()
    assert not c.lost_w[c.delay_w == 0].any()                    # only delayed shipments can be lost


# ---------------------------------------------------------------- break-even and map
def test_break_even_is_a_root_and_map_shape(cal):
    s = Scenario()
    W = np.array([[1.0, 0.0, 0.0], [0.0, 0.5, 0.5], [1 / 3, 1 / 3, 1 / 3], [0.0, 0.0, 1.0]])
    bench = {"recommended": 1, "all_now": 0, "equal_split": 2, "all_late": 3}
    plans = dmap._plans(W, bench)
    b = dmap.break_even(s, cal, plans, "fx_drift_annual_pct", -20.0, 150.0, 40.0, "x", "u")
    if b["status"] == "crossing":
        e = dmap._eval(s.model_copy(update={"fx_drift_annual_pct": b["root"]}), cal, plans)
        assert abs(e["all_now"]["J"] - e["recommended"]["J"]) < 0.1
    mp = dmap.decision_map(s, cal, plans, "fx_drift_annual_pct", [0.0, 80.0], "event_p_escalation", [0.0, 50.0])
    assert np.array(mp["winner"]).shape == (2, 2) and np.array(mp["now_minus_rec_pct"]).shape == (2, 2)
