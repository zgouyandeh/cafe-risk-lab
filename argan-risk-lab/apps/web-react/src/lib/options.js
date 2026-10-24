/* ECharts option builders. Every builder is a pure function of (theme tokens, data). */
import { fa, jdate, addDays } from "./format.js";

const FONT = "Vazirmatn";
const txt = (c) => ({ color: c, fontFamily: FONT });
/** Vertical (or horizontal) soft gradient from a base colour. */
export const grad = (c, horizontal = false) => ({ type: "linear", x: 0, y: 0, x2: horizontal ? 1 : 0, y2: horizontal ? 0 : 1,
  colorStops: [{ offset: 0, color: c }, { offset: 1, color: c + "99" }] });

export const baseAxis = (t, extra = {}) => ({ axisLine: { lineStyle: { color: t.line } }, axisTick: { show: false },
  axisLabel: { ...txt(t.ink2), formatter: (v) => { const n = Number(v); return Number.isNaN(n) ? v : fa(n); } },
  splitLine: { lineStyle: { color: t.line, opacity: 0.7 } }, ...extra });
export const tip = (t, fmt) => ({ trigger: "axis", backgroundColor: t.surface, borderColor: t.line, textStyle: txt(t.ink), formatter: fmt,
  extraCssText: "direction:rtl;text-align:right;border-radius:10px;box-shadow:0 8px 30px rgba(0,0,0,.25)" });
const legend = (t) => ({ top: 0, icon: "roundRect", itemWidth: 14, itemHeight: 4, itemGap: 22, textStyle: txt(t.ink2) });
const lblAxis = (t, extra = {}) => ({ ...txt(t.ink2), ...extra });

export function fanOption(t, fan, weeks, start, yname, scale = 1, marks = [], dec = 2) {
  const x = weeks.map((w) => jdate(addDays(start, w * 7)).replace(/\s?[۰-۹]{4}$/, ""));
  const q = (k) => fan[k].map((v) => v * scale);
  const p5 = q("p5"), p25 = q("p25"), p50 = q("p50"), p75 = q("p75"), p95 = q("p95");
  const band = (lo, hi, name, op) => [{ name, type: "line", data: lo, stack: name, lineStyle: { opacity: 0 }, symbol: "none", silent: true },
    { name, type: "line", data: hi.map((v, i) => v - lo[i]), stack: name, lineStyle: { opacity: 0 }, symbol: "none", areaStyle: { color: t.s1, opacity: op }, silent: true }];
  return { animation: false, grid: { top: 44, bottom: 36, left: 70, right: 16 },
    tooltip: tip(t, (ps) => ps[0].axisValue + "<br>میانه: " + fa(p50[ps[0].dataIndex], 2) + "<br>۲۵–۷۵٪: " + fa(p25[ps[0].dataIndex], 2) + " تا " + fa(p75[ps[0].dataIndex], 2) + "<br>۵–۹۵٪: " + fa(p5[ps[0].dataIndex], 2) + " تا " + fa(p95[ps[0].dataIndex], 2)),
    xAxis: { type: "category", data: x, boundaryGap: false, ...baseAxis(t), axisLabel: { ...lblAxis(t), interval: 1, hideOverlap: true } },
    yAxis: { type: "value", scale: true, name: yname, nameTextStyle: txt(t.ink2), ...baseAxis(t, { axisLabel: { ...lblAxis(t), formatter: (v) => fa(v, dec) } }) },
    series: [...band(p5, p95, "۵–۹۵٪", 0.14), ...band(p25, p75, "۲۵–۷۵٪", 0.28),
      { name: "میانه", type: "line", data: p50, symbol: "none", lineStyle: { color: t.s1, width: 2.4 },
        markLine: marks.length ? { symbol: "none", silent: true, lineStyle: { color: t.ink3, type: "dashed" }, label: { ...lblAxis(t), position: "insideEndTop", distance: 4, formatter: (p) => p.name },
          data: marks.map(([w, name]) => ({ xAxis: w, name })) } : undefined }] };
}

