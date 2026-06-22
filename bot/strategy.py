"""
מנוע אסטרטגיה. כל אסטרטגיה מקבלת DataFrame של נרות (OHLCV) ומחזירה
סדרת איתותים: 1 = קנייה, -1 = מכירה, 0 = החזקה.

האסטרטגיה כאן (TrendMomentum) משלבת מגמה + מומנטום + אופציונלית סנטימנט:
  - מסנן מגמה: מחיר מעל SMA ארוך => מותר ללונג בלבד.
  - כניסה: חציית MACD מעל קו הסיגנל כש-RSI לא בקנייתֿ-יתר.
  - יציאה: חציית MACD מתחת לסיגנל, או RSI בקנייתֿ-יתר קיצונית.

זה *לא* גביע קדוש - זו אסטרטגיה סבירה להתחיל ממנה ולבדוק ב-backtest.
שנה/החלף אותה בקלות ע"י יצירת מחלקה חדשה שיורשת מ-Strategy.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from . import indicators as ind


@dataclass
class StrategyParams:
    rsi_window: int = 14
    rsi_overbought: float = 75.0
    rsi_oversold: float = 30.0
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    trend_sma: int = 200          # מסנן מגמה ארוך-טווח
    use_sentiment: bool = False   # האם לשלב ציון סנטימנט מחדשות
    sentiment_min: float = -0.2   # מתחת לזה - לא נכנסים ללונג


class Strategy:
    """ממשק בסיס. ממש generate_signals."""

    name = "base"

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        raise NotImplementedError


class TrendMomentumStrategy(Strategy):
    name = "trend_momentum"

    def __init__(self, params: StrategyParams | None = None):
        self.p = params or StrategyParams()

    def generate_signals(
        self, df: pd.DataFrame, sentiment: float | None = None
    ) -> pd.Series:
        """
        df חייב להכיל עמודת 'close' (ו'high'/'low' אם רוצים ATR).
        sentiment - ציון אופציונלי ב-[-1, 1] לכל הסדרה (סקלר אחרון).
        """
        close = df["close"]
        p = self.p

        rsi = ind.rsi(close, p.rsi_window)
        macd_df = ind.macd(close, p.macd_fast, p.macd_slow, p.macd_signal)
        trend = ind.sma(close, p.trend_sma)

        macd_up = ind.crossed_above(macd_df["macd"], macd_df["signal"])
        macd_down = ind.crossed_below(macd_df["macd"], macd_df["signal"])

        uptrend = close > trend
        not_overbought = rsi < p.rsi_overbought

        buy = macd_up & uptrend & not_overbought
        sell = macd_down | (rsi > p.rsi_overbought)

        # מסנן סנטימנט (אופציונלי): אם הסנטימנט שלילי מדי - מבטלים קניות
        if p.use_sentiment and sentiment is not None and sentiment < p.sentiment_min:
            buy = buy & False

        signals = pd.Series(0, index=df.index, dtype=int)
        signals[buy] = 1
        signals[sell] = -1
        return signals
