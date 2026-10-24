import { motion } from "framer-motion";
import { ArrowLeft, FlaskConical, ShieldCheck, Coffee, Flame, Layers, Undo2, Scale, Wallet, Ship, Sparkles, SlidersHorizontal, Cpu, ShieldAlert, BadgeCheck } from "lucide-react";
import FloatingBeans from "../components/FloatingBeans.jsx";
import Bean from "../components/Bean.jsx";
import { Link } from "../lib/router.jsx";

const fade = (d = 0) => ({ initial: { opacity: 0, y: 24 }, animate: { opacity: 1, y: 0 }, transition: { duration: 0.7, delay: d, ease: [0.22, 1, 0.36, 1] } });

const PILLARS = [
  { icon: Flame, title: "مونت‌کارلو رژیم‌محور", text: "قیمت قهوه، دلار، تقاضا و نقدینگی در یک مدل مشترک؛ ارز با رژیم‌های آرام و پرتلاطم و جهش‌های تجربی، نه فقط «نوسان بیشتر از گذشته»." },
  { icon: Layers, title: "سناریوهای تنش", text: "پنج سناریوی مشخص (عادی، جهش ارزی، شوک دوگانه، اختلال واردات، بحران شدید) بدون ادعای احتمال برای جنگ یا قطع تأمین." },
  { icon: Undo2, title: "تست استرس معکوس", text: "به‌جای «در این سناریو چه می‌شود؟» می‌پرسد: چه ترکیبی از شوک‌ها برنامه را از کار می‌اندازد و ضعیف‌ترین آن چیست؟" },
  { icon: Scale, title: "بهینه‌سازی مقاوم", text: "سیاستی که در ده‌ها «جهان ممکن» قابل‌قبول بماند؛ Minimax Regret تنها ملاک نیست، معیار مکمل است." },
];
const FACTS = [
  { icon: Wallet, t: "نقدینگی جدا از سود", d: "شرکت می‌تواند سودده باشد و نقدش تمام شود؛ هر دو جدا سنجیده می‌شوند." },
  { icon: Ship, t: "نرخ ارز قابل‌دسترس و زمان تحویل بحران", d: "دو ورودی کلیدی که هزینه‌ی واقعی واردات را می‌سازند، نه نرخ بازار به‌تنهایی." },
  { icon: ShieldCheck, t: "هر توصیه با دلیل", d: "هر جمله از عددهای محاسبه‌شده ساخته می‌شود؛ بدون متن آزاد و بدون حدس." },
];
const STEPS = [
  { icon: SlidersHorizontal, t: "ورودی شما", d: "بودجه، نرخ قابل‌دسترس ارز، تورم منطقه، زمان تحویل" },
  { icon: Cpu, t: "شبیه‌سازی", d: "هزاران مسیر با اعداد تصادفی مشترک" },
  { icon: ShieldAlert, t: "تنش و تنش معکوس", d: "سناریوها و مرز شکست برنامه" },
  { icon: BadgeCheck, t: "توصیه‌ی قابل دفاع", d: "تصمیم، دلیل، بدترین حالت، آستانه‌ی بازنگری، برنامه‌ی جایگزین" },
];

function Title({ kicker, title }) {
  return (
    <div className="text-center">
      <span className="text-sm font-medium" style={{ color: "var(--accent)" }}>{kicker}</span>
      <h2 className="mt-1 text-3xl font-extrabold sm:text-4xl">{title}</h2>
      <div className="mx-auto mt-4 h-1 w-16 rounded-full" style={{ background: "linear-gradient(90deg,var(--accent2),var(--accent))" }} />
    </div>
  );
}

