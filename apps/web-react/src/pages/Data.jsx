import { useState } from "react";
import { motion } from "framer-motion";
import { ArrowLeft, Database, Download, FlaskConical, Upload } from "lucide-react";
import { fa, jdate } from "../lib/format.js";
import { useTheme } from "../lib/theme.jsx";
import { useCompany } from "../lib/company.jsx";
import { useRoute } from "../lib/router.jsx";
import { STATIC } from "../lib/static.jsx";
import Chart from "../components/Chart.jsx";
import { Empty, Grid2, Kpi, Panel, Stack, Table } from "../components/ui.jsx";
import { cashOption, fxOption, pnlOption, priceOption, salesOption, stockOption } from "../lib/companyOptions.js";

const nf = (x, d = 2) => (x == null ? "—" : Math.abs(x) >= 1000 ? fa(x, 0) : fa(x, d));
const ISSUE_FA = { duplicate_rows: "ردیف تکراری", missing: "مقدار گمشده", outlier: "نقطه‌ی پرت", invalid_fx_paid: "نرخ ارز ثبت‌شده نامعتبر", irregular_weeks: "هفته‌ی نامنظم", interpolated_arabica_weeks: "هفته‌ی بدون معامله‌ی آرابیکا (درون‌یابی)" };
const REQUIRED = ["market_weekly", "sales_weekly", "purchases", "inventory_weekly", "collections_weekly", "cash_weekly", "opex_weekly"];

function SourceCard({ icon: Icon, title, text, children, active }) {
  return (
    <div className="panel" style={active ? { outline: "2px solid var(--accent)" } : undefined}>
      <h3 className="flex items-center gap-2 font-semibold"><Icon className="h-5 w-5" style={{ color: "var(--accent)" }} />{title}</h3>
      <p className="muted small mt-1">{text}</p><div className="mt-3 flex flex-wrap gap-2">{children}</div>
    </div>
  );
}

function Upload_({ view, company }) {
  const [status, setStatus] = useState({});
  const send = async (name, file) => {
    try {
      const body = await file.text();
      const r = await fetch("/company/upload/" + name, { method: "PUT", body });
      if (!r.ok) throw new Error((await r.text()).slice(0, 200));
      const j = await r.json();
      setStatus((s) => ({ ...s, [name]: "✓ " + j.rows + " ردیف" }));
    } catch (e) { setStatus((s) => ({ ...s, [name]: "✗ " + e.message })); }
  };
  const names = Object.keys(view?.tables || {}).length ? Object.keys(view.tables) : [...REQUIRED, "pnl_weekly", "annual_pnl", "annual_balance", "annual_by_product"];
  return (
    <Panel title="بارگذاری جدول‌های شرکت (CSV، UTF-8)" sub={`جدول‌های ستاره‌دار لازم‌اند. قالب خالی هر جدول را دانلود کنید. ${""}`}>
      <div className="grid gap-2 md:grid-cols-2">
        {names.map((n) => (
          <div key={n} className="flex items-center justify-between gap-2 rounded-xl p-2" style={{ border: "1px solid var(--line)" }}>
            <span className="small"><b>{n}{REQUIRED.includes(n) ? " *" : ""}</b><br /><a href={`/company/template/${n}.csv`} className="muted">قالب</a></span>
            <span className="muted small">{status[n] || ""}</span>
            <input type="file" accept=".csv,text/csv" className="small" onChange={(e) => e.target.files[0] && send(n, e.target.files[0])} />
          </div>
        ))}
      </div>
      <button className="btn-primary mt-3" disabled={company.busy} onClick={company.calibrateUpload}>برآورد پارامترها از داده‌ی بارگذاری‌شده</button>
    </Panel>
  );
}

