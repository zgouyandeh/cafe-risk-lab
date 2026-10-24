"""Estimate scenario parameters from company tables. Every estimate carries value / se / 95% CI / n / method.
Nothing here is invented: each number is an explicit regression, ratio or order statistic on the company's own data."""
from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.optimize import nnls

from ..data.loaders import CENTS_LB_TO_USD_KG
from .schema import PRODUCTS

K_HARM = 6
MAX_LAG = 8


def _est(value, se=None, n=None, method="", unit="", scale=1.0):
    v = float(value)
    s = None if se is None or not np.isfinite(se) else float(se)
    return {"value": v, "se": s, "ci": None if s is None else [v - 1.96 * s, v + 1.96 * s], "n": n, "method": method, "unit": unit,
            "provenance": "data"}


def _woy(dates: pd.Series) -> np.ndarray:
    return np.array([min(int(d.isocalendar().week) - 1, 51) for d in dates])


def _fourier(woy: np.ndarray, K: int = K_HARM) -> np.ndarray:
    ang = 2 * np.pi * woy[:, None] * np.arange(1, K + 1)[None, :] / 52.0
    return np.hstack([np.sin(ang), np.cos(ang)])


def _vif(phi: float, h: int = 13) -> float:
    return 1 + 2 * sum((1 - k / h) * phi ** k for k in range(1, h))


def demand_block(T: dict) -> dict:
    s = T["sales_weekly"].copy(); m = T["market_weekly"].set_index("week_end")
    cpi = m["cpi_index"]
    out: dict = {}
    seas_curves, fits, resid_tot, tot_obs, tot_fit, eps_list, eps_se, wts = [], {}, [], None, None, [], [], []
    grid = np.arange(52)
    obs_sum = None; fit_sum = None
    for p in PRODUCTS:
        g = s[s["product"] == p].sort_values("week_end").set_index("week_end")
        g = g[~g.index.duplicated()]
        dem = (g["kg_sold"] + g["unmet_kg"].fillna(0)).clip(lower=1.0)
        idx = g.index
        t = np.arange(len(idx)) / 52.0
        real = np.log(g["avg_price_irr_kg"] / cpi.reindex(idx)).to_numpy()
        w = _woy(idx.to_series())
        X = np.column_stack([np.ones(len(idx)), t, real, _fourier(w)])
        y = np.log(dem.to_numpy())
        ok = np.isfinite(X).all(1) & np.isfinite(y)
        res = sm.OLS(y[ok], X[ok]).fit(cov_type="HAC", cov_kwds={"maxlags": 8})
        eps_list.append(-res.params[2]); eps_se.append(res.bse[2]); wts.append(dem.sum())
        b = res.params[3:]
        curve = np.exp(_fourier(grid) @ b)
        seas_curves.append(curve / curve.mean())
        fit = pd.Series(np.exp(X @ res.params + 0.5 * res.resid.var()), index=idx)
        fits[p] = (res, g, dem, w)
        obs_sum = dem if obs_sum is None else obs_sum.add(dem, fill_value=0)
        fit_sum = fit if fit_sum is None else fit_sum.add(fit, fill_value=0)
        out[f"elasticity_{p}"] = _est(-res.params[2], res.bse[2], int(ok.sum()), "OLS log-demand on log real price + trend + Fourier seasonality (HAC)")
    wts = np.array(wts) / sum(wts)
    eps = float(np.dot(wts, eps_list)); eps_s = float(np.dot(wts, eps_se))   # conservative: product errors share the common demand shock → treat as perfectly correlated
    out["demand_price_elasticity"] = _est(eps, eps_s, len(obs_sum), "میانگین وزنی کشش محصولات (وزن = حجم)")
    seas = np.average(np.array(seas_curves), axis=0, weights=wts); seas /= seas.mean()
    idx = obs_sum.index; w_all = _woy(idx.to_series())
    out["season_start_week"] = {"value": int((w_all[-1] + 1) % 52), "provenance": "data", "method": "هفته‌ی بعد از آخرین هفته‌ی داده", "se": None, "ci": None, "n": 1}
    out["seasonal_index"] = {"value": seas.tolist(), "se": None, "ci": None, "n": len(obs_sum), "provenance": "data",
                             "method": f"Fourier K={K_HARM} روی لگاریتم تقاضا، میانگین وزنی محصولات، نرمال‌شده به میانگین ۱", "unit": "ضریب"}
    # deseasonalised demand level (last 13 weeks)
    ds = (obs_sum.to_numpy() / seas[w_all])[-13:]
    out["weekly_demand_kg"] = _est(ds.mean(), ds.std(ddof=1) / np.sqrt(13), 13, "میانگین ۱۳ هفته‌ی اخیر (فروش+کمبود) تقسیم بر شاخص فصلی", "kg/هفته")
    # residuals, CV, AR1, FX correlation
    lr = np.log(obs_sum / fit_sum).dropna()
    sd = float(lr.std(ddof=1)); n = len(lr)
    cv = float(np.sqrt(np.exp(sd ** 2) - 1))
    out["demand_cv"] = _est(cv, cv / np.sqrt(2 * (n - 1)), n, "ضریب تغییرات باقیمانده‌ی لگاریتمی مجموع محصولات", "")
    phi = float(np.corrcoef(lr.values[1:], lr.values[:-1])[0, 1])
    out["demand_ar1"] = _est(phi, (1 - phi ** 2) / np.sqrt(n), n, "خودهمبستگی مرتبه‌ی ۱ باقیمانده‌ها")
    vif = _vif(max(phi, 0.0))
    out["demand_cv_horizon"] = _est(cv * np.sqrt(vif), None, n, f"CV×√VIF (13 هفته، φ={phi:.2f}) برای جمع تقاضای افق", "")
    out["demand_cv_horizon"]["vif"] = vif
    fx = np.log(m["fx_market_irr"]).diff().reindex(lr.index)
    ok = fx.notna()
    r = float(np.corrcoef(lr[ok], fx[ok])[0, 1]); z = np.arctanh(r); se_z = 1 / np.sqrt(ok.sum() - 3)
    out["demand_fx_rho"] = {"value": r, "se": float((np.tanh(z + se_z) - np.tanh(z - se_z)) / 2),
                            "ci": [float(np.tanh(z - 1.96 * se_z)), float(np.tanh(z + 1.96 * se_z))], "n": int(ok.sum()),
                            "method": "همبستگی باقیمانده‌ی تقاضا و بازده هفتگی دلار (فاصله‌ی اطمینان فیشر)", "unit": "", "provenance": "data"}
    return out


