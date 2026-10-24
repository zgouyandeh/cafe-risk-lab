import { Coffee } from "lucide-react";
import { Link, useRoute } from "../lib/router.jsx";
import ThemeSwitcher from "./ThemeSwitcher.jsx";
import { SyntheticBanner } from "../lib/company.jsx";
import { StaticBanner } from "../lib/static.jsx";

const NAV = [["/", "خانه"], ["/data", "داده‌ی شرکت"], ["/app", "تحلیل ساده"], ["/expert", "نسخه‌ی متخصص"]];

export default function Shell({ children, subtitle, extra }) {
  const { path } = useRoute();
  return (
    <>
      <header className="sticky top-0 z-40 border-b" style={{ background: "var(--header)", borderColor: "var(--line)", backdropFilter: "blur(16px)", WebkitBackdropFilter: "blur(16px)" }}>
        <div className="mx-auto flex max-w-[1320px] flex-wrap items-center justify-between gap-3 px-4 py-2.5">
          <Link to="/" className="flex items-center gap-3 no-underline" style={{ color: "var(--ink)" }}>
            <span className="grid h-10 w-10 place-items-center rounded-2xl" style={{ background: "linear-gradient(135deg,var(--accent),var(--accent2))", color: "var(--accent-ink)" }}>
              <Coffee className="h-5 w-5" />
            </span>
            <span className="leading-tight">
              <b className="block text-[1.02rem]">آرگان ریسک‌لب</b>
              <span className="muted text-xs">{subtitle || "تصمیم خرید در شرایط عدم‌قطعیت"}</span>
            </span>
          </Link>
          <nav className="flex items-center gap-1 text-sm">
            {NAV.map(([to, label]) => (
              <Link key={to} to={to} className="rounded-xl px-3 py-1.5 no-underline transition"
                style={path === to ? { background: "color-mix(in srgb,var(--accent) 16%,transparent)", color: "var(--accent)", fontWeight: 600 } : { color: "var(--ink2)" }}>{label}</Link>
            ))}
            {extra}
          </nav>
          <ThemeSwitcher />
        </div>
      </header>
      <StaticBanner />
      <SyntheticBanner />
      {children}
    </>
  );
}
