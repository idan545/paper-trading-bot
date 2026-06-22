"""
שכבת נתונים: שליפת מחירים היסטוריים ובזמן אמת דרך yfinance.
מטפלת בשתי הבורסות (NASDAQ/NYSE ו-TASE) ובהמרת מטבע.

נקודות חשובות לגבי TASE ב-Yahoo Finance:
  - סימבול ישראלי מסתיים ב-".TA"  (למשל "TEVA.TA", "POLI.TA").
  - מחירים מצוטטים לרוב באגורות (ILA) = 1/100 ש"ח. הפונקציה כאן ממירה
    אוטומטית לשקלים אם זוהה מטבע ILA.
  - שער חליפין ILS->USD נשלף מהסימבול "ILS=X".

אם yfinance לא מותקן עדיין:  pip install yfinance
"""
from __future__ import annotations

import pandas as pd

try:
    import yfinance as yf
except ImportError:  # מאפשר import של המודול גם בלי yfinance (לבדיקות)
    yf = None


def _require_yf():
    if yf is None:
        raise RuntimeError(
            "yfinance לא מותקן. הרץ:  pip install yfinance"
        )


def is_tase(symbol: str) -> bool:
    return symbol.upper().endswith(".TA")


def get_history(
    symbol: str, period: str = "2y", interval: str = "1d"
) -> pd.DataFrame:
    """
    מחזיר DataFrame עם עמודות open/high/low/close/volume (אותיות קטנות),
    אינדקס תאריכים. ממיר אגורות->שקלים עבור TASE במידת הצורך.
    """
    _require_yf()
    tk = yf.Ticker(symbol)
    df = tk.history(period=period, interval=interval, auto_adjust=True)
    if df.empty:
        return pd.DataFrame()

    df = df.rename(columns=str.lower)[["open", "high", "low", "close", "volume"]]

    # המרת אגורות -> שקלים אם נדרש
    if is_tase(symbol):
        cur = (tk.fast_info.get("currency") if hasattr(tk, "fast_info") else None) or ""
        if str(cur).upper() in ("ILA", "AGOROT"):
            for c in ("open", "high", "low", "close"):
                df[c] = df[c] / 100.0
    df.index = pd.DatetimeIndex(df.index).tz_localize(None)
    return df


def get_universe_history(
    symbols: list[str], period: str = "2y", interval: str = "1d"
) -> dict[str, pd.DataFrame]:
    out = {}
    for s in symbols:
        try:
            df = get_history(s, period, interval)
            if not df.empty:
                out[s] = df
        except Exception as e:  # noqa: BLE001
            print(f"[warn] failed to fetch {s}: {e}")
    return out


def latest_price(symbol: str) -> float | None:
    _require_yf()
    df = get_history(symbol, period="5d", interval="1d")
    if df.empty:
        return None
    return float(df["close"].iloc[-1])


def usd_ils_rate() -> float:
    """כמה ILS בדולר אחד (למשל ~3.7). מחזיר 1.0 אם נכשל."""
    _require_yf()
    try:
        df = yf.Ticker("ILS=X").history(period="5d")
        if not df.empty:
            return float(df["Close"].iloc[-1])
    except Exception:  # noqa: BLE001
        pass
    return 1.0


def fx_to_usd(symbol: str, usd_ils: float) -> float:
    """שער המרה ממטבע הסימבול ל-USD. TASE בשקלים -> חלוקה בשער."""
    if is_tase(symbol):
        return 1.0 / usd_ils if usd_ils else 1.0
    return 1.0


def currency_of(symbol: str) -> str:
    return "ILS" if is_tase(symbol) else "USD"
