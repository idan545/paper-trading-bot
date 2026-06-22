"""
Backtester: מריץ אסטרטגיה על נתונים היסטוריים ומדמה את התיק נר-אחר-נר.
מטפל בכניסות לפי איתותים, יציאות לפי איתותים/סטופ/יעד, ומחשב מדדי ביצוע.

הערה: זה backtester פשוט ומדויק מספיק ללמידה והשוואת אסטרטגיות. הוא
*לא* מדמה החלקה (slippage), פערי פתיחה, או נזילות. אל תתייחס לתוצאות
כהבטחה - תמיד יש פער בין backtest למציאות.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .portfolio import Portfolio
from .risk import RiskParams, position_size, stop_levels
from .strategy import Strategy
from . import indicators as ind


@dataclass
class BacktestResult:
    equity_curve: pd.Series
    trades: list
    metrics: dict

    def summary(self) -> str:
        m = self.metrics
        lines = [
            "=" * 44,
            f"  תשואה כוללת:      {m['total_return']:+.1%}",
            f"  CAGR:             {m['cagr']:+.1%}",
            f"  Max Drawdown:     {m['max_drawdown']:.1%}",
            f"  Sharpe (שנתי):    {m['sharpe']:.2f}",
            f"  מס' עסקאות:        {m['num_trades']}",
            f"  אחוז הצלחה:        {m['win_rate']:.0%}",
            f"  שווי סופי:         {m['final_value']:,.0f} {m['currency']}",
            "=" * 44,
        ]
        return "\n".join(lines)


def _metrics(equity: pd.Series, trades: list, base_currency: str) -> dict:
    if len(equity) < 2:
        return {
            "total_return": 0.0, "cagr": 0.0, "max_drawdown": 0.0,
            "sharpe": 0.0, "num_trades": len(trades), "win_rate": 0.0,
            "final_value": float(equity.iloc[-1]) if len(equity) else 0.0,
            "currency": base_currency,
        }
    start, end = equity.iloc[0], equity.iloc[-1]
    total_return = end / start - 1.0

    days = max((equity.index[-1] - equity.index[0]).days, 1)
    years = days / 365.25
    cagr = (end / start) ** (1 / years) - 1.0 if years > 0 and start > 0 else 0.0

    roll_max = equity.cummax()
    drawdown = equity / roll_max - 1.0
    max_dd = drawdown.min()

    rets = equity.pct_change().dropna()
    sharpe = 0.0
    if rets.std() > 0:
        sharpe = np.sqrt(252) * rets.mean() / rets.std()

    # אחוז הצלחה לפי עסקאות מכירה רווחיות (קירוב: זוגות buy/sell per symbol)
    wins, total_closed = _win_rate(trades)

    return {
        "total_return": float(total_return),
        "cagr": float(cagr),
        "max_drawdown": float(max_dd),
        "sharpe": float(sharpe),
        "num_trades": len(trades),
        "win_rate": (wins / total_closed) if total_closed else 0.0,
        "final_value": float(end),
        "currency": base_currency,
    }


def _win_rate(trades: list) -> tuple[int, int]:
    """מחשב אחוז עסקאות סגורות רווחיות בשיטת ממוצע נע (FIFO פשוט)."""
    from collections import defaultdict, deque
    lots = defaultdict(deque)   # symbol -> deque of (qty, price)
    wins = closed = 0
    for t in trades:
        if t.side == "BUY":
            lots[t.symbol].append([t.quantity, t.price])
        else:
            qty = t.quantity
            while qty > 1e-9 and lots[t.symbol]:
                lot = lots[t.symbol][0]
                used = min(qty, lot[0])
                pnl = (t.price - lot[1]) * used
                closed += 1
                if pnl > 0:
                    wins += 1
                lot[0] -= used
                qty -= used
                if lot[0] <= 1e-9:
                    lots[t.symbol].popleft()
    return wins, closed


def run_backtest(
    data: dict[str, pd.DataFrame],
    strategy: Strategy,
    starting_cash: float = 100_000.0,
    base_currency: str = "USD",
    risk: RiskParams | None = None,
    fx: dict[str, float] | None = None,
    currencies: dict[str, str] | None = None,
) -> BacktestResult:
    """
    data: סימבול -> DataFrame עם עמודות open/high/low/close (אינדקס תאריכים).
    fx: סימבול -> שער המרה קבוע למטבע בסיס (קירוב; אפשר להעביר 1.0 לכולם).
    currencies: סימבול -> מטבע מקומי.
    """
    risk = risk or RiskParams()
    fx = fx or {}
    currencies = currencies or {}
    pf = Portfolio(starting_cash=starting_cash, base_currency=base_currency)

    # חישוב מראש של איתותים ו-ATR לכל סימבול
    sig: dict[str, pd.Series] = {}
    atr_s: dict[str, pd.Series] = {}
    for sym, df in data.items():
        sig[sym] = strategy.generate_signals(df)
        if {"high", "low", "close"}.issubset(df.columns):
            atr_s[sym] = ind.atr(df["high"], df["low"], df["close"])

    # אינדקס תאריכים מאוחד
    all_dates = sorted(set().union(*[df.index for df in data.values()]))
    open_stops: dict[str, tuple[float, float]] = {}  # symbol -> (stop, target)

    equity_points = []
    for date in all_dates:
        prices_today = {}
        for sym, df in data.items():
            if date not in df.index:
                continue
            row = df.loc[date]
            price = float(row["close"])
            prices_today[sym] = price
            rate = fx.get(sym, 1.0)
            cur = currencies.get(sym, base_currency)

            # 1) בדיקת סטופ/יעד על פוזיציה פתוחה
            if sym in pf.positions and sym in open_stops:
                stop, target = open_stops[sym]
                low = float(row.get("low", price))
                high = float(row.get("high", price))
                if low <= stop:
                    pf.sell(sym, pf.positions[sym].quantity, stop, rate, cur, str(date))
                    open_stops.pop(sym, None)
                    continue
                if high >= target:
                    pf.sell(sym, pf.positions[sym].quantity, target, rate, cur, str(date))
                    open_stops.pop(sym, None)
                    continue

            # 2) איתות
            s = int(sig[sym].get(date, 0)) if date in sig[sym].index else 0
            if s == 1 and sym not in pf.positions:
                equity = pf.total_value(prices_today, fx)
                a = float(atr_s[sym].get(date, np.nan)) if sym in atr_s else None
                a = a if (a is not None and not np.isnan(a)) else None
                qty = position_size(equity, price, rate, risk, a)
                if qty > 0 and pf.buy(sym, qty, price, rate, cur, str(date)):
                    open_stops[sym] = stop_levels(price, risk, a)
            elif s == -1 and sym in pf.positions:
                pf.sell(sym, pf.positions[sym].quantity, price, rate, cur, str(date))
                open_stops.pop(sym, None)

        equity_points.append((date, pf.total_value(prices_today, fx)))

    equity_curve = pd.Series(
        [v for _, v in equity_points],
        index=pd.DatetimeIndex([d for d, _ in equity_points]),
        name="equity",
    )
    metrics = _metrics(equity_curve, pf.trades, base_currency)
    return BacktestResult(equity_curve=equity_curve, trades=pf.trades, metrics=metrics)
