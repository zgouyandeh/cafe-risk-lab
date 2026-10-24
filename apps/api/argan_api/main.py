"""FastAPI layer: thin. All logic lives in argan_engine; this file only does transport, jobs and static files."""
from __future__ import annotations

import json
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import PlainTextResponse
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ValidationError

from argan_engine.advisor import advise
from argan_engine.analysis import run_analysis
from argan_engine.calibrate import CACHE, get_calibration
from argan_engine.company import TABLES, read_table
from argan_engine.company import service as company
from argan_engine.config import Scenario, scenario_schema
from argan_engine.report import render_report

REPO = Path(__file__).resolve().parents[3]
WEB = REPO / "apps" / "web-react" / "dist"
ART = REPO / "artifacts"

app = FastAPI(title="Argan Risk Lab", version="0.1.0")
_pool = ThreadPoolExecutor(max_workers=2)
_jobs: dict[str, dict] = {}
_lock = threading.Lock()
_cal = None


def cal():
    global _cal
    if _cal is None:
        _cal = get_calibration()
    return _cal


class SimRequest(BaseModel):
    scenario: dict = {}
    mode: str = "expert"          # 'simple' runs a lighter configuration
    data_source: dict | None = None   # {"kind": "demo"|"upload", "synthetic": bool, ...}: echoed into the result and the report


def _simple_overrides(d: dict) -> dict:
    d = dict(d)
    return d


def _job(jid: str, scn: Scenario, mode: str, data_source: dict | None = None) -> None:
    def prog(f: float, msg: str) -> None:
        _jobs[jid].update(progress=round(f, 3), message=msg)
    try:
        res = run_analysis(scn, cal(), prog)
        hist = None
        p = ART / "backtest_replay.json"
        if p.exists():
            hist = json.loads(p.read_text(encoding="utf-8"))["fx_13w_change"]["share_down"]
        res["advice"] = advise(res, scn, hist)
        res["scenario"] = scn.model_dump()
        res["data_source"] = data_source
        _jobs[jid].update(status="done", progress=1.0, result=res)
    except Exception as e:                                   # pragma: no cover
        _jobs[jid].update(status="error", error=f"{type(e).__name__}: {e}")


@app.get("/health")
def health():
    return {"status": "ok", "calibration": CACHE.exists()}


@app.get("/config/defaults")
def defaults():
    return {"scenario": Scenario().model_dump(), "schema": scenario_schema()}


@app.get("/data/summary")
def data_summary():
    c = cal()
    return {"as_of": c.as_of, "coffee_last_date": c.coffee_last_date, "coffee_last_c_lb": c.coffee_last_c_lb,
            "coffee_gap_weeks": c.coffee_gap_weeks, "fx_last": c.fx_last, "fx_selected": c.fx_selected,
            "rho_cf": c.rho_cf, "report": c.report, "series": c.series}


@app.get("/backtests")
def backtests():
    out = {}
    for k in ("coffee", "fx", "replay"):
        p = ART / f"backtest_{k}.json"
        out[k] = json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
    return out


@app.post("/simulations")
def create(req: SimRequest):
    d = _simple_overrides(req.scenario) if req.mode == "simple" else dict(req.scenario)
    d = {k: v for k, v in d.items() if v is not None or k in Scenario.model_fields}
    try:
        scn = Scenario(**d)
    except ValidationError as e:
        raise HTTPException(422, detail=json.loads(e.json()))
    jid = uuid.uuid4().hex[:12]
    with _lock:
        _jobs[jid] = {"id": jid, "status": "running", "progress": 0.0, "message": "در صف", "created": time.time(),
                      "mode": req.mode}
    _pool.submit(_job, jid, scn, req.mode, req.data_source)
    return {"id": jid}


@app.get("/simulations/{jid}")
def get_sim(jid: str):
    j = _jobs.get(jid)
    if not j:
        raise HTTPException(404, "unknown simulation")
    return {k: v for k, v in j.items()}


@app.get("/simulations/{jid}/report", response_class=HTMLResponse)
def report(jid: str):
    j = _jobs.get(jid)
    if not j or j.get("status") != "done":
        raise HTTPException(404, "result not ready")
    bt = backtests()
    return render_report(j["result"], bt)


_uploads: dict[str, object] = {}


@app.get("/company/demo")
def company_demo():
    return company.demo_view()


@app.get("/company/demo/{name}.csv", response_class=PlainTextResponse)
def company_demo_csv(name: str):
    t = company.demo_tables()
    if name not in t:
        raise HTTPException(404, "unknown table")
    return PlainTextResponse(company.table_csv(t[name]), media_type="text/csv; charset=utf-8")


@app.get("/company/template/{name}.csv", response_class=PlainTextResponse)
def company_template(name: str):
    if name not in TABLES:
        raise HTTPException(404, "unknown table")
    return PlainTextResponse(company.template_csv(name), media_type="text/csv; charset=utf-8")


@app.put("/company/upload/{name}")
async def company_upload(name: str, request: Request):
    if name not in TABLES:
        raise HTTPException(404, "unknown table")
    body = (await request.body()).decode("utf-8-sig")
    try:
        df = read_table(name, body if "\n" in body else body + "\n")
    except Exception as e:
        raise HTTPException(422, f"CSV نامعتبر: {e}")
    miss = [c for c in TABLES[name][0] if c not in df.columns]
    if miss:
        raise HTTPException(422, f"ستون‌های لازم نیست: {miss}")
    _uploads[name] = df
    return {"table": name, "rows": int(len(df)), "uploaded": sorted(_uploads)}


@app.post("/company/calibrate")
def company_calibrate():
    need = ["market_weekly", "sales_weekly", "purchases", "inventory_weekly", "collections_weekly", "cash_weekly", "opex_weekly"]
    miss = [n for n in need if n not in _uploads]
    if miss:
        raise HTTPException(422, f"جدول‌های لازم بارگذاری نشده: {miss}")
    try:
        return company.build_view(dict(_uploads), None, False)
    except Exception as e:
        raise HTTPException(422, f"برآورد ناموفق: {type(e).__name__}: {e}")


def _spa():
    idx = WEB / "index.html"
    if not idx.exists():
        raise HTTPException(503, "رابط کاربری ساخته نشده است: در apps/web-react دستور npm install و npm run build را اجرا کنید")
    return FileResponse(idx)


@app.get("/")
@app.get("/app")
@app.get("/expert")
@app.get("/data")
def spa():
    return _spa()


if (WEB / "assets").exists():
    app.mount("/assets", StaticFiles(directory=WEB / "assets"), name="assets")