/* ------------------------------------------------------------------ simple UI */
export function compareOption(t, res) {
  const V = res.meta.purchase_value_bn_irr;
  const rel = (k, m) => ((res.benchmarks[k][m] - res.benchmarks.recommended[m]) / V) * 100;
  const keys = ["equal_split", "all_now"], cats = ["سه قسط مساوی", "همه امروز"];
  const lbl = { show: true, position: "top", ...txt(t.ink), formatter: (p) => fa(p.value, 1) + "٪" };
  return { animation: false, grid: { top: 28, bottom: 30, left: 44, right: 12 },
    tooltip: tip(t, (ps) => ps.map((p) => `${p.seriesName}: ${fa(p.value, 2)}٪`).join("<br>")),
    xAxis: { type: "category", data: cats, ...baseAxis(t, { axisLabel: lblAxis(t, { color: t.ink, fontSize: 13 }) }) },
    yAxis: { type: "value", ...baseAxis(t, { axisLabel: { ...lblAxis(t), formatter: (v) => fa(v) + "٪" } }) },
    series: [{ name: "میانگین", type: "bar", barWidth: 34, itemStyle: { color: grad(t.s1), borderRadius: [6, 6, 0, 0] }, label: lbl, data: keys.map((k) => rel(k, "mean_bn")) },
      { name: "بدترین ۵٪", type: "bar", barWidth: 34, itemStyle: { color: grad(t.s2), borderRadius: [6, 6, 0, 0] }, label: lbl, data: keys.map((k) => rel(k, "cvar_bn")) }] };
}
export function flipOption(t, fl, { simple = false, label = "", xname = "" } = {}) {
  const lines = (name, key, color) => ({ name, type: "line", step: "middle", data: fl.rows.map((r) => r[key] * 100), lineStyle: { color, width: 2.4 }, itemStyle: { color }, symbolSize: simple ? 7 : 5 });
  const a = lines(simple ? "با قید نقدینگی" : "با قید", "w_first", t.s1);
  if (simple) a.markLine = { symbol: "none", silent: true, lineStyle: { color: t.ink3, type: "dashed" }, label: { ...lblAxis(t), formatter: "فرض فعلی" }, data: [{ xAxis: String(Math.round(fl.base)) }] };
  return { animation: false, grid: { top: simple ? 24 : 30, bottom: simple ? 40 : 36, left: simple ? 48 : 44, right: 14 },
    legend: simple ? undefined : legend(t),
    tooltip: tip(t, (ps) => `${simple ? "رشد دلار " : ""}${fa(ps[0].axisValue)}${simple ? "٪" : ""}<br>` + ps.map((p) => `${p.seriesName}: ${fa(p.value, 0)}٪`).join("<br>")),
    xAxis: { type: "category", data: fl.rows.map((r) => Math.round(r.value)), name: xname, nameLocation: "middle", nameGap: 26, nameTextStyle: txt(t.ink2), ...baseAxis(t) },
    yAxis: { type: "value", min: 0, max: 100, ...baseAxis(t, { axisLabel: { ...lblAxis(t), formatter: (v) => fa(v) + "٪" } }) },
    series: [a, lines(simple ? "بدون قید" : "بدون قید", "w_unconstrained_first", t.s3)] };
}
export function stressOption(t, res) {
  const V = res.meta.purchase_value_bn_irr, st = res.stress;
  return { animation: false, grid: { top: 12, bottom: 30, left: 150, right: 56 },
    tooltip: tip(t, (ps) => `${ps[0].name}: ${fa(ps[0].value, 1)}٪`),
    yAxis: { type: "category", data: st.map((s) => s.label_fa), inverse: true, axisLine: { show: false, onZero: false }, position: "left", axisTick: { show: false }, axisLabel: { ...lblAxis(t, { color: t.ink }), width: 140, overflow: "break" } },
    xAxis: { type: "value", ...baseAxis(t, { axisLabel: { ...lblAxis(t), formatter: (v) => fa(v) + "٪" } }) },
    series: [{ type: "bar", barWidth: 16, data: st.map((s) => { const d = s.policies.all_now.mean_bn - s.policies.recommended.mean_bn;
      return { value: (d / V) * 100, itemStyle: { color: grad(d >= 0 ? t.s1 : t.s2, true), borderRadius: 4 } }; }),
      label: { show: true, position: "right", ...txt(t.ink), formatter: (p) => fa(p.value, 1) + "٪" } }] };
}