def passthrough_block(T: dict) -> dict:
    s = T["sales_weekly"]; m = T["market_weekly"].sort_values("week_end").set_index("week_end")
    dl_fx = np.log(m["fx_effective_irr"]).diff()
    dcpi = np.log(m["cpi_index"]).diff()
    rows = []
    for p in PRODUCTS:
        g = s[s["product"] == p].drop_duplicates("week_end").set_index("week_end")["avg_price_irr_kg"].reindex(m.index)
        lp = np.log(m[f"price_{p}_usd_kg"]) + np.log(m["fx_effective_irr"])
        dc = lp.diff()
        d = pd.DataFrame({"dS": np.log(g).diff(), "dcpi": dcpi, "gap": (np.log(g) - lp).shift(1)})
        for k in range(MAX_LAG + 1):
            d[f"up{k}"] = dc.clip(lower=0).shift(k); d[f"dn{k}"] = dc.clip(upper=0).shift(k)
        d["product"] = p
        rows.append(d.iloc[MAX_LAG + 1:].dropna())
    D = pd.concat(rows)
    dum = pd.get_dummies(D["product"], dtype=float)           # product-specific equilibrium margin (ECM intercept)
    cols = [f"up{k}" for k in range(MAX_LAG + 1)] + [f"dn{k}" for k in range(MAX_LAG + 1)]
    X = pd.concat([D[cols + ["dcpi", "gap"]], dum], axis=1)
    groups = pd.factorize(D.index)[0]
    res = sm.OLS(D["dS"], X).fit(cov_type="cluster", cov_kwds={"groups": groups})
    b = res.params; V = res.cov_params()
    out = {}
    rng = np.random.default_rng(0)
    draws = rng.multivariate_normal(b[cols].to_numpy(), V.loc[cols, cols].to_numpy(), 1000)
    for tag, name in (("up", "pass_through_up"), ("dn", "pass_through_down")):
        ix = [cols.index(f"{tag}{k}") for k in range(MAX_LAG + 1)]
        beta = b[cols].to_numpy()[ix]; tot = beta.sum()
        c = np.zeros(len(cols)); c[ix] = 1
        se = float(np.sqrt(c @ V.loc[cols, cols].to_numpy() @ c))
        ks = np.arange(MAX_LAG + 1)
        lag = float((ks * beta).sum() / tot) if abs(tot) > 1e-6 else float("nan")
        dr = draws[:, ix]; dtot = dr.sum(1); dl = (dr * ks).sum(1) / np.where(np.abs(dtot) > 1e-6, dtot, np.nan)
        out[name] = _est(tot, se, len(D), "مجموع ضرایب تأخیری ۰..۸ هفته (مثبت/منفی جدا) روی تغییر لگاریتمی هزینه‌ی جایگزینی؛ خوشه‌ای بر هفته")
        out["lag_up_weeks" if tag == "up" else "lag_down_weeks"] = _est(lag, np.nanstd(dl), len(D), "میانگین وزنی تأخیر ضرایب (روش دلتا/شبیه‌سازی)", "هفته")
    out["price_indexation"] = _est(b["dcpi"], res.bse["dcpi"], len(D), "ضریب تغییر شاخص قیمت در معادله‌ی قیمت فروش")
    out["ecm_speed"] = _est(b["gap"], res.bse["gap"], len(D), "سرعت بازگشت حاشیه به هدف (جمله‌ی تصحیح خطا)")
    out["_passthrough_r2"] = {"value": float(res.rsquared)}
    return out


