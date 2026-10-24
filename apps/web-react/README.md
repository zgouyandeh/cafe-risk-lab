# apps/web-react — صفحه‌ی معرفی (React + Tailwind + Framer Motion + Lucide)

    cd apps/web-react
    npm install
    npm run dev        # http://localhost:5173  (دکمه‌ها به / و /expert سرور FastAPI می‌روند)

برای دیدن لینک‌ها، سرور را هم اجرا کنید: `python -m uvicorn argan_api.main:app --app-dir apps/api --port 8000`
(در حالت dev، لینک‌های `/` و `/expert` را روی پورت 8000 باز کنید یا پروکسی را در `vite.config.js` گسترش دهید.)

اجزا: `Hero`، `FloatingBeans` (پارالاکس + شناور)، `Features`، `Pipeline`، `Cta`، `Bean` (SVG).
رنگ‌ها در `tailwind.config.js` (espresso / mocha / cream / gold).