/* ------------------------------------------------------------------ expert UI */
const yearOf = (v) => jdate(v).split(" ").slice(-1)[0];
export function lineSeries(t, dates, values, color, { log = false, area = 0, tipFmt, yfmt, scale = true, ymin, ymax, left = 48 }) {
  return { animation: false, grid: { top: 16, bottom: 30, left, right: 12 },
    tooltip: tip(t, (ps) => `${jdate(dates[ps[0].dataIndex])}<br>${tipFmt(ps[0].value)}`),
    xAxis: { type: "category", data: dates, ...baseAxis(t, { axisLabel: { ...lblAxis(t), formatter: yearOf, interval: 52 } }) },
    yAxis: { type: log ? "log" : "value", scale, min: ymin, max: ymax, ...baseAxis(t, yfmt ? { axisLabel: { ...lblAxis(t), formatter: yfmt } } : {}) },
    series: [{ type: "line", data: values, symbol: "none", lineStyle: { color, width: 1.8 }, areaStyle: area ? { color, opacity: area } : undefined }] };
}
export function histOption(t, edgesLabels, h, color, { interval = 4, tipFmt, left = 40 }) {
  return { animation: false, grid: { top: 16, bottom: 30, left, right: 12 }, tooltip: tip(t, tipFmt),
    xAxis: { type: "category", data: edgesLabels, ...baseAxis(t, { axisLabel: { ...lblAxis(t), interval } }) },
    yAxis: { type: "value", ...baseAxis(t) },
    series: [{ type: "bar", data: h, itemStyle: { color: grad(color), borderRadius: [4, 4, 0, 0] }, barCategoryGap: "15%" }] };
}
export function distOption(t, r) {
  const names = { recommended: "توصیه‌شده", all_now: "همه امروز", equal_split: "سه‌قسط مساوی" }, cols = { recommended: t.s1, all_now: t.s2, equal_split: t.s3 };
  return { animation: false, grid: { top: 30, bottom: 34, left: 44, right: 12 }, legend: legend(t),
    tooltip: tip(t, (ps) => `${fa(ps[0].axisValue, 0)} م.ر<br>` + ps.map((p) => `${p.seriesName}: ${fa(p.value * 100, 1)}٪`).join("<br>")),
    xAxis: { type: "category", data: r.dist.centers_bn.map((v) => Math.round(v)), ...baseAxis(t, { axisLabel: { ...lblAxis(t), formatter: (v) => fa(v), interval: 4 } }) },
    yAxis: { type: "value", ...baseAxis(t, { axisLabel: { ...lblAxis(t), formatter: (v) => fa(v * 100) + "٪" } }) },
    series: Object.keys(names).map((k) => ({ name: names[k], type: "line", smooth: true, symbol: "none", data: r.dist[k], lineStyle: { color: cols[k], width: 2.2 } })) };
}
export function cashOption(t, r, m) {
  const names = { recommended: "توصیه‌شده", all_now: "همه امروز" }, cols = { recommended: t.s1, all_now: t.s2 };
  const cash = (k) => r.traces[k].cash_bn;
  return { animation: false, grid: { top: 30, bottom: 30, left: 56, right: 12 }, legend: legend(t),
    tooltip: tip(t, (ps) => "هفته " + ps[0].axisValue + "<br>" + ps.map((p) => `${p.seriesName}: ${fa(p.value, 0)}`).join("<br>")),
    xAxis: { type: "category", data: m.weeks.map((w) => fa(w)), ...baseAxis(t) }, yAxis: { type: "value", ...baseAxis(t) },
    series: ["recommended", "all_now"].flatMap((k) => [{ name: names[k], type: "line", data: cash(k).p50, symbol: "none", lineStyle: { color: cols[k], width: 2.2 } },
      { name: names[k] + " ۵٪", type: "line", data: cash(k).p5, symbol: "none", lineStyle: { color: cols[k], width: 1, type: "dashed" } }]) };
}
export function frontierOption(t, r) {
  const pts = (f) => r.policies.filter(f).map((p) => ({ value: [p.cvar_bn, p.mean_bn], w: p.w }));
  const ser = (name, color, data, sz) => ({ name, type: "scatter", symbolSize: sz, itemStyle: { color }, data });
  return { animation: false, grid: { top: 20, bottom: 44, left: 64, right: 16 },
    tooltip: { backgroundColor: t.surface, borderColor: t.line, textStyle: txt(t.ink), extraCssText: "direction:rtl;border-radius:10px",
      formatter: (p) => `وزن‌ها: ${p.data.w.map((x) => fa(x, 1)).join(" / ")}<br>میانگین ${fa(p.value[1], 1)} · CVaR ${fa(p.value[0], 1)}` },
    xAxis: { type: "value", scale: true, name: "CVaR (بدترین ۵٪)", nameLocation: "middle", nameGap: 28, nameTextStyle: txt(t.ink2), ...baseAxis(t) },
    yAxis: { type: "value", scale: true, name: "میانگین", nameTextStyle: txt(t.ink2), ...baseAxis(t) },
    series: [ser("ناشدنی", t.ink3, pts((p) => !p.feasible), 7), ser("شدنی", t.s3, pts((p) => p.feasible && !p.pareto), 8), ser("روی مرز", t.s1, pts((p) => p.pareto), 11)] };
}
export function worldsOption(t, w) {
  const bins = 20, vals = w.diff_vs_now_pct, lo = Math.min(...vals), hi = Math.max(...vals), h = new Array(bins).fill(0);
  vals.forEach((v) => (h[Math.min(bins - 1, Math.floor(((v - lo) / (hi - lo + 1e-9)) * bins))]++));
  return { animation: false, grid: { top: 16, bottom: 30, left: 36, right: 12 }, tooltip: tip(t, (ps) => `${ps[0].name}: ${fa(ps[0].value)} جهان`),
    xAxis: { type: "category", data: h.map((_, i) => fa(lo + ((i + 0.5) * (hi - lo)) / bins, 1)), ...baseAxis(t, { axisLabel: { ...lblAxis(t), interval: 3 } }) }, yAxis: { type: "value", ...baseAxis(t) },
    series: [{ type: "bar", data: h.map((v, i) => ({ value: v, itemStyle: { color: grad(lo + ((i + 0.5) * (hi - lo)) / bins >= 0 ? t.s1 : t.s2), borderRadius: [4, 4, 0, 0] } })) }] };
}
export function sensitivityOption(t, sens) {
  const s = sens.slice(0, 10);
  return { animation: false, grid: { top: 8, bottom: 24, left: 170, right: 24 }, tooltip: tip(t, (ps) => `${ps[0].name}: ${fa(ps[0].value, 2)}`),
    yAxis: { type: "category", data: s.map((x) => x.label_fa), inverse: true, axisLine: { show: false, onZero: false }, axisTick: { show: false }, axisLabel: lblAxis(t, { color: t.ink }) },
    xAxis: { type: "value", min: -1, max: 1, ...baseAxis(t, { axisLabel: { ...lblAxis(t), formatter: (v) => fa(v, 1) } }) },
    series: [{ type: "bar", barWidth: 12, data: s.map((x) => ({ value: x.rho, itemStyle: { color: grad(x.rho >= 0 ? t.s1 : t.s2, true), borderRadius: 4 } })) }] };
}

