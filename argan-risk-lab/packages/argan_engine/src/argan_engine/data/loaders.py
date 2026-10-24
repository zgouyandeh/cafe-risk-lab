"""Load and clean the raw market files. Every cleaning decision is recorded in a quality report."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

LB_PER_KG = 1.0 / 0.45359237
CENTS_LB_TO_USD_KG = LB_PER_KG / 100.0


def cents_lb_to_usd_kg(c: float | np.ndarray) -> float | np.ndarray:
    return c * CENTS_LB_TO_USD_KG


@dataclass
class QualityReport:
    notes: list[str] = field(default_factory=list)
    stats: dict = field(default_factory=dict)

    def add(self, msg: str) -> None:
        self.notes.append(msg)


def load_fx(path: str | Path) -> tuple[pd.Series, QualityReport]:
    """USD/IRR (rial per USD). Columns: jalali, gregorian date, source, value."""
    q = QualityReport()
    raw = pd.read_excel(path, header=None, names=["jalali", "date", "src", "fx"])
    n0 = len(raw)
    df = raw.dropna(subset=["date", "fx"]).copy()
    if len(df) != n0:
        q.add(f"{n0 - len(df)} ردیف خالی حذف شد")
    df["date"] = pd.to_datetime(df["date"])
    dup = df["date"].duplicated().sum()
    if dup:
        q.add(f"{dup} ردیف تکراری (تاریخ یکسان) حذف شد")
    df = df.drop_duplicates("date").sort_values("date")
    s = df.set_index("date")["fx"].astype(float)
    if (s <= 0).any():
        raise ValueError("non-positive FX values")
    r = np.log(s).diff().dropna()
    big = r[r.abs() > 0.15]
    if len(big):
        q.add(f"{len(big)} جهش روزانه بیش از ۱۵٪ (حفظ شد؛ احتمالاً رویداد واقعی): "
              + ", ".join(f"{d:%Y-%m-%d}:{v:+.0%}" for d, v in big.items()))
    q.stats.update(n=len(s), start=str(s.index[0].date()), end=str(s.index[-1].date()),
                   first=float(s.iloc[0]), last=float(s.iloc[-1]))
    return s, q


def load_coffee(path: str | Path, vol_window: int = 60, vol_frac: float = 0.10
                ) -> tuple[pd.DataFrame, QualityReport]:
    """Arabica front-month continuous futures (USc/lb).

    Days whose volume is below `vol_frac` of the trailing median are flagged illiquid:
    they occur in the delivery/expiry phase of each contract where quotes are stale and
    High/Low/Close are often inconsistent. Illiquid days are excluded from return estimation.
    """
    q = QualityReport()
    df = pd.read_csv(path).iloc[:, :6]
    df["Date"] = pd.to_datetime(df["Date"], format="%m/%d/%Y")
    df = df.set_index("Date").sort_index()
    df = df[~df.index.duplicated()]
    med = df["Volume"].rolling(vol_window, min_periods=20).median()
    df["liquid"] = df["Volume"] >= vol_frac * med
    df.loc[med.isna(), "liquid"] = True
    bad_ohlc = ((df["Close"] > df["High"] + 1e-6) | (df["Close"] < df["Low"] - 1e-6)).sum()
    q.add(f"{int((~df['liquid']).sum())} روز با حجم کمتر از {vol_frac:.0%} میانه‌ی ۶۰ روزه به‌عنوان غیرنقد کنار گذاشته شد "
          f"(انقضا/تحویل قرارداد؛ قیمت‌های کهنه)")
    q.add(f"{int(bad_ohlc)} ردیف با Close خارج از [Low, High] وجود دارد؛ فقط Close استفاده می‌شود")
    last_liq = df.index[df["liquid"]][-1]
    q.stats.update(n=len(df), start=str(df.index[0].date()), end=str(df.index[-1].date()),
                   last_liquid_date=str(last_liq.date()), last_liquid_close=float(df.loc[last_liq, "Close"]),
                   last_raw_date=str(df.index[-1].date()), last_raw_close=float(df["Close"].iloc[-1]))
    if last_liq < df.index[-1] - pd.Timedelta(days=7):
        q.add(f"آخرین قیمت نقدشونده {last_liq:%Y-%m-%d} است؛ ردیف‌های بعدی (تا {df.index[-1]:%Y-%m-%d}) "
              f"حجم نزدیک صفر دارند و نادیده گرفته شدند")
    return df, q


def weekly_returns(s: pd.Series, anchor: str = "W-FRI") -> tuple[pd.Series, pd.Series]:
    """Weekly last observation and log-returns computed ONLY between consecutive weeks
    (a week with no observation breaks the chain instead of creating a 2-week 'weekly' return)."""
    w = s.resample(anchor).last()
    lw = np.log(w)
    r = lw.diff()
    return w, r.dropna()
