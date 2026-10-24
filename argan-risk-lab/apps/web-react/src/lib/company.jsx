import { createContext, useContext, useState } from "react";
import { api } from "./api.js";

const Ctx = createContext(null);
const INTERNAL = ["demand_seasonal_index", "season_start_week", "pipeline_weeks", "pipeline_kg", "initial_receivables_bn_irr"];

/** Holds the loaded company dataset view (demo or uploaded) and whether its estimates were applied to the forms. */
export function CompanyProvider({ children }) {
  const [view, setView] = useState(null);
  const [applied, setApplied] = useState(false);
  const [token, setToken] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const load = async (loader) => {
    setBusy(true); setError(null);
    try { setView(await loader()); setApplied(false); } catch (e) { setError(e.message); } finally { setBusy(false); }
  };
  const loadDemo = () => load(() => api("/company/demo"));
  const calibrateUpload = () => load(() => api("/company/calibrate", { method: "POST" }));
  const apply = () => { setApplied(true); setToken((n) => n + 1); };
  const clear = () => { setApplied(false); setToken((n) => n + 1); };
  const fieldVals = () => {
    if (!applied || !view) return {};
    const o = {};
    for (const [k, v] of Object.entries(view.overrides.fields)) o[k] = Array.isArray(v) ? v.map((x) => Number(Number(x).toPrecision(6))).join(",") : String(Number(Number(v).toPrecision(6)));
    return o;
  };
  const internal = () => {
    if (!applied || !view) return {};
    const o = { param_se: view.overrides.param_se };
    for (const k of INTERNAL) if (k in view.overrides.fields) o[k] = view.overrides.fields[k];
    return o;
  };
  const dataSource = () => (applied && view ? { kind: view.synthetic ? "demo" : "upload", synthetic: view.synthetic, provenance_counts: view.provenance_counts } : null);
  const provOf = (name) => (applied && view && view.overrides.provenance[name] ? view.overrides.provenance[name].source : null);
  return <Ctx.Provider value={{ view, applied, token, busy, error, loadDemo, calibrateUpload, apply, clear, fieldVals, internal, dataSource, provOf, setView }}>{children}</Ctx.Provider>;
}
export const useCompany = () => useContext(Ctx);

export function SyntheticBanner({ className = "" }) {
  const { view, applied } = useCompany();
  if (!view || !view.synthetic || !applied) return null;
  return (
    <div role="alert" className={`mx-auto max-w-[1400px] px-4 ${className}`}>
      <div className="mt-3 rounded-xl px-4 py-2 text-sm font-semibold" style={{ background: "color-mix(in srgb, var(--bad) 16%, transparent)", border: "2px solid var(--bad)", color: "var(--bad)" }}>
        ⚠ داده‌ی ساختگی (Synthetic): پارامترهای این تحلیل از شرکتِ شبیه‌سازی‌شده برآورد شده‌اند. فقط قیمت آرابیکا و نرخ دلار واقعی‌اند؛ نتایج آزمون خط‌لوله‌اند، نه یافته‌ی یک شرکت واقعی.
      </div>
    </div>
  );
}
