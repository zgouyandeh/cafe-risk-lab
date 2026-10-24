"""Synthetic-company pipeline: parameter recovery, data-quality handling, engine integration."""
import numpy as np
import pytest

from argan_engine.company import clean, estimate_all, recovery_table, to_overrides
from argan_engine.company.synth import generate
from argan_engine.config import Scenario


@pytest.fixture(scope="module")
def world():
    tab, truth = generate()
    T, rep = clean(tab)
    est = estimate_all(T)
    return tab, truth, T, rep, est


def test_shapes_and_labels(world):
    tab, truth, *_ = world
    assert tab["market_weekly"].shape[0] == 255 and len(tab) == 11
    assert "SYNTHETIC" in truth["description"]


def test_data_quality_detects_injected(world):
    *_, rep, _ = world
    kinds = {i["type"] for i in rep["issues"]}
    assert {"duplicate_rows", "missing", "outlier", "invalid_fx_paid"} <= kinds
    assert rep["annual_reconciliation_max_rel_diff"] < 1e-6


def test_parameter_recovery(world):
    tab, truth, T, rep, est = world
    rt = recovery_table(est, truth)
    bad = [r["key"] for r in rt if not r["ok"]]
    assert not bad, bad


def test_seasonal_index_recovered(world):
    *_, truth, T, rep, est = (world[1], *world[2:])
    s = np.array(est["seasonal_index"]["value"]); t = np.array(truth["seasonal_index"])
    assert abs(s.mean() - 1) < 1e-9 and np.abs(s - t).max() < 0.2


def test_receivable_weights_nonneg_sum_one(world):
    w = np.array(world[4]["receivable_lag_weeks"]["weights"])
    assert (w >= 0).all() and abs(w.sum() - 1) < 1e-3


def test_overrides_build_valid_scenario(world):
    ov = to_overrides(world[4])
    s = Scenario(**ov["fields"], param_se=ov["param_se"])
    assert len(s.demand_seasonal_index) == 52 and s.initial_receivables_bn_irr > 0 and s.schedule_days == [0, 14, 28, 42]


def test_opening_receivables_raise_early_cash():
    import numpy as np
    from argan_engine.calibrate import get_calibration
    from argan_engine.sim import build_market
    from argan_engine.sim.engine import simulate_policy
    a = Scenario(n_paths=300); b = a.model_copy(update=dict(initial_receivables_bn_irr=100.0))
    m = build_market(a, get_calibration(), 300, np.random.default_rng(0))
    ra = simulate_policy(m, a, [(0, 1000.0)], trace=True); rb = simulate_policy(m, b, [(0, 1000.0)], trace=True)
    assert rb.trace_cash[:, 3].mean() > ra.trace_cash[:, 3].mean() + 90e9
