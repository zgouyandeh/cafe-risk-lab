import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In dev, forward API + the two existing static UIs to the FastAPI backend (port 8000).
export default defineConfig(({ mode }) => ({
  base: mode === "static" ? "./" : "/",
  plugins: [react()],
  build: { chunkSizeWarningLimit: 1200, outDir: mode === "static" ? "dist-static" : "dist" },
  server: {
    proxy: {
      "/api": { target: "http://127.0.0.1:8000", rewrite: (p) => p.replace(/^\/api/, "") },
    },
  },
}));
