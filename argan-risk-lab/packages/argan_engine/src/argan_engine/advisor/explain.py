"""Plain-language advice built ONLY from computed numbers (no free text generation).
Every sentence is a template filled with quantities from the analysis result, so each claim is traceable."""
from __future__ import annotations

from ..config import Scenario

_FA = str.maketrans("0123456789.-", "۰۱۲۳۴۵۶۷۸۹٫−")


LRI, PDI = "\u2066", "\u2069"          # left-to-right isolate: keeps "−۳٫۲٪" together, minus on the left of the digits


def fa(x, nd: int = 0, sign: bool = False) -> str:
    """Persian digits. A negative (or explicitly signed) number is wrapped in a bidi isolate so the minus sign
    stays attached to the left of the digits inside right-to-left text."""
    r = round(float(x), nd)
    if r == 0:
        r = 0.0                                   # never print "-0" / "+0"
        sign = False
    s = f"{r:+,.{nd}f}" if sign else f"{r:,.{nd}f}"
    s = s.replace(",", "٬").translate(_FA)
    return LRI + s + PDI if (r < 0 or sign) else s


def better_worse(x: float, nd: int = 1, base: str = "") -> str:
    """'X٪ بهتر' / 'X٪ بدتر' / 'تقریباً برابر' -- direction in words, magnitude without a sign."""
    if abs(x) * 100 < 0.5 * 10 ** (-nd):
        return "تقریباً برابر"
    return f"{pct(abs(x), nd)} " + ("بهتر" if x > 0 else "بدتر")


def tolerance_text(t: dict, kind: str) -> str:
    """Honest wording of a reverse-stress tolerance. survives_up_to == 0 / None with a failure means the plan already
    fails the criterion WITHOUT any extra shock; it is not 'tolerates up to zero'."""
    unit = (lambda v: pct(v)) if kind == "fx" else (lambda v: f"{fa(v)} هفته")
    name = "جهش دلار" if kind == "fx" else "تأخیر تحویل"
    up, fa_ = t.get("survives_up_to"), t.get("fails_at")
    if fa_ is None:
        return f"در محدوده‌ی بررسی‌شده، {name} برنامه را از کار نینداخت."
    if up is None or up <= 0:
        return (f"برنامه حتی بدون {name} اضافه هم از معیار شکست عبور می‌کند؛ پس در این برنامه هیچ حاشیه‌ی تحملی برای {name} باقی نمانده است.")
    return f"برنامه تا {unit(up)} {name} تاب می‌آورد و از حدود {unit(fa_)} می‌شکند."


def pct(x: float, nd: int = 0, sign: bool = False) -> str:
    t = fa(x * 100, nd, sign)
    return t[:-1] + "٪" + PDI if t.endswith(PDI) else t + "٪"


def schedule_text(weights, days) -> str:
    parts = []
    for w, d in zip(weights, days):
        if w < 1e-9:
            continue
        when = "امروز" if d == 0 else f"{fa(d)} روز دیگر"
        parts.append(f"{pct(w)} {when}")
    return "، ".join(parts)


