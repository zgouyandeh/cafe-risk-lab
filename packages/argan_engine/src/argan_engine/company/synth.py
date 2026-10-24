"""SYNTHETIC company data generator (a demo fixture, NOT company data).

What is real:   weekly arabica futures (data/raw/arabica_futures.csv) and weekly USD/IRR (data/raw/usd_irr_tgju.xlsx).
What is fake:   everything about the company (sales, purchases, inventory, P&L, cash, receivables, opex) and the
                prices of the other bean types (robusta, specialty, differentials) and the effective FX premium.
The fake part is produced by an explicit data-generating process with KNOWN parameters (returned as `truth`) so the
estimator can be validated by parameter recovery. Realistic quirks are injected on purpose (missing weeks, a duplicated
row, an outlier, a bad entry) and listed in truth['injected_issues'].
Scale: a large importer-roaster, ~55 t/week (~2,900 t/year), four product lines, about 4.9 years of weekly data."""
from __future__ import annotations

from collections import deque
from pathlib import Path

import numpy as np
import pandas as pd

from ..calibrate import DEFAULT_COFFEE, DEFAULT_FX
from ..data import load_coffee, load_fx
from ..data.loaders import CENTS_LB_TO_USD_KG
from .schema import PRODUCTS, PRODUCT_FA

SEED = 20261022
END = "2026-08-21"            # last liquid arabica week
N_WEEKS = 255

BASE_KG = {"washed": 18_000.0, "natural": 13_000.0, "robusta": 16_000.0, "specialty": 8_000.0}
MARKUP = {"washed": 0.12, "natural": 0.10, "robusta": 0.08, "specialty": 0.25}
ELASTICITY = {"washed": 0.6, "natural": 0.5, "robusta": 0.9, "specialty": 0.3}
SHARE_OF_PURCHASES = None  # derived from simulated purchases

TRUE = dict(
    pass_up=0.85, pass_down=0.35, lag_up=1, lag_down=4, indexation=0.15, growth=0.04, ecm_speed=0.03, demand_ar1=0.25, demand_sd=0.20,
    demand_fx_rho=-0.25, recv_weights=[0.06, 0.22, 0.30, 0.20, 0.12, 0.07, 0.03], landing_pct=13.5, transfer_fee_pct=1.2,
    shrink_pct_week=0.05, storage_pct_week=0.15, deposit_rate_pct=20.0, borrow_rate_pct=38.0, fx_premium_mean=0.07,
    lead_weeks_mean=5.0, lead_weeks_sd=0.9, robusta_beta=0.60, opex_pct_of_revenue=0.075)


def fiscal_year(d: pd.Timestamp) -> int:
    return d.year if (d.month, d.day) >= (3, 21) else d.year - 1


def seasonal_profile() -> np.ndarray:
    """52-week index (mean 1): Nowruz peak (weeks 9-12), winter high, summer trough."""
    w = np.arange(52)
    s = 1.0 + 0.16 * np.cos(2 * np.pi * (w - 10) / 52.0)
    s[8:12] += 0.14
    return s / s.mean()


def _ar1(rng, n, phi, sd, mu=0.0):
    x = np.empty(n); x[0] = mu
    for t in range(1, n):
        x[t] = mu + phi * (x[t - 1] - mu) + sd * rng.standard_normal()
    return x


