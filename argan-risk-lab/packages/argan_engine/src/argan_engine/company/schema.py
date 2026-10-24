"""Company data template: the tables a company must provide (weekly + annual), their columns and meaning.
The same spec drives validation, the downloadable templates and docs/DATA_TEMPLATE.md."""
from __future__ import annotations

PRODUCTS = ["washed", "natural", "robusta", "specialty"]
PRODUCT_FA = {"washed": "آرابیکا شسته", "natural": "آرابیکا طبیعی (برزیل)", "robusta": "روبوستا", "specialty": "اسپشیالیتی"}

# name -> (required columns, Persian description, frequency)
TABLES: dict[str, tuple[list[str], str, str]] = {
    "market_weekly": (
        ["week_end", "arabica_c_lb", "price_washed_usd_kg", "price_natural_usd_kg", "price_robusta_usd_kg", "price_specialty_usd_kg",
         "fx_market_irr", "fx_effective_irr", "cpi_index"],
        "قیمت‌های بازار و نرخ مؤثر: آرابیکای بورس (سنت/پوند)، قیمت FOB هر نوع دانه (دلار/کیلو)، نرخ بازار آزاد، نرخ مؤثر پرداخت شرکت، شاخص قیمت", "هفتگی"),
    "sales_weekly": (
        ["week_end", "product", "kg_sold", "unmet_kg", "avg_price_irr_kg", "revenue_irr"],
        "فروش هفتگی هر محصول؛ unmet_kg = سفارش ردشده/ازدست‌رفته به‌علت کمبود موجودی (اگر ثبت نمی‌شود خالی بگذارید؛ تقاضا سانسور می‌شود)", "هفتگی"),
    "purchases": (
        ["shipment_id", "product", "order_date", "arrival_date", "kg", "fob_usd_kg", "fx_paid_irr", "transfer_fee_pct", "freight_pct", "insurance_pct", "customs_pct"],
        "هر محموله‌ی وارداتی: تاریخ سفارش/پرداخت و رسیدن، مقدار، قیمت FOB، نرخ ارز پرداختی، کارمزد انتقال و هزینه‌های حمل/بیمه/گمرک به درصد ارزش FOB", "رویدادی"),
    "inventory_weekly": (
        ["week_end", "product", "on_hand_kg", "shrink_kg", "storage_cost_irr", "inventory_value_irr"],
        "موجودی پایان هفته، افت وزنی/کیفی، هزینه‌ی انبارداری و ارزش دفتری موجودی", "هفتگی"),
    "collections_weekly": (
        ["week_end", "receipts_irr", "receivables_end_irr"],
        "وصول مطالبات هفته و مانده‌ی مطالبات پایان هفته", "هفتگی"),
    "opex_weekly": (
        ["week_end", "salaries_irr", "rent_irr", "marketing_irr", "logistics_irr", "other_irr", "total_opex_irr"],
        "هزینه‌های جاری هفتگی", "هفتگی"),
    "cash_weekly": (
        ["week_end", "cash_end_irr", "debt_end_irr", "interest_income_irr", "interest_expense_irr", "borrowing_irr", "dividends_irr"],
        "نقد و بدهی کوتاه‌مدت پایان هفته، سود دریافتی/پرداختی، استقراض و برداشت سهام‌داران", "هفتگی"),
    "pnl_weekly": (
        ["week_end", "revenue_irr", "cogs_irr", "gross_profit_irr", "storage_irr", "shrink_cost_irr", "opex_irr", "net_interest_irr", "net_profit_irr"],
        "سود و زیان هفتگی (بهای تمام‌شده به روش FIFO)", "هفتگی"),
    "annual_pnl": (
        ["fiscal_year", "jalali_year", "volume_kg", "revenue_irr", "cogs_irr", "gross_profit_irr", "storage_irr", "shrink_cost_irr", "opex_irr", "net_interest_irr", "net_profit_irr"],
        "سود و زیان سالانه (سال مالی از ۱ فروردین)", "سالانه"),
    "annual_balance": (
        ["fiscal_year", "jalali_year", "cash_irr", "receivables_irr", "inventory_irr", "debt_irr", "equity_irr"],
        "ترازنامه‌ی خلاصه‌ی پایان سال", "سالانه"),
    "annual_by_product": (
        ["fiscal_year", "jalali_year", "product", "kg", "revenue_irr", "cogs_irr"],
        "فروش و بهای تمام‌شده‌ی سالانه به تفکیک محصول", "سالانه"),
}