def receivable_block(T: dict) -> dict:
    rev = T["sales_weekly"].groupby("week_end")["revenue_irr"].sum()
    rc = T["collections_weekly"].set_index("week_end")["receipts_irr"].reindex(rev.index)
    L = 10
    X = np.column_stack([rev.shift(k).to_numpy() for k in range(L + 1)])[L:]; y = rc.to_numpy()[L:]
    ok = np.isfinite(X).all(1) & np.isfinite(y)
    X, y = X[ok], y[ok]; sc = y.mean()
    w, _ = nnls(X / sc, y / sc)
    def stats(w_):
        w_ = w_ / w_.sum(); return float((np.arange(L + 1) * w_).sum())
    mean_lag = stats(w)
    rng = np.random.default_rng(1); r = y / sc - (X / sc) @ w; boots = []
    for _ in range(200):
        yb = (X / sc) @ w + rng.choice(r, len(r)); wb, _ = nnls(X / sc, yb); boots.append(stats(wb))
    e = _est(mean_lag, np.std(boots), int(ok.sum()), "NNLS: وصول هفته روی فروش‌های با تأخیر ۰..۱۰ ← میانگین تأخیر وزنی", "هفته")
    e["weights"] = (w / w.sum()).round(4).tolist()
    e["collected_share"] = float(w.sum())
    return {"receivable_lag_weeks": e}


def cost_block(T: dict) -> dict:
    p = T["purchases"].copy(); m = T["market_weekly"].set_index("week_end")
    done = p[p["arrival_date"] <= m.index.max()].copy()
    out = {}
    w = done["kg"] * done["fob_usd_kg"]
    pct = done["freight_pct"] + done["insurance_pct"] + done["customs_pct"]
    n = len(done)
    def wmean(x): 
        mu = float(np.average(x, weights=w)); sd = float(np.sqrt(np.average((x - mu) ** 2, weights=w))); return mu, sd / np.sqrt(n)
    mu, se = wmean(pct); out["landing_cost_pct"] = _est(mu, se, n, "میانگین وزنی (حمل+بیمه+گمرک) به‌درصد ارزش FOB", "%")
    mu, se = wmean(done["transfer_fee_pct"]); out["fx_transfer_cost_pct"] = _est(mu, se, n, "میانگین وزنی کارمزد انتقال ارز", "%")
    ok = (p["fx_paid_irr"] > 0)
    pp = p[ok].copy(); pp["fx_mkt"] = m["fx_market_irr"].reindex(pp["order_date"]).to_numpy()
    pp = pp.dropna(subset=["fx_mkt"]); pp = pp[pp["order_date"] >= pp["order_date"].max() - pd.Timedelta(weeks=104)]
    ratio = (pp["fx_paid_irr"] / pp["fx_mkt"]).to_numpy(); ww = (pp["kg"] * pp["fob_usd_kg"]).to_numpy()
    mu = float(np.average(ratio, weights=ww)); sd = float(np.sqrt(np.average((ratio - mu) ** 2, weights=ww)))
    out["fx_basis_factor"] = _est(mu, sd / np.sqrt(len(pp)), len(pp), "نسبت نرخ پرداختی به نرخ بازار در تاریخ سفارش، میانگین وزنی ۱۰۴ هفته", "×")
    # lead time and delay episodes (only completed shipments → no censoring)
    L = ((done["arrival_date"] - done["order_date"]).dt.days / 7.0).round()
    med = float(L.median())
    out["lead_time_days"] = _est(med * 7, 1.253 * L.std() / np.sqrt(n) * 7, n, "میانه‌ی (رسیدن − سفارش) محموله‌های تکمیل‌شده", "روز")
    extra = L - med; ep = extra >= 2
    pbar = float(ep.mean())
    out["import_delay_prob_pct"] = _est(pbar * 100, 100 * np.sqrt(pbar * (1 - pbar) / n), n, "سهم محموله‌هایی با ≥ ۲ هفته تأخیر بیش از میانه", "%")
    out["import_delay_days"] = _est(float(extra[ep].mean() * 7) if ep.any() else 0.0, float(extra[ep].std() / np.sqrt(max(ep.sum(), 1)) * 7) if ep.sum() > 1 else None,
                                    int(ep.sum()), "میانگین تأخیر اضافی در محموله‌های دارای تأخیر", "روز")
    out["_lead_weeks"] = {"value": L.tolist()}
    return out


