"""Policy family and selection.

Policy = purchase weights w over the allowed order days (w ≥ 0, Σw = 1) applied to a fixed total
quantity Q. The family is a simplex; with 3 order days and step 0.1 it has 66 members (+ equal split).
Every member is evaluated on the SAME simulated paths (common random numbers), so differences are
due to the policy, not to luck. Selection maximises J = (1-λ)E[Π] + λ CVaR_α[Π] subject to
liquidity and shortage constraints; the exact objective values of all members are returned so the
efficient frontier can be drawn (no black box)."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..config import Scenario
from ..risk.metrics import cvar_lower
from ..sim import MarketPaths, orders_from_weights, simulate_policy


def weight_grid(K: int, step: float, add_equal: bool = True) -> np.ndarray:
    units = int(round(1.0 / step))
    out: list[list[int]] = []

    def rec(prefix: list[int], left: int, k: int) -> None:
        if k == 1:
            out.append(prefix + [left])
            return
        for v in range(left + 1):
            rec(prefix + [v], left - v, k - 1)

    rec([], units, K)
    W = np.array(out, float) / units
    if add_equal and K > 1:
        eq = np.full(K, 1.0 / K)
        if not np.any(np.all(np.isclose(W, eq), axis=1)):
            W = np.vstack([W, eq])
    return W


@dataclass
class GridEval:
    weights: np.ndarray          # (P,K)
    profit: np.ndarray | None    # (P,n) real-rial profit samples (kept for paired stats / SSD)
    mean: np.ndarray
    cvar: np.ndarray
    sd: np.ndarray
    breach: np.ndarray           # P(min cash < minimum)
    unmet: np.ndarray            # E[unmet] / E[demand]
    stockout: np.ndarray         # P(any unmet demand)
    floor: np.ndarray            # P(min cash < 0)  (overdraft needed)
    cover: np.ndarray            # P(on-hand stock falls below the safety stock)
    usd_mean: np.ndarray
    acct_mean: np.ndarray
    J: np.ndarray
    n: int
    scale: float                 # purchase value at reference cost, rial (for % normalisation)


def evaluate_grid(mkt: MarketPaths, scn: Scenario, W: np.ndarray, keep_profit: bool = True) -> GridEval:
    P, n = len(W), mkt.n
    sw = scn.schedule_weeks
    min_cash = scn.min_cash_bn_irr * 1e9
    arrs = {k: np.empty(P) for k in ("mean", "cvar", "sd", "breach", "unmet", "stockout", "usd", "acct", "floor", "cover")}
    safety = scn.safety_stock_weeks * scn.weekly_demand_kg
    prof = np.empty((P, n)) if keep_profit else None
    for i, w in enumerate(W):
        r = simulate_policy(mkt, scn, orders_from_weights(w, mkt.Q, sw))
        x = r.profit_real
        if keep_profit:
            prof[i] = x
        arrs["mean"][i] = x.mean()
        arrs["cvar"][i] = cvar_lower(x, scn.cvar_alpha)
        arrs["sd"][i] = x.std(ddof=1)
        arrs["breach"][i] = (r.min_cash < min_cash).mean()
        arrs["unmet"][i] = r.unmet_kg.sum() / r.demand_kg.sum()
        arrs["stockout"][i] = (r.unmet_kg > 1e-6).mean()
        arrs["floor"][i] = (r.min_cash < 0).mean()
        arrs["cover"][i] = (r.min_stock_kg < safety).mean()
        arrs["usd"][i] = r.profit_usd.mean()
        arrs["acct"][i] = r.acct_profit.mean()
    lam = scn.risk_lambda
    J = (1 - lam) * arrs["mean"] + lam * arrs["cvar"]
    return GridEval(W, prof, arrs["mean"], arrs["cvar"], arrs["sd"], arrs["breach"], arrs["unmet"],
                    arrs["stockout"], arrs["floor"], arrs["cover"], arrs["usd"], arrs["acct"], J, n, mkt.Q * mkt.RC_ref)


def feasible_mask(ev: GridEval, scn: Scenario) -> np.ndarray:
    return (ev.breach <= scn.max_liquidity_breach_prob_pct / 100.0 + 1e-12) & \
           (ev.unmet <= scn.max_unmet_demand_pct / 100.0 + 1e-12)


def select_best(ev: GridEval, scn: Scenario) -> dict:
    """Best feasible policy by J. If nothing is feasible, returns the least-violating one and flags it."""
    mask = feasible_mask(ev, scn)
    if mask.any():
        idx = int(np.argmax(np.where(mask, ev.J, -np.inf)))
        return {"idx": idx, "feasible": True, "mask": mask}
    viol = np.maximum(ev.breach - scn.max_liquidity_breach_prob_pct / 100, 0) / max(
        scn.max_liquidity_breach_prob_pct / 100, 1e-3) + np.maximum(
        ev.unmet - scn.max_unmet_demand_pct / 100, 0) / max(scn.max_unmet_demand_pct / 100, 1e-3)
    return {"idx": int(np.argmin(viol)), "feasible": False, "mask": mask}


def pareto_front(mean: np.ndarray, cvar: np.ndarray, mask: np.ndarray | None = None) -> np.ndarray:
    """Indices non-dominated in (mean ↑, cvar ↑) among `mask` members."""
    idx = np.arange(len(mean)) if mask is None else np.flatnonzero(mask)
    keep = []
    for i in idx:
        dominated = np.any((mean[idx] >= mean[i] - 1e-9) & (cvar[idx] >= cvar[i] - 1e-9) &
                           ((mean[idx] > mean[i] + 1e-9) | (cvar[idx] > cvar[i] + 1e-9)))
        if not dominated:
            keep.append(i)
    return np.array(sorted(keep, key=lambda i: mean[i]))
