import { useMemo, useState } from "react";
import { fa, pct, pp, jdate, weightsText, NAMES, tolCell, sfa } from "../lib/format.js";
import { attributionOption, decisionMapOption, cashOption, distOption, fanOption, flipOption, frontierOption, heatmapOption, histOption, lineSeries, sensitivityOption, worldsOption } from "../lib/options.js";
import Chart from "../components/Chart.jsx";
import { Badge, Empty, Grid2, Kpi, Legend, Panel, Stack, Table } from "../components/ui.jsx";

const GROUP_FA = { decision: "تصمیم", operations: "عملیات", imports: "واردات و اختلال", pricing: "قیمت‌گذاری", finance: "مالی", market: "بازار", risk: "ترجیح ریسک", compute: "محاسبات" };
export { GROUP_FA };
const need = <Empty>برای این بخش ابتدا «اجرای تحلیل» را بزنید.</Empty>;

export function TabSummary({ r }) {
  if (!r) return need;
  const m = r.meta, b = r.benchmarks, V = m.purchase_value_bn_irr, rec = b.recommended, a = r.advice;
  const rows = Object.entries(b).map(([k, v]) => [NAMES[k] || k, v.weights.map((x) => fa(x, 2)).join(" / "), fa(v.mean_bn, 1), fa(v.cvar_bn, 1), fa(v.sd_bn, 1), pct(v.breach, 1), pct(v.floor, 1), pct(v.cover_breach, 0), pct(v.unmet, 2), v.feasible ? "✓" : "✗"]);
  const vr = Object.entries(b).filter(([k]) => k !== "recommended").map(([k, v]) => { const d = v.vs_recommended;
    return [NAMES[k] || k, fa(d.mean_diff_bn, 2), `${fa(d.ci_lo_bn, 2)} تا ${fa(d.ci_hi_bn, 2)}`, pct(d.p_rec_better, 0), fa(d.cvar_diff_bn, 2), { A: "توصیه‌شده غالب است", B: "رقیب غالب است", none: "—" }[d.ssd]]; });
  const carry = r.carry.rows.map((c) => [fa(c.day), pct(c.expected_cost_growth, 2), pct(c.financing.deposit, 2), pct(c.financing.borrow, 2), pct(c.holding_cost, 2), pp(c.net_advantage_deposit * 100, 2), pp(c.net_advantage_borrow * 100, 2), pct(c.breakeven_annual_cost_growth.deposit, 1), pct(c.expected_annual_cost_growth, 1)]);
  return (
    <Stack>
      <Panel><Kpi items={[
        ["سیاست توصیه‌شده", weightsText(rec.weights, m.schedule_days)], ["نوع تصمیم", a.decision.kind],
        ["مبنا", m.recommendation_basis === "robust" ? "مقاوم (شانسی + مینیمکس‌ریگرت)" : "اسمی"],
        ["مقدار خرید", fa(m.Q_kg) + " کیلو"], ["ارزش خرید", fa(V, 1) + " میلیارد ریال"], ["مدل ارز", m.fx_model],
        ["روند دلار", fa(m.fx_drift_annual_pct, 1) + "٪"], ["ضریب نرخ مؤثر ارز", fa(m.fx_basis_total, 3)],
        ["تحویل عادی / بحران", `${fa(m.lead_days)} / ${fa(m.crisis_lead_days)} روز`], ["موجودی ایمن", fa(m.safety_stock_kg) + " کیلو"],
        ["قیمت مرجع قهوه", fa(m.P_ref_c_lb, 1) + " سنت/پوند"], ["زمان اجرا", fa(m.elapsed_s, 1) + " ثانیه"]]} /></Panel>
      <Panel title="مقایسه‌ی سیاست‌ها (سود واقعی ریالی، میلیارد ریال با قدرت خرید امروز)" sub={`هدف: (1−λ)·E + λ·CVaR با λ=${fa(m.lambda, 2)}. همه‌ی سیاست‌ها روی مسیرهای تصادفی یکسان (CRN) ارزیابی شده‌اند.`}>
        <Table heads={["سیاست", "وزن‌ها", "میانگین", `CVaR ${fa(m.alpha * 100)}٪`, "انحراف معیار", "P(افت زیر حد ایمن)", "P(نقد زیر صفر)", "P(موجودی زیر ایمن)", "کمبود", "شدنی"]} rows={rows} cls={["", "num", "num", "num", "num", "num", "num", "num", "num", ""]} />
      </Panel>
      <Panel title="اختلاف زوجی: توصیه‌شده منهای رقیب (CRN)" sub="تفاوت‌ها در واحد میلیارد ریال واقعی. SSD = ترجیح هر تصمیم‌گیر ریسک‌گریز.">
        <Table heads={["رقیب", "میانگین اختلاف", "بازه‌ی ۹۵٪", "P(توصیه بهتر)", "اختلاف CVaR", "تسلط تصادفی مرتبه‌ی دوم"]} rows={vr} />
      </Panel>
      <Panel title="تحلیل Carry: چه زمانی پرداخت زودتر ارزان‌تر است؟" sub="مزیت خالص = رشد مورد انتظار بهای جایگزینی − (هزینه‌ی سرمایه و انبارداری). سربه‌سر = رشد سالانه‌ای که مزیت را صفر می‌کند.">
        <Table heads={["روز", "رشد مورد انتظار بها", "هزینه‌ی سپرده", "هزینه‌ی وام", "هزینه‌ی نگه‌داری", "مزیت خالص (سپرده)", "مزیت خالص (وام)", "سربه‌سر سالانه (سپرده)", "رشد سالانه‌ی مورد انتظار"]} rows={carry} />
      </Panel>
    </Stack>
  );
}

