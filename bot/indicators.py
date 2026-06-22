"""
אינדיקטורים טכניים - פונקציות טהורות שמקבלות סדרת מחירים (pandas Series)
ומחזירות סדרה/DataFrame. אין כאן תלות ברשת או בברוקר, כך שאפשר לבדוק הכל
בקלות עם דאטה סינתטי.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def sma(prices: pd.Series, window: int) -> pd.Series:
    """ממוצע נע פשוט."""
    return prices.rolling(window=window, min_periods=window).mean()


def ema(prices: pd.Series, window: int) -> pd.Series:
    """ממוצע נע מעריכי."""
    return prices.ewm(span=window, adjust=False).mean()


def rsi(prices: pd.Series, window: int = 14) -> pd.Series:
    """
    Relative Strength Index לפי שיטת Wilder.
    ערך בין 0 ל-100. מתחת ל-30 = oversold, מעל 70 = overbought.
    """
    delta = prices.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)

    # Wilder smoothing == EMA עם alpha = 1/window
    avg_gain = gain.ewm(alpha=1 / window, min_periods=window, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / window, min_periods=window, adjust=False).mean()

    rs = avg_gain / avg_loss
    out = 100.0 - (100.0 / (1.0 + rs))
    # כשאין הפסדים בכלל ה-RS שואף לאינסוף וה-RSI ל-100
    out = out.where(avg_loss != 0, 100.0)
    return out


def macd(
    prices: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> pd.DataFrame:
    """
    MACD: ההפרש בין EMA מהיר ל-EMA איטי, קו סיגנל (EMA של ה-MACD),
    והיסטוגרמה (ההפרש ביניהם).
    """
    macd_line = ema(prices, fast) - ema(prices, slow)
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    hist = macd_line - signal_line
    return pd.DataFrame(
        {"macd": macd_line, "signal": signal_line, "hist": hist}
    )


def atr(high: pd.Series, low: pd.Series, close: pd.Series, window: int = 14) -> pd.Series:
    """
    Average True Range - מדד תנודתיות. שימושי לחישוב מרחק stop-loss דינמי.
    """
    prev_close = close.shift(1)
    tr = pd.concat(
        [
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1 / window, min_periods=window, adjust=False).mean()


def crossed_above(series_a: pd.Series, series_b: pd.Series) -> pd.Series:
    """True בנקודות שבהן series_a חתכה את series_b כלפי מעלה."""
    a, b = series_a, series_b
    return (a > b) & (a.shift(1) <= b.shift(1))


def crossed_below(series_a: pd.Series, series_b: pd.Series) -> pd.Series:
    """True בנקודות שבהן series_a חתכה את series_b כלפי מטה."""
    a, b = series_a, series_b
    return (a < b) & (a.shift(1) >= b.shift(1))
