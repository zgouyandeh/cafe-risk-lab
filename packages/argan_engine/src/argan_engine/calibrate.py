"""Calibration: raw files -> a JSON-serialisable Calibration holding every fitted object."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from .data import cents_lb_to_usd_kg, load_coffee, load_fx, weekly_returns
from .models import CoffeeModel, FXGBM, FXRegime, FXStudentT, kendall_to_pearson
from .models.diagnostics import arch_lm, ljung_box, moments, variance_ratio
from .models.fx import fx_model_from_dict

REPO = Path(__file__).resolve().parents[4]
DEFAULT_COFFEE = REPO / "data" / "raw" / "arabica_futures.csv"
DEFAULT_FX = REPO / "data" / "raw" / "usd_irr_tgju.xlsx"
CACHE = REPO / "artifacts" / "calibration.json"


@dataclass
class Calibration:
    as_of: str
    coffee_last_date: str
    coffee_last_c_lb: float
    coffee_gap_weeks: float
    fx_last: float
    coffee_model: CoffeeModel
    fx_models: dict                 # kind -> model object
    fx_selected: str                # kind chosen for 'auto'
    rho_cf: float
    event_up: np.ndarray            # empirical positive weekly FX jumps (top decile)
    event_down: np.ndarray          # empirical negative weekly FX jumps (bottom decile)
    report: dict                    # diagnostics for the expert UI
    series: dict                    # chart series

    # ---- (de)serialisation ----
    def to_dict(self) -> dict:
        return {"as_of": self.as_of, "coffee_last_date": self.coffee_last_date,
                "coffee_last_c_lb": self.coffee_last_c_lb, "coffee_gap_weeks": self.coffee_gap_weeks,
                "fx_last": self.fx_last, "coffee_model": self.coffee_model.to_dict(),
                "fx_models": {k: m.to_dict() for k, m in self.fx_models.items()},
                "fx_selected": self.fx_selected, "rho_cf": self.rho_cf,
                "event_up": self.event_up.tolist(), "event_down": self.event_down.tolist(),
                "report": self.report, "series": self.series}

    @classmethod
    def from_dict(cls, d: dict) -> "Calibration":
        return cls(d["as_of"], d["coffee_last_date"], d["coffee_last_c_lb"], d["coffee_gap_weeks"], d["fx_last"],
                   CoffeeModel.from_dict(d["coffee_model"]),
                   {k: fx_model_from_dict(v) for k, v in d["fx_models"].items()}, d["fx_selected"],
                   d["rho_cf"], np.array(d["event_up"]), np.array(d["event_down"]), d["report"], d["series"])

    def save(self, path: Path = CACHE) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), ensure_ascii=False), encoding="utf-8")

    @classmethod
    def load(cls, path: Path = CACHE) -> "Calibration":
        return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))


def _sanitize(o):
    if isinstance(o, dict):
        return {k: _sanitize(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_sanitize(v) for v in o]
    if isinstance(o, (np.floating, np.integer)):
        o = o.item()
    if isinstance(o, float) and not np.isfinite(o):
        return None
    if isinstance(o, np.ndarray):
        return o.tolist()
    return o


def calibrate(coffee_path: Path | str = DEFAULT_COFFEE, fx_path: Path | str = DEFAULT_FX,
              fx_selected: str | None = None) -> Calibration:
    fx, fxq = load_fx(fx_path)
    cdf, cq = load_coffee(coffee_path)
    liq = cdf.loc[cdf["liquid"], "Close"]

    wc, rc = weekly_returns(liq)
    wf, rf = weekly_returns(fx)
    as_of = fx.index[-1]
    last_c_date = liq.index[-1]
    gap_weeks = float((as_of - last_c_date).days / 7.0)

    # ---- coffee ---------------------------------------------------------------------------
    cm = CoffeeModel.fit(rc.values)
    coffee_rep = {
        "moments": moments(rc.values),
        "annual_vol": float(rc.std() * np.sqrt(52)),
        "arch_lm": arch_lm(rc.values),
        "ljung_box_returns": ljung_box(rc.values),
        "ljung_box_squared": ljung_box(rc.values, squared=True),
        "variance_ratio": [variance_ratio(rc.values, q) for q in (2, 4, 13)],
        "vol_by_year": {int(y): float(g.std() * np.sqrt(52)) for y, g in rc.groupby(rc.index.year) if len(g) > 20},
        "model": "historical simulation of weekly log-returns (constant vol), martingale-corrected",
        "quality": cq.notes, "quality_stats": cq.stats,
    }

    # ---- FX --------------------------------------------------------------------------------
    r = rf.values
    gbm, tm = FXGBM.fit(r), FXStudentT.fit(r)
    reg2, info2 = FXRegime.fit(r, k=2)
    reg3, info3 = FXRegime.fit(r, k=3, n_starts=4)
    ll_gbm = float(stats.norm.logpdf(r, gbm.mu, gbm.sigma).sum())
    scale_t = tm.sigma / np.sqrt(tm.nu / (tm.nu - 2))
    ll_t = float(stats.t.logpdf(r, tm.nu, tm.mu, scale_t).sum())
    n = len(r)
    fx_rep = {
        "moments": moments(r),
        "annual_drift_log": float(r.mean() * 52), "annual_vol": float(r.std(ddof=1) * np.sqrt(52)),
        "arch_lm": arch_lm(r), "ljung_box_returns": ljung_box(r), "ljung_box_squared": ljung_box(r, squared=True),
        "fits": {
            "gbm": {"llf": ll_gbm, "bic": -2 * ll_gbm + 2 * np.log(n), "params": gbm.to_dict()},
            "t": {"llf": ll_t, "bic": -2 * ll_t + 3 * np.log(n), "params": tm.to_dict()},
            "regime2": {"llf": info2["llf"], "bic": info2["bic"], "params": reg2.to_dict(),
                        "durations_weeks": reg2.expected_durations().tolist(),
                        "stationary": reg2.stationary().tolist(),
                        "stationary_mean_annual": reg2.mean_weekly() * 52},
            "regime3": {"llf": info3["llf"], "bic": info3["bic"], "params": reg3.to_dict()},
        },
        "quality": fxq.notes, "quality_stats": fxq.stats,
    }

    # ---- dependence ----------------------------------------------------------------------
    j = pd.concat([rc, rf], axis=1, keys=["c", "f"]).dropna()
    tau = float(stats.kendalltau(j["c"], j["f"])[0]) if len(j) > 10 else 0.0
    rho = kendall_to_pearson(tau)
    dep_rep = {"n_overlap": int(len(j)), "kendall_tau": tau, "rho_gaussian_copula": rho,
               "spearman": float(stats.spearmanr(j["c"], j["f"])[0]) if len(j) > 10 else 0.0}

    # ---- empirical jump tails for event overlay --------------------------------------------
    up = r[r >= np.quantile(r, 0.90)]
    down = r[r <= np.quantile(r, 0.10)]
    up, down = up[up > 0], down[down < 0]

    models = {"gbm": gbm, "t": tm, "regime": reg2}
    series = {
        "fx_weekly": {"dates": [d.strftime("%Y-%m-%d") for d in wf.dropna().index], "values": [float(v) for v in wf.dropna().values]},
        "coffee_weekly": {"dates": [d.strftime("%Y-%m-%d") for d in wc.dropna().index[-520:]],
                          "values": [float(v) for v in wc.dropna().values[-520:]]},
        "fx_regime_smoothed": {"dates": [d.strftime("%Y-%m-%d") for d in rf.index],
                               "p_turbulent": [float(v) for v in info2["smoothed"][:, 1]]},
        "fx_returns": [float(v) for v in r], "fx_return_dates": [d.strftime("%Y-%m-%d") for d in rf.index],
        "coffee_returns": [float(v) for v in rc.values],
    }
    report = {"coffee": coffee_rep, "fx": fx_rep, "dependence": dep_rep,
              "event_tails": {"up_n": int(len(up)), "down_n": int(len(down)),
                              "up_mean": float(up.mean()) if len(up) else 0.0,
                              "down_mean": float(down.mean()) if len(down) else 0.0}}
    cal = Calibration(
        as_of=str(as_of.date()), coffee_last_date=str(last_c_date.date()),
        coffee_last_c_lb=float(liq.iloc[-1]), coffee_gap_weeks=gap_weeks, fx_last=float(fx.iloc[-1]),
        coffee_model=cm, fx_models=models, fx_selected=fx_selected or "regime", rho_cf=rho,
        event_up=up, event_down=down, report=_sanitize(report), series=_sanitize(series))
    return cal


def get_calibration(refresh: bool = False) -> Calibration:
    if CACHE.exists() and not refresh:
        return Calibration.load()
    sel = None
    bt = CACHE.parent / "backtest_fx.json"
    if bt.exists():
        sel = json.loads(bt.read_text(encoding="utf-8")).get("selected")
    cal = calibrate(fx_selected=sel)
    cal.save()
    return cal
