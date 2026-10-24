"""End-to-end analysis pipeline: Scenario + Calibration -> JSON-ready result dict."""
from __future__ import annotations

import time
from typing import Callable

import numpy as np

from .calibrate import Calibration
from .config import Scenario
from .optimize import (concat_worlds, convergence, PARAMS, PARAM_LABELS_FA, base_drift_annual_pct, crossing, evaluate_grid, flip_curve,
                       pareto_front, robust_select, run_worlds, select_best, sensitivity_spearman, weight_grid)
from .risk import STRESSES, cvar_lower, paired_diff, ssd_relation, stress_params
from .risk import decision_map as dmap
from .risk.reverse_stress import reverse_stress
from .risk.shapley import shapley
from .risk.metrics import bootstrap_ci
from .sim import apply_shock, build_market, orders_from_weights, simulate_policy, subset
from .sim.market import WEEKS_PER_YEAR, resolve_fx_kind

Q_LEVELS = [5, 25, 50, 75, 95]


def _bn(x) -> float:
    return float(x) / 1e9


def _find(W: np.ndarray, w: np.ndarray) -> int:
    return int(np.argmin(np.abs(W - np.asarray(w)).sum(axis=1)))


def _bands(a: np.ndarray, scale: float = 1.0) -> dict:
    q = np.percentile(a, Q_LEVELS, axis=0) / scale
    return {f"p{p}": q[i].tolist() for i, p in enumerate(Q_LEVELS)} | {"mean": (a.mean(axis=0) / scale).tolist()}


def carry_analysis(scn: Scenario, mkt) -> dict:
    """Closed-form-style 'carry' view: when is paying earlier cheaper than paying later?

    Buying a unit at week 0 instead of week w saves E[C_w]/C_0 − 1 of cost (expected cost growth)
    but costs the financing of that cash for w weeks plus extra storage/shrink. Break-even annualised
    depreciation = the cost growth that exactly offsets that carry."""
    rows = []
    for w in sorted(set(scn.schedule_weeks)):
        if w == 0:
            continue
        growth = float((mkt.RC[:, w] / mkt.RC[:, 0]).mean() - 1.0)           # expected replacement-cost growth
        fx_growth = float((mkt.X[:, w] / mkt.X[:, 0]).mean() - 1.0)
        coffee_growth = float((mkt.P[:, w] / mkt.P[:, 0]).mean() - 1.0)
        fin = {}
        for name, rate in (("deposit", scn.deposit_rate_pct), ("borrow", scn.borrow_rate_pct)):
            fin[name] = (1 + rate / 100) ** (w / WEEKS_PER_YEAR) - 1
        hold = (1 + scn.storage_cost_pct_week / 100 + scn.shrink_pct_week / 100) ** w - 1
        be = {k: float(((1 + f) * (1 + hold)) ** (WEEKS_PER_YEAR / w) - 1) for k, f in fin.items()}
        rows.append({"week": w, "day": int(w * 7), "expected_cost_growth": growth, "fx_growth": fx_growth,
                     "coffee_growth": coffee_growth, "financing": fin, "holding_cost": float(hold),
                     "net_advantage_deposit": growth - ((1 + fin["deposit"]) * (1 + hold) - 1),
                     "net_advantage_borrow": growth - ((1 + fin["borrow"]) * (1 + hold) - 1),
                     "breakeven_annual_cost_growth": be,
                     "expected_annual_cost_growth": float((1 + growth) ** (WEEKS_PER_YEAR / w) - 1)})
    return {"rows": rows}


