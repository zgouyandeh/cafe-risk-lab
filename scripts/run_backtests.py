"""Run all backtests and store JSON in artifacts/ (used by the API and the expert UI)."""
import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from argan_engine.backtest import coffee_var, fx_forecast, policy_replay
from argan_engine.calibrate import CACHE, DEFAULT_COFFEE, DEFAULT_FX, get_calibration
from argan_engine.config import Scenario
from argan_engine.data import load_coffee, load_fx, weekly_returns

warnings.filterwarnings("ignore")
ART = Path(CACHE).parent

fx, _ = load_fx(DEFAULT_FX)
cdf, _ = load_coffee(DEFAULT_COFFEE)
liq = cdf.loc[cdf["liquid"], "Close"]
wc, rc = weekly_returns(liq)
wf, rf = weekly_returns(fx)

print("coffee VaR ..."); (ART / "backtest_coffee.json").write_text(json.dumps(coffee_var.run(rc.values)), encoding="utf-8")
print("FX forecast ..."); fxr = fx_forecast.run(rf.values); (ART / "backtest_fx.json").write_text(json.dumps(fxr), encoding="utf-8")
print("selected FX model:", fxr["selected"])
print("policy replay ...")
rep = policy_replay.run({}, Scenario(), wc, wf); (ART / "backtest_replay.json").write_text(json.dumps(rep), encoding="utf-8")
get_calibration(refresh=True)
print(json.dumps({k: v for k, v in fxr["models"].items()}, indent=1)[:1500])
print(json.dumps(fxr["dm_vs_selected"], indent=1))
print(json.dumps(rep, indent=1)[:2500])
print(json.dumps(json.loads((ART / "backtest_coffee.json").read_text(encoding="utf-8")), indent=1)[:1800])