/* ------------------------------------------------------------------ new in the decision-system version */
const pctLbl = (v) => fa(v * 100) + "٪";
export function heatmapOption(t, rv, coffee, policy = "recommended") {
  const cells = rv.cells.filter((c) => c.coffee === coffee);
  const xs = rv.fx_grid, ys = rv.delay_grid;
  const ratio = (e) => Math.max(e.breach / rv.fail_prob, e.unmet / rv.fail_unmet);
  const data = cells.map((c) => [xs.indexOf(c.fx), ys.indexOf(c.delay_weeks), ratio(c[policy]), c[policy]]);
  return { animation: false, grid: { top: 16, bottom: 56, left: 62, right: 12 },
    tooltip: { backgroundColor: t.surface, borderColor: t.line, textStyle: txt(t.ink), extraCssText: "direction:rtl;text-align:right;border-radius:10px",
      formatter: (p) => { const e = p.data[3]; return `جهش دلار ${pctLbl(xs[p.data[0]])} · تأخیر ${fa(ys[p.data[1]])} هفته<br>احتمال افت نقدینگی: ${fa(e.breach * 100)}٪<br>کمبود تقاضا: ${fa(e.unmet * 100, 1)}٪<br>${e.fail ? "شکست" : "تاب می‌آورد"}`; } },
    xAxis: { type: "category", data: xs.map(pctLbl), name: "جهش دلار", nameLocation: "middle", nameGap: 32, nameTextStyle: txt(t.ink2), axisLabel: lblAxis(t), axisLine: { lineStyle: { color: t.line } }, axisTick: { show: false }, splitArea: { show: false } },
    yAxis: { type: "category", data: ys.map((y) => fa(y)), name: "تأخیر (هفته)", nameTextStyle: txt(t.ink2), axisLabel: lblAxis(t), axisLine: { lineStyle: { color: t.line } }, axisTick: { show: false } },
    visualMap: { show: false, type: "piecewise", dimension: 2, pieces: [{ lt: 0.5, color: t.s3 + "cc" }, { gte: 0.5, lt: 1, color: "#e0a526cc" }, { gte: 1, color: t.s2 }] },
    series: [{ type: "heatmap", data, itemStyle: { borderColor: t.surface, borderWidth: 2, borderRadius: 6 },
      label: { show: true, formatter: (p) => (p.data[3].fail ? "✗" : "✓"), color: "#fff", fontSize: 14, fontWeight: 700 } }] };
}
/** Decision map: colour = value(buy-all-now) - value(recommended) in % of purchase value; ✗ = buy-all-now breaks a limit there. */
export function decisionMapOption(t, mp, base) {
  const xs = mp.x_values, ys = mp.y_values;
  const data = [];
  ys.forEach((_, a) => xs.forEach((_, b) => data.push([b, a, mp.now_minus_rec_pct[a][b], mp.now_feasible[a][b], mp.winner[a][b]])));
  const nm = { recommended: "برنامه‌ی پیشنهادی", all_now: "خرید یک‌جا", equal_split: "سه قسط مساوی", all_late: "همه دیرتر" };
  const win = (w) => (w.startsWith("none:") ? "هیچ‌کدام شدنی نیست؛ کم‌زیان‌ترین: " + nm[w.slice(5)] : nm[w]);
  return { animation: false, grid: { top: 14, bottom: 58, left: 70, right: 12 },
    tooltip: { backgroundColor: t.surface, borderColor: t.line, textStyle: txt(t.ink), extraCssText: "direction:rtl;text-align:right;border-radius:10px",
      formatter: (p) => `روند دلار ${fa(xs[p.data[0]])}٪ · احتمال تشدید ${fa(ys[p.data[1]])}٪<br>ارزش خرید یک‌جا منهای پیشنهادی: ${fa(p.data[2], 2)}٪ از ارزش محموله<br>${p.data[3] ? "خرید یک‌جا حدود را رعایت می‌کند" : "خرید یک‌جا حدود نقدینگی/کمبود را نقض می‌کند"}<br>برنده با رعایت حدود: ${win(p.data[4])}` },
    xAxis: { type: "category", data: xs.map((v) => fa(v)), name: "روند سالانه‌ی دلار (٪)", nameLocation: "middle", nameGap: 34, nameTextStyle: txt(t.ink2), axisLabel: lblAxis(t), axisLine: { lineStyle: { color: t.line } }, axisTick: { show: false } },
    yAxis: { type: "category", data: ys.map((v) => fa(v)), name: "احتمال تشدید تنش (٪)", nameTextStyle: txt(t.ink2), axisLabel: lblAxis(t), axisLine: { lineStyle: { color: t.line } }, axisTick: { show: false } },
    visualMap: { show: false, type: "piecewise", dimension: 2, pieces: [{ lt: -1.5, color: t.s1 }, { gte: -1.5, lt: 0, color: t.s1 + "88" }, { gte: 0, lt: 1.5, color: t.s2 + "99" }, { gte: 1.5, color: t.s2 }] },
    series: [{ type: "heatmap", data, itemStyle: { borderColor: t.surface, borderWidth: 2, borderRadius: 6 },
      label: { show: true, formatter: (p) => fa(p.data[2], 1) + (p.data[3] ? "" : " ✗"), color: "#fff", fontSize: 12, fontWeight: 700 } }] };
}
export function attributionOption(t, attr) {
  const rows = attr.rows;
  return { animation: false, grid: { top: 10, bottom: 28, left: 160, right: 56 }, tooltip: tip(t, (ps) => `${ps[0].name}: ${fa(ps[0].value, 1)}٪ از ارزش محموله`),
    yAxis: { type: "category", data: rows.map((r) => r.label_fa), inverse: true, axisLine: { show: false, onZero: false }, axisTick: { show: false }, axisLabel: lblAxis(t, { color: t.ink }) },
    xAxis: { type: "value", ...baseAxis(t, { axisLabel: { ...lblAxis(t), formatter: (v) => fa(v) + "٪" } }) },
    series: [{ type: "bar", barWidth: 16, data: rows.map((r) => ({ value: r.delta_pct, itemStyle: { color: grad(r.delta_pct >= 0 ? t.s1 : t.s2, true), borderRadius: 4 } })),
      label: { show: true, position: "right", ...txt(t.ink), formatter: (p) => fa(p.value, 1) + "٪" } }] };
}
/** Simple UI: P(cash below the safe minimum) per scenario, recommended vs buy-everything-now. */
export function stressBreachOption(t, res) {
  const rows = res.stress.filter((s) => s.group === "core");
  const lbl = { show: true, position: "right", ...txt(t.ink), formatter: (p) => fa(p.value) + "٪" };
  return { animation: false, grid: { top: 30, bottom: 24, left: 140, right: 50 }, legend: { ...legend(t), top: 0 },
    tooltip: tip(t, (ps) => ps[0].name + "<br>" + ps.map((p) => `${p.seriesName}: ${fa(p.value)}٪`).join("<br>")),
    yAxis: { type: "category", data: rows.map((s) => s.label_fa), inverse: true, axisLine: { show: false, onZero: false }, axisTick: { show: false }, axisLabel: lblAxis(t, { color: t.ink }) },
    xAxis: { type: "value", min: 0, max: 100, ...baseAxis(t, { axisLabel: { ...lblAxis(t), formatter: (v) => fa(v) + "٪" } }) },
    series: [{ name: "برنامه‌ی پیشنهادی", type: "bar", barWidth: 12, itemStyle: { color: grad(t.s1, true), borderRadius: 4 }, label: lbl, data: rows.map((s) => s.policies.recommended.breach * 100) },
      { name: "خرید یک‌جا امروز", type: "bar", barWidth: 12, itemStyle: { color: grad(t.s2, true), borderRadius: 4 }, label: lbl, data: rows.map((s) => s.policies.all_now.breach * 100) }] };
}
