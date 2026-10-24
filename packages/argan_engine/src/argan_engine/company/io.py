"""Load company tables (CSV text/path) and run data-quality checks; returns cleaned tables + a report."""
from __future__ import annotations

import io as _io
from pathlib import Path

import numpy as np
import pandas as pd

from .schema import PRODUCTS, TABLES

DATE_COLS = {"week_end", "order_date", "arrival_date"}


def read_table(name: str, src) -> pd.DataFrame:
    df = pd.read_csv(_io.StringIO(src) if isinstance(src, str) and "\n" in src else src, encoding="utf-8")
    for c in DATE_COLS & set(df.columns):
        df[c] = pd.to_datetime(df[c])
    return df


def load_dir(path: str | Path) -> dict[str, pd.DataFrame]:
    p = Path(path)
    return {n: read_table(n, p / f"{n}.csv") for n in TABLES if (p / f"{n}.csv").exists()}


def clean(tables: dict[str, pd.DataFrame]) -> tuple[dict[str, pd.DataFrame], dict]:
    """Drop duplicates, flag missing/outliers/bad entries; never silently invents values. Returns (tables, report)."""
    rep: dict = {"missing_tables": [t for t in ("market_weekly", "sales_weekly", "purchases", "inventory_weekly",
                                                 "collections_weekly", "cash_weekly", "opex_weekly") if t not in tables],
                 "missing_columns": {}, "issues": []}
    out = {k: v.copy() for k, v in tables.items()}
    for n, df in out.items():
        miss = [c for c in TABLES[n][0] if c not in df.columns]
        if miss:
            rep["missing_columns"][n] = miss
    if "sales_weekly" in out and not rep["missing_columns"].get("sales_weekly"):
        s = out["sales_weekly"]
        d = int(s.duplicated(["week_end", "product"]).sum())
        if d:
            rep["issues"].append({"table": "sales_weekly", "type": "duplicate_rows", "n": d, "action": "حذف تکراری"})
            s = s.drop_duplicates(["week_end", "product"], keep="first")
        nmiss = int(s["kg_sold"].isna().sum())
        if nmiss:
            rep["issues"].append({"table": "sales_weekly", "type": "missing", "n": nmiss, "action": "با میانه‌ی محلی هم‌فصل پر شد (علامت‌گذاری)"})
        out_n = 0
        s = s.sort_values(["product", "week_end"]).copy()
        for p, g in s.groupby("product"):
            med = g["kg_sold"].rolling(9, center=True, min_periods=3).median()
            mad = (g["kg_sold"] - med).abs().rolling(27, center=True, min_periods=5).median() + 1e-9
            bad = ((g["kg_sold"] - med).abs() > 8 * 1.4826 * mad) & (g["kg_sold"] > 3 * med)
            for ix in g.index[bad]:
                rep["issues"].append({"table": "sales_weekly", "type": "outlier", "week_end": str(g.loc[ix, "week_end"].date()), "product": p,
                                      "value": float(g.loc[ix, "kg_sold"]), "local_median": float(med.loc[ix]), "action": "جایگزین با میانه‌ی محلی"})
                s.loc[ix, "kg_sold"] = np.nan; out_n += 1
        # fill missing (incl. removed outliers) with local median; revenue recomputed
        s["kg_filled"] = s["kg_sold"].isna().astype(int)
        for p, g in s.groupby("product"):
            m = g["kg_sold"].rolling(9, center=True, min_periods=2).median()
            s.loc[g.index, "kg_sold"] = g["kg_sold"].fillna(m)
        s["revenue_irr"] = s["revenue_irr"].where(s["kg_filled"] == 0, s["kg_sold"] * s["avg_price_irr_kg"])
        out["sales_weekly"] = s.sort_values(["week_end", "product"]).reset_index(drop=True)
    if "purchases" in out and not rep["missing_columns"].get("purchases"):
        p = out["purchases"]
        bad = p["fx_paid_irr"].fillna(0) <= 0
        if bad.any():
            rep["issues"].append({"table": "purchases", "type": "invalid_fx_paid", "n": int(bad.sum()), "action": "از برآورد نرخ ارزی کنار گذاشته شد"})
        out["purchases"] = p
    if "market_weekly" in out and not rep["missing_columns"].get("market_weekly"):
        m = out["market_weekly"].sort_values("week_end")
        gaps = int((m["week_end"].diff().dt.days.dropna() != 7).sum())
        if gaps:
            rep["issues"].append({"table": "market_weekly", "type": "irregular_weeks", "n": gaps})
        if "arabica_stale" in m:
            rep["issues"].append({"table": "market_weekly", "type": "interpolated_arabica_weeks", "n": int(m["arabica_stale"].sum()),
                                  "action": "هفته‌های بدون معامله‌ی نقدشونده؛ درون‌یابی لگاریتمی"})
        out["market_weekly"] = m.reset_index(drop=True)
    # annual reconciliation: sum of weekly P&L vs annual table
    if "pnl_weekly" in out and "annual_pnl" in out:
        w = out["pnl_weekly"].copy()
        from .synth import fiscal_year
        w["fy"] = w["week_end"].map(fiscal_year)
        g = w.groupby("fy")["revenue_irr"].sum()
        a = out["annual_pnl"].set_index("fiscal_year")["revenue_irr"]
        diff = ((g - a).abs() / a.abs()).dropna()
        rep["annual_reconciliation_max_rel_diff"] = float(diff.max()) if len(diff) else None
    rep["n_weeks"] = int(out["market_weekly"].shape[0]) if "market_weekly" in out else None
    return out, rep