export default function Landing() {
  return (
    <main>
      <section className="relative isolate overflow-hidden">
        <FloatingBeans />
        <div className="relative mx-auto flex min-h-[78vh] max-w-5xl flex-col items-center justify-center px-6 py-20 text-center">
          <motion.span {...fade(0)} className="glass mb-6 inline-flex items-center gap-2 !rounded-full px-4 py-1.5 text-sm" style={{ color: "var(--accent)" }}>
            <Coffee className="h-4 w-4" /> مدیریت ریسک تأمین قهوه‌ی سبز
          </motion.span>
          <motion.h1 {...fade(0.1)} className="text-4xl font-extrabold leading-[1.4] sm:text-6xl">
            اگر پیش‌بینی غلط درآمد،
            <span className="block bg-clip-text text-transparent" style={{ backgroundImage: "linear-gradient(90deg,var(--accent2),var(--accent),var(--glow))" }}>
              چه تصمیمی هنوز قابل دفاع است؟
            </span>
          </motion.h1>
          <motion.p {...fade(0.22)} className="mt-6 max-w-2xl text-lg leading-8 text-ink2">
            این سیستم قیمت قهوه یا دلار را «پیش‌بینی نمی‌کند و رها می‌کند». هزینه‌ی تأمین، سودآوری و نقدینگی را
            در برابر جهش ارز، اختلال واردات و بحران می‌سنجد و تصمیمی می‌دهد که دلیل دارد، مرز شکستش معلوم است و برنامه‌ی جایگزین دارد.
          </motion.p>
          <motion.div {...fade(0.34)} className="mt-10 flex flex-wrap items-center justify-center gap-4">
            <Link to="/app" className="btn-primary group !px-7 !py-3.5 no-underline">شروع تحلیل ساده <ArrowLeft className="h-5 w-5 transition group-hover:-translate-x-1" /></Link>
            <Link to="/expert" className="btn-ghost glass !px-7 !py-3.5 no-underline"><FlaskConical className="h-5 w-5" style={{ color: "var(--accent)" }} /> نسخه‌ی متخصص</Link>
          </motion.div>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-6 py-20">
        <Title kicker="چهار ستون" title="روش‌ها: کم، دقیق و قابل دفاع" />
        <motion.div initial="hidden" whileInView="show" viewport={{ once: true, margin: "-80px" }} transition={{ staggerChildren: 0.09 }} className="mt-12 grid gap-5 sm:grid-cols-2">
          {PILLARS.map(({ icon: Icon, title, text }) => (
            <motion.article key={title} variants={{ hidden: { opacity: 0, y: 26 }, show: { opacity: 1, y: 0 } }} whileHover={{ y: -5 }}
              className="glass group relative overflow-hidden p-7 transition-shadow hover:shadow-glow">
              <div className="absolute -left-10 -top-10 h-36 w-36 rounded-full opacity-0 blur-3xl transition group-hover:opacity-60" style={{ background: "var(--glow)" }} />
              <div className="relative mb-4 grid h-12 w-12 place-items-center rounded-2xl transition group-hover:scale-110 group-hover:-rotate-6"
                style={{ background: "linear-gradient(135deg,var(--accent),var(--accent2))", color: "var(--accent-ink)" }}><Icon className="h-6 w-6" strokeWidth={1.8} /></div>
              <h3 className="relative text-lg font-bold">{title}</h3>
              <p className="relative mt-2 leading-7 text-ink2">{text}</p>
            </motion.article>
          ))}
        </motion.div>
        <div className="mt-6 grid gap-5 md:grid-cols-3">
          {FACTS.map(({ icon: Icon, t, d }) => (
            <motion.div key={t} initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} className="glass flex gap-3 p-5">
              <Icon className="mt-1 h-6 w-6 shrink-0" style={{ color: "var(--accent)" }} strokeWidth={1.8} />
              <div><b>{t}</b><p className="muted small mt-1">{d}</p></div>
            </motion.div>
          ))}
        </div>
      </section>

      <section className="px-6 pb-20">
        <div className="mx-auto max-w-5xl">
          <Title kicker="از ورودی تا توصیه" title="چهار گام روشن" />
          <div className="relative mt-12 grid gap-8 md:grid-cols-4">
            <div className="absolute right-[12%] top-7 hidden h-px w-[76%] md:block" style={{ background: "linear-gradient(90deg,transparent,var(--accent),transparent)", opacity: 0.5 }} />
            {STEPS.map(({ icon: Icon, t, d }, i) => (
              <motion.div key={t} initial={{ opacity: 0, y: 24 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: i * 0.12, duration: 0.6 }} className="relative text-center">
                <motion.div whileHover={{ scale: 1.12 }} className="glass mx-auto grid h-14 w-14 place-items-center !rounded-full" style={{ color: "var(--accent)" }}><Icon className="h-6 w-6" strokeWidth={1.8} /></motion.div>
                <h3 className="mt-4 font-bold">{t}</h3>
                <p className="muted small mt-1 leading-6">{d}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      <section className="px-6 pb-24">
        <motion.div initial={{ opacity: 0, scale: 0.97 }} whileInView={{ opacity: 1, scale: 1 }} viewport={{ once: true }} transition={{ duration: 0.7 }}
          className="relative mx-auto max-w-5xl overflow-hidden rounded-[2rem] p-10 text-center shadow-soft sm:p-16"
          style={{ background: "linear-gradient(135deg,var(--accent),var(--accent2) 55%,var(--glow))", color: "var(--accent-ink)" }}>
          <Bean className="absolute -left-6 -top-6 h-32 w-32 rotate-12 opacity-30" />
          <Bean className="absolute -bottom-8 right-6 h-40 w-40 -rotate-12 opacity-25" tone="#946a54" />
          <Sparkles className="relative mx-auto h-7 w-7" />
          <h2 className="relative mt-4 text-3xl font-extrabold sm:text-4xl">آماده‌اید سناریوی خودتان را بسنجید؟</h2>
          <p className="relative mx-auto mt-3 max-w-xl opacity-90">اعداد شرکت را وارد کنید؛ تصمیم، دلیل‌ها، مرز شکست و برنامه‌ی جایگزین را یک‌جا ببینید.</p>
          <Link to="/app" className="relative mt-8 inline-flex items-center gap-2 rounded-2xl px-8 py-3.5 font-bold no-underline shadow-glow transition hover:scale-105"
            style={{ background: "var(--surface-solid)", color: "var(--ink)" }}><Coffee className="h-5 w-5" style={{ color: "var(--accent)" }} /> ورود به برنامه</Link>
        </motion.div>
        <p className="muted mt-8 text-center text-xs">دمو مرحله‌ی اول · خروجی‌ها تصمیم‌یار هستند و جایگزین قضاوت مدیریتی نیستند · شوک‌های تنش آزمون تاب‌آوری‌اند، نه پیش‌بینی</p>
      </section>
    </main>
  );
}
