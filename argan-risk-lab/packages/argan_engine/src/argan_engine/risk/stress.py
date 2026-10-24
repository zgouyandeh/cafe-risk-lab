"""Named stress scenarios, applied as deterministic overlays on the SAME simulated paths as the base run
(common random numbers), so a scenario's effect is a clean difference, not noise.

Sizes are tests of resilience, NOT forecasts and NOT probabilities: no probability is claimed for war,
sanctions or supply stops. `delay_days=None` means "use the user's crisis-delay input"."""
from __future__ import annotations

from ..config import Scenario

STRESSES = [
    {"id": "normal", "group": "core", "label_fa": "عادی", "desc_fa": "ادامه‌ی روند با نوسان‌های معمول (بدون شوک اضافه)",
     "question_fa": "خرید مرحله‌ای بهتر است یا یک‌جا؟"},
    {"id": "fx_jump", "group": "core", "label_fa": "جهش ارزی", "desc_fa": "دلار ⁦+۵۰٪⁩ در هفته اول",
     "question_fa": "خرید زودتر چه میزان هزینه‌ی احتمالی را کاهش می‌دهد؟", "fx": 0.50},
    {"id": "dual", "group": "core", "label_fa": "شوک دوگانه", "desc_fa": "دلار ⁦+۳۰٪⁩ و قهوه ⁦+۲۵٪⁩ هم‌زمان",
     "question_fa": "شرکت تا چه حد در معرض افزایش هزینه است؟", "fx": 0.30, "coffee": 0.25},
    {"id": "import_disruption", "group": "core", "label_fa": "اختلال واردات",
     "desc_fa": "تأخیر طولانی در تحویل و حمل/بیمه ۴۰٪ گران‌تر", "question_fa": "چند روز موجودی لازم است؟",
     "delay_days": None, "landing_mult": 1.4},
    {"id": "severe_crisis", "group": "core", "label_fa": "بحران شدید",
     "desc_fa": "دلار ⁦+۵۰٪⁩، قهوه ⁦+۳۰٪⁩، تأخیر تحویل، حمل ۴۰٪ گران‌تر، افت ۲۵٪ تقاضا، دو هفته تأخیر بیشتر در وصول و گم‌شدن محموله‌ی دیررسیده در ۲۵٪ مسیرها (پیش‌پرداخت از دست می‌رود)",
     "question_fa": "آیا شرکت می‌تواند فعالیتش را ادامه دهد؟", "fx": 0.50, "coffee": 0.30, "delay_days": None,
     "landing_mult": 1.4, "demand_shift_pct": -25.0, "receivable_extra_weeks": 2, "loss_share": 0.25},
    {"id": "deal_down", "group": "opposite", "label_fa": "کاهش ناگهانی تنش", "desc_fa": "دلار ⁦−۲۵٪⁩ (قهوه بدون تغییر)",
     "question_fa": "اگر زود خریده باشیم چقدر از دست می‌دهیم؟", "fx": -0.25},
    {"id": "frost", "group": "opposite", "label_fa": "یخ‌زدگی/خشکسالی قهوه", "desc_fa": "قهوه ⁦+۴۰٪⁩ (دلار بدون تغییر)",
     "question_fa": "ریسک قیمت جهانی قهوه به‌تنهایی چقدر است؟", "coffee": 0.40},
    {"id": "deal_coffee_down", "group": "opposite", "label_fa": "توافق و ارزانی هم‌زمان", "desc_fa": "دلار ⁦−۲۵٪⁩ و قهوه ⁦−۱۵٪⁩",
     "question_fa": "بدترین حالت برای خریدار زودهنگام چیست؟", "fx": -0.25, "coffee": -0.15},
]


def stress_params(s: dict, scn: Scenario) -> dict:
    """Resolve a stress definition into apply_shock kwargs and a Scenario copy for engine-level changes."""
    dw = scn.delay_weeks if s.get("delay_days", 0) is None else int(round(s.get("delay_days", 0) / 7))
    kw = dict(fx=s.get("fx", 0.0), coffee=s.get("coffee", 0.0), delay_weeks=dw if "delay_days" in s else None,
              landing_pct=scn.landing_cost_pct * s["landing_mult"] if "landing_mult" in s else None,
              demand_shift_pct=s.get("demand_shift_pct", 0.0), loss_share=s.get("loss_share", 0.0))
    upd = {}
    if s.get("receivable_extra_weeks"):
        upd["receivable_lag_weeks"] = scn.receivable_lag_weeks + int(s["receivable_extra_weeks"])
    return {"shock": kw, "scn": scn.model_copy(update=upd) if upd else scn}
