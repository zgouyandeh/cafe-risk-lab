# قالب داده‌ی شرکت

برای جایگزینی داده‌ی ساختگی با داده‌ی واقعی، هر جدول را با همین ستون‌ها (CSV، UTF-8، تاریخ به‌صورت YYYY-MM-DD) بارگذاری کنید.

هیچ‌یک از اعداد مدل از خودِ ما نیامده؛ هر پارامتر از این جدول‌ها برآورد می‌شود (روش هر برآورد در صفحه‌ی «داده‌ی شرکت»).


## market_weekly  (هفتگی)

قیمت‌های بازار و نرخ مؤثر: آرابیکای بورس (سنت/پوند)، قیمت FOB هر نوع دانه (دلار/کیلو)، نرخ بازار آزاد، نرخ مؤثر پرداخت شرکت، شاخص قیمت

`week_end, arabica_c_lb, price_washed_usd_kg, price_natural_usd_kg, price_robusta_usd_kg, price_specialty_usd_kg, fx_market_irr, fx_effective_irr, cpi_index`


## sales_weekly  (هفتگی)

فروش هفتگی هر محصول؛ unmet_kg = سفارش ردشده/ازدست‌رفته به‌علت کمبود موجودی (اگر ثبت نمی‌شود خالی بگذارید؛ تقاضا سانسور می‌شود)

`week_end, product, kg_sold, unmet_kg, avg_price_irr_kg, revenue_irr`


## purchases  (رویدادی)

هر محموله‌ی وارداتی: تاریخ سفارش/پرداخت و رسیدن، مقدار، قیمت FOB، نرخ ارز پرداختی، کارمزد انتقال و هزینه‌های حمل/بیمه/گمرک به درصد ارزش FOB

`shipment_id, product, order_date, arrival_date, kg, fob_usd_kg, fx_paid_irr, transfer_fee_pct, freight_pct, insurance_pct, customs_pct`


## inventory_weekly  (هفتگی)

موجودی پایان هفته، افت وزنی/کیفی، هزینه‌ی انبارداری و ارزش دفتری موجودی

`week_end, product, on_hand_kg, shrink_kg, storage_cost_irr, inventory_value_irr`


## collections_weekly  (هفتگی)

وصول مطالبات هفته و مانده‌ی مطالبات پایان هفته

`week_end, receipts_irr, receivables_end_irr`


## opex_weekly  (هفتگی)

هزینه‌های جاری هفتگی

`week_end, salaries_irr, rent_irr, marketing_irr, logistics_irr, other_irr, total_opex_irr`


## cash_weekly  (هفتگی)

نقد و بدهی کوتاه‌مدت پایان هفته، سود دریافتی/پرداختی، استقراض و برداشت سهام‌داران

`week_end, cash_end_irr, debt_end_irr, interest_income_irr, interest_expense_irr, borrowing_irr, dividends_irr`


## pnl_weekly  (هفتگی)

سود و زیان هفتگی (بهای تمام‌شده به روش FIFO)

`week_end, revenue_irr, cogs_irr, gross_profit_irr, storage_irr, shrink_cost_irr, opex_irr, net_interest_irr, net_profit_irr`


## annual_pnl  (سالانه)

سود و زیان سالانه (سال مالی از ۱ فروردین)

`fiscal_year, jalali_year, volume_kg, revenue_irr, cogs_irr, gross_profit_irr, storage_irr, shrink_cost_irr, opex_irr, net_interest_irr, net_profit_irr`


## annual_balance  (سالانه)

ترازنامه‌ی خلاصه‌ی پایان سال

`fiscal_year, jalali_year, cash_irr, receivables_irr, inventory_irr, debt_irr, equity_irr`


## annual_by_product  (سالانه)

فروش و بهای تمام‌شده‌ی سالانه به تفکیک محصول

`fiscal_year, jalali_year, product, kg, revenue_irr, cogs_irr`


## پیوست: ثبت پرداخت و تحویل هر محموله (اختیاری، برای اعمال قرارداد واقعی)

مدل اکنون پیش‌پرداخت، تسویه هنگام تحویل و محموله‌ی تحویل‌نشده را می‌شناسد. جدول `purchases` بالا برای برآورد نرخ و زمان تحویل کافی است؛ برای کالیبراسیون قرارداد واقعی، هر پرداخت را جداگانه در جدول زیر ثبت کنید (یک ردیف برای هر پرداخت):

`shipment_id, invoice_usd, payment_kind, payment_date, payment_usd, fx_paid_irr, delivery_status, delivery_date, recovered_usd`

* `payment_kind`: `prepayment` (هنگام سفارش) یا `balance` (تسویه‌ی مانده، معمولاً هنگام ورود کالا).
* `invoice_usd`: مبلغ دلاری فاکتور؛ قیمت دلاری در روز سفارش ثابت می‌شود، پس نوسان بعدی قهوه مبلغ همان فاکتور را عوض نمی‌کند، ولی نرخ ارز هر پرداخت اهمیت دارد.
* `fx_paid_irr`: نرخ مؤثر ریالی همان پرداخت (نه نرخ بازار).
* `delivery_status`: `delivered`، `in_transit` یا `not_delivered`. برای `not_delivered` مانده پرداخت نمی‌شود و پیش‌پرداخت بازیابی‌نشده زیان است.
* `recovered_usd`: بخشی از پیش‌پرداخت که از فروشنده، بیمه یا مسیر دیگر بازگشته است (اختیاری؛ در نسخه‌ی کنونی مدل بازیابی صفر فرض می‌شود).
* تاریخ‌ها `YYYY-MM-DD`. هزینه‌ی حمل، بیمه و گمرک در مدل به‌صورت درصدی از ارزش و در تاریخ پرداخت فاکتور لحاظ می‌شود (فرض ساده‌ساز نسخه‌ی اول).

این جدول فعلاً به‌صورت خودکار بارگذاری نمی‌شود؛ پارامترهای `prepay_fraction_pct` و `purchase_mode` در رابط (بخش «قرارداد خرید») دستی تنظیم می‌شوند.