export function TabModels({ S, t }) {
  const d = S.data, f = d.report.fx, c = d.report.coffee, fx = d.series.fx_weekly, rg = d.series.fx_regime_smoothed, cw = d.series.coffee_weekly;
  const o = useMemo(() => {
    const bins = 30, lo = -0.18, hi = 0.18, h = new Array(bins).fill(0);
    d.series.fx_returns.forEach((v) => { const i = Math.min(bins - 1, Math.max(0, Math.floor(((v - lo) / (hi - lo)) * bins))); h[i]++; });
    return {
      m1: lineSeries(t, fx.dates, fx.values, t.s1, { log: true, left: 64, tipFmt: (v) => `${fa(v)} ریال`, yfmt: (v) => fa(v / 1e6, 1) + "م" }),
      m2: lineSeries(t, rg.dates, rg.p_turbulent, t.s2, { area: 0.35, left: 44, scale: false, ymin: 0, ymax: 1, tipFmt: (v) => fa(v * 100) + "٪", yfmt: (v) => fa(v * 100) + "٪" }),
      m3: lineSeries(t, cw.dates, cw.values, t.s3, { tipFmt: (v) => fa(v, 1) }),
      m4: histOption(t, h.map((_, i) => fa((lo + ((i + 0.5) * (hi - lo)) / bins) * 100, 0) + "٪"), h, t.s1, { tipFmt: (ps) => `${ps[0].name}: ${fa(ps[0].value)}` }),
    };
  }, [t, S.data]);
  const fits = Object.entries(f.fits).map(([k, v]) => [k, fa(v.llf, 1), fa(v.bic, 1)]);
  const rgf = f.fits.regime2, p = rgf.params;
  const reg = p.mu.map((mu, i) => [i === 0 ? "آرام" : "پرتلاطم", fa(mu * 5200, 1) + "٪", fa(p.sigma[i] * 100, 2) + "٪", fa(rgf.durations_weeks[i], 1), fa(rgf.stationary[i] * 100, 0) + "٪", fa(p.p_now[i] * 100, 0) + "٪"]);
  const diag = [["ARCH-LM (قهوه، ۸ وقفه)", fa(c.arch_lm.p, 3)], ["ARCH-LM (ارز)", fa(f.arch_lm.p, 3)], ["Ljung-Box بازده (قهوه)", fa(c.ljung_box_returns.p, 3)], ["Ljung-Box مجذور (قهوه)", fa(c.ljung_box_squared.p, 3)],
    ...c.variance_ratio.map((v) => [`نسبت واریانس Lo–MacKinlay q=${v.q} (VR=${fa(v.vr, 2)})`, fa(v.p, 3)])];
  return (
    <Stack>
      <Grid2>
        <Panel title="نرخ دلار (ریال) — مقیاس لگاریتمی" sub="هفتگی، TGJU"><Chart option={o.m1} label="نرخ دلار" /></Panel>
        <Panel title="احتمال رژیم پرتلاطم (هموار‌شده)"><Chart option={o.m2} label="رژیم" /></Panel>
        <Panel title="قیمت آرابیکا (سنت/پوند، هفتگی، فقط روزهای نقدشونده)"><Chart option={o.m3} label="قهوه" /></Panel>
        <Panel title="توزیع بازده‌های هفتگی ارز"><Chart option={o.m4} label="توزیع بازده" /></Panel>
      </Grid2>
      <Panel title="مقایسه‌ی برازش مدل‌های ارز (BIC کمتر بهتر)" sub="رژیم ۳‌حالته با BIC رد می‌شود؛ رژیم ۲‌حالته و t در سطح BIC تقریباً یکسان‌اند."><Table heads={["مدل", "llf", "BIC"]} rows={fits} cls={["", "num", "num"]} /></Panel>
      <Panel title="پارامترهای رژیم ۲‌حالته" sub={`میانگین بلندمدت: ${fa(rgf.stationary_mean_annual * 100, 1)}٪ سالانه`}><Table heads={["حالت", "میانگین (٪ سالانه، لگاریتمی)", "نوسان هفتگی", "ماندگاری (هفته)", "سهم بلندمدت", "احتمال فعلی"]} rows={reg} cls={["", "num", "num", "num", "num", "num"]} /></Panel>
      <Panel title="تشخیص‌ها (p-value)" sub="اثر ARCH هفتگی در قهوه معنادار نیست ⇒ نوسان ثابت با ضریب قابل‌تنظیم. نسبت واریانس معنادار نیست ⇒ گام تصادفی."><Table heads={["آزمون", "p"]} rows={diag} cls={["", "num"]} /></Panel>
      <Panel title="هم‌بستگی قهوه–ارز"><p>τ کندال = {fa(d.report.dependence.kendall_tau, 3)} ⇒ ρ کاپولای گاوسی = {fa(d.rho_cf, 3)} (n={fa(d.report.dependence.n_overlap)} هفته). عملاً مستقل؛ هم‌بستگی تنش از طریق «جهان‌های ممکن» و ضریب دستی لحاظ می‌شود.</p></Panel>
      <Panel title="کیفیت داده"><ul className="small list-disc ps-5">{[...c.quality, ...f.quality].map((x, i) => <li key={i}>{x}</li>)}</ul></Panel>
    </Stack>
  );
}

