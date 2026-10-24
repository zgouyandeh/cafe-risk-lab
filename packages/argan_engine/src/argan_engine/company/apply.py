"""Map company estimates onto Scenario fields (+ provenance and world-prior widths)."""
from __future__ import annotations

SE_INFLATION = 2.0     # estimator SE is sampling error only; model-misspecification uncertainty is covered by a x2 inflation
HORIZON_WEEKS = 13

DIRECT = {  # scenario field -> estimate key
    "weekly_demand_kg": "weekly_demand_kg", "demand_cv": "demand_cv_horizon", "demand_price_elasticity": "demand_price_elasticity",
    "demand_fx_rho": "demand_fx_rho", "landing_cost_pct": "landing_cost_pct", "storage_cost_pct_week": "storage_cost_pct_week",
    "shrink_pct_week": "shrink_pct_week", "initial_inventory_kg": "initial_inventory_kg", "pass_through_up": "pass_through_up",
    "pass_through_down": "pass_through_down", "price_indexation": "price_indexation", "target_markup_pct": "target_markup_pct",
    "initial_cash_bn_irr": "initial_cash_bn_irr", "min_cash_bn_irr": "min_cash_bn_irr", "weekly_opex_bn_irr": "weekly_opex_bn_irr",
    "deposit_rate_pct": "deposit_rate_pct", "borrow_rate_pct": "borrow_rate_pct", "inflation_pct": "inflation_pct",
    "fx_basis_factor": "fx_basis_factor", "fx_transfer_cost_pct": "fx_transfer_cost_pct", "basket_beta": "basket_beta",
    "basket_basis_vol_pct": "basket_basis_vol_pct", "coffee_differential_usd_kg": "coffee_differential_usd_kg",
    "import_delay_prob_pct": "import_delay_prob_pct", "initial_receivables_bn_irr": "initial_receivables_bn_irr",
}
INT_FIELDS = {"import_delay_days": "import_delay_days", "lag_up_weeks": "lag_up_weeks", "lag_down_weeks": "lag_down_weeks", "receivable_lag_weeks": "receivable_lag_weeks",
              "lead_time_days": "lead_time_days"}


def to_overrides(est: dict, synthetic: bool = True) -> dict:
    """Returns {"fields": {...}, "provenance": {field: {...}}, "param_se": {...}, "synthetic": bool}."""
    f, prov = {}, {}
    def note(k, key, kind="data"):
        e = est[key]
        prov[k] = {"source": kind, "estimate_key": key, "se": e.get("se"), "n": e.get("n"), "method": e.get("method")}
    for k, key in DIRECT.items():
        if key in est:
            v = est[key]["value"]
            if k == "borrow_rate_pct" and "deposit_rate_pct" in f:
                v = max(v, f["deposit_rate_pct"])
            f[k] = float(v); note(k, key)
    for k, key in INT_FIELDS.items():
        if key in est:
            v = est[key]["value"]
            f[k] = int(round(v / 7)) if k == "lead_time_days" and False else int(round(v)); note(k, key)
    if "lead_time_days" in f:
        f["lead_time_days"] = int(round(est["lead_time_days"]["value"] / 7)) * 7
    f["demand_seasonal_index"] = [float(x) for x in est["seasonal_index"]["value"]]; prov["demand_seasonal_index"] = {"source": "data", "method": est["seasonal_index"]["method"], "n": est["seasonal_index"]["n"]}
    f["season_start_week"] = int(est["season_start_week"]["value"])
    f["pipeline_weeks"] = list(est["pipeline"]["weeks"]); f["pipeline_kg"] = list(est["pipeline"]["kg"])
    # purchase need over the decision horizon = demand over the horizon (seasonal) - stock - pipeline, valued at recent FOB
    seas = est["seasonal_index"]["value"]; d = f["weekly_demand_kg"]
    need_kg = max(0.0, d * HORIZON_WEEKS * 1.0 - f["initial_inventory_kg"] - sum(f["pipeline_kg"]))
    f["purchase_budget_usd"] = float(min(max(round(need_kg * est["recent_fob_usd_kg"]["value"], -3), 10_000), 5_000_000))
    prov["purchase_budget_usd"] = {"source": "data", "method": f"نیاز خالص افق ({HORIZON_WEEKS} هفته) = تقاضا − موجودی − در راه، به قیمت FOB اخیر (پیشنهاد؛ قابل تغییر)"}
    f["schedule_days"] = [0, 14, 28, 42]; prov["schedule_days"] = {"source": "judgment", "method": "شرکت بزرگ هر دو هفته سفارش می‌دهد؛ نقاط سفارش ۰/۱۴/۲۸/۴۲ روز"}
    se = {}
    for key, name in (("pass_through_up", "pass_through_up"), ("pass_through_down", "pass_through_down"),
                      ("demand_fx_rho", "demand_fx_rho"), ("demand_cv_horizon", "demand_cv")):
        if est[key].get("se"):
            se[name] = float(est[key]["se"]) * SE_INFLATION
    e = est["weekly_demand_kg"]
    if e.get("se"):
        se["weekly_demand_rel"] = float(e["se"] / e["value"]) * SE_INFLATION
    return {"fields": f, "provenance": prov, "param_se": se, "synthetic": synthetic, "se_inflation": SE_INFLATION}


