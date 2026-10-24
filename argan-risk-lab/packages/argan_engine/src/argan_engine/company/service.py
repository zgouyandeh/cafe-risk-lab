"""Glue for the API/UI: build the JSON view of a company dataset (charts, estimates, recovery check, quality)."""
from __future__ import annotations

import io
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .apply import recovery_table, to_overrides
from .estimate import estimate_all
from .io import clean, read_table
from .schema import PRODUCTS, PRODUCT_FA, TABLES
from .synth import generate

SYNTH_NOTE = "داده‌ی ساختگی (Synthetic): فقط قیمت آرابیکا و نرخ دلار واقعی‌اند؛ همه‌ی داده‌های شرکت و قیمت سایر دانه‌ها تولیدشده‌اند."


def _clean(o):
    if isinstance(o, dict):
        return {str(k): _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if isinstance(o, (np.floating, float)):
        return float(o) if np.isfinite(o) else None
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, (pd.Timestamp,)):
        return str(o.date())
    return o


def _series(df: pd.DataFrame, col: str, nd: int = 2):
    return [None if not np.isfinite(x) else round(float(x), nd) for x in df[col].to_numpy(float)]


def charts(T: dict) -> dict:
    m = T["market_weekly"].sort_values("week_end").reset_index(drop=True)
    wk = [str(d.date()) for d in m["week_end"]]
    s = T["sales_weekly"]
    kg = {p: s[s["product"] == p].drop_duplicates("week_end").set_index("week_end")["kg_sold"].reindex(m["week_end"]).round(0).tolist() for p in PRODUCTS}
    unmet = s.groupby("week_end")["unmet_kg"].sum().reindex(m["week_end"]).fillna(0).round(0).tolist()
    pnl = T["pnl_weekly"].set_index("week_end").reindex(m["week_end"])
    inv = T["inventory_weekly"].groupby("week_end")["on_hand_kg"].sum().reindex(m["week_end"])
    cash = T["cash_weekly"].set_index("week_end").reindex(m["week_end"])
    col = T["collections_weekly"].set_index("week_end").reindex(m["week_end"])
    bn = 1e9
    return _clean({
        "weeks": wk,
        "kg": {p: v for p, v in kg.items()}, "unmet_kg": unmet,
        "revenue_bn": (pnl["revenue_irr"] / bn).round(1).tolist(), "gross_bn": (pnl["gross_profit_irr"] / bn).round(1).tolist(),
        "net_bn": (pnl["net_profit_irr"] / bn).round(1).tolist(),
        "inventory_kg": inv.round(0).tolist(), "cash_bn": (cash["cash_end_irr"] / bn).round(1).tolist(), "debt_bn": (cash["debt_end_irr"] / bn).round(1).tolist(),
        "receivables_bn": (col["receivables_end_irr"] / bn).round(1).tolist(),
        "fx_market": _series(m, "fx_market_irr", 0), "fx_effective": _series(m, "fx_effective_irr", 0),
        "arabica_c_lb": _series(m, "arabica_c_lb", 2), "arabica_stale": m["arabica_stale"].astype(int).tolist() if "arabica_stale" in m else None,
        "price_usd_kg": {p: _series(m, f"price_{p}_usd_kg", 3) for p in PRODUCTS},
        "cpi": _series(m, "cpi_index", 2),
    })


def annual(T: dict) -> dict:
    out = {}
    for n in ("annual_pnl", "annual_balance", "annual_by_product"):
        if n in T:
            out[n] = _clean(json.loads(T[n].to_json(orient="records")))
    return out


def preview(T: dict, n: int = 8) -> dict:
    out = {}
    for name, df in T.items():
        d = df.tail(n).copy()
        for c in d.columns:
            if pd.api.types.is_datetime64_any_dtype(d[c]):
                d[c] = d[c].dt.strftime("%Y-%m-%d")
        out[name] = {"columns": list(d.columns), "rows": _clean(d.to_dict(orient="records")), "n_rows": int(len(df)), "description": TABLES[name][1], "frequency": TABLES[name][2]}
    return out


def provenance_counts(ov: dict) -> dict:
    from ..config import Scenario
    fields = Scenario.model_fields
    total = {"data": 0, "judgment": 0, "placeholder": 0}
    for name, fld in fields.items():
        ex = fld.json_schema_extra or {}
        if ex.get("level") == "internal" or name in ("seed", "n_paths", "n_worlds", "n_worlds_max", "paths_per_world", "robust", "flip_analysis",
                                                    "worlds_auto", "cvar_alpha", "risk_lambda", "risk_appetite", "region_label", "grid_step", "fx_model", "purchase_qty_kg"):
            continue
        p = ov["provenance"].get(name, {}).get("source") or ex.get("provenance", "placeholder")
        total[p if p in total else "placeholder"] += 1
    return total


def build_view(T_raw: dict, truth: dict | None, synthetic: bool) -> dict:
    T, rep = clean(T_raw)
    est = estimate_all(T)
    ov = to_overrides(est, synthetic=synthetic)
    view = {
        "synthetic": synthetic, "note": SYNTH_NOTE if synthetic else "داده‌ی شرکت بارگذاری‌شده توسط کاربر",
        "quality": _clean(rep), "estimates": _clean({k: v for k, v in est.items() if not k.startswith("_")}),
        "overrides": _clean(ov), "provenance_counts": provenance_counts(ov),
        "charts": charts(T), "annual": annual(T), "preview": preview(T),
        "tables": {n: {"columns": c, "description": d, "frequency": f, "present": n in T} for n, (c, d, f) in TABLES.items()},
        "n_weeks": int(len(T["market_weekly"])), "start": str(T["market_weekly"]["week_end"].min().date()), "end": str(T["market_weekly"]["week_end"].max().date()),
        "product_fa": PRODUCT_FA,
    }
    if truth is not None:
        rt = recovery_table(est, truth)
        view["recovery"] = _clean(rt)
        view["recovery_ok"] = int(sum(r["ok"] for r in rt)); view["recovery_n"] = len(rt)
        view["injected_issues"] = _clean(truth["injected_issues"])
    return view


_DEMO: dict = {}


def demo_view() -> dict:
    if "view" not in _DEMO:
        tab, truth = generate()
        _DEMO["tables"], _DEMO["truth"] = tab, truth
        _DEMO["view"] = build_view(tab, truth, True)
    return _DEMO["view"]


def demo_tables() -> dict:
    demo_view()
    return _DEMO["tables"]


def template_csv(name: str) -> str:
    cols = TABLES[name][0]
    return ",".join(cols) + "\n"


def table_csv(df: pd.DataFrame) -> str:
    return df.to_csv(index=False)
