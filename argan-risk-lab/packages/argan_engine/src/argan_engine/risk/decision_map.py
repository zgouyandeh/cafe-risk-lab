"""Where does the decision flip?  Break-even beliefs and a two-dimensional decision map.

The advice "stage the purchase" is only as good as the beliefs behind it. This module answers, with the SAME simulator:
  * break-even belief: the value x* of ONE belief (FX drift, escalation probability, jump severity) at which "buy everything now"
    and the recommended staged plan have equal objective value (Brent root-finding on d(x) = J_now(x) - J_rec(x));
  * decision map: for a grid of (escalation probability x jump severity) which of the four reference plans is best,
    subject to the liquidity / service limits, and by how much "buy now" beats (or loses to) the recommendation.
All evaluations use common random numbers (same seed along every axis), so d(x) is smooth enough for root finding.
Objective J = (1-lambda) E[profit] + lambda CVaR_alpha(profit), as a % of purchase value (same as the optimiser)."""
from __future__ import annotations

import numpy as np
from scipy.optimize import brentq

from ..calibrate import Calibration
from ..config import Scenario
from ..sim import build_market, orders_from_weights, simulate_policy
from .metrics import cvar_lower

NAMES = ("recommended", "all_now", "equal_split", "all_late")
N_PATHS = 1500


def _eval(scn: Scenario, cal: Calibration, plans: dict[str, np.ndarray]) -> dict:
    mkt = build_market(scn, cal, N_PATHS, np.random.default_rng(scn.seed + 57))
    sw = scn.schedule_weeks
    scale = mkt.Q * mkt.RC_ref
    lam = scn.risk_lambda
    out = {}
    for k, w in plans.items():
        r = simulate_policy(mkt, scn, orders_from_weights(w, mkt.Q, sw))
        x = r.profit_real
        J = ((1 - lam) * x.mean() + lam * cvar_lower(x, scn.cvar_alpha)) / scale * 100.0
        breach = float((r.min_cash < scn.min_cash_bn_irr * 1e9).mean())
        unmet = float(r.unmet_kg.sum() / r.demand_kg.sum())
        out[k] = {"J": float(J), "breach": breach, "unmet": unmet,
                  "feasible": bool(breach <= scn.max_liquidity_breach_prob_pct / 100 + 1e-12 and unmet <= scn.max_unmet_demand_pct / 100 + 1e-12)}
    out["_fx_rise"] = float((mkt.X[:, -1] / mkt.X[:, 0]).mean() - 1.0)
    return out


def _plans(W: np.ndarray, bench: dict[str, int]) -> dict[str, np.ndarray]:
    return {k: W[bench[k]] for k in NAMES if k in bench}


def break_even(scn: Scenario, cal: Calibration, plans: dict, field: str, lo: float, hi: float, base_value: float, label_fa: str, unit: str) -> dict:
    """Root of J_now(x) - J_rec(x) over one belief. Positive d = buying everything now is better."""
    cache: dict[float, dict] = {}

    def at(x: float) -> dict:
        if x not in cache:
            cache[x] = _eval(scn.model_copy(update={field: float(x)}), cal, {"recommended": plans["recommended"], "all_now": plans["all_now"]})
        return cache[x]

    d = lambda x: at(x)["all_now"]["J"] - at(x)["recommended"]["J"]
    d_lo, d_hi, d_base = d(lo), d(hi), d(base_value)
    row = {"field": field, "label_fa": label_fa, "unit": unit, "lo": lo, "hi": hi, "base": base_value, "d_lo": d_lo, "d_hi": d_hi, "d_base": d_base,
           "now_better_at_base": bool(d_base > 0), "root": None, "status": ""}
    if d_lo * d_hi < 0:
        root = float(brentq(d, lo, hi, xtol=(hi - lo) * 1e-3, maxiter=30))
        e = at(root)
        row.update(root=root, status="crossing", fx_rise_at_root=e["_fx_rise"], now_feasible_at_root=e["all_now"]["feasible"],
                   rec_feasible_at_root=e["recommended"]["feasible"], margin_to_root=root - base_value)
    else:
        row["status"] = "now_always_better" if d_lo > 0 else "staged_always_better"
    return row


def decision_map(scn: Scenario, cal: Calibration, plans: dict, x_field: str, x_vals: list[float], y_field: str, y_vals: list[float]) -> dict:
    """Winner among the reference plans for every (x belief, y belief) cell; feasible plans first, then highest J."""
    win = np.full((len(y_vals), len(x_vals)), "", dtype=object)
    gap = np.zeros((len(y_vals), len(x_vals)))
    now_ok = np.zeros((len(y_vals), len(x_vals)), dtype=bool)
    for a, yv in enumerate(y_vals):
        for b, xv in enumerate(x_vals):
            e = _eval(scn.model_copy(update={x_field: float(xv), y_field: float(yv)}), cal, plans)
            cand = {k: v for k, v in e.items() if not k.startswith("_")}
            feas = {k: v for k, v in cand.items() if v["feasible"]}
            best = max(feas or cand, key=lambda k: (feas or cand)[k]["J"])
            win[a, b] = best if feas else "none:" + best
            gap[a, b] = e["all_now"]["J"] - e["recommended"]["J"]
            now_ok[a, b] = e["all_now"]["feasible"]
    return {"x_field": x_field, "y_field": y_field, "x_values": x_vals, "y_values": y_vals, "winner": win.tolist(),
            "now_minus_rec_pct": gap.tolist(), "now_feasible": now_ok.tolist(), "names": list(NAMES),
            "note": "none:X یعنی هیچ‌یک از چهار برنامه حدود نقدینگی/کمبود را رعایت نمی‌کند و X کم‌زیان‌ترین است"}


def run(scn: Scenario, cal: Calibration, W: np.ndarray, bench: dict[str, int], base_drift: float) -> dict:
    plans = _plans(W, bench)
    d_hi = max(base_drift * 2.5, 120.0)
    scn_sz = scn.model_copy(update={"event_p_escalation": max(scn.event_p_escalation, 30.0)})   # severity only matters if escalation can happen
    be = [break_even(scn, cal, plans, "fx_drift_annual_pct", -20.0, d_hi, base_drift, "روند سالانه‌ی دلار", "٪ سالانه"),
          break_even(scn, cal, plans, "event_p_escalation", 0.0, 100.0, scn.event_p_escalation, "احتمال تشدید تنش در افق", "٪"),
          break_even(scn_sz, cal, plans, "event_size_mult", 0.25, 4.0, scn_sz.event_size_mult, "شدت جهش‌های تنش (با احتمال تشدید ۳۰٪)", "× تاریخچه")]
    xs = sorted({round(v, 0) for v in (0.0, 20.0, 40.0, 60.0, 80.0, 100.0, base_drift, d_hi)})
    xs = [v for v in xs if v <= d_hi]
    return {"break_even": be, "map": decision_map(scn, cal, plans, "fx_drift_annual_pct", [float(v) for v in xs],
                                                   "event_p_escalation", [0.0, 15.0, 30.0, 50.0, 75.0]),
            "base": {"fx_drift_annual_pct": base_drift, "event_p_escalation": scn.event_p_escalation}}