export function TabForecast({ r, t }) {
  const o = useMemo(() => {
    if (!r) return null;
    const m = r.meta, marks = m.schedule_weeks.map((w, i) => [w, i === 0 ? "امروز" : fa(m.schedule_days[i]) + " روز"]), st = r.traces.recommended.stock_kg;
    return { f1: fanOption(t, r.fans.fx, m.weeks, m.as_of, "", 1, marks), f2: fanOption(t, r.fans.coffee, m.weeks, m.as_of, "", 1, []), f3: fanOption(t, r.fans.rc_million, m.weeks, m.as_of, "", 1, [], 1),
      f4: distOption(t, r), f5: cashOption(t, r, m), f6: fanOption(t, st, m.weeks, m.as_of, "", 1, [], 0) };
  }, [t, r]);
  if (!r) return need;
  return (
    <Grid2>
      <Panel title="نرخ دلار نسبت به امروز (چندک‌های ۵/۲۵/۵۰/۷۵/۹۵)"><Chart option={o.f1} /></Panel>
      <Panel title="قیمت قهوه نسبت به امروز"><Chart option={o.f2} /></Panel>
      <Panel title="بهای جایگزینی ریالی (میلیون ریال/کیلو)"><Chart option={o.f3} /></Panel>
      <Panel title="توزیع سود واقعی (میلیارد ریال)"><Chart option={o.f4} /></Panel>
      <Panel title="نقدینگی: میانه و ۵٪ — توصیه‌شده در برابر همه‌امروز (میلیارد ریال)"><Chart option={o.f5} /></Panel>
      <Panel title="موجودی انبار (کیلو): توصیه‌شده"><Chart option={o.f6} /></Panel>
    </Grid2>
  );
}

export function TabPolicies({ r, t }) {
  const o = useMemo(() => r && frontierOption(t, r), [t, r]);
  if (!r) return need;
  const top = [...r.policies].sort((a, b) => b.mean_bn - a.mean_bn).slice(0, 15).map((p) => [p.w.map((x) => fa(x, 1)).join(" / "), fa(p.mean_bn, 1), fa(p.cvar_bn, 1), pct(p.breach, 1), pct(p.unmet, 2), p.feasible ? "✓" : "✗", p.pareto ? "◆" : ""]);
  return (
    <Stack>
      <Panel title="مرز کارا: میانگین در برابر CVaR (هر نقطه یک سیاست)" sub="راست‌تر و بالاتر = بهتر. نقاط ناشدنی قیدهای نقدینگی/کمبود را نقض می‌کنند.">
        <Legend items={[[t.s1, "شدنی و روی مرز"], [t.s3, "شدنی"], [t.ink3, "ناشدنی"]]} /><Chart option={o} tall />
      </Panel>
      <Panel title="۱۵ سیاست برتر بر اساس میانگین"><Table heads={["وزن‌ها", "میانگین", "CVaR", "P(افت نقدینگی)", "کمبود", "شدنی", "پارتو"]} rows={top} cls={["num", "num", "num", "num", "num", "", ""]} /></Panel>
    </Stack>
  );
}

