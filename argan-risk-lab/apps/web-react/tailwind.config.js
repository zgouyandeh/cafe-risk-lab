/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        ink: "var(--ink)", ink2: "var(--ink2)", ink3: "var(--ink3)", line: "var(--line)",
        surface: "var(--surface)", accent: "var(--accent)", accent2: "var(--accent2)", "accent-ink": "var(--accent-ink)",
      },
      fontFamily: { sans: ["Vazirmatn", "Tahoma", "sans-serif"] },
      boxShadow: { soft: "var(--shadow)", glow: "0 0 0 1px var(--accent-ring), 0 14px 50px -12px var(--accent-glow)" },
    },
  },
  plugins: [],
};
