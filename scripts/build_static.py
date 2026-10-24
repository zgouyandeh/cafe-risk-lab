"""Pre-compute everything the static (server-less) site needs -> apps/web-react/public/static-data/.
Run:  python scripts/build_static.py     (~2 min). The output is committed so GitHub Pages needs no Python."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "packages" / "argan_engine" / "src"), str(ROOT / "apps" / "api")]
from argan_api import main as api  # noqa: E402
from argan_engine.advisor import advise  # noqa: E402
from argan_engine.analysis import run_analysis  # noqa: E402
from argan_engine.company import service as company  # noqa: E402
from argan_engine.config import Scenario  # noqa: E402
from argan_engine.report import render_report  # noqa: E402

OUT = ROOT / "apps" / "web-react" / "public" / "static-data"
(OUT / "results").mkdir(parents=True, exist_ok=True); (OUT / "reports").mkdir(exist_ok=True)

PRESETS = [
    {"id": "baseline", "label": "ادامه‌ی روند تاریخی", "desc": "پیش‌فرض‌های مدل؛ روند دلار از داده‌ی تاریخی برآورد می‌شود.", "scenario": {}},
    {"id": "stress", "label": "تنش و جهش ارز", "desc": "روند دلار تندتر، نوسان بیشتر، احتمال تشدید تنش ۲۵٪، ۱۵٪ احتمال تأخیر ۶ هفته‌ای محموله و ۳۰٪ از تأخیرها به گم‌شدن محموله می‌انجامد.",
     "scenario": {"fx_drift_annual_pct": 90.0, "fx_vol_mult": 1.3, "event_p_escalation": 25.0, "event_p_deal": 5.0,
                  "import_delay_prob_pct": 15.0, "import_delay_days": 42, "import_loss_prob_pct": 30.0}},
    {"id": "deal", "label": "توافق و کاهش تنش", "desc": "روند دلار ملایم، احتمال توافق ۴۰٪.",
     "scenario": {"fx_drift_annual_pct": 10.0, "event_p_escalation": 3.0, "event_p_deal": 40.0}},
]

view = company.demo_view()
ov = view["overrides"]
PRESETS.append({"id": "company", "label": "شرکت نمونه‌ی ساختگی (پارامترها از داده)", "desc": "پارامترها از ۲۵۵ هفته داده‌ی ساختگی برآورد شده‌اند. ساختگی است.",
                "scenario": {**ov["fields"], "param_se": ov["param_se"]}, "data_source": {"kind": "demo", "synthetic": True, "provenance_counts": view["provenance_counts"]}})

def dump(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, allow_nan=False, default=lambda o: o.item() if hasattr(o, "item") else str(o)), encoding="utf-8")

cal = api.cal()
dump(OUT / "defaults.json", {"scenario": Scenario().model_dump(), "schema": api.scenario_schema()})
dump(OUT / "summary.json", api.data_summary())
bt = api.backtests(); dump(OUT / "backtests.json", bt)
dump(OUT / "company_demo.json", view)
hist = None
p = api.ART / "backtest_replay.json"
if p.exists():
    hist = json.loads(p.read_text(encoding="utf-8"))["fx_13w_change"]["share_down"]
index = []
for pr in PRESETS:
    print("running", pr["id"], flush=True)
    scn = Scenario(**pr["scenario"])
    res = run_analysis(scn, cal)
    res["advice"] = advise(res, scn, hist); res["scenario"] = scn.model_dump(); res["data_source"] = pr.get("data_source")
    dump(OUT / "results" / f"{pr['id']}.json", res)
    (OUT / "reports" / f"{pr['id']}.html").write_text(render_report(res, bt), encoding="utf-8")
    index.append({k: pr[k] for k in ("id", "label", "desc")} | {"synthetic": bool(pr.get("data_source"))})
dump(OUT / "presets.json", index)
print("done", sum(f.stat().st_size for f in OUT.rglob("*") if f.is_file()) // 1024, "KB")
