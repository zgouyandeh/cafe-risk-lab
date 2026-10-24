"""Reverse stress testing: instead of asking "what happens in scenario X?", ask
"which combination of shocks makes the plan fail?" and "what is the weakest such combination?".

Failure definitions (both reported, both user-visible):
  liquidity  – in at least `fail_prob` of the paths cash falls below the safe minimum
  supply     – expected unmet demand exceeds `fail_unmet` of total demand
Shock space: FX jump × coffee jump × import delay, applied to the SAME paths as the base run.
Severity of a combination = Euclidean norm in natural units:
  FX / coffee jump in units of the historical 13-week standard deviation of log-changes,
  delay in units of the normal lead time (floor of 1 week).
The "weakest failure" is the failing grid point with the smallest severity (minimum-norm shock,
cf. Breuer & Csiszár 2013 on systematic stress tests; here independence between the axes is assumed,
consistent with the near-zero measured coffee–FX dependence)."""
from __future__ import annotations

import numpy as np

from ..calibrate import Calibration
from ..config import Scenario
from ..sim import MarketPaths, apply_shock, orders_from_weights, simulate_policy

FX_GRID = [0.0, 0.10, 0.20, 0.30, 0.40, 0.50, 0.75, 1.00, 1.50]
COFFEE_GRID = [0.0, 0.25, 0.50]
DELAY_GRID = [0, 2, 4, 6, 8, 12]


def severity_units(scn: Scenario, cal: Calibration) -> dict:
    fx_s = cal.report["fx"]["moments"]["std"] * np.sqrt(13.0)
    c_s = cal.report["coffee"]["moments"]["std"] * np.sqrt(13.0)
    return {"fx": float(fx_s), "coffee": float(c_s), "delay_weeks": float(max(scn.lead_weeks, 1))}


def _eval(mkt: MarketPaths, scn: Scenario, W: np.ndarray, idx: int) -> dict:
    r = simulate_policy(mkt, scn, orders_from_weights(W[idx], mkt.Q, scn.schedule_weeks))
    return {"breach": float((r.min_cash < scn.min_cash_bn_irr * 1e9).mean()),
            "floor": float((r.min_cash < 0).mean()),
            "unmet": float(r.unmet_kg.sum() / r.demand_kg.sum())}


def reverse_stress(mkt: MarketPaths, scn: Scenario, cal: Calibration, W: np.ndarray, policies: dict[str, int],
                   fail_prob: float = 0.5, fail_unmet: float = 0.20) -> dict:
    units = severity_units(scn, cal)
    cells = []
    for dw in DELAY_GRID:
        for c in COFFEE_GRID:
            for fx in FX_GRID:
                m2 = apply_shock(mkt, scn, fx=fx, coffee=c, delay_weeks=dw)
                row = {"fx": fx, "coffee": c, "delay_weeks": dw,
                       "severity": float(np.sqrt((np.log1p(fx) / units["fx"]) ** 2 + (np.log1p(c) / units["coffee"]) ** 2
                                                 + (dw / units["delay_weeks"]) ** 2))}
                for name, idx in policies.items():
                    e = _eval(m2, scn, W, idx)
                    e["fail_liquidity"] = bool(e["breach"] >= fail_prob)
                    e["fail_supply"] = bool(e["unmet"] >= fail_unmet)
                    e["fail"] = e["fail_liquidity"] or e["fail_supply"]
                    row[name] = e
                cells.append(row)

    def tolerance(name: str, axis: str) -> dict:
        """Largest single-axis shock (other axes at zero) with no failure; first failing value."""
        grid = {"fx": FX_GRID, "coffee": COFFEE_GRID, "delay_weeks": DELAY_GRID}[axis]
        ok, bad = None, None
        for v in grid:
            cell = next(c for c in cells if c[axis] == v and all(c[o] == 0 for o in ("fx", "coffee", "delay_weeks") if o != axis))
            if cell[name]["fail"]:
                bad = v
                break
            ok = v
        return {"survives_up_to": ok, "fails_at": bad}

    out = {"fail_prob": fail_prob, "fail_unmet": fail_unmet, "units": units,
           "fx_grid": FX_GRID, "coffee_grid": COFFEE_GRID, "delay_grid": DELAY_GRID, "cells": cells,
           "tolerance": {}, "weakest": {}}
    for name in policies:
        out["tolerance"][name] = {ax: tolerance(name, ax) for ax in ("fx", "coffee", "delay_weeks")}
        failing = [c for c in cells if c[name]["fail"]]
        if failing:
            w = min(failing, key=lambda c: c["severity"])
            kind = "liquidity" if w[name]["fail_liquidity"] else "supply"
            out["weakest"][name] = {"fx": w["fx"], "coffee": w["coffee"], "delay_weeks": w["delay_weeks"],
                                    "severity": w["severity"], "kind": kind, "breach": w[name]["breach"], "unmet": w[name]["unmet"]}
        else:
            out["weakest"][name] = None
    return out