export function TabRobust({ r, t }) {
  const o = useMemo(() => r?.worlds && { r1: worldsOption(t, r.worlds), r2: sensitivityOption(t, r.sensitivity) }, [t, r]);
  if (!r) return need;
  const w = r.worlds;
  if (!w) return <Empty>تحلیل استحکام غیرفعال بود.</Empty>;
  const sr = r.scenario_robust, cv = w.convergence;
  return (
    <Stack>
      <Panel><Kpi items={[["جهان‌های ممکن", fa(w.n)], ["شدنی بودن توصیه", pct(w.share_feasible_rec)], ["بهتر از همه‌امروز", pct(w.rec_beats_all_now_share)], ["بهتر از سه‌قسط مساوی", pct(w.rec_beats_equal_share)],
        ["ریگرت چندک ۹۰٪", fa(w.q90_regret_pct, 2) + "٪ ارزش"], ["بهترین در جهان", pct(w.rec_best_in_world_share)]]} /></Panel>
      <Grid2>
        <Panel title="اختلاف توصیه‌شده با «همه امروز» در جهان‌ها (٪ ارزش محموله)"><Chart option={o.r1} /></Panel>
        <Panel title="حساسیت سراسری: همبستگی رتبه‌ای پارامترها با اختلاف" sub="اسپیرمن؛ از همان جهان‌ها، بدون شبیه‌سازی اضافه"><Chart option={o.r2} /></Panel>
      </Grid2>
      {cv && <Panel title="آزمون همگرایی: آیا تعداد جهان‌ها کافی است؟" sub={`انتخاب مقاوم روی زیرمجموعه‌های تصادفی از جهان‌ها تکرار شد (${fa(cv.reps)} بار) و با انتخاب روی همه‌ی ${fa(cv.n_full)} جهان مقایسه شد. «نزدیک» = وزن‌ها حداکثر یک گام شبکه فرق دارند.`}>
        <Table heads={["تعداد جهان‌ها (زیرمجموعه)", "همان سیاست", "نزدیک (یک گام)", "میانه‌ی فاصله‌ی وزن‌ها"]} rows={cv.rows.map((x) => [fa(x.worlds), pct(x.agree), pct(x.close), fa(x.median_gap, 2)])} cls={["num", "num", "num", "num"]} />
        <p className="small mt-2">{cv.adequate ? "پایدار: افزودن جهان‌های بیشتر تصمیم را تغییر نمی‌دهد." : "هنوز کاملاً پایدار نیست؛ سقف جهان‌ها را بالا ببرید."}
          {cv.history?.length > 1 && ` تعداد جهان‌ها خودکار از ${fa(cv.history[0].worlds)} تا ${fa(w.n)} افزایش یافت.`}</p></Panel>}
      {sr && <Panel title="بهینه‌سازی مقاوم روی مجموعه‌ی سناریوها (بدترین حالت)" sub="سیاستی که بدترین نتیجه‌اش در هشت سناریوی نام‌برده بهتر است؛ معیار مکمل، نه تنها ملاک.">
        <Table heads={["", "وزن‌ها", "بدترین نتیجه (٪ ارزش)", "سناریوی بدترین"]} rows={[["توصیه‌شده (جهان‌های ممکن)", r.recommended.weights.map((x) => fa(x, 2)).join(" / "), fa(sr.recommended_worst_value_pct, 1), r.stress.find((s) => s.id === sr.recommended_worst_scenario)?.label_fa],
          ["بهینه‌ی بدترین‌حالت", sr.weights.map((x) => fa(x, 2)).join(" / "), fa(sr.worst_value_pct, 1), r.stress.find((s) => s.id === sr.worst_scenario)?.label_fa]]} cls={["", "num", "num", ""]} />
        <p className="small mt-2">{sr.agrees ? "هر دو معیار یک سیاست را انتخاب می‌کنند." : `دو معیار متفاوت‌اند؛ تفاوت بدترین حالت ${fa(sr.regret_pct, 2)}٪ از ارزش محموله است.`}</p></Panel>}
      <Panel title="جدول حساسیت"><Table heads={["پارامتر", "ρ اسپیرمن", "p"]} rows={r.sensitivity.map((s) => [s.label_fa, fa(s.rho, 2), fa(s.p, 3)])} cls={["", "num", "num"]} /></Panel>
    </Stack>
  );
}

