"""Manager-facing wording: limit violations are never hidden, 'zero tolerance' is worded honestly, negative numbers are isolated."""
import pytest

from argan_engine.advisor import advise
from argan_engine.advisor.explain import better_worse, fa, pct, tolerance_text
from argan_engine.analysis import run_analysis
from argan_engine.config import Scenario


def test_tolerance_zero_means_fails_without_shock():
    t = tolerance_text({"survives_up_to": 0.0, "fails_at": 0.1}, "fx")
    assert "حتی بدون" in t and "تا ۰" not in t
    assert "حتی بدون" in tolerance_text({"survives_up_to": None, "fails_at": 1}, "delay")
    ok = tolerance_text({"survives_up_to": 0.25, "fails_at": 0.5}, "fx")
    assert "۲۵٪" in ok and "۵۰٪" in ok
    assert "نینداخت" in tolerance_text({"survives_up_to": 1.0, "fails_at": None}, "fx")


def test_negative_numbers_are_isolated_and_no_negative_zero():
    assert fa(-3.2, 1).startswith("⁦") and fa(-3.2, 1).endswith("⁩") and "−" in fa(-3.2, 1)
    assert pct(-0.032, 1).count("٪") == 1 and pct(-0.032, 1).endswith("⁩")
    assert "−" not in fa(-0.01, 1) and "+" not in fa(0.0, 1, True)
    assert better_worse(-0.03) == "۳٫۰٪ بدتر" and better_worse(0.03) == "۳٫۰٪ بهتر" and better_worse(0.0) == "تقریباً برابر"


@pytest.fixture(scope="module")
def tight(cal):
    s = Scenario(n_paths=1500, n_worlds=8, worlds_auto=False, max_unmet_demand_pct=0.01, max_liquidity_breach_prob_pct=0.5,
                 initial_inventory_kg=0.0, import_delay_prob_pct=60, import_delay_days=42)
    res = run_analysis(s, cal)
    res["scenario"] = s.model_dump()
    return s, res, advise(res, s, None)


def test_violated_limits_are_flagged_and_confidence_capped(tight):
    s, res, a = tight
    rec = res["benchmarks"]["recommended"]
    if rec["unmet"] > s.max_unmet_demand_pct / 100 or rec["breach"] > s.max_liquidity_breach_prob_pct / 100:
        assert not a["status"]["respects_limits"] and a["status"]["violations"]
        assert a["headline"].startswith("هشدار")
        assert a["confidence"]["level"] == "پایین"
    else:
        pytest.skip("limits happened to hold")


def test_worst_case_states_the_limit(tight):
    s, res, a = tight
    wc = a["worst_case"]
    assert "exceeds_limits" in wc
    if wc["exceeds_limits"]:
        assert "حد مجاز" in wc["text"]


def test_jalali_dates_and_natural_frequency():
    from argan_engine.advisor.explain import jalali_text, of100
    assert jalali_text("2026-03-21") == "۱ فروردین ۱۴۰۵" and jalali_text("2026-10-18") == "۲۶ مهر ۱۴۰۵"
    assert of100(0.72) == "حدود ۷۲ حالت از هر ۱۰۰ حالت" and of100(0.0) == "تقریباً در هیچ حالتی"


def test_manager_summary_is_actionable(tight):
    s, res, a = tight
    mg = a["manager"]
    assert mg["steps"] and mg["why"] and mg["caveats"] and mg["action"]
    assert all(k in mg["steps"][0] for k in ("when", "date", "share", "kg", "usd"))
    if not a["status"]["respects_limits"]:
        assert mg["warning"] and mg["sure"]["level"] == "پایین"
    from argan_engine.report.render import render_report
    res["advice"] = a
    html = render_report(res, {})
    assert "چه کار کنیم" in html and html.index("چه کار کنیم") < html.index("ضمیمه‌ی فنی")
    assert "CVaR" not in html.split("ضمیمه‌ی فنی")[0]


def test_forecast_wrong_table(tight):
    s, res, a = tight
    w = a["manager"]["wrong"]
    assert len(w) == 5 and all(r["verdict"] in ("ادامه می‌یابد", "در خطر", "شکست می‌خورد") for r in w)
    st = {x["id"]: x["policies"]["recommended"] for x in res["stress"]}
    ids = [x["id"] for x in res["stress"] if x["group"] == "core"]
    for r, i in zip(w, ids):                      # sign of the printed number equals the sign of the computed one
        assert (st[i]["mean_bn"] < -0.5) == ("−" in r["mean"])
