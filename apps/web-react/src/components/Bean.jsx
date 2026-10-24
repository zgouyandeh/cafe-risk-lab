import { useId } from "react";

/** Stylised coffee bean (pure SVG, inherits size from className). */
export default function Bean({ className = "", tone = "#7a5240", crease = "#150d09" }) {
  const id = useId().replace(/:/g, "");
  return (
    <svg viewBox="0 0 64 64" className={className} aria-hidden="true">
      <defs>
        <radialGradient id={id} cx="35%" cy="30%" r="80%">
          <stop offset="0" stopColor="#b08670" />
          <stop offset="0.55" stopColor={tone} />
          <stop offset="1" stopColor="#2b1c16" />
        </radialGradient>
      </defs>
      <ellipse cx="32" cy="32" rx="19" ry="27" fill={`url(#${id})`} transform="rotate(32 32 32)" />
      <path d="M22 12c10 10-8 18 2 28s-2 12 4 14" fill="none" stroke={crease} strokeWidth="2.6" strokeLinecap="round" opacity=".85" transform="rotate(0 32 32)" />
    </svg>
  );
}