export function TabStress({ r, t }) {
  const o = useMemo(() => r && { at: attributionOption(t, r.attribution), fl: r.flip.drift && flipOption(t, r.flip.drift, { xname: "رشد سالانه‌ی دلار (٪)" }), fp: r.flip.p_deal && flipOption(t, r.flip.p_deal, { xname: "احتمال توافق (٪)" }), fe: r.flip.lead && flipOption(t, r.flip.lead, { xname: "زمان تحویل (روز)" }) }, [t, r]);
  if (!r) return need;
  const P = ["recommended", "all_now", "equal_split", "all_late"];
  const rows = r.stress.map((s) => [s.label_fa + (s.group === "opposite" ? " (مخالف)" : ""), s.desc_fa, ...P.map((k) => <span key={k}>{fa(s.policies[k].mean_bn, 1)}<span className="muted small block whitespace-nowrap">{pct(s.policies[k].breach, 0)} · {pct(s.policies[k].floor, 0)} · {pct(s.policies[k].unmet, 0)}</span></span>)]);
  const at = r.attribution;
  return (
    <Stack>
      <Panel title="سناریوهای اصلی — میانگین سود واقعی (میلیارد ریال) و در پرانتز: افت زیر حد ایمن · نقد زیر صفر · کمبود"
        sub="اندازه‌ی شوک‌ها آزمون تاب‌آوری است، نه پیش‌بینی و نه احتمال؛ برای جنگ یا قطع تأمین احتمال ساختگی گذاشته نشده. همه‌ی سناریوها روی همان مسیرهای تصادفی پایه (CRN) اعمال شده‌اند.">
        <Table heads={["سناریو", "توضیح", "توصیه‌شده", "همه امروز", "سه‌قسط مساوی", "همه دیرتر"]} rows={rows} />
        <ul className="small muted mt-2 list-disc ps-5">{r.stress.filter((s) => s.group === "core").map((s) => <li key={s.id}><b>{s.label_fa}:</b> {s.question_fa}</li>)}</ul>
      </Panel>
      <Panel title="سهم هر عامل در «بحران شدید» (مقدار شاپلی)" sub={`شاپلی: سهم هر عامل = میانگین وزنی اثر افزودن آن به همه‌ی زیرمجموعه‌های ممکن از عامل‌های دیگر (${fa(at.n_coalitions)} ترکیب روی همان مسیرها)، پس مجموع سهم‌ها دقیقاً برابر کل زیان است (خطا ${at.interaction_pct.toExponential(0)}). مجموع: ${sfa(at.total_delta_pct, 1)}٪؛ احتمال افت نقدینگی از ${pct(at.base_breach)} به ${pct(at.total_breach)} می‌رسد. توجه: ارزش دارایی به بهای جایگزینی سنجیده می‌شود، پس جهش ارز ارزش موجودی را بالا می‌برد و زیان اصلی از کانال نقدینگی و کمبود می‌آید.`}>
        <Chart option={o.at} />
        <Table heads={["عامل", "سهم شاپلی از تغییر ارزش (٪)", "به‌تنهایی (٪)", "سهم شاپلی از احتمال افت نقدینگی", "به‌تنهایی"]} rows={at.rows.map((x) => [x.label_fa, sfa(x.delta_pct, 1), sfa(x.alone_pct, 1), pct(x.breach, 0), pct(x.alone_breach, 0)])} cls={["", "num", "num", "num", "num"]} />
      </Panel>
      <Grid2>
        <Panel title="سهم بهینه‌ی خرید امروز در برابر روند سالانه‌ی دلار">{o.fl && <Chart option={o.fl} />}</Panel>
        <Panel title="سهم بهینه‌ی خرید امروز در برابر احتمال توافق/کاهش تنش (٪)">{o.fp && <Chart option={o.fp} />}</Panel>
        <Panel title="سهم بهینه‌ی خرید امروز در برابر زمان تحویل عادی (روز)" sub="آستانه‌ی بازنگری: جایی که سهم خرید فوری از نصف می‌گذرد">{o.fe && <Chart option={o.fe} />}</Panel>
      </Grid2>
    </Stack>
  );
}