def recovery_table(est: dict, truth: dict) -> list[dict]:
    """Compare estimates with the generator's known truth (demo only)."""
    t = truth
    pairs = [
        ("demand_price_elasticity", t["elasticity_weighted"], "کشش قیمتی تقاضا"),
        ("weekly_demand_kg", t["weekly_demand_deseason_last13_kg"], "تقاضای هفتگی (بدون فصل)"),
        ("demand_cv", t["demand_cv_total"], "ضریب تغییرات تقاضا"),
        ("demand_fx_rho", t["demand_fx_rho_total"], "همبستگی تقاضا–دلار"),
        ("pass_through_up", t["pass_up"], "انتقال افزایش هزینه"),
        ("pass_through_down", t["pass_down"], "انتقال کاهش هزینه"),
        ("lag_up_weeks", t["lag_up"], "تأخیر انتقال افزایش (هفته)"),
        ("lag_down_weeks", t["lag_down"], "تأخیر انتقال کاهش (هفته)"),
        ("price_indexation", t["indexation"], "ضریب تورمی قیمت"),
        ("receivable_lag_weeks", t["recv_mean_lag_weeks"], "میانگین تأخیر وصول (هفته)"),
        ("landing_cost_pct", t["landing_pct"], "هزینه‌ی ترخیص و حمل (٪)"),
        ("fx_transfer_cost_pct", t["transfer_fee_pct"], "کارمزد انتقال ارز (٪)"),
        ("fx_basis_factor", t["fx_basis_factor_last104"], "ضریب نرخ مؤثر / بازار"),
        ("lead_time_days", t["lead_median_weeks"] * 7, "زمان تحویل (روز)"),
        ("storage_cost_pct_week", t["storage_pct_week"], "هزینه‌ی انبار (٪ هفتگی)"),
        ("shrink_pct_week", t["shrink_pct_week"], "افت (٪ هفتگی)"),
        ("deposit_rate_pct", t["deposit_rate_pct"], "نرخ سپرده (٪)"),
        ("borrow_rate_pct", t["borrow_rate_pct"], "نرخ استقراض (٪)"),
        ("inflation_pct", t["inflation_last52_pct"], "تورم ۵۲ هفته (٪)"),
        ("target_markup_pct", t["markup_realized_last52_pct"], "حاشیه‌ی قیمت فروش به هزینه‌ی جایگزینی (٪)"),
    ]
    out = []
    for key, truth_v, label in pairs:
        if key not in est:
            continue
        e = est[key]; v = e["value"]; se = e.get("se")
        err = v - truth_v
        scale = abs(truth_v) if abs(truth_v) > 1e-9 else 1.0
        in_ci = bool(e["ci"] and e["ci"][0] <= truth_v <= e["ci"][1])
        ok = in_ci or abs(err) / scale <= 0.10
        out.append({"key": key, "label": label, "estimate": v, "se": se, "truth": float(truth_v), "rel_err": float(err / scale), "in_ci": in_ci, "ok": ok})
    return out
