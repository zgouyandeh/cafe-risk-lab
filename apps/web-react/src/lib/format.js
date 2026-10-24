/* Persian digits, Jalali dates, shared labels. */
const nf = (d = 0) => new Intl.NumberFormat("fa-IR", { minimumFractionDigits: d, maximumFractionDigits: d });
export const fa = (x, d = 0) => (x == null || Number.isNaN(x) ? "—" : nf(d).format(x));
// A signed number is wrapped in a left-to-right isolate so the minus/plus stays on the left of the digits inside RTL text.
const iso = (s) => "\u2066" + s + "\u2069";
const signed = (x, d, sign, suffix) => {
  if (x == null || Number.isNaN(x)) return "—";
  const r = Number(x.toFixed(d)); const txt = fa(Math.abs(r), d) + suffix;
  if (r < 0) return iso("\u2212" + txt);
  return sign && r > 0 ? iso("+" + txt) : txt;
};
export const pct = (x, d = 0, sign = false) => signed(x == null ? null : x * 100, d, sign, "٪");
export const pp = (x, d = 1, sign = true) => signed(x, d, sign, "٪");
export const sfa = (x, d = 0) => signed(x, d, false, "");
/* reverse-stress tolerance: "survives up to 0" really means "fails even without an extra shock" */
export const tolCell = (t, fmt, none = "در محدوده‌ی بررسی‌شده شکست دیده نشد") =>
  t.fails_at == null ? none : (t.survives_up_to == null || t.survives_up_to <= 0) ? "حتی بدون شوک اضافه از معیار شکست عبور می‌کند" : "تا " + fmt(t.survives_up_to);
const jf = new Intl.DateTimeFormat("fa-IR-u-ca-persian", { year: "numeric", month: "long", day: "numeric" });
export const jdate = (iso) => jf.format(new Date(iso + "T12:00:00"));
export const addDays = (iso, n) => { const d = new Date(iso + "T12:00:00"); d.setDate(d.getDate() + n); return d.toISOString().slice(0, 10); };
export const weightsText = (w, days) => w.map((x, i) => [x, days[i]]).filter(([x]) => x > 1e-9)
  .map(([x, d]) => `${pct(x)} ${d === 0 ? "امروز" : fa(d) + " روز دیگر"}`).join("، ");
export const NAMES = { recommended: "توصیه‌شده", all_now: "همه امروز", equal_split: "سه قسط مساوی", all_late: "همه دیرتر",
  unconstrained_best: "بهینه بدون قید", nominal_best: "بهینه‌ی اسمی" };
