/* ECharts options for the company-data page. Pure functions of (theme tokens, view.charts). */
import { fa, jdate } from "./format.js";
import { baseAxis, tip } from "./options.js";

const FONT = "Vazirmatn";
const txt = (c) => ({ color: c, fontFamily: FONT });
const xs = (c) => c.weeks.map((w) => jdate(w).replace(/^[۰-۹]{1,2}\s/, ""));
const base = (t, c, extra = {}) => ({
  animation: false, grid: { top: 40, bottom: 34, left: 74, right: 18 },
  legend: { top: 0, icon: "roundRect", itemWidth: 14, itemHeight: 4, itemGap: 20, textStyle: txt(t.ink2) },
  tooltip: tip(t, (ps) => ps[0].axisValue + "<br>" + ps.map((p) => `${p.seriesName}: ${fa(p.value, 1)}`).join("<br>")),
  xAxis: { type: "category", data: xs(c), boundaryGap: false, ...baseAxis(t), axisLabel: { ...txt(t.ink2), hideOverlap: true, interval: 25 } },
  ...extra,
});
const line = (name, data, color, extra = {}) => ({ name, type: "line", data, symbol: "none", lineStyle: { color, width: 2 }, itemStyle: { color }, ...extra });
const yAx = (t, extra = {}) => ({ type: "value", ...baseAxis(t), ...extra });

export const salesOption = (t, c, P) => {
  const cols = [t.s1, t.s2, t.s3, t.ink3];
  return base(t, c, { yAxis: yAx(t, { name: "کیلوگرم/هفته", nameTextStyle: txt(t.ink2) }),
    series: Object.keys(c.kg).map((p, i) => line(P[p], c.kg[p], cols[i], { stack: "kg", areaStyle: { color: cols[i], opacity: 0.55 }, lineStyle: { width: 1, color: cols[i] } })) });
};
export const pnlOption = (t, c) => base(t, c, { yAxis: yAx(t, { name: "میلیارد ریال", nameTextStyle: txt(t.ink2), type: "log" }),
  series: [line("فروش", c.revenue_bn, t.s1), line("سود ناخالص", c.gross_bn, t.s2), line("سود خالص", c.net_bn, t.s3)] });
export const stockOption = (t, c) => base(t, c, { yAxis: [yAx(t, { name: "موجودی (کیلوگرم)", nameTextStyle: txt(t.ink2) }), yAx(t, { name: "کمبود", nameTextStyle: txt(t.ink2), splitLine: { show: false } })],
  series: [line("موجودی پایان هفته", c.inventory_kg, t.s1, { areaStyle: { color: t.s1, opacity: 0.18 } }), { name: "فروش ازدست‌رفته (کمبود)", type: "bar", yAxisIndex: 1, data: c.unmet_kg, itemStyle: { color: t.s2 } }] });
export const cashOption = (t, c) => base(t, c, { yAxis: yAx(t, { name: "میلیارد ریال", nameTextStyle: txt(t.ink2) }),
  series: [line("نقد", c.cash_bn, t.s1), line("بدهی کوتاه‌مدت", c.debt_bn, t.s2), line("مطالبات", c.receivables_bn, t.s3)] });
export const fxOption = (t, c) => base(t, c, { yAxis: yAx(t, { name: "ریال/دلار", nameTextStyle: txt(t.ink2), type: "log" }),
  series: [line("نرخ بازار (واقعی)", c.fx_market, t.s1), line("نرخ مؤثر پرداخت شرکت (ساختگی)", c.fx_effective, t.s2)] });
export const priceOption = (t, c, P) => {
  const cols = [t.s1, t.s2, t.s3, t.ink3];
  return base(t, c, { yAxis: yAx(t, { name: "دلار/کیلو (FOB)", nameTextStyle: txt(t.ink2), scale: true }),
    series: Object.keys(c.price_usd_kg).map((p, i) => line((p === "washed" ? "آرابیکا شسته (واقعی)" : P[p] + " (ساختگی)"), c.price_usd_kg[p], cols[i], p === "washed" ? { lineStyle: { color: cols[i], width: 2.6 } } : {})) });
};
