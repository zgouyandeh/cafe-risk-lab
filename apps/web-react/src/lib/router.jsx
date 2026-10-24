import { createContext, useContext, useEffect, useState } from "react";
import { STATIC } from "./static.jsx";

const Ctx = createContext(null);
const here = () => (STATIC ? window.location.hash.replace(/^#/, "") || "/" : window.location.pathname);
export function Router({ children }) {
  const [path, setPath] = useState(here());
  useEffect(() => {
    const f = () => setPath(here());
    window.addEventListener(STATIC ? "hashchange" : "popstate", f);
    return () => window.removeEventListener(STATIC ? "hashchange" : "popstate", f);
  }, []);
  const go = (to) => {
    if (to === here()) return;
    if (STATIC) window.location.hash = to; else { window.history.pushState({}, "", to); setPath(to); }
    window.scrollTo(0, 0);
  };
  return <Ctx.Provider value={{ path, go }}>{children}</Ctx.Provider>;
}
export const useRoute = () => useContext(Ctx);
export function Link({ to, className, children, ...rest }) {
  const { go } = useRoute();
  return <a href={STATIC ? "#" + to : to} className={className} onClick={(e) => { if (!e.metaKey && !e.ctrlKey && !e.shiftKey) { e.preventDefault(); go(to); } }} {...rest}>{children}</a>;
}
