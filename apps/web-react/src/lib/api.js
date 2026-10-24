import { STATIC, currentPreset, staticUrl } from "./static.jsx";

const MAP = { "/config/defaults": "defaults.json", "/data/summary": "summary.json", "/backtests": "backtests.json", "/company/demo": "company_demo.json" };

export async function api(path, opts) {
  if (STATIC) {
    const f = MAP[path];
    if (!f) throw new Error("در نسخه‌ی ایستا در دسترس نیست (برای بارگذاری داده‌ی خودتان نسخه‌ی زنده را اجرا کنید).");
    const r = await fetch(staticUrl(f));
    if (!r.ok) throw new Error("فایل ایستا پیدا نشد: " + f);
    return r.json();
  }
  const r = await fetch(path, opts);
  if (!r.ok) throw new Error((await r.text()).slice(0, 400));
  return r.json();
}
export async function runSimulation(scenario, mode, onProgress, dataSource = null) {
  if (STATIC) {
    const id = dataSource && dataSource.synthetic ? "company" : currentPreset();
    if (onProgress) onProgress(0.5, "بارگذاری نتیجه‌ی از پیش محاسبه‌شده");
    const r = await fetch(staticUrl(`results/${id}.json`));
    if (!r.ok) throw new Error("نتیجه‌ی ایستا پیدا نشد: " + id);
    return { id, result: await r.json() };
  }
  const { id } = await api("/simulations", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ scenario, mode, data_source: dataSource }) });
  for (;;) {
    await new Promise((r) => setTimeout(r, 700));
    const j = await api("/simulations/" + id);
    if (onProgress) onProgress(j.progress || 0, j.message || "");
    if (j.status === "done") return { id, result: j.result };
    if (j.status === "error") throw new Error(j.error);
  }
}