def advise(res: dict, scn: Scenario, hist_share_down: float | None = None) -> dict:
    m = res["meta"]
    rec = res["benchmarks"]["recommended"]
    now, eq = res["benchmarks"]["all_now"], res["benchmarks"]["equal_split"]
    V = m["purchase_value_bn_irr"]
    days = m["schedule_days"]
    W = rec["weights"]
    Q = m["Q_kg"]
    sched = [{"day": d, "share": w, "kg": w * Q, "usd": w * scn.purchase_budget_usd}
             for w, d in zip(W, days) if w > 1e-9]
    out: dict = {"headline": "بهترین زمان‌بندی خرید: " + schedule_text(W, days),
                 "schedule": sched, "factors": [], "numbers": {}, "notes": []}

    # ---- numbers (as % of purchase value) -----------------------------------------------------------
    vn, ve = rec["vs_recommended"], None
    d_now = (rec["mean_bn"] - now["mean_bn"]) / V            # recommended minus all-now (expected)
    d_eq = (rec["mean_bn"] - eq["mean_bn"]) / V
    t_now = (rec["cvar_bn"] - now["cvar_bn"]) / V
    t_eq = (rec["cvar_bn"] - eq["cvar_bn"]) / V
    out["numbers"] = {"vs_all_now_expected_pct": d_now * 100, "vs_equal_expected_pct": d_eq * 100,
                      "vs_all_now_tail_pct": t_now * 100, "vs_equal_tail_pct": t_eq * 100,
                      "liquidity_breach_rec": rec["breach"], "liquidity_breach_now": now["breach"],
                      "unmet_rec": rec["unmet"], "unmet_eq": eq["unmet"], "unmet_now": now["unmet"]}

    # ---- does the recommended plan respect the user's own limits? ---------------------------------------------
    lim_b, lim_u = scn.max_liquidity_breach_prob_pct / 100, scn.max_unmet_demand_pct / 100
    viol = []
    if rec["unmet"] > lim_u + 1e-9:
        viol.append(f"کمبود موجودی مورد انتظار {pct(rec['unmet'], 1)} از تقاضاست، در حالی که حد مجاز {pct(lim_u, 1)} است.")
    if rec["breach"] > lim_b + 1e-9:
        viol.append(f"احتمال افت نقدینگی زیر حد ایمن {pct(rec['breach'], 1)} است، در حالی که حد مجاز {pct(lim_b, 1)} است.")
    any_ok = res["recommended"]["any_feasible"]
    out["status"] = {"respects_limits": not viol, "any_feasible_option": bool(any_ok), "violations": viol}
    if viol:
        out["status"]["text"] = ("این برنامه همه‌ی حدود تعیین‌شده را رعایت نمی‌کند: " + " ".join(viol) + " "
                                 + ("هیچ زمان‌بندی دیگری هم همه‌ی حدود را رعایت نمی‌کند؛ این برنامه فقط «کم‌نقض‌ترین» گزینه است، نه یک گزینه‌ی قابل‌قبول."
                                    if not any_ok else "گزینه‌ی دیگری هست که حدود را رعایت می‌کند؛ پیشنهاد باید با آن مقایسه شود."))
        out["headline"] = "هشدار: هیچ گزینه‌ی کاملاً قابل‌قبولی پیدا نشد. کم‌نقض‌ترین زمان‌بندی: " + schedule_text(W, days)
    else:
        out["status"]["text"] = "برنامه‌ی پیشنهادی در حالت پایه، حدود نقدینگی و کمبود موجودی را رعایت می‌کند."

    # ---- factor 1: carry ---------------------------------------------------------------------------------
    carry = res["carry"]["rows"]
    if carry:
        c = carry[0]
        growth, fin, hold = c["expected_cost_growth"], c["financing"]["deposit"], c["holding_cost"]
        adv = c["net_advantage_deposit"]
        out["factors"].append({
            "kind": "carry", "strength": abs(adv),
            "title": "هزینه‌ی انتظار در برابر هزینه‌ی نگه‌داری",
            "text": (f"طبق مدل، بهای ریالی کالا طی {fa(c['day'])} روز به‌طور متوسط {pct(growth, 1)} بالا می‌رود؛ "
                     f"در مقابل، بستن پول و نگه‌داری در انبار حدود {pct((1 + fin) * (1 + hold) - 1, 1)} خرج دارد. "
                     + (f"پس خرید زودتر فقط حدود {pct(adv, 1)} در هر {fa(c['day'])} روز مزیت متوسط دارد" if adv >= 0 else
                      f"پس خرید زودتر در هر {fa(c['day'])} روز به‌طور متوسط حدود {pct(-adv, 1)} زیان دارد")
                     + (" (اگر پول را قرض بگیرید تقریباً صفر یا منفی)." if c["net_advantage_borrow"] < 0.002 else "."))})

    # ---- factor 2: binding constraint / tail ---------------------------------------------------------------------
    lim = scn.max_liquidity_breach_prob_pct / 100
    if now["breach"] > lim:
        out["factors"].append({
            "kind": "liquidity", "strength": now["breach"],
            "title": "نقدینگی، محدودکننده‌ی اصلی است",
            "text": (f"اگر همه‌ی محموله را امروز بخرید، در {pct(now['breach'])} سناریوها نقدینگی شما زیر حد ایمن "
                     f"({fa(scn.min_cash_bn_irr)} میلیارد ریال) می‌رود؛ با برنامه‌ی پیشنهادی این احتمال {pct(rec['breach'])} است.")})
    st = {s["id"]: s for s in res["stress"]}
    dd = st.get("deal_down")
    if dd:
        loss_now = (dd["policies"]["all_now"]["mean_bn"] - dd["policies"]["recommended"]["mean_bn"]) / V
        if loss_now < -0.02:
            out["factors"].append({
                "kind": "deal", "strength": abs(loss_now),
                "title": "ریسک افت ناگهانی دلار (توافق/کاهش تنش)",
                "text": (f"اگر دلار ناگهان ۲۵٪ ارزان شود، خرید یک‌جای امروز حدود {pct(-loss_now, 1)} از ارزش محموله "
                         f"بدتر از برنامه‌ی پیشنهادی عمل می‌کند."
                         + (f" در تاریخچه‌ی داده‌ها، در {pct(hist_share_down)} از پنجره‌های ۱۳‌هفته‌ای دلار پایین آمده است."
                            if hist_share_down is not None else ""))})
    if rec["unmet"] > 0.005 or eq["unmet"] > 0.01:
        out["factors"].append({
            "kind": "stockout", "strength": eq["unmet"],
            "title": "کمبود موجودی",
            "text": (f"با خرید مرحله‌ای ساده (مساوی در ۳ مرحله) حدود {pct(eq['unmet'], 1)} از تقاضا بی‌پاسخ می‌ماند؛ "
                     f"برنامه‌ی پیشنهادی {pct(rec['unmet'], 1)}.")})
    out["factors"].sort(key=lambda f: -f["strength"])
    out["factors"] = out["factors"][:3]

    # ---- evidence sentences (plain language: who wins, by how much, and why a manager should care) ---------------
    tail = pct(1 - scn.cvar_alpha)
    def _cmp(name, d, t):
        avg = f"به‌طور میانگین، برنامه‌ی پیشنهادی نسبت به «{name}» {better_worse(d)} است (برحسب سهمی از ارزش محموله)."
        if abs(t) * 100 < 0.05:
            bad = f"در بدترین {tail} حالت‌های بازار، دو گزینه تقریباً برابرند."
        elif t > 0:
            bad = (f"در بدترین {tail} حالت‌های بازار (یعنی وقتی دلار یا قهوه خیلی بد حرکت می‌کند) برنامه‌ی پیشنهادی {better_worse(t)} است؛ "
                   f"یعنی مزیت اصلی آن محافظت در روزهای بد است.")
        else:
            bad = (f"در بدترین {tail} حالت‌های بازار برنامه‌ی پیشنهادی {better_worse(t)} است؛ "
                   f"یعنی در روزهای بد، «{name}» ضرر کمتری می‌دهد و پیشنهاد در این بخش ضعیف‌تر است.")
        return avg + " " + bad
    out["evidence"] = [_cmp("خرید یک‌جا امروز", d_now, t_now), _cmp("سه قسط مساوی", d_eq, t_eq)]
    out["technical"] = [{"title": "معیارها", "text": "«بدترین ۵٪» یعنی میانگین نتیجه در بدترین بخش از مسیرهای شبیه‌سازی (CVaR). همه‌ی مقایسه‌ها روی مسیرهای تصادفی یکسان انجام شده‌اند."}]
    # ---- confidence ------------------------------------------------------------------------------------------------------
    w = res.get("worlds")
    core_bad = any(x["group"] == "core" and (x["policies"]["recommended"]["unmet"] > lim_u or x["policies"]["recommended"]["breach"] > lim_b)
                   for x in res["stress"])
    wc_note = " این اطمینان درباره‌ی شرایط پایه است؛ در بعضی سناریوهای تنش حدود نقض می‌شود (بخش «بدترین وضعیت»)." if core_bad else ""
    if w:
        share = w["rec_beats_equal_share"]
        feas = w["share_feasible_rec"]
        level = "بالا" if share >= 0.75 and feas >= 0.8 else "متوسط" if share >= 0.55 else "پایین"
        reason = ""
        if viol:                                   # a plan that breaks its own limits cannot be recommended with confidence
            level, reason = "پایین", " چون برنامه در حالت پایه حدود کمبود/نقدینگی را رعایت نمی‌کند، نمی‌توان آن را با اطمینان توصیه کرد."
        elif feas < 0.8:
            level = "پایین" if feas < 0.5 else min(level, "متوسط", key=["پایین", "متوسط", "بالا"].index)
            reason = f" چون حدود فقط در {pct(feas)} جهان‌ها رعایت می‌شود، اطمینان محدود شد."
        out["confidence"] = {
            "level": level, "share_beats_equal": share, "share_beats_now": w["rec_beats_all_now_share"], "share_feasible": feas,
            "text": (f"{fa(w['n'])} «جهان ممکن» (با پارامترهای نامطمئن متفاوت) آزمایش شد. برنامه در {pct(share)} آن‌ها از سه‌قسط مساوی بهتر بود "
                     f"و حدود نقدینگی/کمبود را در {pct(feas)} آن‌ها رعایت کرد." + reason + wc_note)}
    # ---- what changes the answer -----------------------------------------------------------------------------------------
    fl = res.get("flip", {})
    if fl.get("drift"):
        cr = fl["drift"]["cross50"]
        base = fl["drift"]["base"]
        txt = (f"سهم خرید امروز به انتظار شما از رشد سالانه‌ی دلار (در مدل: {pct(base / 100)}) وابسته است. "
               + (f"اگر این انتظار از حدود {pct(cr / 100)} بیشتر باشد، سهم خرید امروز از نصف بیشتر می‌شود." if cr is not None else
                  "در بازه‌ی بررسی‌شده، سهم خرید امروز از نصف عبور نمی‌کند."))
        out["flip"] = {"text": txt, "cross50": cr, "base": base}
    _decision_blocks(res, scn, out, rec, now, eq, V, W, days)
    out["manager"] = manager_summary(res, scn, out, rec, now, V, W, days, hist_share_down)
    rec_info = res["recommended"]
    if not rec_info["any_feasible"]:
        pass                                        # reported in out["status"] (top of the result), not as a footnote
    ub = res["benchmarks"].get("unconstrained_best")
    if ub and abs(ub["J_bn"] - rec["J_bn"]) / V > 0.001:
        out["notes"].append(f"هزینه‌ی رعایت قیدها: حدود {pct(abs(ub['J_bn'] - rec['J_bn']) / V, 2)} از ارزش محموله در هدف مبتنی بر میانگین–CVaR.")
    if m["coffee_gap_weeks"] > 2:
        out["notes"].append(f"آخرین قیمت نقدشونده‌ی قهوه در داده‌ها {fa(m['coffee_gap_weeks'])} هفته قدیمی است؛ این عدم‌قطعیت در مدل لحاظ شد. "
                            "برای دقت بیشتر قیمت امروز را وارد کنید.")
    out["notes"].append("اعداد نقدینگی، نرخ سود، حاشیه و هزینه‌ها نمونه‌اند و باید با داده‌ی واقعی شرکت جایگزین شوند.")
    return out


