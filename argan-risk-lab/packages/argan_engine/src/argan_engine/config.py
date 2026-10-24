"""Single source of truth for every user-adjustable input.

Each field carries UI metadata (Persian label, unit, range, provenance, audience level).
The API serves this metadata so both UIs are generated from the same definitions.

provenance:
  data        – estimated from the uploaded market data (can be overridden)
  judgment    – expert judgment; no data in the repo identifies it
  placeholder – illustrative number that MUST be replaced with company data
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


def F(default: Any, label: str, *, unit: str = "", group: str, level: str = "expert",
      prov: str = "placeholder", lo: float | None = None, hi: float | None = None,
      step: float | None = None, hint: str = "", **kw: Any) -> Any:
    extra = {"label_fa": label, "unit": unit, "group": group, "level": level,
             "provenance": prov, "hint_fa": hint}
    if lo is not None:
        extra["min"] = lo
    if hi is not None:
        extra["max"] = hi
    if step is not None:
        extra["step"] = step
    return Field(default, json_schema_extra=extra, **kw)


class Scenario(BaseModel):
    """Everything needed to run one analysis. Percent fields are plain percents (60 = 60%)."""

    # ---- decision ---------------------------------------------------------------------
    purchase_budget_usd: float = F(100_000, "ارزش خرید محموله", unit="دلار", group="decision",
                                   level="simple", prov="judgment", lo=1_000, hi=5_000_000, step=1_000,
                                   hint="مقدار فیزیکی خرید از تقسیم این مبلغ بر قیمت روز محاسبه می‌شود")
    purchase_qty_kg: float | None = F(None, "مقدار خرید (اختیاری)", unit="کیلوگرم", group="decision",
                                      prov="judgment", lo=100, hi=500_000, step=100,
                                      hint="اگر پر شود به‌جای مبلغ، مقدار ثابت کیلویی خرید فرض می‌شود")
    purchase_mode: Literal["fixed_quantity", "fixed_usd_budget"] = F(
        "fixed_quantity", "نوع تعهد خرید", group="decision", level="expert", prov="judgment",
        hint="مقدار ثابت: همه‌ی سیاست‌ها همان تعداد کیلوگرم را می‌خرند و مبلغ نهایی با قیمت جهانی تغییر می‌کند. "
             "مبلغ دلاری ثابت: هر قسط همان مبلغ دلاری را خرج می‌کند و مقدار خریداری‌شده با قیمت روز سفارش تغییر می‌کند")
    prepay_fraction_pct: float = F(100.0, "سهم پیش‌پرداخت از فاکتور", unit="%", group="decision", level="expert",
                                   prov="placeholder", lo=0, hi=100, step=10,
                                   hint="سهمی از مبلغ دلاری فاکتور که هنگام سفارش پرداخت می‌شود؛ باقی هنگام ورود کالا و با نرخ ارز همان روز تسویه می‌شود. "
                                        "پیش‌فرض ۱۰۰٪ فقط برای سازگاری با نسخه‌ی قبل است، نه قرارداد واقعی")
    horizon_days: int = F(90, "افق تصمیم", unit="روز", group="decision", level="simple", prov="judgment",
                          lo=28, hi=180, step=7)
    lead_time_days: int = F(14, "زمان تحویل (سفارش تا انبار)", unit="روز", group="decision", level="simple",
                            prov="placeholder", lo=0, hi=90, step=7,
                            hint="حمل دریایی/گمرک؛ در مدل به هفته گرد می‌شود")
    schedule_days: list[int] = F([0, 30, 60], "روزهای ممکن برای سفارش", unit="روز", group="decision",
                                 prov="judgment", hint="سیاست‌ها وزن‌دهی روی این روزهاست")
    grid_step: float = F(0.1, "گام شبکه وزن‌ها", group="decision", prov="judgment", lo=0.05, hi=0.34, step=0.05)

    # ---- operations -------------------------------------------------------------------
    initial_inventory_kg: float = F(3_000, "موجودی فعلی انبار", unit="کیلوگرم", group="operations",
                                    level="simple", lo=0, hi=500_000, step=100)
    weekly_demand_kg: float = F(1_000, "میانگین فروش هفتگی", unit="کیلوگرم", group="operations",
                                level="simple", lo=10, hi=100_000, step=50)
    demand_cv: float = F(0.25, "ضریب تغییرات تقاضای هفتگی", group="operations", lo=0.0, hi=1.0, step=0.05,
                         hint="انحراف معیار ÷ میانگین. با داده فروش واقعی جایگزین شود")
    demand_price_elasticity: float = F(0.3, "کشش قیمتی تقاضا", group="operations", prov="judgment",
                                       lo=0.0, hi=2.0, step=0.1,
                                       hint="0 یعنی تقاضا به قیمت واقعی حساس نیست")
    demand_fx_rho: float = F(-0.2, "هم‌بستگی شوک تقاضا با شوک ارز", group="operations", prov="judgment",
                             lo=-0.9, hi=0.5, step=0.05,
                             hint="منفی یعنی در جهش ارز، تقاضا هم‌زمان افت می‌کند (wrong-way risk)")
    landing_cost_pct: float = F(15.0, "هزینه حمل، بیمه، گمرک", unit="% ارزش کالا", group="operations",
                                prov="placeholder", lo=0, hi=60, step=1)
    storage_cost_pct_week: float = F(0.15, "هزینه انبارداری", unit="% ارزش موجودی در هفته",
                                     group="operations", prov="placeholder", lo=0, hi=2, step=0.05)
    shrink_pct_week: float = F(0.05, "افت کیفی/وزنی", unit="% در هفته", group="operations",
                               prov="placeholder", lo=0, hi=2, step=0.05)
    terminal_haircut_pct: float = F(0.0, "کسر ارزش موجودی پایان افق", unit="%", group="operations",
                                    prov="judgment", lo=0, hi=50, step=1,
                                    hint="اگر فروش فوری موجودی با تخفیف ممکن است")

    safety_stock_weeks: float = F(1.0, "حداقل موجودی ایمن", unit="هفته فروش", group="operations", level="simple",
                                  prov="judgment", lo=0, hi=12, step=0.5,
                                  hint="ریسک افتادن موجودی زیر این حد در گزارش می‌آید")
    demand_shift_pct: float = F(0.0, "تغییر ثابت سطح تقاضا (فروض تنش)", unit="%", group="operations",
                                prov="judgment", lo=-80, hi=100, step=5,
                                hint="۰ = بدون تغییر. در تحلیل تنش برای «افت تقاضا» استفاده می‌شود")

    demand_seasonal_index: list[float] = F([], "شاخص فصلی تقاضا (۵۲ هفته، میانگین ۱)", group="operations", level="internal",
                                           prov="data", hint="خالی = بدون فصل. از داده‌ی فروش شرکت برآورد می‌شود")
    season_start_week: int = F(0, "هفته‌ی سال در آغاز افق (۰ تا ۵۱)", group="operations", level="internal", prov="data", lo=0, hi=51, step=1)
    pipeline_weeks: list[int] = F([], "هفته‌ی رسیدن محموله‌های در راه", group="operations", level="internal", prov="data",
                                  hint="محموله‌هایی که قبلاً سفارش و پرداخت شده‌اند")
    pipeline_kg: list[float] = F([], "مقدار محموله‌های در راه", unit="کیلوگرم", group="operations", level="internal", prov="data")

    # ---- imports / supply disruption ------------------------------------------------------
    import_delay_prob_pct: float = F(0.0, "احتمال تأخیر محموله (قضاوت شما)", unit="%", group="imports",
                                     prov="judgment", lo=0, hi=100, step=5,
                                     hint="پیش‌فرض ۰: مدل برای وقایع جنگی احتمال ساختگی نمی‌گذارد؛ اثر تأخیر در سناریوهای تنش سنجیده می‌شود")
    import_loss_prob_pct: float = F(0.0, "احتمال گم‌شدن محموله‌ی دچار تأخیر (پیش‌پرداخت از دست می‌رود)", unit="% از تأخیرها", group="imports",
                                    level="expert", prov="placeholder", lo=0, hi=100, step=5,
                                    hint="0 = هر محموله‌ی دیررسیده سرانجام می‌رسد. اگر مثلاً ۲۵ بگذارید، در ۲۵٪ مسیرهای دارای تأخیر محموله هرگز نمی‌رسد ولی پولش پرداخت شده است. این یک باور است، نه برآورد")
    import_delay_days: int = F(42, "تأخیر اضافه در شرایط بحران", unit="روز", group="imports", level="simple",
                               prov="placeholder", lo=0, hi=180, step=7,
                               hint="زمان تحویل بحران = زمان تحویل عادی + این مقدار")

    # ---- pricing ----------------------------------------------------------------------
    target_markup_pct: float = F(30.0, "حاشیه سود روی بهای جایگزینی", unit="%", group="pricing",
                                 level="simple", prov="placeholder", lo=0, hi=200, step=1,
                                 hint="قیمت فروش اولیه = بهای جایگزینی × (1+حاشیه)")
    pass_through_up: float = F(0.85, "انتقال افزایش هزینه به قیمت فروش", group="pricing", prov="judgment",
                               lo=0, hi=1.5, step=0.05, hint="β: چه کسری از جهش هزینه به مشتری منتقل می‌شود")
    pass_through_down: float = F(0.40, "انتقال کاهش هزینه به قیمت فروش", group="pricing", prov="judgment",
                                 lo=0, hi=1.5, step=0.05, hint="قیمت‌ها معمولاً به‌سرعت بالا می‌روند و کند پایین می‌آیند")
    lag_up_weeks: int = F(1, "تأخیر انتقال افزایش", unit="هفته", group="pricing", prov="judgment", lo=0, hi=12, step=1)
    price_indexation: float = F(0.0, "پیروی قیمت فروش از تورم عمومی (علاوه بر هزینه)", group="pricing",
                                prov="judgment", lo=0, hi=1, step=0.1,
                                hint="0 = قیمت فقط از بهای جایگزینی پیروی می‌کند؛ 1 = قیمت هم‌پای تورم عمومی بالا می‌رود")
    lag_down_weeks: int = F(4, "تأخیر انتقال کاهش", unit="هفته", group="pricing", prov="judgment", lo=0, hi=26, step=1)

    # ---- finance ----------------------------------------------------------------------
    initial_cash_bn_irr: float = F(360.0, "نقدینگی در دسترس", unit="میلیارد ریال", group="finance",
                                   level="simple", lo=0, hi=100_000, step=10)
    min_cash_bn_irr: float = F(50.0, "حداقل نقدینگی ایمن", unit="میلیارد ریال", group="finance",
                               level="simple", prov="judgment", lo=0, hi=100_000, step=5)
    weekly_opex_bn_irr: float = F(10.0, "هزینه جاری هفتگی (حقوق، اجاره، …)", unit="میلیارد ریال",
                                  group="finance", lo=0, hi=10_000, step=1)
    initial_receivables_bn_irr: float = F(0.0, "مطالبات وصول‌نشده‌ی فعلی", unit="میلیارد ریال", group="finance", level="internal",
                                          prov="data", lo=0, hi=1_000_000, step=10,
                                          hint="فروش‌های قبلی که در هفته‌های آینده وصول می‌شود؛ از جدول وصول شرکت")
    receivable_lag_weeks: int = F(2, "تأخیر وصول مطالبات", unit="هفته", group="finance", lo=0, hi=12, step=1)
    deposit_rate_pct: float = F(25.0, "نرخ سود سپرده (بازده نقد مازاد)", unit="% سالانه", group="finance",
                                prov="placeholder", lo=0, hi=200, step=1)
    borrow_rate_pct: float = F(40.0, "نرخ تأمین مالی/اضافه‌برداشت", unit="% سالانه", group="finance",
                               prov="placeholder", lo=0, hi=300, step=1)
    inflation_pct: float = F(60.0, "تورم سالانه منطقه فعالیت", unit="% سالانه", group="finance",
                             level="simple", prov="placeholder", lo=0, hi=300, step=1,
                             hint="برای تبدیل سود به قدرت خرید امروز. تورم استان/منطقه خودتان را وارد کنید")
    region_label: str = F("", "نام منطقه (برچسب گزارش)", group="finance", level="simple", prov="judgment")

    # ---- market -----------------------------------------------------------------------
    fx_model: Literal["auto", "regime", "t", "gbm"] = F("auto", "مدل نرخ ارز", group="market", prov="data",
                                                        hint="auto = برنده‌ی بک‌تست خارج از نمونه")
    fx_drift_annual_pct: float | None = F(None, "روند سالانه دلار (دستی)", unit="% لگاریتمی سالانه",
                                          group="market", level="simple", prov="data", lo=-50, hi=300, step=1,
                                          hint="خالی = برآورد تاریخی. عدد شما جایگزین میانگین بلندمدت مدل می‌شود")
    fx_vol_mult: float = F(1.0, "ضریب نوسان ارز", group="market", prov="judgment", lo=0.3, hi=3, step=0.05)
    coffee_vol_mult: float = F(1.0, "ضریب نوسان قهوه", group="market", prov="judgment", lo=0.3, hi=3, step=0.05)
    corr_coffee_fx: float | None = F(None, "هم‌بستگی قهوه–ارز", group="market", prov="data",
                                     lo=-0.9, hi=0.9, step=0.05, hint="خالی = برآورد از داده (تقریباً صفر)")
    event_p_escalation: float = F(0.0, "احتمال تشدید تنش (جهش اضافه به بالا) در افق", unit="%", group="market",
                                  level="simple", prov="judgment", lo=0, hi=100, step=1,
                                  hint="افزون بر آنچه در تاریخچه دیده شده؛ اندازه‌ی جهش از تاریخچه بوت‌استرپ می‌شود")
    event_size_mult: float = F(1.0, "شدت جهش‌های تشدید تنش (ضریب اندازه)", unit="×", group="market", level="expert", prov="judgment",
                               lo=0.25, hi=4, step=0.25, hint="۱ = اندازه‌ی جهش‌های دیده‌شده در تاریخچه؛ ۲ = دو برابر. باور شما، نه برآورد")
    event_p_deal: float = F(0.0, "احتمال کاهش تنش/توافق (جهش اضافه به پایین) در افق", unit="%", group="market",
                            level="simple", prov="judgment", lo=0, hi=100, step=1)
    coffee_spot_c_lb: float | None = F(None, "قیمت امروز آرابیکا (اختیاری)", unit="سنت بر پوند", group="market",
                                       level="simple", prov="data", lo=50, hi=1000, step=1,
                                       hint="داده‌ی قهوه بعد از ۲۰ آگوست ۲۰۲۶ نقدشونده نیست؛ قیمت امروز را اینجا وارد کنید")
    coffee_differential_usd_kg: float = F(0.0, "پریمیوم/دیفرانسیل نسبت به آرابیکای نیویورک", unit="دلار بر کیلو",
                                          group="market", prov="placeholder", lo=-3, hi=10, step=0.1)
    fx_spot_irr: float | None = F(None, "نرخ دلار امروز (اختیاری)", unit="ریال", group="market", level="simple",
                                  prov="data", lo=10_000, hi=50_000_000, step=1_000)
    fx_basis_factor: float = F(1.0, "نرخ ارزی که شرکت واقعاً می‌تواند با آن پرداخت کند (نسبت به بازار آزاد)",
                               group="market", level="simple", prov="placeholder", lo=0.3, hi=1.5, step=0.01,
                               hint="۱ = همان نرخ آزاد؛ ۱٫۰۸ یعنی ۸٪ گران‌تر از بازار آزاد")
    param_se: dict[str, float] = F({}, "خطای معیار برآوردها از داده‌ی شرکت", group="market", level="internal", prov="data",
                                   hint="برای باریک‌کردن بازه‌ی جهان‌های ممکن وقتی پارامتر از داده برآورد شده")
    basket_beta: float = F(1.0, "حساسیت قیمت سبد خرید به آرابیکا", group="market", prov="placeholder", lo=0.2, hi=1.5, step=0.05,
                           hint="۱ = سبد مثل آرابیکا حرکت می‌کند. از داده‌ی خرید شرکت (روبوستا، اسپشیالیتی، …) برآورد می‌شود")
    basket_basis_vol_pct: float = F(0.0, "نوسان هفتگی مستقل سبد (غیر از آرابیکا)", unit="% هفتگی", group="market", prov="placeholder",
                                    lo=0, hi=10, step=0.1)
    fx_transfer_cost_pct: float = F(0.0, "هزینه‌ی انتقال پول (کارمزد، واسطه)", unit="% مبلغ", group="market",
                                    prov="placeholder", lo=0, hi=50, step=0.5,
                                    hint="به هزینه‌ی ریالی واردات افزوده می‌شود")

    # ---- risk preferences -------------------------------------------------------------
    cvar_alpha: float = F(0.95, "سطح اطمینان CVaR", group="risk", prov="judgment", lo=0.8, hi=0.99, step=0.01)
    risk_lambda: float = F(0.3, "وزن ریسک در هدف (0 = فقط میانگین، 1 = فقط بدترین دنباله)", group="risk",
                           prov="judgment", lo=0.0, hi=0.95, step=0.05)
    risk_appetite: Literal["cautious", "balanced", "bold", "custom"] = F("balanced", "اشتهای ریسک", group="risk",
                                                                        level="simple", prov="judgment")
    max_liquidity_breach_prob_pct: float = F(10.0, "حداکثر احتمال افت نقدینگی زیر حد ایمن", unit="%", group="risk",
                                             prov="judgment", lo=0, hi=100, step=1)
    max_unmet_demand_pct: float = F(5.0, "حداکثر کمبود مورد انتظار (از کل تقاضا)", unit="%", group="risk",
                                    prov="judgment", lo=0, hi=100, step=0.5)

    # ---- compute ----------------------------------------------------------------------
    n_paths: int = F(6_000, "تعداد مسیر مونت‌کارلو", group="compute", prov="judgment", lo=500, hi=100_000, step=500)
    robust: bool = F(True, "تحلیل استحکام (جهان‌های ممکن)", group="compute", prov="judgment")
    n_worlds: int = F(40, "تعداد جهان‌های ممکن", group="compute", prov="judgment", lo=8, hi=300, step=4)
    worlds_auto: bool = F(True, "افزایش خودکار جهان‌ها تا همگرایی", group="compute", prov="judgment",
                          hint="اگر انتخاب سیاست با زیرمجموعه‌ی جهان‌ها پایدار نبود، جهان‌های بیشتری اضافه می‌شود")
    n_worlds_max: int = F(120, "سقف تعداد جهان‌ها", group="compute", prov="judgment", lo=8, hi=400, step=8)
    paths_per_world: int = F(1_200, "مسیر در هر جهان", group="compute", prov="judgment", lo=200, hi=10_000, step=100)
    flip_analysis: bool = F(True, "منحنی «چه چیزی تصمیم را عوض می‌کند»", group="compute", prov="judgment")
    seed: int = F(20261020, "بذر تصادفی", group="compute", prov="judgment")

    @field_validator("schedule_days")
    @classmethod
    def _sched(cls, v: list[int]) -> list[int]:
        v = sorted(set(int(x) for x in v))
        if not v or v[0] < 0 or len(v) > 5:
            raise ValueError("schedule_days must have 1..5 non-negative days")
        return v

    @model_validator(mode="after")
    def _check_lists(self) -> "Scenario":
        if len(self.pipeline_weeks) != len(self.pipeline_kg):
            raise ValueError("pipeline_weeks and pipeline_kg must have the same length")
        if self.demand_seasonal_index and len(self.demand_seasonal_index) != 52:
            raise ValueError("demand_seasonal_index must have 52 values or be empty")
        return self

    @model_validator(mode="after")
    def _check(self) -> "Scenario":
        if self.borrow_rate_pct < self.deposit_rate_pct:
            raise ValueError("borrow rate must be >= deposit rate")
        if self.risk_appetite != "custom":
            self.risk_lambda = {"cautious": 0.6, "balanced": 0.3, "bold": 0.1}[self.risk_appetite]
        return self

    # ---- derived ----------------------------------------------------------------------
    @property
    def horizon_weeks(self) -> int:
        return max(4, int(round(self.horizon_days / 7)))

    @property
    def lead_weeks(self) -> int:
        return int(round(self.lead_time_days / 7))

    @property
    def delay_weeks(self) -> int:
        return int(round(self.import_delay_days / 7))

    @property
    def crisis_lead_days(self) -> int:
        return int(self.lead_weeks * 7 + self.delay_weeks * 7)

    @property
    def fx_basis_total(self) -> float:
        """Effective rial-per-USD multiplier actually paid (access premium × transfer cost)."""
        return self.fx_basis_factor * (1.0 + self.fx_transfer_cost_pct / 100.0)

    @property
    def schedule_weeks(self) -> list[int]:
        w = [int(round(d / 7)) for d in self.schedule_days]
        return [min(x, self.horizon_weeks - 1) for x in w]


def scenario_schema() -> list[dict]:
    """Field metadata list used by the UIs."""
    out = []
    for name, f in Scenario.model_fields.items():
        extra = dict(f.json_schema_extra or {})
        extra.update(name=name, default=f.default,
                     type=("bool" if isinstance(f.default, bool) else
                           "enum" if "Literal" in str(f.annotation) else
                           "list" if isinstance(f.default, list) else
                           "text" if isinstance(f.default, str) else "number"))
        if extra["type"] == "enum":
            extra["options"] = list(getattr(f.annotation, "__args__", []))
        out.append(extra)
    return out
