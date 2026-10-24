import { Badge } from "./ui.jsx";

/** One schema-driven input. `value` is always a string/boolean in form state (converted on submit). */
export default function Field({ f, value, onChange, enumLabels = {}, placeholder = "", showProv = true, key_ = false }) {
  const id = "f_" + f.name;
  const head = (
    <span className="field-head">
      <span>{f.label_fa}{showProv && <Badge p={f.provenance} />}</span>
      <span className="field-unit">{f.unit || ""}</span>
    </span>
  );
  const hint = f.hint_fa ? <span className="field-hint">{f.hint_fa}</span> : null;
  if (f.type === "enum") {
    const opts = f.options.filter((o) => o !== "custom");
    if (Object.keys(enumLabels).length)
      return (
        <fieldset className="field-label">
          <span className="text-sm">{f.label_fa}</span>
          <div className="seg" role="radiogroup">
            {opts.map((o) => (
              <label key={o}><input type="radio" name={f.name} value={o} checked={value === o} onChange={() => onChange(o)} />{enumLabels[o] || o}</label>
            ))}
          </div>
        </fieldset>
      );
    return (
      <label className="field-label" htmlFor={id}>{head}
        <select id={id} className="input" value={value} onChange={(e) => onChange(e.target.value)}>{f.options.map((o) => <option key={o}>{o}</option>)}</select>{hint}
      </label>
    );
  }
  if (f.type === "bool")
    return (
      <label className="field-label flex items-center justify-between gap-3">{head}
        <input id={id} type="checkbox" checked={!!value} onChange={(e) => onChange(e.target.checked)} className="h-4 w-4" style={{ accentColor: "var(--accent)" }} />
      </label>
    );
  return (
    <label className="field-label" htmlFor={id}>{head}
      <input id={id} className="input" type={f.type === "number" ? "number" : "text"} step="any" min={f.min} max={f.max} value={value ?? ""} placeholder={placeholder}
        inputMode={f.type === "number" ? "decimal" : undefined} onChange={(e) => onChange(e.target.value)} />
      {hint}
    </label>
  );
}

export const initialValues = (schema) =>
  Object.fromEntries(schema.map((f) => [f.name, f.type === "list" ? (f.default || []).join(",") : f.type === "bool" ? !!f.default : f.default ?? ""]));

export function toScenario(schema, v, defaults) {
  const o = {};
  for (const f of schema) {
    if (f.level === "internal") continue;   // set only from company data (see lib/company.jsx)
    const x = v[f.name];
    if (f.type === "bool") o[f.name] = !!x;
    else if (f.type === "list") o[f.name] = String(x).split(",").map((s) => Number(s.trim())).filter((n) => !Number.isNaN(n));
    else if (f.type === "number") o[f.name] = String(x).trim() === "" ? null : Number(x);
    else o[f.name] = x;
  }
  for (const k of ["purchase_budget_usd", "horizon_days", "lead_time_days"]) if (o[k] == null) o[k] = defaults[k];
  return o;
}
