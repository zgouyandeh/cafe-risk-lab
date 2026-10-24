import { createContext, useContext, useEffect, useState } from "react";

/** Static (server-less) build: results are pre-computed JSON files. Enabled with VITE_STATIC=1 at build time. */
export const STATIC = import.meta.env.VITE_STATIC === "1";
export const BASE = import.meta.env.BASE_URL || "/";
export const staticUrl = (p) => `${BASE}static-data/${p}`;
export const reportUrl = (id) => (STATIC ? staticUrl(`reports/${id}.html`) : `/simulations/${id}/report`);

let current = "baseline";
export const currentPreset = () => current;

const Ctx = createContext({ preset: "baseline", presets: [], setPreset: () => {} });
export function StaticProvider({ children }) {
  const [presets, setPresets] = useState([]);
  const [preset, setP] = useState("baseline");
  useEffect(() => { if (STATIC) fetch(staticUrl("presets.json")).then((r) => r.json()).then(setPresets).catch(() => {}); }, []);
  const setPreset = (id) => { current = id; setP(id); };
  return <Ctx.Provider value={{ preset, presets, setPreset }}>{children}</Ctx.Provider>;
}
export const useStatic = () => useContext(Ctx);

export function StaticBanner() {
  const { preset, presets, setPreset } = useStatic();
  if (!STATIC) return null;
  const cur = presets.find((p) => p.id === preset);
  return (
    <div className="mx-auto max-w-[1400px] px-4">
      <div className="mt-3 rounded-xl px-4 py-2 text-sm" style={{ background: "color-mix(in srgb, var(--accent) 12%, transparent)", border: "1px solid var(--accent)" }}>
        <b>نسخه‌ی ایستا (نمایشی):</b> نتایج از پیش محاسبه‌شده‌اند و تغییر فیلدها محاسبه‌ی تازه نمی‌کند؛ دکمه‌ی «اجرا» نتیجه‌ی حالت انتخاب‌شده را نشان می‌دهد. برای اجرای زنده، پروژه را با Docker اجرا کنید (راهنما در README).
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <span className="muted">حالت بازار:</span>
          {presets.filter((p) => !p.synthetic).map((p) => (
            <button key={p.id} type="button" className="tab" aria-selected={preset === p.id} title={p.desc} onClick={() => setPreset(p.id)}>{p.label}</button>
          ))}
          {cur && <span className="muted small">{cur.desc}</span>}
        </div>
      </div>
    </div>
  );
}
