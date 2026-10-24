import numpy as np
import pytest

from argan_engine.calibrate import get_calibration
from argan_engine.config import Scenario


@pytest.fixture(scope="session")
def cal():
    return get_calibration()


def det_scenario(**kw) -> Scenario:
    """Deterministic world: no randomness in prices/demand, so results can be checked in closed form."""
    base = dict(fx_model="gbm", fx_vol_mult=1e-9, coffee_vol_mult=1e-9, demand_cv=0.0, demand_price_elasticity=0.0,
                coffee_spot_c_lb=300.0, fx_spot_irr=2_000_000.0, fx_drift_annual_pct=40.0, event_p_escalation=0,
                event_p_deal=0, initial_inventory_kg=0.0, weekly_demand_kg=1e-6, weekly_opex_bn_irr=0.0,
                storage_cost_pct_week=0.0, shrink_pct_week=0.0, receivable_lag_weeks=0, initial_cash_bn_irr=1000.0,
                deposit_rate_pct=30.0, borrow_rate_pct=30.0, inflation_pct=0.0, landing_cost_pct=0.0,
                schedule_days=[0, 28], lead_time_days=14, horizon_days=91, robust=False, flip_analysis=False)
    base.update(kw)
    return Scenario(**base)