def inventory_block(T: dict) -> dict:
    inv = T["inventory_weekly"]; g = inv.groupby("week_end")[["on_hand_kg", "shrink_kg", "storage_cost_irr", "inventory_value_irr"]].sum()
    st = (g["storage_cost_irr"] / g["inventory_value_irr"]).iloc[1:] * 100
    sh = (g["shrink_kg"] / (g["on_hand_kg"] + g["shrink_kg"])).iloc[1:] * 100
    out = {"storage_cost_pct_week": _est(st.mean(), st.std() / np.sqrt(len(st)), len(st), "هزینه‌ی انبار ÷ ارزش موجودی (متوسط هفتگی)", "% هفتگی"),
           "shrink_pct_week": _est(sh.mean(), sh.std() / np.sqrt(len(sh)), len(sh), "افت وزنی ÷ موجودی (متوسط هفتگی)", "% هفتگی"),
           "initial_inventory_kg": _est(g["on_hand_kg"].iloc[-1], None, 1, "موجودی آخرین هفته", "kg")}
    return out


def finance_block(T: dict) -> dict:
    c = T["cash_weekly"].sort_values("week_end").reset_index(drop=True); o = T["opex_weekly"]; m = T["market_weekly"]
    out = {}
    prev_cash = c["cash_end_irr"].shift(1).clip(lower=0); prev_debt = c["debt_end_irr"].shift(1)
    ok = prev_cash > 0
    r = (c["interest_income_irr"][ok] * 52 / prev_cash[ok]) * 100
    out["deposit_rate_pct"] = _est(r.mean(), r.std() / np.sqrt(len(r)), len(r), "سود دریافتی ×۵۲ ÷ نقد ابتدای هفته", "% سالانه")
    okd = prev_debt > 1e6
    if okd.sum() >= 3:
        rb = (c["interest_expense_irr"][okd] * 52 / prev_debt[okd]) * 100
        out["borrow_rate_pct"] = _est(rb.mean(), rb.std() / np.sqrt(len(rb)), int(okd.sum()), "سود پرداختی ×۵۲ ÷ بدهی ابتدای هفته (هفته‌های دارای بدهی)", "% سالانه")
    x = o["total_opex_irr"].iloc[-13:] / 1e9
    out["weekly_opex_bn_irr"] = _est(x.mean(), x.std(ddof=1) / np.sqrt(13), 13, "میانگین ۱۳ هفته‌ی اخیر", "میلیارد ریال")
    cpi = m.sort_values("week_end")["cpi_index"].to_numpy()
    out["inflation_pct"] = _est((cpi[-1] / cpi[-53] - 1) * 100, None, 52, "تغییر شاخص قیمت در ۵۲ هفته‌ی اخیر", "% سالانه")
    out["initial_receivables_bn_irr"] = _est(T["collections_weekly"].sort_values("week_end")["receivables_end_irr"].iloc[-1] / 1e9, None, 1, "مانده‌ی مطالبات آخرین هفته", "میلیارد ریال")
    cash = c["cash_end_irr"] / 1e9
    out["initial_cash_bn_irr"] = _est(cash.iloc[-1], None, 1, "نقد آخرین هفته", "میلیارد ریال")
    out["min_cash_bn_irr"] = _est(cash.quantile(0.05), None, len(cash), "صدک ۵٪ نقد هفتگی (کفی که شرکت عملاً نگه داشته)", "میلیارد ریال")
    out["initial_debt_bn_irr"] = _est(c["debt_end_irr"].iloc[-1] / 1e9, None, 1, "بدهی آخرین هفته", "میلیارد ریال")
    return out


