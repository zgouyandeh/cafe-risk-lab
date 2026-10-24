import { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import { Calculator, FileText, AlertTriangle, Compass, LifeBuoy, Gauge, ShieldCheck, TrendingDown, Clock, Boxes, Banknote, Truck, Landmark } from "lucide-react";
import { api } from "../lib/api.js";
import { fa, pct, jdate, addDays, weightsText, tolCell } from "../lib/format.js";
import { useTheme } from "../lib/theme.jsx";
import { useSim } from "../lib/useSim.js";
import { useCompany } from "../lib/company.jsx";
import { reportUrl } from "../lib/static.jsx";
import { compareOption, fanOption, flipOption, stressBreachOption } from "../lib/options.js";
import Chart from "../components/Chart.jsx";
import Field, { initialValues, toScenario } from "../components/Field.jsx";
import { Empty, Html, Legend, Panel, Progress } from "../components/ui.jsx";
import { Link } from "../lib/router.jsx";

const KEY = ["fx_basis_factor", "import_delay_days"];
const GROUPS = [
  ["محموله و انبار", ["purchase_budget_usd", "initial_inventory_kg", "weekly_demand_kg", "safety_stock_weeks"]],
  ["پول و ریسک", ["initial_cash_bn_irr", "min_cash_bn_irr", "risk_appetite"]],
  ["نظر شما درباره‌ی بازار", ["inflation_pct", "fx_drift_annual_pct", "event_p_deal", "event_p_escalation"]],
];
const MORE = ["horizon_days", "lead_time_days", "import_delay_prob_pct", "fx_transfer_cost_pct", "target_markup_pct", "coffee_spot_c_lb", "fx_spot_irr", "region_label"];
const OPT_FA = { cautious: "محتاط", balanced: "متعادل", bold: "جسور" };
const ICONS = { "حداقل موجودی": Boxes, "خرید اضطراری": Truck, "تأمین‌کننده‌ی جایگزین": Compass, "کاهش تعهد خرید": TrendingDown, "خط اعتباری اضطراری": Landmark };

export default function Simple() {
  const { t, mode, palette } = useTheme();
  const [meta, setMeta] = useState(null);
  const [vals, setVals] = useState({});
  const [err, setErr] = useState(null);
  const [sim, run] = useSim("simple");
  const company = useCompany();

  useEffect(() => {
    Promise.all([api("/config/defaults"), api("/data/summary")]).then(([d, ds]) => {
      const schema = Object.fromEntries(d.schema.map((f) => [f.name, f]));
      setMeta({ schema, list: d.schema, defaults: d.scenario, data: ds });
      setVals(initialValues(d.schema));
    }).catch((e) => setErr(e.message));
  }, []);

  useEffect(() => { if (meta) setVals((v) => ({ ...v, ...company.fieldVals() })); }, [company.token, !!meta]); // eslint-disable-line
  if (err) return <Empty>خطا در بارگذاری: {err}</Empty>;
  if (!meta) return <Empty>در حال بارگذاری داده‌ها…</Empty>;
  const set = (n) => (v) => setVals((s) => ({ ...s, [n]: v }));
  const field = (n, extra = {}) => <Field key={n} f={{ ...meta.schema[n], provenance: company.provOf(n) || meta.schema[n].provenance }} value={vals[n]} onChange={set(n)} enumLabels={n === "risk_appetite" ? OPT_FA : {}} showProv={true}
    placeholder={n === "fx_drift_annual_pct" ? `برآورد تاریخی: ${fa(meta.data.report.fx.annual_drift_log * 100)}` : ""} {...extra} />;
  const submit = (e) => { e.preventDefault(); run({ ...toScenario(meta.list, vals, meta.defaults), ...company.internal() }, company.dataSource()); };

  return (
    <main className="mx-auto max-w-[1320px] px-4 py-6">
      <div className="muted small mb-4">نرخ دلار تا {jdate(meta.data.as_of)} · قیمت قهوه تا {jdate(meta.data.coffee_last_date)}</div>
      <div className="grid items-start gap-5 lg:grid-cols-[350px_minmax(0,1fr)]">
        <aside className="flex flex-col gap-3 lg:sticky lg:top-24">
          <form onSubmit={submit} className="panel" autoComplete="off">
            <fieldset className="mb-3 rounded-2xl p-3" style={{ border: "1px solid var(--accent)", background: "color-mix(in srgb, var(--accent) 8%, transparent)" }}>
              <legend className="flex items-center gap-1.5 px-2 text-sm font-semibold" style={{ color: "var(--accent)" }}><Gauge className="h-4 w-4" /> دو ورودی کلیدی واردات</legend>
              <p className="muted small">هزینه‌ی واقعی واردات فقط نرخ بازار نیست؛ نرخی که واقعاً می‌توانید با آن پرداخت کنید و زمان تحویل در بحران تعیین‌کننده‌اند.</p>
              {KEY.map((n) => field(n))}
            </fieldset>
            {GROUPS.map(([title, names]) => (
              <fieldset key={title} className="mb-2"><legend className="mb-1 font-semibold">{title}</legend>{names.map((n) => field(n))}</fieldset>
            ))}
            <details className="mb-3"><summary className="cursor-pointer py-1 font-semibold">جزئیات بیشتر</summary>{MORE.map((n) => field(n))}</details>
            <button className="btn-primary w-full" disabled={sim.running} type="submit"><Calculator className="h-4 w-4" /> محاسبه‌ی بهترین تصمیم</button>
            {sim.running && <><Progress value={sim.progress} /><div className="muted small mt-1" role="status">{sim.message}</div></>}
            {sim.error && <div className="mt-2 font-semibold" style={{ color: "var(--bad)" }}>خطا: {sim.error}</div>}
          </form>
          <p className="muted small px-1">برچسب «نمونه» یعنی عدد پیش‌فرض فقط برای نمایش است و باید با داده‌ی واقعی شرکت جایگزین شود.</p>
        </aside>
        <section aria-live="polite" className="flex min-w-0 flex-col gap-4">
          {sim.result ? <Results key={sim.id} res={sim.result} id={sim.id} t={t} /> : <Empty>ورودی‌ها را بررسی کنید و «محاسبه» را بزنید. نتیجه چند ثانیه بعد اینجا نمایش داده می‌شود.</Empty>}
        </section>
      </div>
    </main>
  );
}

function Timeline({ res, adv }) {
  const H = res.meta.H * 7, W = 900, h = 160, pad = 90;
  const x = (d) => pad + (d / H) * (W - 2 * pad);
  const maxShare = Math.max(...adv.schedule.map((s) => s.share), 0.01);
  return (
    <svg viewBox={`0 0 ${W} ${h}`} role="img" aria-label="زمان‌بندی خرید" className="block h-auto w-full" style={{ direction: "ltr" }}>
      <defs><linearGradient id="tlg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" style={{ stopColor: "var(--accent2)" }} /><stop offset="1" style={{ stopColor: "var(--accent)" }} /></linearGradient></defs>
      <line x1={pad} x2={W - pad} y1={h - 36} y2={h - 36} stroke="var(--line)" strokeWidth="2" />
      {adv.schedule.map((s) => {
        const bh = 22 + 78 * (s.share / maxShare), cx = x(s.day);
        return (
          <g key={s.day} style={{ fontFamily: "Vazirmatn" }}>
            <rect x={cx - 28} y={h - 36 - bh} width="56" height={bh} rx="8" fill="url(#tlg)" />
            <text x={cx} y={h - 42 - bh} textAnchor="middle" fontSize="17" fontWeight="700" fill="var(--ink)">{pct(s.share)}</text>
            <text x={cx} y={h - 20} textAnchor="middle" fontSize="13" fill="var(--ink2)">{s.day === 0 ? "امروز" : fa(s.day) + " روز بعد"}</text>
            <text x={cx} y={h - 5} textAnchor="middle" fontSize="11.5" fill="var(--ink3)">{fa(s.kg)} کیلو · {fa(s.usd)}$</text>
            <title>{jdate(addDays(res.meta.as_of, s.day))}</title>
          </g>
        );
      })}
    </svg>
  );
}

function Results({ res, id, t }) {
  const a = res.advice, days = res.meta.schedule_days, conf = a.confidence;
  const confColor = conf ? { "بالا": "var(--good)", "متوسط": "var(--warn)", "پایین": "var(--bad)" }[conf.level] : "var(--ink3)";
  const marks = useMemo(() => res.meta.schedule_weeks.map((w, i) => [w, i === 0 ? "امروز" : fa(days[i]) + " روز"]), [res]);
  const o1 = useMemo(() => compareOption(t, res), [t, res]);
  const o2 = useMemo(() => fanOption(t, res.fans.fx, res.meta.weeks, res.meta.as_of, "", res.meta.X0 / 1e6, marks), [t, res]);
  const o3 = useMemo(() => res.flip.drift && flipOption(t, res.flip.drift, { simple: true, xname: "رشد سالانه‌ی دلار (٪)" }), [t, res]);
  const o4 = useMemo(() => stressBreachOption(t, res), [t, res]);
  const tol = res.reverse?.tolerance?.recommended, wk = res.reverse?.weakest?.recommended;
  const wc = a.worst_case;

  return (
    <>
      <Panel className="!p-6">
        <div className="muted small">برنامه‌ی پیشنهادی برای محموله‌ی {fa(res.scenario.purchase_budget_usd)} دلاری {res.scenario.region_label ? "· " + res.scenario.region_label : ""}</div>
        <div className="mt-1 text-sm font-semibold" style={{ color: "var(--accent)" }}>{a.decision.kind}</div>
        <div className="my-1 mb-3 text-2xl font-bold leading-snug">{weightsText(res.recommended.weights, days)}</div>
        <Timeline res={res} adv={a} />
        {conf && <div className="mt-3 flex items-start gap-2 font-semibold"><i className="mt-2 inline-block h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: confColor }} />
          <span>اطمینان {conf.level}: <span className="small font-normal">{conf.text}</span></span></div>}
      </Panel>

      {a.status && !a.status.respects_limits && (
        <Panel className="!p-5" delay={0.02}>
          <div className="flex gap-3"><AlertTriangle className="mt-1 h-5 w-5 shrink-0" style={{ color: "var(--bad)" }} />
            <div><b>این برنامه همه‌ی حدود شما را رعایت نمی‌کند</b>
              <ul className="small mt-1 list-disc ps-5">{a.status.violations.map((v, i) => <li key={i}>{v}</li>)}</ul>
              <p className="small mt-2">{a.status.any_feasible_option ? "گزینه‌ی دیگری هست که حدود را رعایت می‌کند؛ پیش از تصمیم با آن مقایسه کنید." : "هیچ زمان‌بندی‌ای همه‌ی حدود را رعایت نمی‌کند. این فقط کم‌نقض‌ترین گزینه است، نه یک گزینه‌ی قابل‌قبول؛ حدود یا فرضیات (نقدینگی، زمان تحویل، مقدار خرید) را بازبینی کنید."}</p></div></div>
        </Panel>)}

      <Panel title="چرا این تصمیم؟" delay={0.05}>
        <div className="grid gap-3 md:grid-cols-3">
          {a.why.map((w, i) => {
            const Icon = [Banknote, ShieldCheck, Boxes][i];
            return <div key={w.title} className="rounded-2xl p-3" style={{ border: "1px solid var(--line)" }}>
              <div className="flex items-center gap-2 font-semibold"><Icon className="h-4 w-4" style={{ color: "var(--accent)" }} />{w.title}</div>
              <p className="small mt-1 text-ink2">{w.text}</p></div>;
          })}
        </div>
        <h4 className="mt-4 font-semibold">دو چیزی که این تصمیم را می‌سازد</h4>
        <div className="mt-2 grid gap-3 md:grid-cols-2">
          {a.factors.slice(0, 2).map((f) => (
            <div key={f.title} className="py-1 ps-3" style={{ borderInlineStart: "3px solid var(--accent)" }}><b>{f.title}</b><div className="small text-ink2"><Html html={f.text} /></div></div>
          ))}
        </div>
      </Panel>

      <div className="grid gap-4 xl:grid-cols-2">
        <Panel title="این برنامه در برابر گزینه‌های ساده" sub="تفاوت با برنامه‌ی پیشنهادی، به درصد ارزش محموله (مثبت = بهتر از پیشنهاد)">
          <Legend items={[[t.s1, "در حالت میانگین"], [t.s2, "در بدترین ۵٪ سناریوها"]]} /><Chart option={o1} label="مقایسه گزینه‌ها" />
        </Panel>
        <Panel title="دلار در ۳ ماه آینده (میلیون ریال)" sub="میانه و بازه‌های ۵۰٪ و ۹۰٪؛ خط‌چین‌ها روزهای خرید"><Chart option={o2} label="پیش‌بینی نرخ دلار" /></Panel>
        <Panel className="xl:col-span-2" title="در سناریوهای تنش نقدینگی چقدر در خطر است؟" sub="احتمال افتادن نقدینگی زیر حد ایمن. شوک‌ها آزمون تاب‌آوری‌اند، نه پیش‌بینی"><Chart option={o4} label="ریسک نقدینگی در سناریوها" /></Panel>
        {o3 && <Panel title="اگر نظر شما درباره‌ی دلار فرق کند…" sub="سهم بهینه‌ی خرید امروز بر حسب رشد سالانه‌ی دلار">
          <Legend items={[[t.s1, "با قید نقدینگی"], [t.s3, "بدون قید"]]} /><Chart option={o3} label="حساسیت تصمیم" /></Panel>}
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Panel title="بدترین وضعیت قابل‌تصور در سناریوهای بررسی‌شده" delay={0.05}>
          <div className="flex gap-3"><AlertTriangle className="mt-1 h-5 w-5 shrink-0" style={{ color: "var(--bad)" }} />
            <div><p className="small">{wc.text}</p>{wc.tradeoff && <p className="small mt-2 font-medium" style={{ color: "var(--warn)" }}>{wc.tradeoff}</p>}</div></div>
          {tol && (
            <div className="mt-3 grid grid-cols-2 gap-2">
              <div className="rounded-2xl p-3" style={{ border: "1px solid var(--line)" }}><div className="muted small">تحمل جهش دلار</div>
                <b className="small">{tolCell(tol.fx, (v) => pct(v), "تا حدود بررسی‌شده تاب می‌آورد")}</b>{tol.fx.fails_at != null && (tol.fx.survives_up_to ?? 0) > 0 && <div className="muted small">شکست از {pct(tol.fx.fails_at)}</div>}</div>
              <div className="rounded-2xl p-3" style={{ border: "1px solid var(--line)" }}><div className="muted small">تحمل تأخیر تحویل</div>
                <b className="small">{tolCell(tol.delay_weeks, (v) => fa(v) + " هفته", "تا حدود بررسی‌شده تاب می‌آورد")}</b>{tol.delay_weeks.fails_at != null && (tol.delay_weeks.survives_up_to ?? 0) > 0 && <div className="muted small">شکست از {fa(tol.delay_weeks.fails_at)} هفته</div>}</div>
            </div>)}
          {wk && <p className="muted small mt-2">ضعیف‌ترین ترکیبی که برنامه را از کار می‌اندازد (تست استرس معکوس): جهش دلار {pct(wk.fx)}، تأخیر {fa(wk.delay_weeks)} هفته ({wk.kind === "supply" ? "کمبود تأمین" : "کمبود نقدینگی"}).</p>}
        </Panel>
        <Panel title="چه زمانی این تصمیم دیگر مناسب نیست؟" delay={0.1}>
          <ul className="flex flex-col gap-2">{a.triggers.map((x, i) => <li key={i} className="flex gap-2 small"><Compass className="mt-1 h-4 w-4 shrink-0" style={{ color: "var(--accent)" }} />{x}</li>)}</ul>
          {a.break_even && <><h4 className="mt-3 font-semibold">آستانه‌ی باور شما</h4><ul className="small mt-1 list-disc ps-5">{a.break_even.map((b, i) => <li key={i}>{b.text}</li>)}</ul></>}
        </Panel>
      </div>

      <Panel title="برنامه‌ی جایگزین" sub="اگر وضعیت بدتر از انتظار شد" delay={0.1}>
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {a.contingency.map((c) => { const Icon = ICONS[c.title] || LifeBuoy;
            return <div key={c.title} className="rounded-2xl p-3" style={{ border: "1px solid var(--line)" }}>
              <div className="flex items-center gap-2 font-semibold"><Icon className="h-4 w-4" style={{ color: "var(--accent)" }} />{c.title}</div>
              <p className="small mt-1 text-ink2">{c.text}</p></div>; })}
        </div>
      </Panel>

      <Panel>
        <details><summary className="cursor-pointer font-semibold">شواهد و محدودیت‌ها</summary>
          <ul className="small mt-2 list-disc ps-5">{a.evidence.map((e, i) => <li key={i}><Html html={e} /></li>)}{a.flip && <li>{a.flip.text}</li>}</ul>
          {a.technical && <ul className="muted small mt-2 list-disc ps-5">{a.technical.map((e, i) => <li key={i}><b>{e.title}: </b>{e.text}</li>)}</ul>}
          <ul className="muted small mt-2 list-disc ps-5">{a.notes.map((n, i) => <li key={i}><Html html={n} /></li>)}</ul>
          <p className="small mt-3 flex flex-wrap gap-4">
            <a href={reportUrl(id)} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1"><FileText className="h-4 w-4" /> گزارش مدیریتی قابل‌چاپ</a>
            <Link to="/expert">جزئیات ریاضی در نسخه‌ی متخصص</Link>
          </p>
        </details>
      </Panel>
    </>
  );
}
