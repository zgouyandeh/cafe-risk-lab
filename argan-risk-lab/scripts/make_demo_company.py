"""Regenerate the SYNTHETIC demo company (data/company_demo/*.csv + ground_truth.json) and docs/DATA_TEMPLATE.md."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "argan_engine" / "src"))
from argan_engine.company.schema import TABLES  # noqa: E402
from argan_engine.company.synth import generate, write_csv  # noqa: E402

tab, truth = generate()
write_csv(tab, truth, ROOT / "data" / "company_demo")
lines = ["# قالب داده‌ی شرکت\n", "برای جایگزینی داده‌ی ساختگی با داده‌ی واقعی، هر جدول را با همین ستون‌ها (CSV، UTF-8، تاریخ به‌صورت YYYY-MM-DD) بارگذاری کنید.\n",
         "هیچ‌یک از اعداد مدل از خودِ ما نیامده؛ هر پارامتر از این جدول‌ها برآورد می‌شود (روش هر برآورد در صفحه‌ی «داده‌ی شرکت»).\n"]
for n, (cols, desc, freq) in TABLES.items():
    lines += [f"\n## {n}  ({freq})\n", desc + "\n", "`" + ", ".join(cols) + "`\n"]
APPENDIX = '\n\n## پیوست: ثبت پرداخت و تحویل هر محموله (اختیاری، برای اعمال قرارداد واقعی)\n\nمدل اکنون پیش\u200cپرداخت، تسویه هنگام تحویل و محموله\u200cی تحویل\u200cنشده را می\u200cشناسد. جدول `purchases` بالا برای برآورد نرخ و زمان تحویل کافی است؛ برای کالیبراسیون قرارداد واقعی، هر پرداخت را جداگانه در جدول زیر ثبت کنید (یک ردیف برای هر پرداخت):\n\n`shipment_id, invoice_usd, payment_kind, payment_date, payment_usd, fx_paid_irr, delivery_status, delivery_date, recovered_usd`\n\n* `payment_kind`: `prepayment` (هنگام سفارش) یا `balance` (تسویه\u200cی مانده، معمولاً هنگام ورود کالا).\n* `invoice_usd`: مبلغ دلاری فاکتور؛ قیمت دلاری در روز سفارش ثابت می\u200cشود، پس نوسان بعدی قهوه مبلغ همان فاکتور را عوض نمی\u200cکند، ولی نرخ ارز هر پرداخت اهمیت دارد.\n* `fx_paid_irr`: نرخ مؤثر ریالی همان پرداخت (نه نرخ بازار).\n* `delivery_status`: `delivered`، `in_transit` یا `not_delivered`. برای `not_delivered` مانده پرداخت نمی\u200cشود و پیش\u200cپرداخت بازیابی\u200cنشده زیان است.\n* `recovered_usd`: بخشی از پیش\u200cپرداخت که از فروشنده، بیمه یا مسیر دیگر بازگشته است (اختیاری؛ در نسخه\u200cی کنونی مدل بازیابی صفر فرض می\u200cشود).\n* تاریخ\u200cها `YYYY-MM-DD`. هزینه\u200cی حمل، بیمه و گمرک در مدل به\u200cصورت درصدی از ارزش و در تاریخ پرداخت فاکتور لحاظ می\u200cشود (فرض ساده\u200cساز نسخه\u200cی اول).\n\nاین جدول فعلاً به\u200cصورت خودکار بارگذاری نمی\u200cشود؛ پارامترهای `prepay_fraction_pct` و `purchase_mode` در رابط (بخش «قرارداد خرید») دستی تنظیم می\u200cشوند.\n'
(ROOT / "docs" / "DATA_TEMPLATE.md").write_text("\n".join(lines) + APPENDIX, encoding="utf-8")
print("ok", len(tab), "tables")
