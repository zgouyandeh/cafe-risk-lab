import { useEffect, useState } from "react";
import { FileText, Play, RotateCcw } from "lucide-react";
import { api } from "../lib/api.js";
import { fa, jdate } from "../lib/format.js";
import { useTheme } from "../lib/theme.jsx";
import { useCompany } from "../lib/company.jsx";
import { reportUrl } from "../lib/static.jsx";
import { useSim } from "../lib/useSim.js";
import Field, { initialValues, toScenario } from "../components/Field.jsx";
import { Empty, Progress } from "../components/ui.jsx";
import { GROUP_FA, TabAssump, TabBacktest, TabDecision, TabForecast, TabMethod, TabModels, TabPolicies, TabReverse, TabRobust, TabStress, TabSummary } from "./ExpertTabs.jsx";

const TABS = [["summary", "خلاصه"], ["models", "داده و مدل‌ها"], ["forecast", "پیش‌بینی و مسیرها"], ["policies", "سیاست‌ها و مرز کارا"], ["robust", "استحکام"],
  ["stress", "سناریوها و شاپلی"], ["decision", "آستانه و نقشه‌ی تصمیم"], ["reverse", "تنش معکوس"], ["backtest", "بک‌تست"], ["assump", "فرضیات"], ["method", "روش‌شناسی"]];
const KEY = ["fx_basis_factor", "import_delay_days"];

export default function Expert() {
  const { t } = useTheme();
  const [S, setS] = useState(null);
  const [vals, setVals] = useState({});
  const [tab, setTab] = useState("summary");
  const [err, setErr] = useState(null);
  const [sim, run] = useSim("expert");
  const company = useCompany();

  useEffect(() => {
    Promise.all([api("/config/defaults"), api("/data/summary"), api("/backtests")]).then(([d, ds, bt]) => {
      setS({ schema: d.schema, defaults: d.scenario, data: ds, bt });
      setVals(initialValues(d.schema));
    }).catch((e) => setErr(e.message));
  }, []);

  useEffect(() => { if (S) setVals((v) => ({ ...v, ...company.fieldVals() })); }, [company.token, !!S]); // eslint-disable-line
  if (err) return <Empty>خطا: {err}</Empty>;
  if (!S) return <Empty>در حال بارگذاری…</Empty>;
  const groups = {};
  S.schema.filter((f) => f.level !== "internal").forEach((f) => (groups[f.group] ||= []).push({ ...f, provenance: company.provOf(f.name) || f.provenance }));
  const ctx = { ...S, res: sim.result };
  const submit = (e) => { e.preventDefault(); const sc = toScenario(S.schema, vals, S.defaults); delete sc.risk_lambda; run({ ...sc, ...company.internal() }, company.dataSource()); };
  const body = { summary: <TabSummary r={sim.result} />, models: <TabModels S={ctx} t={t} />, forecast: <TabForecast r={sim.result} t={t} />, policies: <TabPolicies r={sim.result} t={t} />,
    robust: <TabRobust r={sim.result} t={t} />, stress: <TabStress r={sim.result} t={t} />, decision: <TabDecision r={sim.result} t={t} />, reverse: <TabReverse r={sim.result} t={t} />, backtest: <TabBacktest S={ctx} />, assump: <TabAssump S={ctx} />, method: <TabMethod /> }[tab];

  return (
    <main className="mx-auto max-w-[1400px] px-4 py-6">
      <div className="muted small mb-4">دلار تا {jdate(S.data.as_of)} · قهوه (نقدشونده) تا {jdate(S.data.coffee_last_date)} · مدل انتخابی ارز: {S.data.fx_selected}</div>
      <div className="grid items-start gap-5 lg:grid-cols-[360px_minmax(0,1fr)]">
        <aside className="lg:sticky lg:top-24">
          <form onSubmit={submit} className="panel max-h-[calc(100vh-7rem)] overflow-y-auto" autoComplete="off">
            <fieldset className="mb-3 rounded-2xl p-3" style={{ border: "1px solid var(--accent)", background: "color-mix(in srgb, var(--accent) 8%, transparent)" }}>
              <legend className="px-2 text-sm font-semibold" style={{ color: "var(--accent)" }}>دو پارامتر کلیدی واردات</legend>
              {KEY.map((n) => { const f0 = S.schema.find((x) => x.name === n); const f = { ...f0, provenance: company.provOf(n) || f0.provenance }; return <Field key={n} f={f} value={vals[n]} onChange={(v) => setVals((s) => ({ ...s, [n]: v }))} />; })}
            </fieldset>
            {Object.entries(groups).map(([g, fs], i) => (
              <details key={g} open={i < 2} className="mb-2"><summary className="cursor-pointer py-1 font-semibold">{GROUP_FA[g] || g}</summary>
                {fs.filter((f) => !KEY.includes(f.name)).map((f) => <Field key={f.name} f={f} value={vals[f.name]} onChange={(v) => setVals((s) => ({ ...s, [f.name]: v }))} />)}</details>
            ))}
            <button className="btn-primary mt-2 w-full" disabled={sim.running} type="submit"><Play className="h-4 w-4" /> اجرای تحلیل</button>
            <button className="btn-ghost mt-2 w-full" type="button" onClick={() => setVals(initialValues(S.schema))}><RotateCcw className="h-4 w-4" /> بازگشت به پیش‌فرض‌ها</button>
            {sim.running && <><Progress value={sim.progress} /><div className="muted small mt-1" role="status">{sim.message}</div></>}
            {sim.error && <div className="mt-2 font-semibold" style={{ color: "var(--bad)" }}>خطا: {sim.error}</div>}
            {sim.result && <div className="muted small mt-2">انجام شد ({fa(sim.result.meta.elapsed_s, 1)} ثانیه)</div>}
            {sim.id && sim.result && <a className="btn-ghost mt-2 w-full no-underline" href={reportUrl(sim.id)} target="_blank" rel="noreferrer"><FileText className="h-4 w-4" /> گزارش قابل‌چاپ</a>}
          </form>
        </aside>
        <section className="min-w-0">
          <div role="tablist" className="mb-4 flex gap-1 overflow-x-auto pb-1">
            {TABS.map(([k, v]) => <button key={k} role="tab" type="button" className="tab" aria-selected={tab === k} onClick={() => setTab(k)}>{v}</button>)}
          </div>
          {body}
        </section>
      </div>
    </main>
  );
}