def generate(seed: int = SEED) -> tuple[dict[str, pd.DataFrame], dict]:
    rng = np.random.default_rng(seed)
    weeks = pd.date_range(end=END, periods=N_WEEKS, freq="W-FRI")
    T, P = len(weeks), len(PRODUCTS)

    # ------------------------------------------------------------------ REAL market series
    fx_s, _ = load_fx(DEFAULT_FX)
    fx_mkt = fx_s.resample("W-FRI").last().ffill().reindex(weeks).ffill().to_numpy()
    cf, _ = load_coffee(DEFAULT_COFFEE)
    ara_raw = cf.loc[cf["liquid"], "Close"].resample("W-FRI").last().reindex(weeks)
    stale = ara_raw.isna().to_numpy()
    ara = np.exp(np.log(ara_raw).interpolate(limit_direction="both")).to_numpy()        # USc/lb
    ara_usd = ara * CENTS_LB_TO_USD_KG
    r_ara = np.diff(np.log(ara_usd), prepend=np.log(ara_usd[0]))
    r_fx = np.diff(np.log(fx_mkt), prepend=np.log(fx_mkt[0]))

    # ------------------------------------------------------------------ SYNTHETIC prices of other beans
    d_w = _ar1(rng, T, 0.97, 0.05, 0.55)
    d_n = _ar1(rng, T, 0.97, 0.05, -0.12)
    prem = _ar1(rng, T, 0.97, 0.07, 1.8)
    s_star = np.log(0.55)
    s = np.empty(T); s[0] = s_star
    for t in range(1, T):                                   # log(robusta/arabica): mean-reverting, beta(robusta)=0.6 on arabica returns
        s[t] = s[t - 1] - 0.02 * (s[t - 1] - s_star) - (1 - TRUE["robusta_beta"]) * r_ara[t] + 0.03 * rng.standard_normal()
    price = np.column_stack([ara_usd + d_w, ara_usd + d_n, ara_usd * np.exp(s), ara_usd + prem])        # USD/kg FOB
    price = np.maximum(price, 0.8)

    # effective FX: market rate x (1 + access premium); premium widens in FX spikes
    fx_prem = np.empty(T); fx_prem[0] = TRUE["fx_premium_mean"]
    for t in range(1, T):
        fx_prem[t] = (TRUE["fx_premium_mean"] * 0.04 + 0.96 * fx_prem[t - 1] + 0.010 * rng.standard_normal()
                      + 0.35 * max(r_fx[t] - 0.04, 0.0))
    fx_prem = np.clip(fx_prem, 0.0, 0.30)
    fx_eff = fx_mkt * (1 + fx_prem)

    infl_annual = np.linspace(0.38, 0.55, T) + 0.02 * rng.standard_normal(T).cumsum() / np.sqrt(np.arange(1, T + 1))
    dcpi = np.log1p(np.clip(infl_annual, 0.2, 0.8)) / 52 + 0.0015 * rng.standard_normal(T)
    dcpi[0] = 0.0
    cpi = 100 * np.exp(np.cumsum(dcpi))

    land = TRUE["landing_pct"] / 100.0
    fee = TRUE["transfer_fee_pct"] / 100.0
    rcu = price * (fx_eff * (1 + land) * (1 + fee))[:, None]                    # replacement cost, IRR/kg

    # ------------------------------------------------------------------ sale prices: asymmetric lagged pass-through
    S = np.empty((T, P)); S[0] = rcu[0] * (1 + np.array([MARKUP[p] for p in PRODUCTS]))
    dl = np.diff(np.log(rcu), axis=0, prepend=np.log(rcu[:1]))
    pn = 0.006 * rng.standard_normal((T, P))
    mk = np.array([MARKUP[p] for p in PRODUCTS])
    for t in range(1, T):
        iu, idn = t - TRUE["lag_up"], t - TRUE["lag_down"]
        up = np.maximum(dl[iu], 0.0) if iu >= 1 else 0.0
        dn = np.minimum(dl[idn], 0.0) if idn >= 1 else 0.0
        gap = np.log(rcu[t - 1] * (1 + mk)) - np.log(S[t - 1])          # margin error-correction (pricing anchored to target markup)
        S[t] = S[t - 1] * np.exp(TRUE["pass_up"] * up + TRUE["pass_down"] * dn + TRUE["indexation"] * dcpi[t]
                                 + TRUE["ecm_speed"] * gap + pn[t])

    # ------------------------------------------------------------------ latent demand
    seas = seasonal_profile()
    woy = np.array([min(w.isocalendar().week - 1, 51) for w in weeks])
    z_fx = (r_fx - r_fx.mean()) / r_fx.std()
    rho = TRUE["demand_fx_rho"]
    common = rho * z_fx + np.sqrt(1 - rho ** 2) * rng.standard_normal(T)
    e = np.sqrt(0.7) * common[:, None] + np.sqrt(0.3) * rng.standard_normal((T, P))
    u = np.empty((T, P)); u[0] = e[0]
    a = TRUE["demand_ar1"]
    for t in range(1, T):
        u[t] = a * u[t - 1] + np.sqrt(1 - a ** 2) * e[t]
    sd = TRUE["demand_sd"]
    S_real = S / (cpi / cpi[0])[:, None]
    ratio = S_real / S_real[0]
    base = np.array([BASE_KG[p] for p in PRODUCTS])
    eps = np.array([ELASTICITY[p] for p in PRODUCTS])
    trend = (1 + TRUE["growth"]) ** (np.arange(T) / 52.0)
    D = base[None, :] * trend[:, None] * seas[woy][:, None] * ratio ** (-eps[None, :]) * np.exp(sd * u - 0.5 * sd ** 2)

    # ------------------------------------------------------------------ operations: reorder policy, FIFO, cash
    crisis_starts = [int(T * f) for f in (0.22, 0.52, 0.80)]
    def lead_for(t_order: int) -> int:
        L = max(2, int(round(rng.normal(TRUE["lead_weeks_mean"], TRUE["lead_weeks_sd"]))))
        if any(cs <= t_order < cs + 7 for cs in crisis_starts):
            L += int(rng.integers(3, 7))
        elif rng.random() < 0.04:
            L += int(rng.integers(2, 4))
        return L

    layers = [deque() for _ in range(P)]                  # (kg, unit_cost)
    for i in range(P):
        layers[i].append([6 * BASE_KG[PRODUCTS[i]], rcu[0, i] * 0.97])
    pipeline: list[dict] = []
    shipments: list[dict] = []
    sold = np.zeros((T, P)); unmet = np.zeros((T, P)); cogs = np.zeros((T, P)); shrink_kg = np.zeros((T, P)); shrink_cost = np.zeros((T, P))
    onhand_end = np.zeros((T, P)); inv_val = np.zeros((T, P)); storage = np.zeros((T, P))
    revenue = np.zeros((T, P))
    demand_ewma = base.copy()
    w_rec = np.array(TRUE["recv_weights"])
    opex_total = np.zeros(T); opex_parts = np.zeros((T, 5))
    comp = np.array([0.45, 0.12, 0.13, 0.18, 0.12])
    cash = np.zeros(T); debt = np.zeros(T); int_inc = np.zeros(T); int_exp = np.zeros(T); borrow = np.zeros(T); divs = np.zeros(T)
    receipts = np.zeros(T); recv_end = np.zeros(T)
    pay_order = np.zeros(T); pay_landing = np.zeros(T)
    sales_hist = np.zeros(T + len(w_rec) + 2)
    rev0 = float((D[0] * S[0]).sum())
    sales_hist[:len(w_rec)] = rev0 * 0.98                    # pre-history sales still being collected
    opex_base = TRUE["opex_pct_of_revenue"] * rev0
    cash_prev = 10 * opex_base; debt_prev = 0.0
    outflow_ewma = opex_base * 6
    cash[:] = 0
    for t in range(T):
        # --- arrivals
        landing_t = 0.0
        for sh in [x for x in pipeline if x["arr"] == t]:
            i = sh["i"]
            land_irr = sh["kg"] * sh["fob"] * fx_eff[t] * sh["land_pct"]
            landing_t += land_irr
            unit = (sh["pay_irr"] + land_irr) / sh["kg"]
            layers[i].append([sh["kg"], unit])
            pipeline.remove(sh)
        # --- reorder every 2 weeks (company's naive rule: ~11 weeks of cover on a moving demand estimate)
        paid = 0.0
        if t % 2 == 0 and t < T - 3:
            for i in range(P):
                onhand = sum(l[0] for l in layers[i]); pipe = sum(x["kg"] for x in pipeline if x["i"] == i)
                target = demand_ewma[i] * 11.0
                q = max(0.0, target - onhand - pipe)
                q = float(np.floor(q / 2500.0) * 2500.0)
                if q >= 5000.0:
                    L = lead_for(t)
                    lp = float(np.clip(rng.normal(land * 100, 1.5), 9, 18))
                    ins = float(np.clip(rng.normal(0.8, 0.15), 0.4, 1.4)); frt = float(np.clip(rng.normal(5.2, 1.3), 2, 10))
                    cus = float(lp - ins - frt)
                    fee_pct = float(np.clip(rng.normal(TRUE["transfer_fee_pct"], 0.2), 0.5, 2.5))
                    fob = float(price[t, i] * (1 + 0.004 * rng.standard_normal()))
                    pay_irr = q * fob * fx_eff[t] * (1 + fee_pct / 100.0)
                    paid += pay_irr
                    arr = t + L
                    sid = f"SH{len(shipments) + 1:04d}"
                    shipments.append(dict(shipment_id=sid, product=PRODUCTS[i], order_date=weeks[t], arrival_date=weeks[min(arr, T - 1)] + pd.Timedelta(weeks=max(0, arr - (T - 1))),
                                          kg=q, fob_usd_kg=fob, fx_paid_irr=float(fx_eff[t]), transfer_fee_pct=fee_pct, freight_pct=frt, insurance_pct=ins, customs_pct=cus))
                    pipeline.append(dict(i=i, kg=q, arr=arr, fob=fob, pay_irr=pay_irr, land_pct=lp / 100.0))
        pay_order[t] = paid; pay_landing[t] = landing_t
        # --- sales (FIFO)
        for i in range(P):
            avail = sum(l[0] for l in layers[i])
            s_kg = min(D[t, i], avail)
            sold[t, i] = s_kg; unmet[t, i] = D[t, i] - s_kg
            rem = s_kg; c = 0.0
            while rem > 1e-9 and layers[i]:
                lay = layers[i][0]; take = min(lay[0], rem)
                c += take * lay[1]; lay[0] -= take; rem -= take
                if lay[0] <= 1e-9:
                    layers[i].popleft()
            cogs[t, i] = c; revenue[t, i] = s_kg * S[t, i]
            tot = sum(l[0] for l in layers[i])
            sk = TRUE["shrink_pct_week"] / 100.0 * tot
            if tot > 0:
                shrink_cost[t, i] = sum(l[0] * l[1] for l in layers[i]) * TRUE["shrink_pct_week"] / 100.0
                for l in layers[i]:
                    l[0] *= (1 - TRUE["shrink_pct_week"] / 100.0)
            shrink_kg[t, i] = sk
            onhand_end[t, i] = sum(l[0] for l in layers[i])
            inv_val[t, i] = sum(l[0] * l[1] for l in layers[i])
            storage[t, i] = TRUE["storage_pct_week"] / 100.0 * inv_val[t, i]
            demand_ewma[i] = 0.85 * demand_ewma[i] + 0.15 * D[t, i] * 1.05
        rev_t = revenue[t].sum()
        sales_hist[t + len(w_rec)] = rev_t
        # --- collections: weekly revenue is collected with lag distribution
        receipts[t] = sum(w_rec[k] * sales_hist[t + len(w_rec) - k] for k in range(len(w_rec)))
        recv_end[t] = sum(sales_hist[t + len(w_rec) - k] * (1 - w_rec[:k + 1].sum()) for k in range(len(w_rec)))
        # --- opex
        scale = cpi[t] / cpi[0] * (1 + 0.02) ** (t / 52.0)
        o = opex_base * scale * (1 + 0.04 * rng.standard_normal())
        parts = o * comp * (1 + 0.05 * rng.standard_normal(5))
        if t % 4 == 0:
            parts[1] *= 3.2                                  # rent paid monthly (lumpy)
        else:
            parts[1] *= 0.27
        opex_parts[t] = parts; opex_total[t] = parts.sum()
        # --- cash and short-term financing
        inc = TRUE["deposit_rate_pct"] / 100 / 52 * max(cash_prev, 0.0)
        exp_ = TRUE["borrow_rate_pct"] / 100 / 52 * debt_prev
        c = cash_prev + receipts[t] - paid - landing_t - opex_total[t] - storage[t].sum() + inc - exp_
        outflow_ewma = 0.9 * outflow_ewma + 0.1 * (paid + landing_t + opex_total[t])
        lo, hi = 3.0 * opex_base * scale, 8.0 * opex_base * scale + 0.4 * outflow_ewma
        d = debt_prev
        if c < lo:
            b = lo - c; d += b; c = lo; borrow[t] = b
        elif c > hi:
            rep = min(d, c - hi); d -= rep; c -= rep
            if c > hi and d <= 1e-6:
                divs[t] = c - hi; c = hi
        cash[t], debt[t], int_inc[t], int_exp[t] = c, d, inc, exp_
        cash_prev, debt_prev = c, d

    # ------------------------------------------------------------------ tables
    wk = pd.Series(weeks)
    def r0(x):
        return np.round(x, 0)
    tab: dict[str, pd.DataFrame] = {}
    tab["market_weekly"] = pd.DataFrame({
        "week_end": weeks, "arabica_c_lb": np.round(ara, 2), "arabica_stale": stale.astype(int),
        "price_washed_usd_kg": np.round(price[:, 0], 3), "price_natural_usd_kg": np.round(price[:, 1], 3),
        "price_robusta_usd_kg": np.round(price[:, 2], 3), "price_specialty_usd_kg": np.round(price[:, 3], 3),
        "fx_market_irr": np.round(fx_mkt, 0), "fx_effective_irr": np.round(fx_eff, 0), "cpi_index": np.round(cpi, 3)})
    rows = []
    for i, p in enumerate(PRODUCTS):
        rows.append(pd.DataFrame({"week_end": weeks, "product": p, "kg_sold": np.round(sold[:, i], 1), "unmet_kg": np.round(unmet[:, i], 1),
                                  "avg_price_irr_kg": r0(S[:, i]), "revenue_irr": r0(revenue[:, i])}))
    tab["sales_weekly"] = pd.concat(rows).sort_values(["week_end", "product"]).reset_index(drop=True)
    sh = pd.DataFrame(shipments)
    for c_ in ("kg", "fob_usd_kg", "fx_paid_irr", "transfer_fee_pct", "freight_pct", "insurance_pct", "customs_pct"):
        sh[c_] = sh[c_].round(3 if c_ != "kg" and c_ != "fx_paid_irr" else 1)
    sh["order_date"] = pd.to_datetime(sh["order_date"]); sh["arrival_date"] = pd.to_datetime(sh["arrival_date"])
    tab["purchases"] = sh
    rows = []
    for i, p in enumerate(PRODUCTS):
        rows.append(pd.DataFrame({"week_end": weeks, "product": p, "on_hand_kg": np.round(onhand_end[:, i], 1), "shrink_kg": np.round(shrink_kg[:, i], 2),
                                  "storage_cost_irr": r0(storage[:, i]), "inventory_value_irr": r0(inv_val[:, i])}))
    tab["inventory_weekly"] = pd.concat(rows).sort_values(["week_end", "product"]).reset_index(drop=True)
    tab["collections_weekly"] = pd.DataFrame({"week_end": weeks, "receipts_irr": r0(receipts), "receivables_end_irr": r0(recv_end)})
    tab["opex_weekly"] = pd.DataFrame({"week_end": weeks, "salaries_irr": r0(opex_parts[:, 0]), "rent_irr": r0(opex_parts[:, 1]), "marketing_irr": r0(opex_parts[:, 2]),
                                       "logistics_irr": r0(opex_parts[:, 3]), "other_irr": r0(opex_parts[:, 4]), "total_opex_irr": r0(opex_total)})
    tab["cash_weekly"] = pd.DataFrame({"week_end": weeks, "cash_end_irr": r0(cash), "debt_end_irr": r0(debt), "interest_income_irr": r0(int_inc),
                                       "interest_expense_irr": r0(int_exp), "borrowing_irr": r0(borrow), "dividends_irr": r0(divs)})
    rev, cg, st, sk_c = revenue.sum(1), cogs.sum(1), storage.sum(1), shrink_cost.sum(1)
    net = rev - cg - st - sk_c - opex_total + int_inc - int_exp
    tab["pnl_weekly"] = pd.DataFrame({"week_end": weeks, "revenue_irr": r0(rev), "cogs_irr": r0(cg), "gross_profit_irr": r0(rev - cg), "storage_irr": r0(st),
                                      "shrink_cost_irr": r0(sk_c), "opex_irr": r0(opex_total), "net_interest_irr": r0(int_inc - int_exp), "net_profit_irr": r0(net)})
    fy = np.array([fiscal_year(w) for w in weeks])
    ann = pd.DataFrame({"fiscal_year": fy, "volume_kg": sold.sum(1), "revenue_irr": rev, "cogs_irr": cg, "gross_profit_irr": rev - cg, "storage_irr": st,
                        "shrink_cost_irr": sk_c, "opex_irr": opex_total, "net_interest_irr": int_inc - int_exp, "net_profit_irr": net})
    a = ann.groupby("fiscal_year").sum().reset_index()
    a.insert(1, "jalali_year", a["fiscal_year"] - 621)
    tab["annual_pnl"] = a.round(0)
    last_of_fy = pd.DataFrame({"fiscal_year": fy, "i": np.arange(T)}).groupby("fiscal_year")["i"].max()
    bal = pd.DataFrame({"fiscal_year": last_of_fy.index, "jalali_year": last_of_fy.index - 621, "cash_irr": cash[last_of_fy.values],
                        "receivables_irr": recv_end[last_of_fy.values], "inventory_irr": inv_val.sum(1)[last_of_fy.values], "debt_irr": debt[last_of_fy.values]})
    bal["equity_irr"] = bal["cash_irr"] + bal["receivables_irr"] + bal["inventory_irr"] - bal["debt_irr"]
    tab["annual_balance"] = bal.round(0)
    rows = []
    for i, p in enumerate(PRODUCTS):
        d_ = pd.DataFrame({"fiscal_year": fy, "kg": sold[:, i], "revenue_irr": revenue[:, i], "cogs_irr": cogs[:, i]}).groupby("fiscal_year").sum().reset_index()
        d_.insert(1, "jalali_year", d_["fiscal_year"] - 621); d_.insert(2, "product", p)
        rows.append(d_)
    tab["annual_by_product"] = pd.concat(rows).sort_values(["fiscal_year", "product"]).round(0).reset_index(drop=True)

    # ------------------------------------------------------------------ injected data-quality issues
    issues = []
    sales = tab["sales_weekly"]
    for k in rng.choice(len(sales), 2, replace=False):
        sales.loc[k, ["kg_sold", "revenue_irr"]] = np.nan
        issues.append({"table": "sales_weekly", "type": "missing", "week_end": str(sales.loc[k, "week_end"].date()), "product": sales.loc[k, "product"]})
    k = int(rng.integers(40, len(sales) - 40))
    tab["sales_weekly"] = pd.concat([sales.iloc[:k + 1], sales.iloc[[k]], sales.iloc[k + 1:]]).reset_index(drop=True)
    issues.append({"table": "sales_weekly", "type": "duplicate_row", "week_end": str(sales.loc[k, "week_end"].date()), "product": sales.loc[k, "product"]})
    sales = tab["sales_weekly"]
    kk = int(sales.index[(sales["product"] == "washed") & sales["kg_sold"].notna()][120])
    sales.loc[kk, "kg_sold"] *= 10
    issues.append({"table": "sales_weekly", "type": "outlier_x10", "week_end": str(sales.loc[kk, "week_end"].date()), "product": "washed"})
    pk = int(rng.integers(5, len(tab["purchases"]) - 5))
    tab["purchases"].loc[pk, "fx_paid_irr"] = 0.0
    issues.append({"table": "purchases", "type": "bad_entry_fx_zero", "shipment_id": tab["purchases"].loc[pk, "shipment_id"]})

    # ------------------------------------------------------------------ ground truth (population parameters of the generator)
    tot_sold_dec = D.sum(1) / (seas[woy])                    # deseasonalised total demand
    det = base[None, :] * trend[:, None] * seas[woy][:, None] * ratio ** (-eps[None, :])
    lr = np.log(D.sum(1) / det.sum(1))
    truth = dict(TRUE)
    truth.update(demand_cv_total=float(lr.std()), demand_fx_rho_total=float(np.corrcoef(lr, r_fx)[0, 1]),
                 markup_realized_last52_pct=float(np.average((S / rcu - 1)[-52:], weights=revenue[-52:] + 1) * 100))
    truth.update(
        products=PRODUCTS, elasticity=ELASTICITY, elasticity_weighted=float(np.average(eps, weights=sold.sum(0))),
        seasonal_index=seas.tolist(), demand_cv_per_product=float(np.sqrt(np.exp(sd ** 2) - 1)),
        fx_basis_factor_last104=float((fx_eff / fx_mkt)[-104:].mean()),
        weekly_demand_last13_kg=float(D[-13:].sum(1).mean()), weekly_demand_deseason_last13_kg=float(tot_sold_dec[-13:].mean()),
        recv_mean_lag_weeks=float(sum(k * w for k, w in enumerate(TRUE["recv_weights"]))),
        inflation_last52_pct=float((np.exp(dcpi[-52:].sum()) - 1) * 100),
        lead_median_weeks=float(TRUE["lead_weeks_mean"]), crisis_windows=[[str(weeks[c].date()), str(weeks[min(c + 6, T - 1)].date())] for c in crisis_starts],
        n_weeks=T, start=str(weeks[0].date()), end=str(weeks[-1].date()), injected_issues=issues,
        description="SYNTHETIC company; market series for arabica and USD/IRR are real, all company data and other bean prices are generated.")
    return tab, truth


def write_csv(tables: dict[str, pd.DataFrame], truth: dict, out_dir: str | Path) -> Path:
    import json
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    for name, df in tables.items():
        df.to_csv(out / f"{name}.csv", index=False, encoding="utf-8")
    (out / "ground_truth.json").write_text(json.dumps(truth, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    (out / "README.txt").write_text("SYNTHETIC DEMO COMPANY. Only arabica_c_lb and fx_market_irr in market_weekly are real market data; "
                                    "everything else is generated (see ground_truth.json). Not company data.\n", encoding="utf-8")
    return out
