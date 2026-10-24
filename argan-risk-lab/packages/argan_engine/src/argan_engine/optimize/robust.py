"""Robustness across 'possible worlds'.

Parameters that cannot be pinned down from data are drawn by Latin-hypercube sampling (McKay, Beckman,
Conover 1979) from explicit priors; each world gets its own Monte-Carlo run; every policy is scored in
every world. A policy is recommended only if it keeps constraints in most worlds (chance constraint) and
has small high-quantile regret (minimax-regret family; Savage 1951)."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import stats
from scipy.stats import qmc

from ..calibrate import Calibration
from ..config import Scenario
from ..sim import build_market
from .policy_search import GridEval, evaluate_grid

PARAMS = ["fx_drift", "fx_vol_mult", "coffee_vol_mult", "rho_cf", "demand_fx_rho", "p_escalation", "p_deal",
          "pass_up", "pass_down", "weekly_demand", "demand_cv", "rate_mult", "inflation_mult"]
PARAM_LABELS_FA = {
    "fx_drift": "روند سالانه دلار", "fx_vol_mult": "نوسان ارز", "coffee_vol_mult": "نوسان قهوه",
    "rho_cf": "هم‌بستگی قهوه–ارز", "demand_fx_rho": "افت تقاضا هم‌زمان با جهش ارز",
    "p_escalation": "احتمال تشدید تنش", "p_deal": "احتمال توافق/کاهش تنش",
    "pass_up": "انتقال افزایش هزینه به قیمت", "pass_down": "انتقال کاهش هزینه به قیمت",
    "weekly_demand": "سطح تقاضا", "demand_cv": "نوسان تقاضا", "rate_mult": "نرخ‌های بهره", "inflation_mult": "تورم",
}


def fx_drift_se_annual(cal: Calibration) -> float:
    m = cal.report["fx"]["moments"]
    return float(m["std"] / np.sqrt(m["n"]) * 52.0)


def base_drift_annual_pct(scn: Scenario, cal: Calibration) -> float:
    if scn.fx_drift_annual_pct is not None:
        return scn.fx_drift_annual_pct
    from ..sim.market import resolve_fx_kind
    return cal.fx_models[resolve_fx_kind(scn, cal)].mean_weekly() * 52 * 100


def world_from_unit(u: np.ndarray, base: Scenario, cal: Calibration) -> tuple[Scenario, np.ndarray]:
    d0 = base_drift_annual_pct(base, cal)
    se = fx_drift_se_annual(cal) * 100
    drift = d0 + se * stats.norm.ppf(np.clip(u[0], 1e-4, 1 - 1e-4))
    p_cap = max(0.30, 2 * base.event_p_escalation / 100)
    pd_cap = max(0.30, 2 * base.event_p_deal / 100)
    def nrm(i, mean, key, lo, hi, default):
        se_ = base.param_se.get(key)
        if se_ is None:
            return default
        return float(np.clip(mean + 1.0 * se_ * stats.norm.ppf(np.clip(u[i], 1e-4, 1 - 1e-4)) * 1.0, lo, hi))
    vals = np.array([
        drift,
        np.exp(0.20 * stats.norm.ppf(np.clip(u[1], 1e-4, 1 - 1e-4))),
        np.exp(0.15 * stats.norm.ppf(np.clip(u[2], 1e-4, 1 - 1e-4))),
        -0.1 + 0.6 * u[3],
        nrm(4, base.demand_fx_rho, "demand_fx_rho", -0.9, 0.5, -0.6 + 0.7 * u[4]),
        100 * p_cap * u[5],
        100 * pd_cap * u[6],
        nrm(7, base.pass_through_up, "pass_through_up", 0.0, 1.5, 0.6 + 0.4 * u[7]),
        nrm(8, base.pass_through_down, "pass_through_down", 0.0, 1.5, 0.1 + 0.6 * u[8]),
        (np.exp(stats.norm.ppf(np.clip(u[9], 1e-4, 1 - 1e-4)) * base.param_se["weekly_demand_rel"])
         if "weekly_demand_rel" in base.param_se else np.exp(0.15 * stats.norm.ppf(np.clip(u[9], 1e-4, 1 - 1e-4)))),
        nrm(10, base.demand_cv, "demand_cv", 0.03, 1.0, 0.15 + 0.25 * u[10]),
        0.75 + 0.5 * u[11],
        0.8 + 0.45 * u[12],
    ])
    dep = base.deposit_rate_pct * vals[11]
    bor = max(base.borrow_rate_pct * vals[11], dep)
    w = base.model_copy(update=dict(
        fx_drift_annual_pct=float(vals[0]), fx_vol_mult=base.fx_vol_mult * float(vals[1]),
        coffee_vol_mult=base.coffee_vol_mult * float(vals[2]), corr_coffee_fx=float(vals[3]),
        demand_fx_rho=float(vals[4]), event_p_escalation=float(vals[5]), event_p_deal=float(vals[6]),
        pass_through_up=float(vals[7]), pass_through_down=float(vals[8]),
        weekly_demand_kg=base.weekly_demand_kg * float(vals[9]), demand_cv=float(vals[10]),
        deposit_rate_pct=float(dep), borrow_rate_pct=float(bor),
        inflation_pct=base.inflation_pct * float(vals[12])))
    return w, vals


@dataclass
class WorldsResult:
    params: np.ndarray           # (W, 13) sampled parameter values
    J: np.ndarray                # (W, P)
    mean: np.ndarray
    cvar: np.ndarray
    breach: np.ndarray
    unmet: np.ndarray
    scale: np.ndarray            # (W,)


def run_worlds(base: Scenario, cal: Calibration, W: np.ndarray, progress=None, n: int | None = None,
               batch: int = 0) -> WorldsResult:
    """`batch` > 0 draws an additional, independently stratified Latin-hypercube batch (different seeds)."""
    nw = n or base.n_worlds
    sampler = qmc.LatinHypercube(d=len(PARAMS), seed=base.seed + 7 + 9973 * batch)
    U = sampler.random(nw)
    P = len(W)
    out = {k: np.empty((nw, P)) for k in ("J", "mean", "cvar", "breach", "unmet")}
    params, scale = np.empty((nw, len(PARAMS))), np.empty(nw)
    for i in range(nw):
        w_scn, vals = world_from_unit(U[i], base, cal)
        rng = np.random.default_rng(base.seed + 1000 + i + 100_000 * batch)
        mkt = build_market(w_scn, cal, base.paths_per_world, rng)
        ev = evaluate_grid(mkt, w_scn, W, keep_profit=False)
        out["J"][i], out["mean"][i], out["cvar"][i] = ev.J, ev.mean, ev.cvar
        out["breach"][i], out["unmet"][i] = ev.breach, ev.unmet
        params[i], scale[i] = vals, ev.scale
        if progress:
            progress((i + 1) / nw)
    return WorldsResult(params, out["J"], out["mean"], out["cvar"], out["breach"], out["unmet"], scale)


def concat_worlds(a: WorldsResult, b: WorldsResult) -> WorldsResult:
    return WorldsResult(*(np.concatenate([x, y]) for x, y in zip(
        (a.params, a.J, a.mean, a.cvar, a.breach, a.unmet, a.scale), (b.params, b.J, b.mean, b.cvar, b.breach, b.unmet, b.scale))))


def robust_select(wr: WorldsResult, base: Scenario, chance: float = 0.8, q: float = 0.9) -> dict:
    """Chance-constrained minimax-regret choice.

    1. keep policies feasible (breach ≤ limit and unmet ≤ limit) in at least `chance` of the worlds
    2. regret_w(p) = max_{p' in kept} J_w(p') − J_w(p), normalised by purchase value
    3. choose the policy with the smallest q-quantile of regret (ties: smaller mean regret)"""
    lim_b, lim_u = base.max_liquidity_breach_prob_pct / 100, base.max_unmet_demand_pct / 100
    feas_w = (wr.breach <= lim_b + 1e-12) & (wr.unmet <= lim_u + 1e-12)       # (W,P)
    share = feas_w.mean(axis=0)
    keep = share >= chance
    relaxed = False
    if not keep.any():
        keep = share >= share.max() - 1e-12
        relaxed = True
    Jn = wr.J / wr.scale[:, None]
    best = np.where(keep[None, :], Jn, -np.inf).max(axis=1)
    regret = np.where(keep[None, :], best[:, None] - Jn, np.inf)               # (W,P) normalised
    q_reg = np.quantile(np.where(np.isfinite(regret), regret, np.nan), q, axis=0)
    m_reg = np.nanmean(np.where(np.isfinite(regret), regret, np.nan), axis=0)
    score = np.where(keep, q_reg + 1e-6 * m_reg, np.inf)
    idx = int(np.argmin(score))
    winners = np.where(keep[None, :], Jn, -np.inf).argmax(axis=1)
    win_share = np.bincount(winners, minlength=Jn.shape[1]) / len(winners)
    return {"idx": idx, "keep": keep, "share_feasible": share, "q_regret": q_reg, "mean_regret": m_reg,
            "relaxed": relaxed, "win_share": win_share, "regret": regret}


def sensitivity_spearman(wr: WorldsResult, target: np.ndarray) -> list[dict]:
    """Rank correlation of each sampled parameter with a scalar target per world
    (global sensitivity from the same worlds; no extra simulations)."""
    out = []
    for j, name in enumerate(PARAMS):
        rho, p = stats.spearmanr(wr.params[:, j], target)
        out.append({"param": name, "label_fa": PARAM_LABELS_FA[name], "rho": float(0 if np.isnan(rho) else rho),
                    "p": float(1 if np.isnan(p) else p)})
    return sorted(out, key=lambda d: -abs(d["rho"]))


def convergence(wr: WorldsResult, base: Scenario, W: np.ndarray, reps: int = 40, seed: int = 0) -> dict:
    """Is the number of possible worlds enough? Re-run the robust selection on random sub-collections of
    worlds (without replacement) and compare with the choice made on ALL worlds.
      agree  – same policy;  close – chosen weights within one grid step of the full-set choice.
    Stable agreement at 75% of the worlds means adding worlds would not change the decision."""
    N = len(wr.J)
    i_full = robust_select(wr, base)["idx"]
    step = base.grid_step + 1e-9
    rng = np.random.default_rng(seed)
    sizes = [k for k in sorted({max(6, int(round(N * f))) for f in (0.25, 0.5, 0.75)}) if k < N]
    rows = []
    for k in sizes:
        picks = []
        for _ in range(reps):
            ids = rng.choice(N, size=k, replace=False)
            sub = WorldsResult(wr.params[ids], wr.J[ids], wr.mean[ids], wr.cvar[ids], wr.breach[ids], wr.unmet[ids], wr.scale[ids])
            picks.append(robust_select(sub, base)["idx"])
        picks = np.array(picks)
        dist = np.abs(W[picks] - W[i_full]).max(axis=1)
        rows.append({"worlds": int(k), "agree": float((picks == i_full).mean()), "close": float((dist <= step).mean()),
                     "median_gap": float(np.median(dist))})
    ok = bool(rows) and rows[-1]["close"] >= 0.8
    return {"rows": rows, "n_full": int(N), "reps": reps, "adequate": ok, "idx_full": int(i_full),
            "min_worlds_close90": next((r["worlds"] for r in rows if r["close"] >= 0.9), None)}