# ------------------------------------------------------------------------------------------------------------------
def _decision_blocks(res: dict, scn: Scenario, out: dict, rec: dict, now: dict, eq: dict, V: float, W, days) -> None:
    """Decision, why, worst case, review triggers and contingency plan -- all numbers come from `res`."""
    m = res["meta"]
    nz = [i for i, w in enumerate(W) if w > 1e-9]
    if W[0] >= 0.85:
        kind = "خرید زودهنگام (یک‌جا)"
    elif len(nz) == 1 and nz[0] == len(W) - 1:
        kind = "تأخیر در خرید"
    else:
        kind = "خرید مرحله‌ای"
    out["decision"] = {"kind": kind, "text": f"{kind}: {schedule_text(W, days)}"}

    d_now = (rec["mean_bn"] - now["mean_bn"]) / V
    t_now = (rec["cvar_bn"] - now["cvar_bn"]) / V
    out["why"] = [
        {"title": "هزینه و سود", "text": f"نسبت به خرید یک‌جا امروز، به‌طور میانگین {better_worse(d_now)} و در بدترین {pct(1 - scn.cvar_alpha)} حالت‌ها {better_worse(t_now)} است."},
        {"title": "نقدینگی", "text": f"احتمال افت نقدینگی زیر حد ایمن: {pct(rec['breach'])} با این برنامه، در برابر {pct(now['breach'])} با خرید یک‌جا (حد مجاز: {pct(scn.max_liquidity_breach_prob_pct / 100)})."},
        {"title": "کمبود موجودی", "text": f"کمبود مورد انتظار: {pct(rec['unmet'], 1)} از تقاضا (حد مجاز: {pct(scn.max_unmet_demand_pct / 100, 1)}). احتمال افتادن موجودی زیر حداقل ایمن ({fa(scn.safety_stock_weeks, 1)} هفته فروش): {pct(rec['cover_breach'])}."},
    ]

    # ---- worst examined scenario ------------------------------------------------------------------------------------
    st = {s["id"]: s for s in res["stress"]}
    core = [s for s in res["stress"] if s["group"] == "core" and s["id"] != "normal"]
    normal = st["normal"]["policies"]["recommended"]
    worst = max(core, key=lambda s: (s["policies"]["recommended"]["floor"], s["policies"]["recommended"]["breach"]))
    wr, wn = worst["policies"]["recommended"], worst["policies"]["all_now"]
    out["worst_case"] = {
        "id": worst["id"], "label": worst["label_fa"], "desc": worst["desc_fa"], "breach": wr["breach"], "floor": wr["floor"],
        "unmet": wr["unmet"], "breach_now": wn["breach"], "floor_now": wn["floor"],
        "text": (f"بدترین سناریوی بررسی‌شده «{worst['label_fa']}» ({worst['desc_fa']}) است: در آن، نقدینگی در {pct(wr['breach'])} مسیرها "
                 f"زیر حد ایمن و در {pct(wr['floor'])} مسیرها زیر صفر می‌رود و {pct(wr['unmet'], 0)} از تقاضا بی‌پاسخ می‌ماند. "
                 "این اندازه‌ی شوک آزمون تاب‌آوری است، نه پیش‌بینی یا احتمال."),
    }
    lim_u_, lim_b_ = scn.max_unmet_demand_pct / 100, scn.max_liquidity_breach_prob_pct / 100
    over = []
    if wr["unmet"] > lim_u_:
        over.append(f"کمبود موجودی ({pct(wr['unmet'], 0)}) از حد مجاز ({pct(lim_u_, 1)}) بیشتر است")
    if wr["breach"] > lim_b_:
        over.append(f"احتمال افت نقدینگی ({pct(wr['breach'])}) از حد مجاز ({pct(lim_b_)}) بیشتر است")
    out["worst_case"]["exceeds_limits"] = over
    if over:
        out["worst_case"]["text"] += " در این سناریو حدود مجاز نقض می‌شود: " + "؛ ".join(over) + ". یعنی در چنین شوکی برنامه به‌تنهایی کافی نیست و باید برنامه‌ی جایگزین فعال شود."
    if wn["floor"] < wr["floor"] - 0.05:
        out["worst_case"]["tradeoff"] = (f"هشدار صادقانه: در این سناریو، برنامه‌ی پیشنهادی از نظر نقدینگی شکننده‌تر از خرید یک‌جاست "
                                         f"(افت زیر صفر: {pct(wr['floor'])} در برابر {pct(wn['floor'])})، چون اقساط بعدی به نرخ بالاتر پرداخت می‌شود؛ "
                                         "در عوض در کاهش ناگهانی دلار بسیار بهتر عمل می‌کند.")

    # ---- break-even beliefs (where does "buy everything now" overtake the staged plan?) ----------------------------------
    dm = res.get("decision_map")
    if dm:
        be_txt = []
        for b in dm["break_even"]:
            u = b["unit"]
            if b["status"] == "crossing":
                side = "بیشتر" if b["d_hi"] > 0 else "کمتر"
                feas = ("ولی در آن نقطه خرید یک‌جا حدود نقدینگی/کمبود را رعایت نمی‌کند"
                        if not b.get("now_feasible_at_root") else "و در آن نقطه خرید یک‌جا حدود را رعایت می‌کند")
                txt = (f"{b['label_fa']}: اگر باور شما از حدود {fa(b['root'], 1)} {u} {side} شود، خرید یک‌جا از نظر ارزش هدف (میانگین و دم زیان) "
                       f"از برنامه‌ی پیشنهادی بهتر می‌شود (باور فعلی: {fa(b['base'], 1)}). معادل رشد مورد انتظار دلار در افق ≈ {pct(b['fx_rise_at_root'], 0)}؛ {feas}.")
            elif b["status"] == "staged_always_better":
                txt = f"{b['label_fa']}: در بازه‌ی {fa(b['lo'], 1)} تا {fa(b['hi'], 1)} {u} خرید مرحله‌ای همیشه بهتر از خرید یک‌جاست."
            else:
                txt = f"{b['label_fa']}: در بازه‌ی {fa(b['lo'], 1)} تا {fa(b['hi'], 1)} {u} خرید یک‌جا همیشه از نظر ارزش هدف بهتر است."
            be_txt.append({"title": b["label_fa"], "text": txt})
        out["break_even"] = be_txt
    at = res.get("attribution")
    if at:
        rows = sorted(at["rows"], key=lambda r: r["delta_pct"])
        neg = [r for r in rows if r["delta_pct"] < -0.5]
        out["attribution_text"] = (
            f"در سناریوی بحران شدید، میانگین نتیجه‌ی برنامه‌ی پیشنهادی حدود {pct(abs(at['total_delta_pct']) / 100, 1)} از ارزش محموله "
            + ("کاهش" if at['total_delta_pct'] < 0 else "افزایش") + " می‌یابد. "
            + ("عامل‌هایی که بیشترین زیان را می‌سازند (سهم شاپلی؛ مجموع سهم‌ها دقیقاً برابر کل تغییر است): " + "؛ ".join(f"{r['label_fa']} {pct(abs(r['delta_pct']) / 100, 1)}" for r in neg) + ". " if neg else "")
            + "توجه: چون موجودی به هزینه‌ی جایگزینی ارزش‌گذاری می‌شود، جهش دلار/قهوه ارزش انبار را بالا می‌برد و زیانش از مسیر نقدینگی و کمبود می‌آید، نه از ارزش دفتری.")

    # ---- review triggers -------------------------------------------------------------------------------------------------
    trig = []
    fl = res.get("flip", {})
    if fl.get("drift") and fl["drift"]["cross50"] is not None:
        trig.append(f"انتظار شما از رشد سالانه‌ی دلار از حدود {pct(fl['drift']['cross50'] / 100)} بیشتر شود (در مدل: {pct(fl['drift']['base'] / 100)}).")
    if fl.get("lead") and fl["lead"]["cross50"] is not None:
        trig.append(f"زمان تحویل عادی از حدود {fa(fl['lead']['cross50'])} روز بیشتر شود (فعلی: {fa(fl['lead']['base'])} روز).")
    rv = res.get("reverse", {})
    tol = rv.get("tolerance", {}).get("recommended")
    if tol:
        out["tolerance_text"] = {"fx": tolerance_text(tol["fx"], "fx"), "delay": tolerance_text(tol["delay_weeks"], "delay")}
        if tol["fx"]["fails_at"] is not None and (tol["fx"]["survives_up_to"] or 0) > 0:
            trig.append(out["tolerance_text"]["fx"])
        if tol["delay_weeks"]["fails_at"] is not None and (tol["delay_weeks"]["survives_up_to"] or 0) > 0:
            trig.append(out["tolerance_text"]["delay"])
    out["triggers"] = trig

    # ---- contingency plan --------------------------------------------------------------------------------------------------
    plan = []
    cl_w = m["crisis_lead_days"] / 7
    need_kg = scn.weekly_demand_kg * cl_w
    cover_w = scn.initial_inventory_kg / scn.weekly_demand_kg
    plan.append({"title": "حداقل موجودی", "text": (
        f"زمان تحویل در بحران حدود {fa(m['crisis_lead_days'])} روز است ({fa(cl_w, 1)} هفته). برای تحمل آن بدون کمبود، حدود {fa(need_kg)} کیلو موجودی لازم است؛ "
        f"موجودی فعلی {fa(scn.initial_inventory_kg)} کیلو، یعنی {fa(cover_w, 1)} هفته فروش.")})
    deficit = max(0.0, need_kg - scn.initial_inventory_kg)
    if deficit > 0:
        cost_bn = deficit * m["RC_ref"] / 1e9
        plan.append({"title": "خرید اضطراری", "text": (
            f"اگر موجودی از پوشش زمان تحویل بحران کمتر شود، شکاف حدود {fa(deficit)} کیلو است (≈ {fa(cost_bn, 1)} میلیارد ریال به بهای امروز) "
            "و باید با نرخ و زمان تحویل سریع‌تر تأمین شود.")})
    ci = res.get("contingency_inputs", {})
    d = ci.get("import_disruption")
    if d:
        plan.append({"title": "تأمین‌کننده‌ی جایگزین", "text": (
            f"در اختلال واردات به‌طور متوسط {fa(d['unmet_kg'])} کیلو ({pct(d['unmet_share'])} تقاضای افق) بی‌پاسخ می‌ماند؛ "
            "هر مقدار که تأمین‌کننده‌ی جایگزین با تحویل کوتاه‌تر بتواند پوشش دهد، از همین کمبود کم می‌شود.")})
    later = [(d_, w_) for d_, w_ in zip(days, W) if d_ > 0 and w_ > 1e-9]
    if later:
        d_, w_ = later[0]
        pay = w_ * V
        plan.append({"title": "کاهش تعهد خرید", "text": (
            f"پیش از پرداخت قسط روز {fa(d_)} (≈ {fa(pay, 1)} میلیارد ریال به بهای امروز): اگر نقدینگی از {fa(scn.min_cash_bn_irr + pay, 0)} میلیارد ریال "
            f"(حد ایمن + قسط) کمتر بود، قسط را کاهش دهید یا به تعویق بیندازید.")})
    sc_ = ci.get("severe_crisis")
    if sc_ and sc_["credit_need_p95_bn"] > 0:
        plan.append({"title": "خط اعتباری اضطراری", "text": (
            f"در بحران شدید برای آنکه در ۹۵٪ مسیرها نقدینگی زیر حد ایمن نرود، حدود {fa(sc_['credit_need_p95_bn'], 0)} میلیارد ریال خط اعتباری آماده لازم است.")})
    out["contingency"] = plan

    # ---- robustness notes ------------------------------------------------------------------------------------------------------
    sr = res.get("scenario_robust")
    if sr and not sr["agrees"] and sr["regret_pct"] > 0.05:
        out["notes"].append(f"اگر فقط بدترین سناریوی بررسی‌شده معیار بود، برنامه‌ی دیگری ({schedule_text(sr['weights'], days)}) انتخاب می‌شد؛ "
                            f"تفاوت در بدترین حالت {pct(sr['regret_pct'] / 100, 1)} از ارزش محموله است. بنابراین Minimax Regret/بدترین‌حالت معیار مکمل است، نه تنها ملاک.")
    w = res.get("worlds")
    if w and w.get("convergence"):
        c = w["convergence"]
        hist = c.get("history", [])
        grew = len(hist) > 1
        out["notes"].append(
            f"آزمون همگرایی: انتخاب سیاست با {fa(w['n'])} جهان " + ("پایدار است" if c["adequate"] else "هنوز کاملاً پایدار نیست (جهان‌های بیشتر پیشنهاد می‌شود)")
            + (f"؛ تعداد جهان‌ها خودکار از {fa(hist[0]['worlds'])} به {fa(w['n'])} افزایش یافت." if grew else "."))


