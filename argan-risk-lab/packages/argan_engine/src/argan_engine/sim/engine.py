"""Weekly inventory / cash engine with explicit event order, lead time, receivables and FIFO.

Event order inside week t (documented in docs/METHODOLOGY.md):
 1. orders scheduled for week t are placed; the prepaid share of the USD invoice is paid at the week-t rate
    (invoice USD price fixed at order date); fixed-USD mode scales kg by P_ref / P_t
 2. orders placed in week t-L (+ delay) arrive and join on-hand stock; the invoice balance is paid at the arrival-week rate
 3. demand D_t is realised; sales = min(D_t, on-hand); the rest is lost (no back-orders)
 4. FIFO cost of goods sold; storage cost on average stock; shrink on closing stock
 5. operating cost is paid; cash trough is recorded (conservatively before this week's receipts)
 6. receipts from sales made in week t-R arrive; interest accrues on the closing balance
Terminal wealth = cash + receivables + stock (on-hand + in-transit) at replacement cost - unpaid invoice balance of\ngoods still in transit (at the end-of-horizon rate). Shipments that never arrive are neither stocked nor settled.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..config import Scenario
from .market import WEEKS_PER_YEAR, MarketPaths


@dataclass
class PolicyResult:
    profit_nom: np.ndarray
    profit_real: np.ndarray
    profit_usd: np.ndarray
    acct_profit: np.ndarray        # FIFO accounting profit (no inventory revaluation)
    min_cash: np.ndarray
    unmet_kg: np.ndarray
    demand_kg: np.ndarray
    end_stock_kg: np.ndarray
    min_stock_kg: np.ndarray       # lowest on-hand stock at any week end
    paid: np.ndarray               # total rial paid for purchases
    interest: np.ndarray
    shrink_cost: np.ndarray | None = None   # cost of goods lost to shrink
    lost_cost: np.ndarray | None = None     # cost of shipments that never arrived (prepayment lost)
    paid_order: np.ndarray | None = None    # rial paid when orders were placed (prepayments)
    paid_arrival: np.ndarray | None = None  # rial paid when goods arrived (settlement of the invoice balance)
    ap_end: np.ndarray | None = None        # unpaid invoice balance of goods still in transit at the end of the horizon
    holding_gain: np.ndarray | None = None  # (end stock at replacement cost - at cost) - revaluation of opening stock
    trace_cash: np.ndarray | None = None
    trace_stock: np.ndarray | None = None


def orders_from_weights(weights, Q: float, schedule_weeks: list[int]) -> list[tuple[int, float]]:
    return [(int(w), float(x) * Q) for w, x in zip(schedule_weeks, weights) if x > 1e-12]


def simulate_policy(mkt: MarketPaths, scn: Scenario, orders: list[tuple[int, float]],
                    trace: bool = False) -> PolicyResult:
    n, H = mkt.n, mkt.H
    L, R = scn.lead_weeks, scn.receivable_lag_weeks
    r_dep = (1 + scn.deposit_rate_pct / 100) ** (1 / WEEKS_PER_YEAR) - 1
    r_bor = (1 + scn.borrow_rate_pct / 100) ** (1 / WEEKS_PER_YEAR) - 1
    st, sh = scn.storage_cost_pct_week / 100, scn.shrink_pct_week / 100
    cash0 = scn.initial_cash_bn_irr * 1e9 if mkt.cash0 is None else mkt.cash0
    opex0 = scn.weekly_opex_bn_irr * 1e9 if mkt.opex0 is None else mkt.opex0
    rc_ref = np.full(n, mkt.RC_ref) if mkt.rc_ref_path is None else mkt.rc_ref_path

    # FIFO layers: [arrival_week, qty(n), unit_cost(n)] ; layer 0 = opening stock
    # layer = [base_arrival_week, qty(n), unit_cost(n), arrival_week_per_path(n)]; the per-path arrival
    # includes the (possibly random) import delay.
    delay = np.zeros(n, dtype=int) if mkt.delay_w is None else mkt.delay_w
    lost = np.zeros(n, dtype=bool) if mkt.lost_w is None else mkt.lost_w
    BIG = 10 ** 6
    q_orig = [np.full(n, scn.initial_inventory_kg)]
    layers = [[0, np.full(n, scn.initial_inventory_kg), rc_ref, np.zeros(n, dtype=int)]]
    order_by_week: dict[int, list[tuple[float, int]]] = {}
    alpha = scn.prepay_fraction_pct / 100.0
    budget_mode = scn.purchase_mode == "fixed_usd_budget"
    P_ref = mkt.meta.get("P_ref_usd_kg", None)
    land = 1.0 + scn.landing_cost_pct / 100.0
    meta: dict[int, dict] = {}                                   # per ordered layer: order-date USD price, prepaid unit cost
    for w_p, q_p in zip(scn.pipeline_weeks, scn.pipeline_kg):          # already-paid shipments on the water
        layers.append([int(w_p), np.zeros(n) + float(q_p), rc_ref, np.where(lost, BIG, int(w_p) + delay)])
        q_orig.append(np.zeros(n) + float(q_p))
    for q_idx, (wk, q) in enumerate(orders):
        layers.append([wk + L, np.zeros(n) + q, None, np.where(lost, BIG, wk + L + delay)])
        q_orig.append(np.zeros(n) + q)
        order_by_week.setdefault(wk, []).append((q, len(layers) - 1))
    cash = np.zeros(n) + cash0
    onhand = np.full(n, scn.initial_inventory_kg, dtype=float)
    recv = np.zeros((n, H + R + 2))
    if scn.initial_receivables_bn_irr > 0:                      # opening receivables collected over the first R+1 weeks
        k = min(R + 1, H)
        recv[:, :k] += scn.initial_receivables_bn_irr * 1e9 / k
    min_cash = cash.copy()
    min_stock = onhand.copy()
    unmet = np.zeros(n)
    demand_tot = np.zeros(n)
    paid = np.zeros(n)
    paid_order = np.zeros(n)
    paid_arrival = np.zeros(n)
    cogs = np.zeros(n)
    revenue = np.zeros(n)
    storage_tot = np.zeros(n)
    opex_tot = np.zeros(n)
    shrink_cost = np.zeros(n)
    interest = np.zeros(n)
    tr_cash = np.empty((n, H + 1)) if trace else None
    tr_stock = np.empty((n, H + 1)) if trace else None
    if trace:
        tr_cash[:, 0], tr_stock[:, 0] = cash, onhand

    for t in range(H):
        # 1. place + pay orders
        for q, li in order_by_week.get(t, []):
            p_ord = mkt.P[:, t]
            if budget_mode and P_ref:                              # fixed USD per tranche: kg bought = budget / order-date price
                q = q * P_ref / p_ord
                layers[li][1] = q.copy(); q_orig[li] = q.copy()
            pre_unit = alpha * p_ord * mkt.X[:, t] * land           # prepaid part of the invoice (USD price fixed at order date)
            unit = mkt.RC[:, t]                                    # provisional full cost (replaced at arrival)
            layers[li][2] = unit
            meta[li] = {"p": p_ord, "pre": pre_unit}
            pay = q * pre_unit
            cash = cash - pay
            paid += pay
            paid_order += pay
        # 2. arrivals
        for li, (arr, qty, cst, arr_p) in enumerate(layers):
            if li > 0:
                here = arr_p == t
                onhand = onhand + np.where(here, qty, 0.0)
                if li in meta and alpha < 1.0:                      # settle the invoice balance at the arrival-week rate
                    settle_unit = (1.0 - alpha) * meta[li]["p"] * mkt.X[:, t] * land
                    pay = np.where(here, qty * settle_unit, 0.0)
                    cash = cash - pay; paid += pay; paid_arrival += pay
                if li in meta:
                    layers[li][2] = np.where(here, meta[li]["pre"] + (1.0 - alpha) * meta[li]["p"] * mkt.X[:, t] * land, layers[li][2])
        # 3. demand and sales
        d = mkt.D[:, t]
        s = np.minimum(d, onhand)
        unmet += d - s
        demand_tot += d
        closing = onhand - s
        rev_t = s * mkt.S[:, t]
        revenue += rev_t
        recv[:, t + R] += rev_t
        # 4. FIFO COGS, storage, shrink
        remaining = s.copy()
        for li, (arr, qty, cst, arr_p) in sorted(enumerate(layers), key=lambda x: x[1][0]):
            if cst is not None and arr <= t:
                avail = np.where(arr_p <= t, layers[li][1], 0.0)
                take = np.minimum(avail, remaining)
                cogs += take * cst
                layers[li][1] = layers[li][1] - take
                remaining = remaining - take
        storage = st * 0.5 * (onhand + closing) * mkt.RC[:, t]
        storage_tot += storage
        for li, (arr, qty, cst, arr_p) in enumerate(layers):
            if arr <= t:
                if cst is not None:
                    shrink_cost += np.where(arr_p <= t, layers[li][1] * sh * cst, 0.0)
                layers[li][1] = layers[li][1] * np.where(arr_p <= t, 1 - sh, 1.0)
        onhand = closing * (1 - sh)
        min_stock = np.minimum(min_stock, onhand)
        # 5. opex and trough
        opex = opex0 * mkt.CPI[t]
        opex_tot += opex
        cash = cash - opex - storage
        min_cash = np.minimum(min_cash, cash)
        # 6. receipts and interest
        cash = cash + recv[:, t]
        before = cash
        cash = np.where(cash >= 0, cash * (1 + r_dep), cash * (1 + r_bor))
        interest += cash - before
        if trace:
            tr_cash[:, t + 1], tr_stock[:, t + 1] = cash, onhand

    recv_out = recv[:, H:].sum(axis=1)
    recv_open = scn.initial_receivables_bn_irr * 1e9
    pipeline_qty = np.zeros(n); ap_end = np.zeros(n)
    for li, lay in enumerate(layers):
        if li > 0:
            wait = (lay[3] >= H) & ~lost
            pipeline_qty += np.where(wait, lay[1], 0.0)
            if li in meta:                                          # unpaid balance of goods not yet arrived, at the end-of-horizon rate
                ap_end += np.where(wait, lay[1] * (1.0 - alpha) * meta[li]["p"] * mkt.X[:, H] * land, 0.0)
                layers[li][2] = np.where(wait, meta[li]["pre"] + (1.0 - alpha) * meta[li]["p"] * mkt.X[:, H] * land, layers[li][2])
    goods = onhand + pipeline_qty
    inv_val = goods * mkt.RC[:, H] * (1 - scn.terminal_haircut_pct / 100)
    W_T = cash + recv_out + inv_val - ap_end
    # accounting split of the wealth change:  dW = acct_profit - shrink_cost - lost_cost + holding_gain
    cost_end = np.zeros(n); lost_cost = np.zeros(n)
    for li, (arr, qty, cst, arr_p) in enumerate(layers):
        if cst is None:
            continue
        cost_end += np.where(lost & (li > 0), 0.0, qty * cst)
        if li > 0:
            pre = meta[li]["pre"] if li in meta else cst
            lost_cost += np.where(lost, q_orig[li] * pre, 0.0)
    inv_units0 = scn.initial_inventory_kg + float(sum(scn.pipeline_kg))
    reval_open = inv_units0 * (mkt.RC[:, 0] - rc_ref)
    holding_gain = inv_val - cost_end - reval_open
    W_0 = cash0 + recv_open + (scn.initial_inventory_kg + float(sum(scn.pipeline_kg))) * mkt.RC[:, 0]
    return PolicyResult(
        profit_nom=W_T - W_0,
        profit_real=W_T / mkt.CPI[H] - W_0,
        profit_usd=W_T / mkt.X[:, H] - W_0 / mkt.X[:, 0],
        acct_profit=revenue - cogs - opex_tot - storage_tot + interest,
        min_cash=min_cash, unmet_kg=unmet, demand_kg=demand_tot, end_stock_kg=goods, min_stock_kg=min_stock,
        paid=paid, paid_order=paid_order, paid_arrival=paid_arrival, ap_end=ap_end, interest=interest, shrink_cost=shrink_cost, lost_cost=lost_cost, holding_gain=holding_gain, trace_cash=tr_cash, trace_stock=tr_stock)
