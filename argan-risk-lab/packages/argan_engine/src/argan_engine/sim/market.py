"""Joint scenario generator: coffee, FX, sale price, demand (all vectorised over paths, weekly grid)."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..calibrate import Calibration
from ..config import Scenario
from ..data import cents_lb_to_usd_kg
from ..models import apply_event_overlay, correlated_normals

WEEKS_PER_YEAR = 52.0


@dataclass
class MarketPaths:
    n: int
    H: int
    P: np.ndarray         # (n, H+1) coffee, USD/kg (incl. differential)
    X: np.ndarray         # (n, H+1) effective rial per USD
    RC: np.ndarray        # (n, H+1) landed replacement cost, rial/kg
    S: np.ndarray         # (n, H+1) sale price, rial/kg
    D: np.ndarray         # (n, H) demand, kg
    CPI: np.ndarray       # (H+1,)
    Q: float              # planned purchase, kg
    RC_ref: float         # firm-known landed cost at t0 (reference), rial/kg
    S0: float
    fx_model: str
    fx_states: np.ndarray | None = None
    meta: dict = field(default_factory=dict)
    # optional per-path overrides (historical replay): arrays of shape (n,)
    cash0: np.ndarray | None = None
    opex0: np.ndarray | None = None
    rc_ref_path: np.ndarray | None = None
    delay_w: np.ndarray | None = None   # (n,) extra import delay in weeks (per path)
    lost_w: np.ndarray | None = None    # (n,) bool: shipments never arrive on this path (prepayment lost)


def sale_price_path(RC: np.ndarray, S0: float | np.ndarray, scn: Scenario) -> np.ndarray:
    """Sale price: log-changes = asymmetric, lagged pass-through of replacement-cost changes
    (+ optional indexation to general inflation)."""
    n, H1 = RC.shape
    H = H1 - 1
    dlog = np.diff(np.log(RC), axis=1)                                # dlog[:, t-1] = change into week t
    pos, neg = np.maximum(dlog, 0.0), np.minimum(dlog, 0.0)
    idx = scn.price_indexation * np.log1p(scn.inflation_pct / 100.0) / WEEKS_PER_YEAR
    S = np.empty_like(RC)
    S[:, 0] = S0
    for t in range(1, H + 1):
        iu, idn = t - scn.lag_up_weeks, t - scn.lag_down_weeks
        up = pos[:, iu - 1] if iu >= 1 else 0.0
        dn = neg[:, idn - 1] if idn >= 1 else 0.0
        S[:, t] = S[:, t - 1] * np.exp(scn.pass_through_up * up + scn.pass_through_down * dn + idx)
    return S


def demand_paths(S: np.ndarray, S0: float | np.ndarray, CPI: np.ndarray, zd: np.ndarray, scn: Scenario
                 ) -> np.ndarray:
    """Weekly demand: log-normal (non-negative, mean-preserving) with constant-elasticity response to the
    real sale price relative to its starting level."""
    H = S.shape[1] - 1
    sig_l = np.sqrt(np.log1p(scn.demand_cv ** 2))
    base = scn.weekly_demand_kg * (1.0 + scn.demand_shift_pct / 100.0) * np.exp(sig_l * zd - 0.5 * sig_l ** 2)
    if scn.demand_seasonal_index:
        seas = np.asarray(scn.demand_seasonal_index, float)
        base = base * seas[(scn.season_start_week + np.arange(H)) % 52][None, :]
    S0a = np.asarray(S0).reshape(-1, 1) if np.ndim(S0) else S0
    ratio = S[:, :H] / (S0a * CPI[None, :H])
    return base * ratio ** (-scn.demand_price_elasticity)


def resolve_fx_kind(scn: Scenario, cal: Calibration) -> str:
    return cal.fx_selected if scn.fx_model == "auto" else scn.fx_model


def build_market(scn: Scenario, cal: Calibration, n: int, rng: np.random.Generator,
                 shocks: list[tuple[int, float, float]] | None = None) -> MarketPaths:
    """shocks: optional deterministic stress overlay [(week, fx_log_shock, coffee_log_shock)] applied to the
    returns of that decision-week (0 = first week) on every path."""
    H = scn.horizon_weeks
    gap = 0 if scn.coffee_spot_c_lb else int(round(cal.coffee_gap_weeks))
    W = gap + H

    rho_cf = cal.rho_cf if scn.corr_coffee_fx is None else scn.corr_coffee_fx
    zc, zx, zd = correlated_normals(n, W, rho_cf, scn.demand_fx_rho, 0.0, rng)

    # ---- coffee ---------------------------------------------------------------------------
    rc = cal.coffee_model.log_returns(zc, scn.coffee_vol_mult)
    if scn.basket_beta != 1.0 or scn.basket_basis_vol_pct > 0:
        # purchase basket (robusta, specialty, …) = beta × arabica + independent basis; keep it a martingale
        rc = scn.basket_beta * rc
        if scn.basket_basis_vol_pct > 0:
            rb = np.random.default_rng(int(rng.integers(0, 2 ** 32 - 1)))
            rc = rc + rb.standard_normal(rc.shape) * scn.basket_basis_vol_pct / 100.0
        rc = rc - np.log(np.exp(rc).mean(axis=0, keepdims=True))
    for (wk, _fxs, cs) in (shocks or []):
        rc[:, gap + wk] += cs
    p_ref_c = scn.coffee_spot_c_lb or cal.coffee_last_c_lb            # USc/lb used for sizing
    p_last = p_ref_c
    logP = np.log(p_last) + np.concatenate([np.zeros((n, 1)), np.cumsum(rc, axis=1)], axis=1)
    logP = logP[:, gap:]                                              # drop the pre-decision gap, keep P at t0..tH
    P_c = np.exp(logP)                                                # USc/lb (n, H+1)
    P = cents_lb_to_usd_kg(P_c) + scn.coffee_differential_usd_kg
    P_ref = cents_lb_to_usd_kg(p_ref_c) + scn.coffee_differential_usd_kg

    # ---- FX -------------------------------------------------------------------------------
    kind = resolve_fx_kind(scn, cal)
    model = cal.fx_models[kind]
    if scn.fx_drift_annual_pct is not None:
        model = model.with_drift(scn.fx_drift_annual_pct / 100.0)
    if scn.fx_vol_mult != 1.0:
        model = model.with_vol_mult(scn.fx_vol_mult)
    zx_h = zx[:, gap:]
    rx, states = model.simulate(zx_h, rng)
    rx = apply_event_overlay(rx, scn.event_p_escalation / 100.0, scn.event_p_deal / 100.0,
                             cal.event_up * scn.event_size_mult, cal.event_down, rng)
    for (wk, fxs, _cs) in (shocks or []):
        rx[:, wk] += fxs
    X0 = scn.fx_spot_irr or cal.fx_last
    X = X0 * np.exp(np.concatenate([np.zeros((n, 1)), np.cumsum(rx, axis=1)], axis=1))
    X = X * scn.fx_basis_total

    # ---- costs, prices, demand ---------------------------------------------------------
    land = 1.0 + scn.landing_cost_pct / 100.0
    RC = P * X * land
    RC_ref = P_ref * X0 * scn.fx_basis_total * land
    S0 = RC_ref * (1.0 + scn.target_markup_pct / 100.0)
    S = sale_price_path(RC, S0, scn)
    CPI = (1.0 + scn.inflation_pct / 100.0) ** (np.arange(H + 1) / WEEKS_PER_YEAR)
    D = demand_paths(S, S0, CPI, zd[:, gap:], scn)

    Q = scn.purchase_qty_kg or scn.purchase_budget_usd / P_ref
    meta = {"P_ref_usd_kg": float(P_ref), "P_ref_c_lb": float(p_ref_c), "X0": float(X0 * scn.fx_basis_total),
            "gap_weeks": gap, "rho_cf": float(rho_cf)}
    # import delay (drawn LAST so the random stream of everything else is unchanged when p = 0)
    p_d, dw = scn.import_delay_prob_pct / 100.0, scn.delay_weeks
    if p_d <= 0 or dw == 0:
        delay = np.zeros(n, dtype=int)
    elif p_d >= 1:
        delay = np.full(n, dw, dtype=int)
    else:
        delay = (rng.random(n) < p_d).astype(int) * dw
    lost = None
    if scn.import_loss_prob_pct > 0:                          # drawn after the delay: streams unchanged when the loss belief is 0
        lost = (delay > 0) & (rng.random(n) < scn.import_loss_prob_pct / 100.0)
    return MarketPaths(n=n, H=H, P=P, X=X, RC=RC, S=S, D=D, CPI=CPI, Q=float(Q), RC_ref=float(RC_ref),
                       S0=float(S0), fx_model=kind, fx_states=states, meta=meta, delay_w=delay, lost_w=lost)


def subset(mkt: MarketPaths, n: int) -> MarketPaths:
    """First n paths of a market (keeps common random numbers across scenarios)."""
    from dataclasses import replace
    n = min(n, mkt.n)
    sl = lambda a: None if a is None else a[:n]
    return replace(mkt, n=n, P=mkt.P[:n], X=mkt.X[:n], RC=mkt.RC[:n], S=mkt.S[:n], D=mkt.D[:n],
                   fx_states=sl(mkt.fx_states), cash0=sl(mkt.cash0), opex0=sl(mkt.opex0),
                   rc_ref_path=sl(mkt.rc_ref_path), delay_w=sl(mkt.delay_w), lost_w=sl(mkt.lost_w))


def apply_shock(mkt: MarketPaths, scn: Scenario, *, fx: float = 0.0, coffee: float = 0.0, delay_weeks: int | None = None,
                landing_pct: float | None = None, demand_shift_pct: float = 0.0, from_week: int = 1,
                loss_share: float = 0.0) -> MarketPaths:
    """Deterministic overlay on an existing market (common random numbers with the base run):
    fx / coffee are instantaneous relative jumps (0.5 = +50%) applied from `from_week` on; the sale price and
    demand are re-derived from the shocked replacement cost with the same pass-through / elasticity rules.
    delay_weeks (None = keep) sets the import delay on every path; landing_pct re-prices freight/insurance/customs."""
    from dataclasses import replace
    H = mkt.H
    k = (1.0 + fx) * (1.0 + coffee)
    if landing_pct is not None:
        k *= (1.0 + landing_pct / 100.0) / (1.0 + scn.landing_cost_pct / 100.0)
    up = np.ones(H + 1)
    up[from_week:] = k
    RC2 = mkt.RC * up[None, :]
    X2 = mkt.X.copy(); X2[:, from_week:] *= (1.0 + fx)
    P2 = mkt.P.copy(); P2[:, from_week:] *= (1.0 + coffee)
    S2 = sale_price_path(RC2, mkt.S0, scn)
    D2 = mkt.D * (S2[:, :H] / mkt.S[:, :H]) ** (-scn.demand_price_elasticity) * (1.0 + demand_shift_pct / 100.0)
    dw = mkt.delay_w if delay_weeks is None else np.full(mkt.n, int(delay_weeks), dtype=int)
    lost = mkt.lost_w
    if loss_share > 0:                                          # a fixed, seed-derived subset of paths loses its shipments (CRN-stable)
        u = np.random.default_rng(scn.seed + 101).random(mkt.n)
        lost = (u < loss_share) | (mkt.lost_w if mkt.lost_w is not None else False)
    return replace(mkt, RC=RC2, X=X2, P=P2, S=S2, D=D2, delay_w=dw, lost_w=lost)