export function TabReverse({ r, t }) {
  const [coffee, setCoffee] = useState(0);
  const [policy, setPolicy] = useState("recommended");
  const rv = r?.reverse;
  const o = useMemo(() => rv && heatmapOption(t, rv, coffee, policy), [t, rv, coffee, policy]);
  if (!r) return need;
  const nm = { recommended: "توصیه‌شده", all_now: "همه امروز" };
  const tolRows = Object.keys(nm).map((k) => { const x = rv.tolerance[k], w = rv.weakest[k];
    return [nm[k], tolCell(x.fx, (v) => pct(v)), tolCell(x.coffee, (v) => pct(v)), tolCell(x.delay_weeks, (v) => fa(v) + " هفته"),
      w ? `جهش دلار ${pct(w.fx)} · جهش قهوه ${pct(w.coffee)} · تأخیر ${fa(w.delay_weeks)} هفته (${w.kind === "supply" ? "تأمین" : "نقدینگی"}؛ شدت ${fa(w.severity, 2)})` : "شکست دیده نشد"]; });
  return (
    <Stack>
      <Panel title="تست استرس معکوس" sub={`به‌جای «در سناریوی X چه می‌شود؟»: کدام ترکیب شوک‌ها برنامه را از کار می‌اندازد؟ شکست = در دست‌کم ${pct(rv.fail_prob)} مسیرها نقدینگی زیر حد ایمن برود یا کمبود از ${pct(rv.fail_unmet)} تقاضا بیشتر شود. شوک‌ها روی همان مسیرهای پایه اعمال می‌شوند.`}>
        <Table heads={["سیاست", "تحمل جهش دلار", "تحمل جهش قهوه", "تحمل تأخیر تحویل", "ضعیف‌ترین ترکیب شکست"]} rows={tolRows} />
        <p className="muted small mt-2">شدت = فاصله‌ی اقلیدسی در واحد: انحراف معیار ۱۳‌هفته‌ی تاریخی ارز ({fa(rv.units.fx, 3)}) و قهوه ({fa(rv.units.coffee, 3)}) در مقیاس لگاریتمی، و تأخیر بر حسب مضرب زمان تحویل عادی ({fa(rv.units.delay_weeks)} هفته). فرض استقلال محورها با همبستگی تقریباً صفر اندازه‌گیری‌شده سازگار است. ضعیف‌ترین شکست = ترکیب شکست‌خورده با کمترین شدت (کمینه‌ی نُرم).</p>
      </Panel>
      <Panel title="نقشه‌ی شکست: جهش دلار × تأخیر تحویل">
        <div className="mb-2 flex flex-wrap items-center gap-4 text-sm">
          <label className="flex items-center gap-2">سیاست <select className="input !mt-0 !w-auto" value={policy} onChange={(e) => setPolicy(e.target.value)}>{Object.entries(nm).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>
          <label className="flex items-center gap-2">جهش قهوه <select className="input !mt-0 !w-auto" value={coffee} onChange={(e) => setCoffee(Number(e.target.value))}>{rv.coffee_grid.map((c) => <option key={c} value={c}>{pct(c)}</option>)}</select></label>
        </div>
        <Legend items={[[t.s3, "✓ تاب می‌آورد"], ["#e0a526", "✓ نزدیک به مرز"], [t.s2, "✗ شکست"]]} />
        <Chart option={o} tall label="نقشه شکست" />
      </Panel>
    </Stack>
  );
}

export function TabBacktest({ S }) {
  const b = S.bt;
  if (!b || !b.fx) return <Empty>بک‌تست‌ها اجرا نشده‌اند (scripts/run_backtests.py).</Empty>;
  const fx = b.fx, cf = b.coffee, rp = b.replay;
  const fxRows = Object.entries(fx.models).map(([k, v]) => [k, fa(v.crps, 4), pct(v.coverage["50"], 0), pct(v.coverage["80"], 0), pct(v.coverage["90"], 0), fx.dm_vs_best[k] ? fa(fx.dm_vs_best[k].p, 3) : "بهترین"]);
  const cfRows = Object.entries(cf.models).flatMap(([k, v]) => Object.entries(v).map(([lv, x]) => [k, lv + "٪", `${x.violations}/${x.n}`, pct(x.rate, 1), fa(x.p, 3), fa(x.independence_p, 3)]));
  const rpRows = Object.entries(rp.policies).map(([k, v]) => [NAMES[k] || k, pp(v.deposit.advantage_of_earlier_mean * 100, 1), `${pp(v.deposit.ci[0] * 100, 1)} تا ${pp(v.deposit.ci[1] * 100, 1)}`, pct(v.deposit.share_windows_earlier_better, 0), pp(v.borrow.advantage_of_earlier_mean * 100, 1), `${pp(v.borrow.ci[0] * 100, 1)} تا ${pp(v.borrow.ci[1] * 100, 1)}`]);
  return (
    <Stack>
      <Panel title={`پیش‌بینی توزیع تغییر ۱۳هفته‌ای ارز — ${fa(fx.n_origins)} مبدأ، پنجره‌ی انبساطی`} sub={<>بهترین CRPS: {fx.best_by_crps}. مجموعه‌ی نامتمایز: {fx.tie_set.join("، ")}. مدل انتخابی برای auto: <b>{fx.selected}</b>. مدل بدون روند (rw0) معنادار بدتر است ⇒ روند واقعی است.</>}>
        <Table heads={["مدل", "CRPS (کمتر بهتر)", "پوشش ۵۰٪", "پوشش ۸۰٪", "پوشش ۹۰٪", "p دیبولد–ماریانو در برابر بهترین"]} rows={fxRows} cls={["", "num", "num", "num", "num", "num"]} /></Panel>
      <Panel title={`VaR هفتگی قهوه — ${fa(cf.n_forecasts)} پیش‌بینی خارج از نمونه`} sub="p>0.05 یعنی پوشش مشاهده‌شده با پوشش اسمی سازگار است.">
        <Table heads={["مدل", "سطح", "تخطی", "نرخ", "p کوپیک", "p استقلال کریستوفرسن"]} rows={cfRows} cls={["", "", "num", "num", "num", "num"]} /></Panel>
      <Panel title={`بازپخش تاریخی مدل‌آزاد — ${fa(rp.n_windows)} پنجره‌ی ۱۳هفته‌ای (${rp.start} تا ${rp.end})`} sub={`هزینه‌ی ریالی با قیمت‌های واقعی؛ پس از کسر هزینه‌ی سرمایه و انبارداری. پنجره‌ها هم‌پوشان‌اند ⇒ بوت‌استرپ ایستا با بلوک ۱۳. در ${pct(rp.fx_13w_change.share_down, 0)} پنجره‌ها دلار پایین آمده است.`}>
        <Table heads={["مقایسه با «همه امروز»", "مزیت خرید زودتر (سپرده)", "بازه‌ی بوت‌استرپ", "سهم پنجره‌ها", "مزیت (وام)", "بازه"]} rows={rpRows} /></Panel>
    </Stack>
  );
}

export function TabAssump({ S }) {
  const sc = S.res ? S.res.scenario : S.defaults;
  const rows = S.schema.map((f) => [GROUP_FA[f.group] || f.group, f.label_fa, f.unit || "", Array.isArray(sc[f.name]) ? sc[f.name].join(",") : String(sc[f.name] ?? "خودکار"), <Badge key={f.name} p={f.provenance} />]);
  return <Panel title="همه‌ی فرضیات و منشأ آن‌ها" sub="«نمونه» = باید با داده‌ی شرکت جایگزین شود. «قضاوت» = بدون داده‌ی شناسایی‌کننده؛ در جهان‌های ممکن تغییر داده می‌شود. «از داده» = برآوردشده.">
    <Table heads={["گروه", "پارامتر", "واحد", "مقدار", "منشأ"]} rows={rows} cls={["", "", "", "num", ""]} /></Panel>;
}

export const TabMethod = () => (
  <Panel title="روش‌شناسی (خلاصه)" className="max-w-4xl">
    <ol className="small list-decimal ps-5 leading-[2.1]">
      <li><b>قهوه:</b> شبیه‌سازی تاریخی بازده‌های لگاریتمی هفتگی (۲۶ سال، فقط روزهای نقدشونده)، تصحیح میانگین تا قیمت آتی مارتینگل باشد (E[P_T]=P_0). ARCH-LM هفتگی معنادار نیست ⇒ بدون GARCH.</li>
      <li><b>ارز:</b> مدل مارکوف دو‌حالته با میانگین و واریانس متغیر (Hamilton 1989)؛ انتخاب بین gbm/t/regime با CRPS خارج از نمونه و آزمون دیبولد–ماریانو. روند بلندمدت با نظر کاربر قابل‌جایگزینی است. نرخ مؤثر پرداخت = بازار × ضریب دسترسی × (۱+هزینه‌ی انتقال).</li>
      <li><b>رویداد:</b> جهش‌های اضافه‌ی تشدید/توافق؛ اندازه از دم‌های تجربی تاریخچه، احتمال = قضاوت کاربر (پیش‌فرض صفر). احتمال تأخیر محموله نیز قضاوت کاربر و پیش‌فرض صفر است؛ اثر تأخیر در سناریوهای تنش سنجیده می‌شود.</li>
      <li><b>وابستگی:</b> کاپولای گاوسی با ρ=sin(πτ/2)؛ تقاضا با شوک ارز هم‌بسته (wrong-way risk).</li>
      <li><b>موتور:</b> هفتگی با ترتیب رویداد مشخص: سفارش/پرداخت → رسیدن کالا (با تأخیر احتمالی در هر مسیر) → تقاضا و فروش → FIFO، انبارداری، افت → هزینه‌ی جاری → وصول مطالبات و بهره. ارزش پایان افق: بهای جایگزینی.</li>
      <li><b>هدف:</b> J=(1−λ)E[Π]+λ·CVaR_α[Π] (Rockafellar–Uryasev 2000)، با قیود احتمال افت نقدینگی و کمبود، و ریسک افتادن موجودی زیر حداقل ایمن گزارش می‌شود.</li>
      <li><b>سناریوهای تنش:</b> پنج سناریوی اصلی (عادی، جهش ارزی، شوک دوگانه، اختلال واردات، بحران شدید) + سه سناریوی مخالف، با اعمال قطعی روی همان مسیرهای پایه (اعداد تصادفی مشترک). بدون احتمال ادعاشده.</li>
      <li><b>تست استرس معکوس:</b> شبکه‌ی جهش دلار × جهش قهوه × تأخیر تحویل؛ شکست = افت نقدینگی در ≥۵۰٪ مسیرها یا کمبود ≥۲۰٪؛ ضعیف‌ترین ترکیب شکست = کمینه‌ی نُرم اقلیدسی در واحدهای σ تاریخی (برگرفته از رویکرد تست‌های استرس سیستماتیک).</li>
      <li><b>بهینه‌سازی مقاوم:</b> Latin-hypercube روی پارامترهای نامطمئن؛ قید شانسی (≥۸۰٪ جهان‌ها) + مینیمکس ریگرت (چندک ۹۰٪)، و به‌عنوان معیار مکمل بهینه‌ی بدترین‌حالت روی مجموعه‌ی سناریوها. تعداد جهان‌ها با آزمون همگرایی (زیرنمونه‌گیری) سنجیده و در صورت ناپایداری خودکار افزایش می‌یابد.</li>
      <li><b>قرارداد خرید:</b> دو نوع تعهد: «مقدار ثابت» (همه‌ی سیاست‌ها همان کیلوگرم را می‌خرند) یا «مبلغ دلاری ثابت» (هر قسط همان دلار را خرج می‌کند و کیلوگرم با قیمت روز سفارش تغییر می‌کند). قیمت دلاری فاکتور هنگام سفارش ثابت می‌شود؛ سهم پیش‌پرداخت با نرخ ارز روز سفارش و باقی با نرخ روز ورود کالا پرداخت می‌شود. مانده‌ی پرداخت‌نشده‌ی کالای در راه در پایان افق از ثروت کسر می‌شود؛ محموله‌ی گم‌شده نه وارد موجودی می‌شود نه مانده‌اش پرداخت می‌شود و پیش‌پرداخت زیان است.</li>
      <li><b>تفکیک عوامل (شاپلی):</b> شش عامل بحران شدید (دلار، قهوه، تأخیر و گرانی حمل، افت تقاضا، تأخیر وصول، گم‌شدن محموله)؛ سهم هر عامل با مقدار شاپلی دقیق (۶۴ ترکیب روی همان مسیرها) و مجموع سهم‌ها برابر کل زیان (آزمون کارایی).</li>
      <li><b>آستانه‌ی باور و نقشه‌ی تصمیم:</b> برای هر باور (روند دلار، احتمال تشدید، شدت جهش) مقداری که خرید یک‌جا و برنامه‌ی پیشنهادی را هم‌ارزش می‌کند با ریشه‌یابی Brent؛ و نقشه‌ی دوبعدی روند دلار × احتمال تشدید با ✗ برای جاهایی که خرید یک‌جا حدود را نقض می‌کند.</li>
      <li><b>گم‌شدن محموله:</b> باور کاربر (پیش‌فرض ۰): در درصدی از مسیرهای دارای تأخیر، محموله هرگز نمی‌رسد و پیش‌پرداخت از دست می‌رود. اتحاد حسابداری ΔW = سود FIFO − افت وزنی − محموله‌ی گم‌شده + سود نگهداری در آزمون واحد بررسی می‌شود.</li>
      <li><b>اعتبارسنجی:</b> کوپیک/کریستوفرسن، CRPS+DM، بازپخش مدل‌آزاد با بوت‌استرپ ایستا؛ آزمون‌های واحد از جمله بازیابی پارامتر، شرط carry تحلیلی، اثر تأخیر و پایداری همگرایی.</li>
    </ol>
    <p className="muted small mt-3">جزئیات و مراجع: docs/METHODOLOGY.md</p>
  </Panel>
);

export function TabDecision({ r, t }) {
  const dm = r?.decision_map;
  const o = useMemo(() => dm && decisionMapOption(t, dm.map, dm.base), [t, dm]);
  if (!r) return need;
  if (!dm) return <Empty>«تحلیل حساسیت تصمیم» در تنظیمات خاموش بوده است.</Empty>;
  const be = dm.break_even.map((b) => [b.label_fa, fa(b.base, 1) + " " + b.unit,
    b.status === "crossing" ? fa(b.root, 1) + " " + b.unit : b.status === "staged_always_better" ? "هرگز (مرحله‌ای همیشه بهتر)" : "همیشه (خرید یک‌جا بهتر)",
    b.status === "crossing" ? "≈ " + pct(b.fx_rise_at_root, 0) : "—",
    b.status === "crossing" ? (b.now_feasible_at_root ? "رعایت می‌کند" : "نقض می‌کند") : "—"]);
  const ac = r.accounting;
  const nm = { recommended: "برنامه‌ی پیشنهادی", all_now: "خرید یک‌جا" };
  return (
    <Stack>
      <Panel title="آستانه‌ی باور (break-even)" sub="مقدار یک باور که در آن «خرید یک‌جا» و «برنامه‌ی پیشنهادی» ارزش هدف برابر دارند (ریشه‌یابی Brent روی اختلاف دو ارزش، روی مسیرهای تصادفی یکسان). بالاتر از آن، خرید یک‌جا از نظر ارزش هدف برنده است.">
        <Table heads={["باور", "مقدار فعلی", "آستانه", "رشد مورد انتظار دلار در افق در آستانه", "خرید یک‌جا در آستانه حدود را…"]} rows={be} cls={["", "num", "num", "num", ""]} />
        <ul className="small muted mt-2 list-disc ps-5">{(r.advice.break_even || []).map((b, i) => <li key={i}>{b.text}</li>)}</ul>
      </Panel>
      <Panel title="نقشه‌ی تصمیم: روند دلار × احتمال تشدید تنش" sub="رنگ و عدد = ارزش هدف خرید یک‌جا منهای ارزش برنامه‌ی پیشنهادی (٪ ارزش محموله): آبی یعنی مرحله‌ای بهتر، نارنجی یعنی خرید یک‌جا بهتر. ✗ یعنی در آن باور، خرید یک‌جا حدود نقدینگی/کمبود را نقض می‌کند، پس حتی با ارزش بالاتر مجاز نیست.">
        <Chart option={o} label="نقشه‌ی تصمیم" tall />
      </Panel>
      <Panel title="تفکیک حسابداری تغییر ثروت" sub="تغییر ثروت = سود حسابداری FIFO − افت وزنی − محموله‌ی گم‌شده + سود نگهداری (ارزش جایگزینی منهای بهای تمام‌شده). میانگین روی مسیرها، میلیارد ریال. ستون آخر بیشینه‌ی خطای این اتحاد روی همه‌ی مسیرها است (آزمون واحد).">
        <Table heads={["برنامه", "تغییر ثروت", "سود FIFO", "افت وزنی", "محموله‌ی گم‌شده", "سود نگهداری", "بیشینه‌ی خطا (ریال)"]}
          rows={Object.keys(nm).map((k) => [nm[k], fa(ac[k].delta_w_bn, 1), fa(ac[k].fifo_profit_bn, 1), fa(ac[k].shrink_cost_bn, 2), fa(ac[k].lost_cost_bn, 1), fa(ac[k].holding_gain_bn, 1), ac[k].max_abs_error_rial.toExponential(1)])} cls={["", "num", "num", "num", "num", "num", "num"]} />
      </Panel>
    </Stack>
  );
}
