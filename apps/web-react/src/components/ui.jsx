import { motion } from "framer-motion";

export const Html = ({ html, className = "" }) => <span className={className} dangerouslySetInnerHTML={{ __html: html }} />;

export function Panel({ title, sub, children, className = "", delay = 0 }) {
  return (
    <motion.section initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.45, delay }} className={`panel ${className}`}>
      {title && <h3 className="font-semibold text-ink">{title}</h3>}
      {sub && <div className="muted small">{sub}</div>}
      <div className={title || sub ? "mt-2" : ""}>{children}</div>
    </motion.section>
  );
}
export const Empty = ({ children }) => <div className="panel py-10 text-center muted">{children}</div>;
export const Stack = ({ children, className = "" }) => <div className={`flex flex-col gap-4 ${className}`}>{children}</div>;
export const Grid2 = ({ children }) => <div className="grid gap-4 grid-cols-1 xl:grid-cols-2">{children}</div>;

export function Table({ heads, rows, cls = [] }) {
  return (
    <div className="overflow-x-auto">
      <table className="tbl">
        <thead><tr>{heads.map((h, i) => <th key={i}>{h}</th>)}</tr></thead>
        <tbody>{rows.map((r, i) => <tr key={i}>{r.map((c, j) => <td key={j} className={cls[j] || ""}>{c}</td>)}</tr>)}</tbody>
      </table>
    </div>
  );
}
export const Kpi = ({ items }) => (
  <div className="kpi">{items.map(([l, v]) => <div key={l}><span className="muted small">{l}</span><b>{v}</b></div>)}</div>
);
export const Legend = ({ items }) => (
  <div className="legend">{items.map(([c, l]) => <span key={l}><i style={{ background: c }} />{l}</span>)}</div>
);
const PROV = { data: "از داده", judgment: "قضاوت", placeholder: "نمونه" };
export const Badge = ({ p }) => (p ? <span className={`badge badge-${p}`}>{PROV[p] || p}</span> : null);
export const Progress = ({ value }) => (
  <div className="mt-3 h-1.5 overflow-hidden rounded-full" style={{ background: "var(--line)" }}>
    <div className="h-full rounded-full transition-all duration-300" style={{ width: `${value * 100}%`, background: "linear-gradient(90deg,var(--accent),var(--accent2))" }} />
  </div>
);
