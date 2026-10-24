import { motion, useScroll, useTransform, useReducedMotion } from "framer-motion";
import Bean from "./Bean.jsx";

// Deterministic layout -> no hydration/reload jitter.
const BEANS = [
  { x: "6%", y: "14%", s: 54, r: -20, d: 7, depth: 60, tone: "#7a5240" },
  { x: "86%", y: "10%", s: 72, r: 25, d: 9, depth: 120, tone: "#946a54" },
  { x: "14%", y: "70%", s: 86, r: 40, d: 11, depth: 160, tone: "#3b261d" },
  { x: "78%", y: "64%", s: 48, r: -35, d: 8, depth: 50, tone: "#7a5240" },
  { x: "48%", y: "86%", s: 38, r: 10, d: 6, depth: 80, tone: "#946a54" },
  { x: "60%", y: "6%", s: 34, r: -60, d: 10, depth: 40, tone: "#3b261d" },
];

export default function FloatingBeans() {
  const reduce = useReducedMotion();
  const { scrollY } = useScroll();
  const shift = useTransform(scrollY, [0, 700], [0, 1]);

  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden">
      {BEANS.map((b, i) => (
        <ParallaxBean key={i} b={b} i={i} shift={shift} reduce={reduce} />
      ))}
    </div>
  );
}

function ParallaxBean({ b, i, shift, reduce }) {
  const y = useTransform(shift, (v) => v * b.depth);
  return (
    <motion.div style={{ left: b.x, top: b.y, y }} className="absolute">
      <motion.div
        animate={reduce ? undefined : { y: [0, -16, 0], rotate: [b.r, b.r + 8, b.r] }}
        transition={{ duration: b.d, repeat: Infinity, ease: "easeInOut", delay: i * 0.4 }}
        style={{ rotate: b.r, width: b.s, height: b.s }}
        className="opacity-80 drop-shadow-[0_12px_14px_rgba(0,0,0,.30)]"
      >
        <Bean className="h-full w-full" tone={b.tone} />
      </motion.div>
    </motion.div>
  );
}