def basket_block(T: dict) -> dict:
    p = T["purchases"]; m = T["market_weekly"].sort_values("week_end").set_index("week_end")
    last = p[(p["order_date"] >= m.index.max() - pd.Timedelta(weeks=104)) & (p["fx_paid_irr"] > 0)]
    val = (last["kg"] * last["fob_usd_kg"]).groupby(last["product"]).sum().reindex(PRODUCTS).fillna(0); w = val / val.sum()
    lp = sum(w[q] * np.log(m[f"price_{q}_usd_kg"]) for q in PRODUCTS)
    rb = lp.diff().dropna(); ra = np.log(m["arabica_c_lb"]).diff().reindex(rb.index)
    res = sm.OLS(rb, sm.add_constant(ra)).fit(cov_type="HAC", cov_kwds={"maxlags": 4})
    out = {"basket_beta": _est(res.params.iloc[1], res.bse.iloc[1], len(rb), "رگرسیون بازده سبد خرید (وزن ارزش خرید ۱۰۴ هفته) روی بازده آرابیکا (HAC)"),
           "basket_basis_vol_pct": _est(res.resid.std(ddof=2) * 100, res.resid.std() * 100 / np.sqrt(2 * len(rb)), len(rb), "انحراف معیار باقیمانده", "% هفتگی")}
    basket = sum(w[q] * m[f"price_{q}_usd_kg"] for q in PRODUCTS)
    ara = m["arabica_c_lb"] * CENTS_LB_TO_USD_KG
    d = (basket - ara).iloc[-13:]
    out["coffee_differential_usd_kg"] = _est(d.mean(), d.std(ddof=1) / np.sqrt(13), 13, "اختلاف قیمت سبد خرید (وزن خرید) با آرابیکای بورس، ۱۳ هفته", "USD/kg")
    out["_basket_weights"] = {"value": w.round(4).to_dict()}
    wk = p[(p["order_date"] >= m.index.max() - pd.Timedelta(weeks=26)) & (p["fx_paid_irr"] > 0)]
    out["recent_weekly_purchase_usd"] = _est((wk["kg"] * wk["fob_usd_kg"]).sum() / 26, None, len(wk), "میانگین هفتگی ارزش خرید FOB در ۲۶ هفته‌ی اخیر", "USD/هفته")
    out["recent_fob_usd_kg"] = _est((wk["kg"] * wk["fob_usd_kg"]).sum() / wk["kg"].sum(), None, len(wk), "میانگین وزنی قیمت FOB خریدهای ۲۶ هفته‌ی اخیر", "USD/kg")
    out["_current_fx_market"] = {"value": float(m["fx_market_irr"].iloc[-1])}
    return out


def pipeline_block(T: dict) -> dict:
    m = T["market_weekly"]; last = m["week_end"].max(); p = T["purchases"]
    inflight = p[(p["order_date"] <= last) & (p["arrival_date"] > last)].copy()
    inflight["weeks"] = np.ceil((inflight["arrival_date"] - last).dt.days / 7).astype(int)
    g = inflight.groupby("weeks")["kg"].sum()
    return {"pipeline": {"weeks": g.index.astype(int).tolist(), "kg": g.round(0).tolist(), "provenance": "data",
                         "method": "محموله‌های پرداخت‌شده که هنوز نرسیده‌اند (لیست خرید)", "value": float(g.sum())}}


def margin_block(T: dict, landing_pct: float, fee_pct: float) -> dict:
    s = T["sales_weekly"]; m = T["market_weekly"].set_index("week_end")
    s = s[s["week_end"] >= m.index.max() - pd.Timedelta(weeks=52)].drop_duplicates(["week_end", "product"])
    rc = np.array([m.loc[w, f"price_{pp}_usd_kg"] * m.loc[w, "fx_effective_irr"] for w, pp in zip(s["week_end"], s["product"])]) * (1 + landing_pct / 100) * (1 + fee_pct / 100)
    r = (s["avg_price_irr_kg"].to_numpy() / rc) - 1; w = s["revenue_irr"].fillna(0).to_numpy() + 1
    mu = float(np.average(r, weights=w)); sd = float(np.sqrt(np.average((r - mu) ** 2, weights=w)))
    return {"target_markup_pct": _est(mu * 100, sd * 100 / np.sqrt(len(r)), len(r), "میانگین وزنی (قیمت فروش ÷ هزینه‌ی جایگزینی − ۱) در ۵۲ هفته", "%")}


def estimate_all(T: dict) -> dict:
    est = {}
    est.update(demand_block(T)); est.update(passthrough_block(T)); est.update(receivable_block(T))
    c = cost_block(T); est.update(c)
    est.update(inventory_block(T)); est.update(finance_block(T)); est.update(basket_block(T)); est.update(pipeline_block(T))
    est.update(margin_block(T, c["landing_cost_pct"]["value"], c["fx_transfer_cost_pct"]["value"]))
    return est