export default function Data() {
  const { t } = useTheme();
  const { go } = useRoute();
  const company = useCompany();
  const { view } = company;
  const [tbl, setTbl] = useState("sales_weekly");
  const [mode, setMode] = useState("demo");
  const synth = view?.synthetic;

  return (
    <main className="mx-auto max-w-[1400px] px-4 py-6">
      <Stack>
        <div className="grid gap-4 md:grid-cols-2">
          <SourceCard icon={FlaskConical} title="شرکت نمونه‌ی ساختگی (بزرگ)" active={mode === "demo"} text="۲۵۵ هفته (حدود ۴٫۹ سال)، چهار محصول، ۱۱ جدول هفتگی و سالانه. فقط آرابیکا و دلار واقعی‌اند؛ باقی با فرایند مولد با پارامترهای معلوم تولید شده تا درستیِ برآورد قابل‌آزمون باشد.">
            <button className="btn-primary" disabled={company.busy} onClick={() => { setMode("demo"); company.loadDemo(); }}><Database className="h-4 w-4" /> بارگذاری و برآورد</button>
            {!STATIC && <a className="btn-ghost no-underline" href="/company/demo/sales_weekly.csv"><Download className="h-4 w-4" /> نمونه CSV</a>}
          </SourceCard>
          {!STATIC && <SourceCard icon={Upload} title="داده‌ی شرکت خودتان" active={mode === "upload"} text="همان جدول‌ها را با همان ستون‌ها بارگذاری کنید؛ مدل بدون تغییر از آن‌ها برآورد می‌کند. داده‌ی ساختگی باید بعداً با داده‌ی واقعی جایگزین شود.">
            <button className="btn-ghost" onClick={() => setMode("upload")}>نمایش فرم بارگذاری</button>
          </SourceCard>}
        </div>
        {mode === "upload" && <Upload_ view={view} company={company} />}
        {company.busy && <Empty>در حال برآورد…</Empty>}
        {company.error && <Empty><span style={{ color: "var(--bad)" }}>خطا: {company.error}</span></Empty>}
        {!view && !company.busy && <Empty>یک منبع داده را انتخاب کنید.</Empty>}

        {view && (<>
          {synth && <div role="alert" className="rounded-xl px-4 py-2 text-sm font-semibold" style={{ background: "color-mix(in srgb, var(--bad) 16%, transparent)", border: "2px solid var(--bad)", color: "var(--bad)" }}>⚠ {view.note}</div>}
          <Panel>
            <Kpi items={[["بازه‌ی داده", `${jdate(view.start)} تا ${jdate(view.end)}`], ["تعداد هفته", fa(view.n_weeks)],
              ["پارامترهای از داده", fa(view.provenance_counts.data)], ["قضاوت (غیرداده)", fa(view.provenance_counts.judgment)], ["نمونه/جایگزین", fa(view.provenance_counts.placeholder)],
              ...(view.recovery ? [["بازیابی پارامترهای معلوم", `${fa(view.recovery_ok)} از ${fa(view.recovery_n)}`]] : [])]} />
            <div className="mt-3 flex flex-wrap gap-2">
              <button className="btn-primary" onClick={() => { company.apply(); go("/expert"); }}><ArrowLeft className="h-4 w-4" /> اعمال برآوردها و رفتن به نسخه‌ی متخصص</button>
              <button className="btn-ghost" onClick={() => { company.apply(); go("/app"); }}>اعمال و رفتن به تحلیل ساده</button>
              {company.applied && <button className="btn-ghost" onClick={company.clear}>لغو اعمال{company.applied ? " (اعمال‌شده ✓)" : ""}</button>}
            </div>
            <p className="muted small mt-2">با اعمال، فیلدهای فرم با برچسب «از داده» پر می‌شوند و خطای معیار برآوردها (×{view.overrides.se_inflation}) بازه‌ی «جهان‌های ممکن» را تعیین می‌کند. هنوز می‌توانید هر فیلد را دستی عوض کنید.</p>
          </Panel>

          <Grid2>
            <Panel title="فروش هفتگی به تفکیک محصول (کیلوگرم)" sub="فصل نوروز و روند رشد؛ افت‌های کوتاه یعنی کمبود موجودی"><Chart option={salesOption(t, view.charts, view.product_fa)} label="فروش" /></Panel>
            <Panel title="فروش، سود ناخالص و سود خالص (میلیارد ریال، مقیاس لگاریتمی)"><Chart option={pnlOption(t, view.charts)} label="سود و زیان" /></Panel>
            <Panel title="موجودی و فروش ازدست‌رفته" sub="ستون‌ها = تقاضایی که به‌علت کمبود موجودی برآورده نشد"><Chart option={stockOption(t, view.charts)} label="موجودی" /></Panel>
            <Panel title="نقد، بدهی و مطالبات (میلیارد ریال)"><Chart option={cashOption(t, view.charts)} label="نقدینگی" /></Panel>
            <Panel title="نرخ دلار: بازار و نرخ مؤثر پرداخت" sub="فاصله‌ی این دو همان ضریب نرخ مؤثر است که مدل از خریدها برآورد می‌کند"><Chart option={fxOption(t, view.charts)} label="دلار" /></Panel>
            <Panel title="قیمت FOB انواع دانه (دلار/کیلو)" sub="فقط آرابیکای شسته بر پایه‌ی داده‌ی واقعی است؛ سه نوع دیگر ساختگی‌اند"><Chart option={priceOption(t, view.charts, view.product_fa)} label="قیمت‌ها" /></Panel>
          </Grid2>

          <Panel title="برآورد پارامترها از داده" sub={view.recovery ? "ستون «حقیقت» فقط برای داده‌ی ساختگی موجود است (پارامتر مولد). ✓ یعنی برآورد در بازه‌ی ۹۵٪ یا ≤ ۱۰٪ خطای نسبی." : "هر عدد از یک رگرسیون یا نسبت صریح روی داده‌ی شرکت می‌آید."}>
            <Table heads={["پارامتر", "برآورد", "خطای معیار", "بازه‌ی ۹۵٪", ...(view.recovery ? ["حقیقت", "✓"] : []), "روش"]}
              rows={Object.entries(view.estimates).filter(([k, e]) => typeof e.value === "number" && !["pipeline", "recent_weekly_purchase_usd", "recent_fob_usd_kg"].includes(k)).map(([k, e]) => {
                const rec = view.recovery?.find((r) => r.key === k);
                return [k, nf(e.value, 3), nf(e.se, 3), e.ci ? `${nf(e.ci[0], 3)} تا ${nf(e.ci[1], 3)}` : "—", ...(view.recovery ? [rec ? nf(rec.truth, 3) : "—", rec ? (rec.ok ? "✓" : "✗") : ""] : []), e.method || ""];
              })}
              cls={["", "num", "num", "num", ...(view.recovery ? ["num", ""] : []), "small"]} />
          </Panel>

          <Panel title="کیفیت داده" sub="مسائل شناسایی‌شده و اقدام انجام‌شده؛ هیچ مقداری بی‌صدا ساخته نمی‌شود">
            <Table heads={["جدول", "نوع", "تعداد/جزئیات", "اقدام"]} rows={view.quality.issues.map((i) => [i.table, ISSUE_FA[i.type] || i.type, i.n ?? `${i.week_end || ""} ${i.product || ""}`, i.action || ""])} />
            {view.quality.annual_reconciliation_max_rel_diff != null && <p className="muted small mt-2">تطبیق سالانه: بیشینه‌ی اختلاف نسبی جمع هفتگی فروش با جدول سالانه = {view.quality.annual_reconciliation_max_rel_diff.toExponential(1)}</p>}
            {view.injected_issues && <p className="muted small">خطاهای عمداً تزریق‌شده در داده‌ی ساختگی: {view.injected_issues.length} مورد (برای آزمون شناسایی).</p>}
          </Panel>

          <Panel title="جدول‌های سالانه (سال مالی ایران از ۱ فروردین)">
            {Object.entries(view.annual).map(([n, rows]) => (
              <div key={n} className="mb-3"><b className="small">{n}</b>
                <Table heads={Object.keys(rows[0])} rows={rows.map((r) => Object.values(r).map((v) => (typeof v === "number" ? nf(v, 0) : v)))} cls={Object.keys(rows[0]).map(() => "num")} /></div>
            ))}
          </Panel>

          <Panel title="پیش‌نمایش جدول‌های خام" sub="۸ ردیف آخر هر جدول">
            <div role="tablist" className="mb-2 flex flex-wrap gap-1">{Object.keys(view.preview).map((k) => <button key={k} className="tab" aria-selected={tbl === k} onClick={() => setTbl(k)}>{k}</button>)}</div>
            {view.preview[tbl] && <><p className="muted small">{view.preview[tbl].description} ({view.preview[tbl].frequency}، {fa(view.preview[tbl].n_rows)} ردیف)</p>
              <Table heads={view.preview[tbl].columns} rows={view.preview[tbl].rows.map((r) => view.preview[tbl].columns.map((c) => (typeof r[c] === "number" ? nf(r[c], 2) : String(r[c] ?? ""))))} cls={view.preview[tbl].columns.map(() => "num")} /></>}
          </Panel>
        </>)}
      </Stack>
    </main>
  );
}
