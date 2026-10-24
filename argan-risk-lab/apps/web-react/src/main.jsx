import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";
import "./index.css";

// Charts measure text at creation time, so make sure the Persian font is loaded before the first render.
const fonts = ["400", "600", "700"].map((w) => document.fonts.load(`${w} 14px Vazirmatn`).catch(() => null));
Promise.race([Promise.all(fonts), new Promise((r) => setTimeout(r, 1500))]).finally(() => {
  createRoot(document.getElementById("root")).render(<App />);
});