# ------------------------------------------------------------------------------------------------------------------
# Plain-language manager summary: what to do, why, how sure, what to check before each payment, what if things go badly.
_MONTHS = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور", "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"]


def jalali_text(iso: str, add_days: int = 0) -> str:
    """'2026-10-18' (+ days) -> '۲۶ مهر ۱۴۰۵' (standard Gregorian -> Jalali conversion)."""
    import datetime as _dt
    d = _dt.date.fromisoformat(str(iso)[:10]) + _dt.timedelta(days=add_days)
    gy, gm, gd = d.year, d.month, d.day
    g_dm = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    gy2 = gy + 1 if gm > 2 else gy
    days = 355666 + 365 * gy + (gy2 + 3) // 4 - (gy2 + 99) // 100 + (gy2 + 399) // 400 + gd + g_dm[gm - 1]
    jy = -1595 + 33 * (days // 12053); days %= 12053
    jy += 4 * (days // 1461); days %= 1461
    if days > 365:
        jy += (days - 1) // 365; days = (days - 1) % 365
    if days < 186:
        jm, jd = 1 + days // 31, 1 + days % 31
    else:
        jm, jd = 7 + (days - 186) // 30, 1 + (days - 186) % 30
    return f"{fa(jd)} {_MONTHS[jm - 1]} {fa(jy).replace('٬', '')}"


def of100(p: float) -> str:
    """Probability as a natural frequency: 0.72 -> 'حدود ۷۲ حالت از هر ۱۰۰ حالت'."""
    k = int(round(p * 100))
    if k <= 0:
        return "تقریباً در هیچ حالتی"
    if k >= 100:
        return "تقریباً در همه‌ی حالت‌ها"
    return f"حدود {fa(k)} حالت از هر ۱۰۰ حالت"


def _kg_text(kg: float) -> str:
    return f"{fa(kg / 1000, 1)} تن" if kg >= 1000 else f"{fa(kg)} کیلوگرم"


def manager_summary(res, scn, out, rec, now, V, W, days, hist) -> dict:
    m = res["meta"]
    lim_b, lim_u = scn.max_liquidity_breach_prob_pct / 100, scn.max_unmet_demand_pct / 100
    base_date = m["as_of"]
    # 1. what to do ---------------------------------------------------------------------------------------------------
    steps = []
    for w_, d_ in zip(W, days):
        if w_ < 1e-9:
            continue
        steps.append({"when": "امروز" if d_ == 0 else f"{fa(d_)} روز دیگر", "date": jalali_text(base_date, d_),
                      "share": f"{fa(round(w_ * 100))}٪ محموله", "kg": _kg_text(w_ * m["Q_kg"]),
                      "usd": f"{fa(round(w_ * scn.purchase_budget_usd, -2))} دلار", "bn": f"{fa(w_ * V, 0)} میلیارد ریال"})
    single = len(steps) == 1
    action = ("کل محموله را یک‌جا و " + steps[0]["when"] + " بخرید." if single else
              f"محموله را یک‌جا نخرید؛ آن را در {fa(len(steps))} مرحله بخرید:")
    if not out["status"]["respects_limits"]:
        action = ("هیچ برنامه‌ی خریدی همه‌ی حدود شما را رعایت نمی‌کند. کم‌نقض‌ترین گزینه (نه یک توصیه‌ی مطمئن) این است: "
                  + ("کل محموله را یک‌جا و " + steps[0]["when"] + " بخرید." if single else f"خرید در {fa(len(steps))} مرحله:")
                  + " پیش از اجرا، حدود یا فرضیات (نقدینگی، زمان تحویل، مقدار خرید) را بازبینی کنید.")
    # 2. why ----------------------------------------------------------------------------------------------------------------
    why = []
    if now["breach"] > rec["breach"] + 0.02:
        why.append({"title": "پول نقد شرکت را حفظ می‌کند",
                    "text": (f"اگر همه‌ی محموله را امروز بخرید، {of100(now['breach'])} بازار، پول نقد شما از حداقل ایمن ({fa(scn.min_cash_bn_irr)} میلیارد ریال) پایین‌تر می‌رود. "
                             f"با خرید مرحله‌ای این اتفاق {of100(rec['breach'])} می‌افتد.")})
    st = {x["id"]: x for x in res["stress"]}
    dd = st.get("deal_down")
    if dd:
        loss = (dd["policies"]["all_now"]["mean_bn"] - dd["policies"]["recommended"]["mean_bn"]) / V
        if loss > 0.02:
            why.append({"title": "اگر دلار ناگهان ارزان شود، ضرر کمتری می‌کنید",
                        "text": (f"اگر دلار ناگهان ۲۵٪ ارزان شود، خرید یک‌جا حدود {pct(loss, 0)} از ارزش محموله بیشتر ضرر می‌کند، چون همه‌ی پول را با دلار گران پرداخته‌اید."
                                 + (f" در گذشته در {of100(hist)} بازه‌های سه‌ماهه دلار پایین آمده است." if hist else ""))})
    d_now = (rec["mean_bn"] - now["mean_bn"]) / V
    if abs(d_now) < 0.01:
        cost = f"در بازار عادی، هزینه‌ی این برنامه با خرید یک‌جا تقریباً یکی است (اختلاف کمتر از {pct(max(abs(d_now), 0.005) + 0.005, 0)} ارزش محموله)."
    elif d_now > 0:
        cost = f"در بازار عادی هم این برنامه به‌طور میانگین حدود {pct(d_now, 0)} از ارزش محموله بهتر از خرید یک‌جا است."
    else:
        cost = f"بهای این احتیاط: در بازار عادی این برنامه به‌طور میانگین حدود {pct(-d_now, 0)} از ارزش محموله گران‌تر از خرید یک‌جا تمام می‌شود."
    if not single:
        why.append({"title": "هزینه‌ی احتیاط", "text": cost})
    if rec["unmet"] <= lim_u:
        why.append({"title": "کالا کم نمی‌آید",
                    "text": f"با این برنامه انتظار می‌رود حدود {pct(rec['unmet'], 0)} از تقاضا بی‌پاسخ بماند؛ حد مجاز شما {pct(lim_u, 0)} است."})
    # 3. how sure -----------------------------------------------------------------------------------------------------------
    conf = out.get("confidence")
    sure = None
    if conf:
        sure = {"level": conf["level"],
                "text": (f"ما محاسبه را با {fa(res['worlds']['n'])} فرض متفاوت درباره‌ی بازار تکرار کردیم. در {of100(conf['share_feasible'])} این فرض‌ها، "
                         "برنامه حدود نقدینگی و کمبود شما را رعایت کرد. "
                         + ("اطمینان کامل نیست؛ پیش از هر قسط وضعیت را دوباره بسنجید." if conf["level"] != "بالا" else "")
                         + (" چون برنامه حتی در حالت عادی حدود شما را رعایت نمی‌کند، به این توصیه تکیه نکنید و فرضیات را اصلاح کنید." if not out["status"]["respects_limits"] else ""))}
    # 4. checks before each payment ------------------------------------------------------------------------------------------
    checks = []
    later = [(d_, w_) for d_, w_ in zip(days, W) if d_ > 0 and w_ > 1e-9]
    if later:
        d_, w_ = later[0]
        need = scn.min_cash_bn_irr + w_ * V
        checks.append(f"پیش از پرداخت قسط روز {fa(d_)} ({jalali_text(base_date, d_)}): اگر پول نقد از {fa(need)} میلیارد ریال کمتر بود (حداقل ایمن {fa(scn.min_cash_bn_irr)} به‌علاوه‌ی قسط {fa(w_ * V)})، قسط را کوچک‌تر کنید یا عقب بیندازید.")
    fl = res.get("flip", {})
    if fl.get("drift") and fl["drift"]["cross50"] is not None:
        checks.append(f"اگر باور دارید دلار طی یک سال بیش از {pct(fl['drift']['cross50'] / 100)} گران می‌شود (این گزارش {pct(fl['drift']['base'] / 100)} فرض کرده)، سهم خرید امروز را بیشتر کنید، تا جایی که نقدینگی اجازه می‌دهد.")
    if fl.get("lead") and fl["lead"]["cross50"] is not None:
        checks.append(f"اگر زمان رسیدن کالا از {fa(fl['lead']['cross50'])} روز بیشتر شد (اکنون {fa(fl['lead']['base'])} روز)، برنامه را دوباره بررسی کنید.")
    tol = res.get("reverse", {}).get("tolerance", {}).get("recommended")
    if tol:
        if tol["fx"]["fails_at"] is not None and (tol["fx"]["survives_up_to"] or 0) > 0:
            checks.append(f"اگر دلار طی چند هفته بیش از {pct(tol['fx']['survives_up_to'])} گران شد، تصمیم را دوباره بگیرید؛ از حدود {pct(tol['fx']['fails_at'])} به بالا نقدینگی یا کالا کم می‌آید.")
        elif tol["fx"]["fails_at"] is not None:
            checks.append("این برنامه حتی بدون جهش اضافه‌ی دلار هم از معیار ما عبور می‌کند؛ حاشیه‌ی ایمنی برای گران‌شدن دلار نمانده است.")
        if tol["delay_weeks"]["fails_at"] is not None and (tol["delay_weeks"]["survives_up_to"] or 0) > 0:
            checks.append(f"تأخیر تا {fa(tol['delay_weeks']['survives_up_to'])} هفته در رسیدن کالا قابل تحمل است؛ از حدود {fa(tol['delay_weeks']['fails_at'])} هفته به بالا مشکل جدی می‌شود.")
        elif tol["delay_weeks"]["fails_at"] is not None:
            checks.append("این برنامه حتی بدون تأخیر اضافه در رسیدن کالا هم از معیار ما عبور می‌کند.")
    # 5. if things go badly -----------------------------------------------------------------------------------------------------
    bad = []
    ci = res.get("contingency_inputs", {})
    sc_ = ci.get("severe_crisis")
    if sc_ and sc_["credit_need_p95_bn"] > 0:
        bad.append(f"خط اعتباری: اگر چند اتفاق بد هم‌زمان رخ دهد (مثلاً دلار ۵۰٪ گران شود و محموله دیر برسد یا گم شود)، حدود {fa(sc_['credit_need_p95_bn'], 0)} میلیارد ریال اعتبار آماده لازم است.")
    cl_w = m["crisis_lead_days"] / 7
    need_kg = scn.weekly_demand_kg * cl_w
    if need_kg > scn.initial_inventory_kg:
        bad.append(f"موجودی ایمن: برای تحمل {fa(cl_w, 0)} هفته تأخیر، حدود {_kg_text(need_kg)} کالا لازم است؛ اکنون {_kg_text(scn.initial_inventory_kg)} دارید. "
                   f"کمبود حدود {_kg_text(need_kg - scn.initial_inventory_kg)} است و باید از قبل تأمین‌کننده‌ی دوم یا خرید اضطراری برایش پیش‌بینی کنید.")
    wcx = out.get("worst_case", {}).get("exceeds_limits")
    honest = ("در بدترین حالتی که آزمودیم (چند شوک هم‌زمان) این برنامه به‌تنهایی کافی نیست و حدود شما نقض می‌شود؛ این یک آزمون سخت است، نه پیش‌بینی."
              if wcx else "در بدترین حالتی که آزمودیم، حدود شما نقض نشد.")
    # 6. caveats ------------------------------------------------------------------------------------------------------------------
    cav = []
    if (res.get("data_source") or {}).get("synthetic"):
        cav.append("داده‌ی شرکت ساختگی است؛ این گزارش آزمون روش است، نه نتیجه برای شرکت واقعی.")
    cav.append("اعداد نقدینگی، حاشیه‌ی سود و هزینه‌ها نمونه‌اند و باید با داده‌ی واقعی جایگزین شوند.")
    if m["coffee_gap_weeks"] > 2:
        cav.append(f"آخرین قیمت قهوه‌ی موجود {fa(m['coffee_gap_weeks'])} هفته قدیمی است؛ قیمت امروز را وارد کنید.")
    cav.append("نتیجه پیش‌بینی بازار نیست؛ می‌گوید با این فرض‌ها کدام روش خرید محتاطانه‌تر است.")
    # 7. "what if our forecast is wrong?" table (recommended plan under each core scenario) ----------------------------------
    wrong = []
    for x in res["stress"]:
        if x["group"] != "core":
            continue
        r_ = x["policies"]["recommended"]
        if r_["floor"] >= 0.5 or r_["unmet"] >= 0.2:
            verdict = "شکست می‌خورد"
        elif r_["breach"] > lim_b + 1e-9 or r_["unmet"] > lim_u + 1e-9:
            verdict = "در خطر"
        else:
            verdict = "ادامه می‌یابد"
        wrong.append({"label": x["label_fa"], "desc": x["desc_fa"] if len(x["desc_fa"]) <= 60 else "چند شوک هم‌زمان (شرح کامل در ضمیمه‌ی فنی)", "mean": fa(r_["mean_bn"], 0), "tail": fa(r_["cvar_bn"], 0),
                      "breach": pct(r_["breach"], 0), "supply": pct(max(0.0, 1 - r_["unmet"]), 0), "verdict": verdict})
    return {"wrong": wrong, "action": action, "steps": steps, "why": why, "sure": sure, "checks": checks, "bad": bad, "honest_worst": honest, "caveats": cav,
            "warning": None if out["status"]["respects_limits"] else out["status"]["text"]}
