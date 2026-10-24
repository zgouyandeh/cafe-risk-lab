"""Printable Persian management report (HTML) from a finished analysis."""
from __future__ import annotations

from jinja2 import Template

from ..advisor import fa, pct
from ..advisor.explain import better_worse, jalali_text, tolerance_text

TPL = Template("""<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8">
<title>گزارش مدیریتی خرید قهوه</title>
<style>
body{font-family:Vazirmatn,Tahoma,sans-serif;max-width:900px;margin:2rem auto;padding:0 1rem;line-height:1.9;color:#1b1f23}
h1{font-size:1.6rem}h2{border-bottom:2px solid #ddd;padding-bottom:.3rem;margin-top:2rem}
table{border-collapse:collapse;width:100%}td,th{border:1px solid #ccc;padding:.4rem .6rem;text-align:right}
th{background:#f3f4f6}.box{background:#f8fafc;border:1px solid #dbe3ec;padding:1rem;border-radius:8px}
.warn{background:#fff7ed;border-color:#fdba74}.syn{background:#fee2e2;border:2px solid #dc2626;color:#7f1d1d;padding:.7rem 1rem;border-radius:8px;font-weight:700;margin:1rem 0}small{color:#555}</style></head><body>
<h1>گزارش مدیریتی: زمان‌بندی خرید محموله‌ی قهوه</h1>
{% if res.data_source and res.data_source.synthetic %}<div class="syn">⚠ داده‌ی ساختگی: ارقام شرکت (فروش، موجودی، نقدینگی) شبیه‌سازی‌شده‌اند و فقط قیمت آرابیکا و نرخ دلار واقعی‌اند. این گزارش آزمون روش است، نه یافته درباره‌ی شرکت واقعی.</div>{% endif %}
<small>تاریخ تحلیل: {{ jd(m.as_of) }} · آخرین قیمت قهوه‌ی موجود: {{ jd(m.coffee_last_date) }} · نمونه‌کار مستقل؛ برای آرگن مستقر نشده و به داده‌ی داخلی هیچ شرکتی دسترسی ندارد.</small>

<h2>۱. چه کار کنیم؟</h2>
{% if mg.warning %}<div class="syn" style="background:#fff7ed;border-color:#ea580c;color:#7c2d12">توجه: {{ mg.warning }}</div>{% endif %}
<div class="box"><p style="font-size:1.15rem"><b>{{ mg.action }}</b></p>
{% if mg.steps|length > 1 or true %}<table><tr><th>زمان</th><th>تاریخ</th><th>سهم</th><th>مقدار</th><th>مبلغ</th></tr>
{% for st in mg.steps %}<tr><td>{{ st.when }}</td><td>{{ st.date }}</td><td>{{ st.share }}</td><td>{{ st.kg }}</td><td>{{ st.usd }} (حدود {{ st.bn }})</td></tr>{% endfor %}</table>{% endif %}
<small>مبلغ‌ها به قیمت و نرخ امروزند؛ مبلغ واقعی هر قسط با قیمت آن روز تغییر می‌کند.</small></div>

<h2>۲. چرا این‌طور؟</h2>
<ul>{% for w in mg.why %}<li><b>{{ w.title }}:</b> {{ w.text }}</li>{% endfor %}</ul>

<h2>۳. چقدر مطمئنیم؟</h2>
{% if mg.sure %}<div class="box"><p><b>اطمینان: {{ mg.sure.level }}.</b> {{ mg.sure.text }}</p></div>{% endif %}

<h2>۴. اگر پیش‌بینی ما غلط باشد؟</h2>
<p>تصمیم خوب نباید فقط وقتی پیش‌بینی درست است خوب باشد. اینجا می‌بینیم همین برنامه زیر فشار چه می‌شود. عددها به میلیارد ریال‌اند؛ <b>عدد منفی یعنی زیان و عدد مثبت یعنی سود</b>. این شوک‌ها آزمون‌اند، نه پیش‌بینی.</p>
<table><tr><th>اگر این اتفاق بیفتد...</th><th>سود یا زیان مورد انتظار</th><th>نتیجه در بدترین ۵٪ حالت‌ها</th><th>احتمال افت نقدینگی زیر حد ایمن</th><th>تأمین تقاضا</th><th>نتیجه</th></tr>
{% for w in mg.wrong %}<tr><td><b>{{ w.label }}</b><br><small>{{ w.desc }}</small></td><td>{{ w.mean }}</td><td>{{ w.tail }}</td><td>{{ w.breach }}</td><td>{{ w.supply }}</td><td><b>{{ w.verdict }}</b></td></tr>{% endfor %}</table>
<small>«ادامه می‌یابد» یعنی حدود نقدینگی و کمبود شما رعایت می‌شود؛ «در خطر» یعنی یکی از حدود نقض می‌شود؛ «شکست می‌خورد» یعنی نقدینگی در نیمی از حالت‌ها منفی می‌شود یا یک‌پنجم تقاضا بی‌پاسخ می‌ماند.</small>

<h2>۵. پیش از هر پرداخت این‌ها را بررسی کنید</h2>
<ul>{% for c in mg.checks %}<li>{{ c }}</li>{% endfor %}</ul>

<h2>۶. اگر اوضاع بدتر از انتظار شد</h2>
<p>{{ mg.honest_worst }}</p>
<ul>{% for c in mg.bad %}<li>{{ c }}</li>{% endfor %}</ul>

<h2>۷. چه چیزی را باید به یاد داشت؟</h2>
<ul>{% for c in mg.caveats %}<li>{{ c }}</li>{% endfor %}</ul>

<h1 style="margin-top:3rem">ضمیمه‌ی فنی</h1>
<small>این بخش برای متخصص ریسک است؛ برای تصمیم لازم نیست. در جدول‌ها، عدد منفی یعنی زیان؛ واحد «میلیارد ریال» است.</small>
<h2>الف. توضیح تفصیلی تصمیم</h2>
<div class="box"><p><b>{{ a.headline }}</b></p>
{% for e in a.evidence %}<p>{{ e }}</p>{% endfor %}
{% if a.confidence %}<p>درجه‌ی اطمینان فنی: {{ a.confidence.level }}. {{ a.confidence.text }}</p>{% endif %}
<ul>{% for w in a.why %}<li><b>{{ w.title }}:</b> {{ w.text }}</li>{% endfor %}{% for f in a.factors %}<li><b>{{ f.title }}:</b> {{ f.text }}</li>{% endfor %}</ul>
<p><b>بدترین وضعیت بررسی‌شده:</b> {{ a.worst_case.text }} {% if a.worst_case.tradeoff %}{{ a.worst_case.tradeoff }}{% endif %}</p>
{% if a.break_even %}<p><b>آستانه‌ی باور درباره‌ی دلار:</b></p><ul>{% for b in a.break_even %}<li>{{ b.text }}</li>{% endfor %}</ul>{% endif %}
<p><b>برنامه‌ی جایگزین (تفصیلی):</b></p><ul>{% for c in a.contingency %}<li><b>{{ c.title }}:</b> {{ c.text }}</li>{% endfor %}</ul>
<p><b>فرضیات و محدودیت‌ها:</b></p><ul>
<li>قرارداد خرید: نوع تعهد «{{ 'مقدار ثابت' if res.scenario.purchase_mode != 'fixed_usd_budget' else 'مبلغ دلاری ثابت' }}»، پیش‌پرداخت {{ fa(res.scenario.prepay_fraction_pct) }}٪ از فاکتور (باقی هنگام ورود کالا با نرخ همان روز)؛ مانده‌ی پرداخت‌نشده‌ی کالای در راه از ثروت پایان افق کسر می‌شود.</li>
<li>پوشش ریسک ارزی و سیاست تطبیقی در این نسخه نیستند. شوک‌های تنش اندازه‌ی آزمون‌اند، نه احتمال رخداد.</li>
{% for n in a.notes %}<li>{{ n }}</li>{% endfor %}</ul></div>
<small>مدل ارز: {{ fx_name }} · {{ fa(m.n_paths) }} مسیر شبیه‌سازی</small>
<h2>ب. مقایسه‌ی سیاست‌ها</h2>
<table><tr><th>سیاست</th><th>وزن‌ها</th><th>میانگین نتیجه (میلیارد ریال واقعی)</th><th>میانگین بدترین بخش (CVaR)</th><th>احتمال افت نقدینگی</th><th>کمبود</th></tr>
{% for k,v in b.items() %}<tr><td>{{ names.get(k,k) }}</td><td>{{ wtxt(v.weights) }}</td>
<td>{{ fa(v.mean_bn,1) }}</td><td>{{ fa(v.cvar_bn,1) }}</td><td>{{ pct(v.breach,1) }}</td><td>{{ pct(v.unmet,2) }}</td></tr>{% endfor %}</table>
<h2>پ. آزمون‌های تنش (میانگین نتیجه، میلیارد ریال)</h2>
<table><tr><th>سناریو</th><th>توضیح</th><th>توصیه‌شده</th><th>همه امروز</th><th>سه‌قسط مساوی</th></tr>
{% for s in res.stress %}<tr><td>{{ s.label_fa }}</td><td>{{ s.desc_fa }}</td><td>{{ fa(s.policies.recommended.mean_bn,1) }}</td>
<td>{{ fa(s.policies.all_now.mean_bn,1) }}</td><td>{{ fa(s.policies.equal_split.mean_bn,1) }}</td></tr>{% endfor %}</table>
{% if res.reverse %}<h2>ت. تست استرس معکوس</h2>
<p>پرسش: چه ترکیبی از شوک‌ها برنامه را از کار می‌اندازد؟ «شکست» یعنی در دست‌کم {{ pct(res.reverse.fail_prob) }} مسیرها نقدینگی زیر حد ایمن برود یا کمبود از {{ pct(res.reverse.fail_unmet) }} تقاضا بیشتر شود.</p>
<table><tr><th>سیاست</th><th>جهش دلار</th><th>تأخیر تحویل</th></tr>
{% for k in ['recommended','all_now'] %}{% set t = res.reverse.tolerance[k] %}<tr><td>{{ names.get(k,k) }}</td>
<td>{{ tol_text(t.fx,'fx') }}</td><td>{{ tol_text(t.delay_weeks,'delay') }}</td></tr>{% endfor %}</table>{% endif %}
{% if a.attribution_text %}<h2>ث. سهم هر عامل از زیان بحران (شاپلی)</h2><p>{{ a.attribution_text }}</p>{% endif %}
{% if res.accounting %}<h2>ج. آزمون هویت حسابداری</h2><p>تغییر ثروت = سود حسابداری (FIFO) − افت موجودی − زیان محموله‌های تحویل‌نشده + سود/زیان نگهداری (بازارزیابی موجودی). این رابطه روی هر مسیر بررسی می‌شود و باید برقرار باشد.</p>{% endif %}
<h2>چ. اعتبارسنجی مدل‌ها (بک‌تست خارج از نمونه)</h2>
{% if bt.fx %}<p>پیش‌بینی توزیع ۱۳‌هفته‌ای ارز: مدل بدون روند به‌طور معنادار بدتر از مدل‌های دارای روند بود (آزمون دیبولد–ماریانو). سه مدل دارای روند از نظر آماری قابل‌تفکیک نبودند؛ مدل «{{ bt.fx.selected }}» به‌دلیل توصیف بهتر دنباله‌ها انتخاب شد.</p>{% endif %}
{% if bt.replay %}<p>بازپخش تاریخی ({{ fa(bt.replay.n_windows) }} پنجره): خرید یک‌جای زودتر نسبت به سه‌قسط مساوی، پس از کسر هزینه‌ی سرمایه، به‌طور متوسط {{ better(bt.replay.policies.equal_split.deposit.advantage_of_earlier_mean) }} بود
(فاصله اطمینان بوت‌استرپ از {{ pct(bt.replay.policies.equal_split.deposit.ci[0],1,True) }} تا {{ pct(bt.replay.policies.equal_split.deposit.ci[1],1,True) }}).</p>{% endif %}
<h2>ح. راهنمای واژه‌ها</h2><ul>
<li><b>بدترین ۵٪ حالت‌ها (CVaR):</b> میانگین نتیجه در بدترین بخش حالت‌های شبیه‌سازی‌شده؛ نشان می‌دهد وقتی بازار بد می‌شود چه می‌گذرد.</li>
<li><b>جهان ممکن:</b> یک مجموعه فرض متفاوت درباره‌ی پارامترهای نامطمئن (نوسان، کشش تقاضا و غیره).</li>
<li><b>تست استرس معکوس:</b> به‌جای آزمودن یک سناریوی مشخص، می‌پرسد چه اندازه شوک برنامه را از کار می‌اندازد.</li>
<li><b>شاپلی:</b> روشی برای سهم‌دادن زیان کل بین عوامل، به‌طوری که جمع سهم‌ها دقیقاً برابر کل باشد.</li></ul>
</body></html>""")

NAMES = {"recommended": "توصیه‌شده", "all_now": "همه امروز", "equal_split": "سه قسط مساوی", "all_late": "همه دیرتر",
         "unconstrained_best": "بهینه بدون قید", "nominal_best": "بهینه‌ی اسمی"}


def render_report(res: dict, bt: dict) -> str:
    class D(dict):
        __getattr__ = dict.get
    def wrap(x):
        if isinstance(x, dict):
            return D({k: wrap(v) for k, v in x.items()})
        if isinstance(x, list):
            return [wrap(v) for v in x]
        return x
    return TPL.render(res=wrap(res), m=wrap(res["meta"]), a=wrap(res["advice"]), b=res["benchmarks"] and wrap(res["benchmarks"]),
                      bt=wrap(bt), fa=fa, pct=pct, names=NAMES, tol_text=tolerance_text, better=better_worse,
                      mg=wrap(res["advice"]["manager"]), jd=lambda d: jalali_text(d) if d else "—",
                      wtxt=lambda w: " / ".join(f"{fa(round(x * 100))}٪" for x in w),
                      fx_name={"regime": "رژیمی (دو حالت بازار)", "gbm": "حرکت براونی"}.get(res["meta"]["fx_model"], res["meta"]["fx_model"]))
