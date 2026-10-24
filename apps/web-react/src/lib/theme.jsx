import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { TOKENS } from "./chartTheme.js";

export const PALETTES = [
  { id: "mocha", label: "موکا", a: "#e0a15a", b: "#b4682c" },
  { id: "ocean", label: "اقیانوس", a: "#5aa9f0", b: "#6a5bd6" },
  { id: "aurora", label: "شفق", a: "#4fd1a5", b: "#4a7fd6" },
];
const KEY = "argan-theme";
const read = () => { try { return JSON.parse(localStorage.getItem(KEY) || "null"); } catch { return null; } };
const write = (v) => { try { localStorage.setItem(KEY, JSON.stringify(v)); } catch { /* storage may be blocked */ } };

const Ctx = createContext(null);
export function ThemeProvider({ children }) {
  const saved = read();
  const [mode, setMode] = useState(saved?.mode || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"));
  const [palette, setPalette] = useState(saved?.palette || "mocha");
  useEffect(() => {
    document.documentElement.dataset.mode = mode;
    document.documentElement.dataset.palette = palette;
    write({ mode, palette });
  }, [mode, palette]);
  const value = useMemo(() => ({ mode, palette, setMode, setPalette, t: TOKENS[mode] }), [mode, palette]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}
export const useTheme = () => useContext(Ctx);
