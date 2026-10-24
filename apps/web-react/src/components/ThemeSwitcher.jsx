import { useState } from "react";
import { Moon, Sun, Palette } from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";
import { PALETTES, useTheme } from "../lib/theme.jsx";

export default function ThemeSwitcher() {
  const { mode, setMode, palette, setPalette } = useTheme();
  const [open, setOpen] = useState(false);
  return (
    <div className="relative flex items-center gap-2">
      <button type="button" onClick={() => setMode(mode === "dark" ? "light" : "dark")} className="btn-ghost !px-2.5" aria-label={mode === "dark" ? "تم روشن" : "تم تیره"} title={mode === "dark" ? "تم روشن" : "تم تیره"}>
        <AnimatePresence mode="wait" initial={false}>
          <motion.span key={mode} initial={{ rotate: -60, opacity: 0 }} animate={{ rotate: 0, opacity: 1 }} exit={{ rotate: 60, opacity: 0 }} transition={{ duration: 0.18 }}>
            {mode === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </motion.span>
        </AnimatePresence>
      </button>
      <button type="button" onClick={() => setOpen((o) => !o)} className="btn-ghost !px-2.5" aria-expanded={open} aria-label="انتخاب رنگ‌بندی" title="رنگ‌بندی">
        <Palette className="h-4 w-4" />
      </button>
      <AnimatePresence>
        {open && (
          <motion.div initial={{ opacity: 0, y: -6, scale: 0.97 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: -6 }}
            className="glass absolute left-0 top-full z-50 mt-2 w-48 p-2" style={{ background: "var(--surface-solid)" }} role="menu">
            {PALETTES.map((p) => (
              <button key={p.id} type="button" role="menuitemradio" aria-checked={palette === p.id} onClick={() => { setPalette(p.id); setOpen(false); }}
                className="flex w-full items-center gap-3 rounded-xl px-2.5 py-2 text-sm transition hover:bg-black/5 dark:hover:bg-white/10"
                style={palette === p.id ? { outline: "2px solid var(--accent)" } : undefined}>
                <span className="h-6 w-6 rounded-full" style={{ background: `linear-gradient(135deg, ${p.a}, ${p.b})` }} />
                {p.label}
              </button>
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