def run_analysis(scn: Scenario, cal: Calibration, progress: Callable[[float, str], None] | None = None) -> dict:
    t0 = time.time()
    prog = progress or (lambda f, m: None)
    H, K = scn.horizon_weeks, len(scn.schedule_days)
    W = weight_grid(K, scn.grid_step)
    sw = scn.schedule_weeks

    # ---------------- nominal run ------------------------------------------------------------------
    prog(0.02, "شبیه‌سازی مونت‌کارلو")
    rng = np.random.default_rng(scn.seed)
    mkt = build_market(scn, cal, scn.n_paths, rng)
    ev = evaluate_grid(mkt, scn, W)
    nom = select_best(ev, scn)
    scale = ev.scale
    i_now = _find(W, np.eye(K)[0])
    i_eq = _find(W, np.full(K, 1.0 / K))
    i_late = _find(W, np.eye(K)[-1])
    i_unc = int(np.argmax(ev.J))                                   # unconstrained optimum

    # ---------------- robustness -------------------------------------------------------------------
    rs, wr = None, None
    i_rec, rec_basis = nom["idx"], "nominal"
    if scn.robust:
        prog(0.15, "تحلیل استحکام در جهان‌های ممکن")
        pr = lambda f: prog(0.15 + 0.4 * f, "تحلیل استحکام در جهان‌های ممکن")
        wr = run_worlds(scn, cal, W, progress=pr)
        conv_hist = []
        cv = convergence(wr, scn, W, seed=scn.seed + 11)
        conv_hist.append({"worlds": int(len(wr.J)), "close": cv["rows"][-1]["close"] if cv["rows"] else None})
        batch = 1
        while scn.worlds_auto and not cv["adequate"] and len(wr.J) < scn.n_worlds_max:
            prog(0.4, f"افزودن جهان‌های بیشتر برای همگرایی ({len(wr.J)} → {len(wr.J) + 20})")
            wr = concat_worlds(wr, run_worlds(scn, cal, W, n=20, batch=batch))
            batch += 1
            cv = convergence(wr, scn, W, seed=scn.seed + 11)
            conv_hist.append({"worlds": int(len(wr.J)), "close": cv["rows"][-1]["close"] if cv["rows"] else None})
        cv["history"] = conv_hist
        rs = robust_select(wr, scn)
        i_rec, rec_basis = rs["idx"], "robust"

    # ---------------- details for recommended + benchmarks -----------------------------------------
    prog(0.58, "محاسبه جزئیات سیاست توصیه‌شده")
    bench = {"recommended": i_rec, "all_now": i_now, "equal_split": i_eq, "all_late": i_late}
    if i_unc not in bench.values():
        bench["unconstrained_best"] = i_unc
    if nom["idx"] not in bench.values():
        bench["nominal_best"] = nom["idx"]
    traces = {}
    for name, i in bench.items():
        r = simulate_policy(mkt, scn, orders_from_weights(W[i], mkt.Q, sw), trace=True)
        traces[name] = r
    accounting = {}
    for name in ("recommended", "all_now"):
        r_ = traces[name]
        accounting[name] = {"delta_w_bn": _bn(r_.profit_nom.mean()), "fifo_profit_bn": _bn(r_.acct_profit.mean()), "shrink_cost_bn": _bn(-r_.shrink_cost.mean()),
                            "lost_cost_bn": _bn(-r_.lost_cost.mean()), "holding_gain_bn": _bn(r_.holding_gain.mean()),
                            "max_abs_error_rial": float(np.abs(r_.profit_nom - (r_.acct_profit - r_.shrink_cost - r_.lost_cost + r_.holding_gain)).max())}
    cmp_rows = {}
    x_rec = ev.profit[i_rec]
    for name, i in bench.items():
        x = ev.profit[i]
        pd_ = paired_diff(x_rec, x) if name != "recommended" else None
        cmp_rows[name] = {
            "idx": int(i), "weights": W[i].tolist(), "mean_bn": _bn(ev.mean[i]), "cvar_bn": _bn(ev.cvar[i]),
            "sd_bn": _bn(ev.sd[i]), "breach": float(ev.breach[i]), "unmet": float(ev.unmet[i]),
            "stockout": float(ev.stockout[i]), "floor": float(ev.floor[i]), "cover_breach": float(ev.cover[i]), "usd_mean": float(ev.usd_mean[i]), "acct_mean_bn": _bn(ev.acct_mean[i]),
            "feasible": bool(nom["mask"][i]), "J_bn": _bn(ev.J[i]),
            "vs_recommended": None if pd_ is None else {
                "mean_diff_bn": _bn(pd_["mean"]), "ci_lo_bn": _bn(pd_["lo"]), "ci_hi_bn": _bn(pd_["hi"]),
                "p_rec_better": pd_["p_better"],
                "cvar_diff_bn": _bn(cvar_lower(x_rec, scn.cvar_alpha) - cvar_lower(x, scn.cvar_alpha)),
                "ssd": ssd_relation(x_rec, x)}}
    scn_value = mkt.Q * mkt.RC_ref
    # ---------------- Pareto frontier ---------------------------------------------------------------
    pf = pareto_front(ev.mean, ev.cvar, nom["mask"])
    policies = [{"w": ev.weights[i].tolist(), "mean_bn": _bn(ev.mean[i]), "cvar_bn": _bn(ev.cvar[i]),
                 "breach": float(ev.breach[i]), "unmet": float(ev.unmet[i]), "feasible": bool(nom["mask"][i]),
                 "pareto": bool(i in set(pf.tolist()))} for i in range(len(W))]

    # ---------------- market fans -------------------------------------------------------------------
    fx_fan = _bands(mkt.X / mkt.X[:, [0]])
    coffee_fan = _bands(mkt.P / mkt.P[:, [0]])
    rc_fan = _bands(mkt.RC / 1e6)
    hist_edges = np.linspace(np.percentile(ev.profit, 0.5), np.percentile(ev.profit, 99.5), 41)
    dist = {}
    for name in ("recommended", "all_now", "equal_split"):
        h, _ = np.histogram(np.clip(ev.profit[bench[name]], hist_edges[0], hist_edges[-1]), bins=hist_edges)
        dist[name] = (h / h.sum()).tolist()
    centers = ((hist_edges[:-1] + hist_edges[1:]) / 2 / 1e9).tolist()
    trace_out = {}
    for name in ("recommended", "all_now", "equal_split"):
        r = traces[name]
        trace_out[name] = {"cash_bn": _bands(r.trace_cash, 1e9), "stock_kg": _bands(r.trace_stock)}

    # ---------------- named scenarios (common random numbers with the base run) ------------------------
    prog(0.64, "سناریوهای تنش")
    n_s = min(2500, mkt.n)
    base_s = subset(mkt, n_s)
    names4 = ("recommended", "all_now", "equal_split", "all_late")
    stress_out, Jscen, scen_ids = [], [], []
    for s_ in STRESSES:
        sp = stress_params(s_, scn)
        m2 = apply_shock(base_s, sp["scn"], **sp["shock"])
        evs = evaluate_grid(m2, sp["scn"], W, keep_profit=False)
        row = {"id": s_["id"], "group": s_["group"], "label_fa": s_["label_fa"], "desc_fa": s_["desc_fa"],
               "question_fa": s_["question_fa"], "policies": {}}
        for name in names4:
            i = bench[name]
            row["policies"][name] = {"mean_bn": _bn(evs.mean[i]), "cvar_bn": _bn(evs.cvar[i]), "breach": float(evs.breach[i]),
                                     "floor": float(evs.floor[i]), "unmet": float(evs.unmet[i]), "cover_breach": float(evs.cover[i])}
        row["best_idx"] = int(np.argmax(evs.J))
        row["best_weights"] = W[row["best_idx"]].tolist()
        stress_out.append(row)
        Jscen.append(evs.J / evs.scale)
        scen_ids.append(s_["id"])
    Jscen = np.array(Jscen)                                        # (S, P)
    # robust optimisation over the scenario set (worst-case J) -- a complement to the worlds-based choice
    wc = Jscen.min(axis=0)
    i_wc = int(np.argmax(wc))
    scen_robust = {"idx": i_wc, "weights": W[i_wc].tolist(), "worst_value_pct": float(wc[i_wc] * 100),
                   "worst_scenario": scen_ids[int(np.argmin(Jscen[:, i_wc]))],
                   "recommended_worst_value_pct": float(wc[i_rec] * 100),
                   "recommended_worst_scenario": scen_ids[int(np.argmin(Jscen[:, i_rec]))],
                   "agrees": bool(np.allclose(W[i_wc], W[i_rec])),
                   "regret_pct": float((wc[i_wc] - wc[i_rec]) * 100)}

    # ---------------- attribution: exact Shapley split of the severe-crisis loss -------------------------------
    prog(0.69, "تفکیک عوامل زیان (شاپلی)")
    sc = next(x for x in STRESSES if x["id"] == "severe_crisis")
    sp = stress_params(sc, scn)
    sh_ = sp["shock"]
    comps = {"fx": dict(fx=sh_["fx"]), "coffee": dict(coffee=sh_["coffee"]),
             "supply": dict(delay_weeks=sh_["delay_weeks"], landing_pct=sh_["landing_pct"]),
             "demand": dict(demand_shift_pct=sh_["demand_shift_pct"]), "receivable": {},
             "loss": dict(loss_share=sh_["loss_share"])}
    labels = {"fx": "جهش دلار", "coffee": "جهش قیمت قهوه", "supply": "تأخیر و گرانی حمل", "demand": "افت تقاضا",
              "receivable": "تأخیر وصول مطالبات", "loss": "گم‌شدن محموله و پیش‌پرداخت"}
    players = list(comps)
    lim_ = scn.min_cash_bn_irr * 1e9
    _cache: dict = {}
    def _state(S: frozenset) -> tuple[float, float]:
        if S not in _cache:
            kw = {}
            for k in S:
                kw.update(comps[k])
            scn_ = sp["scn"] if "receivable" in S else scn
            m_ = apply_shock(base_s, scn_, **kw) if kw else base_s
            r_ = simulate_policy(m_, scn_, orders_from_weights(W[i_rec], m_.Q, sw))
            _cache[S] = (float(r_.profit_real.mean()) / scn_value * 100, float((r_.min_cash < lim_).mean()))
        return _cache[S]
    sh_mean = shapley(players, lambda S: _state(S)[0])
    sh_br = shapley(players, lambda S: _state(S)[1])
    attr_rows = [{"factor": k, "label_fa": labels[k], "delta_pct": sh_mean["phi"][k], "breach": sh_br["phi"][k],
                  "alone_pct": _state(frozenset([k]))[0] - sh_mean["baseline"], "alone_breach": _state(frozenset([k]))[1] - sh_br["baseline"]}
                 for k in players]
    attribution = {"scenario": "severe_crisis", "method": "shapley", "base_breach": sh_br["baseline"], "total_delta_pct": sh_mean["total"],
                   "total_breach": sh_br["full"], "rows": attr_rows,
                   "interaction_pct": sh_mean["efficiency_gap"], "efficiency_gap_breach": sh_br["efficiency_gap"], "n_coalitions": sh_mean["n_evals"]}

    # ---------------- liquidity need under crisis (for the contingency plan) -----------------------------------
    cont_in = {}
    for sid in ("severe_crisis", "import_disruption"):
        s_ = next(x for x in STRESSES if x["id"] == sid)
        sp_ = stress_params(s_, scn)
        m_ = apply_shock(base_s, sp_["scn"], **sp_["shock"])
        r_ = simulate_policy(m_, sp_["scn"], orders_from_weights(W[i_rec], m_.Q, sw))
        lim_ = scn.min_cash_bn_irr * 1e9
        cont_in[sid] = {"min_cash_p5_bn": _bn(np.percentile(r_.min_cash, 5)), "min_cash_p50_bn": _bn(np.percentile(r_.min_cash, 50)),
                        "credit_need_p95_bn": _bn(max(0.0, lim_ - np.percentile(r_.min_cash, 5))),
                        "unmet_kg": float(r_.unmet_kg.mean()), "unmet_share": float(r_.unmet_kg.sum() / r_.demand_kg.sum())}

    # ---------------- reverse stress test ---------------------------------------------------------------------
    prog(0.72, "تست استرس معکوس")
    rpol = {"recommended": bench["recommended"], "all_now": bench["all_now"]}
    reverse = reverse_stress(subset(mkt, 1500), scn, cal, W, rpol)

    # ---------------- flip analysis ---------------------------------------------------------------------
    flips = {}
    if scn.flip_analysis:
        prog(0.72, "منحنی حساسیت تصمیم")
        d0 = base_drift_annual_pct(scn, cal)
        dvals = sorted(set(np.round(np.linspace(-10, max(d0 * 2.2, 100), 11), 1).tolist() + [round(d0, 1)]))
        rows_d = flip_curve(scn, cal, "fx_drift_annual_pct", dvals, W)
        pvals = [0, 10, 20, 30, 40, 50, 60]
        rows_p = flip_curve(scn, cal, "event_p_deal", pvals, W)
        lvals = sorted(set([7, 14, 21, 28, 35, 42, 56] + [scn.lead_time_days]))
        rows_l = flip_curve(scn.model_copy(update={"import_delay_prob_pct": 0.0}), cal, "lead_time_days", lvals, W)
        flips = {"drift": {"values": dvals, "rows": rows_d, "base": d0, "cross50": crossing(rows_d)},
                 "p_deal": {"values": pvals, "rows": rows_p, "base": scn.event_p_deal, "cross50": crossing(rows_p)},
                 "lead": {"values": lvals, "rows": rows_l, "base": scn.lead_time_days, "cross50": crossing(rows_l)}}

    # ---------------- break-even beliefs and two-dimensional decision map -----------------------------------
    dec_map = None
    if scn.flip_analysis:
        prog(0.8, "آستانه‌ی باور و نقشه‌ی تصمیم")
        dec_map = dmap.run(scn, cal, W, bench, base_drift_annual_pct(scn, cal))

    # ---------------- sensitivity (global, from worlds) ---------------------------------------------------
    sens = []
    worlds_out = None
    if wr is not None:
        tgt = (wr.J[:, i_rec] - wr.J[:, i_now]) / wr.scale        # recommended minus 'all now', per world
        sens = sensitivity_spearman(wr, tgt)
        beats_now = float((tgt > 0).mean())
        tgt2 = (wr.J[:, i_rec] - wr.J[:, i_eq]) / wr.scale
        worlds_out = {
            "n": int(len(wr.J)), "share_feasible_rec": float(rs["share_feasible"][i_rec]),
            "q90_regret_pct": float(rs["q_regret"][i_rec] * 100), "mean_regret_pct": float(rs["mean_regret"][i_rec] * 100),
            "rec_beats_all_now_share": beats_now, "rec_beats_equal_share": float((tgt2 > 0).mean()),
            "rec_best_in_world_share": float(rs["win_share"][i_rec]), "relaxed": bool(rs["relaxed"]),
            "diff_vs_now_pct": (tgt * 100).tolist(), "diff_vs_equal_pct": (tgt2 * 100).tolist(),
            "param_names": PARAMS, "param_labels_fa": [PARAM_LABELS_FA[p] for p in PARAMS],
            "params": wr.params.tolist(),
            "convergence": cv,
            "regret_rec_pct": (np.where(np.isfinite(rs["regret"][:, i_rec]), rs["regret"][:, i_rec], np.nan) * 100).tolist()}

    carry = carry_analysis(scn, mkt)
    # ---------------- assemble ----------------------------------------------------------------------------
    d0 = base_drift_annual_pct(scn, cal)
    res = {
        "meta": {"elapsed_s": round(time.time() - t0, 2), "as_of": cal.as_of, "coffee_last_date": str(cal.coffee_last_date), "H": H, "weeks": list(range(H + 1)),
                 "schedule_days": scn.schedule_days, "schedule_weeks": sw, "lead_weeks": scn.lead_weeks,
                 "Q_kg": mkt.Q, "purchase_value_bn_irr": _bn(scale), "fx_model": mkt.fx_model, "P_ref_c_lb": mkt.meta["P_ref_c_lb"],
                 "P_ref_usd_kg": mkt.meta["P_ref_usd_kg"], "X0": mkt.meta["X0"], "RC_ref": mkt.RC_ref, "S0": mkt.S0,
                 "coffee_gap_weeks": mkt.meta["gap_weeks"], "rho_cf": mkt.meta["rho_cf"], "fx_drift_annual_pct": d0,
                 "n_paths": scn.n_paths, "recommendation_basis": rec_basis, "n_policies": len(W),
                 "alpha": scn.cvar_alpha, "lambda": scn.risk_lambda, "crisis_lead_days": scn.crisis_lead_days,
                 "lead_days": scn.lead_weeks * 7, "safety_stock_kg": scn.safety_stock_weeks * scn.weekly_demand_kg,
                 "fx_basis_total": scn.fx_basis_total},
        "recommended": {"idx": int(i_rec), "weights": W[i_rec].tolist(), "nominal_feasible": bool(nom["mask"][i_rec]),
                        "any_feasible": bool(nom["feasible"]), "nominal_best_idx": int(nom["idx"]),
                        "nominal_best_weights": W[nom["idx"]].tolist()},
        "benchmarks": cmp_rows, "policies": policies,
        "fans": {"fx": fx_fan, "coffee": coffee_fan, "rc_million": rc_fan},
        "dist": {"centers_bn": centers, **dist}, "traces": trace_out,
        "stress": stress_out, "scenario_robust": scen_robust, "contingency_inputs": cont_in, "attribution": attribution, "reverse": reverse, "flip": flips, "decision_map": dec_map, "accounting": accounting, "sensitivity": sens, "worlds": worlds_out, "carry": carry,
        "market_stats": {"fx_up_prob": float((mkt.X[:, -1] > mkt.X[:, 0]).mean()),
                         "fx_p5": float(np.percentile(mkt.X[:, -1] / mkt.X[:, 0], 5)),
                         "fx_p95": float(np.percentile(mkt.X[:, -1] / mkt.X[:, 0], 95)),
                         "fx_mean": float((mkt.X[:, -1] / mkt.X[:, 0]).mean()),
                         "coffee_p5": float(np.percentile(mkt.P[:, -1] / mkt.P[:, 0], 5)),
                         "coffee_p95": float(np.percentile(mkt.P[:, -1] / mkt.P[:, 0], 95)),
                         "turbulent_share": None if mkt.fx_states is None else float((mkt.fx_states == mkt.fx_states.max()).mean())},
    }
    prog(1.0, "پایان")
    return res
