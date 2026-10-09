"""
לולאת paper-trading חיה. כל הרצה:
  1. שולפת נתונים עדכניים לכל היוניברס.
  2. מחשבת איתות לנר האחרון של כל סימבול.
  3. (אופציונלי) משקללת סנטימנט חדשות.
  4. מבצעת קנייה/מכירה בתיק הסימולציה.
  5. שומרת את מצב התיק לקובץ JSON ומדפיסה סיכום.

מתוכנן לרוץ כ-cron יומי (אחרי סגירת מסחר) או ידנית. המצב נשמר בין הרצות.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

import numpy as np

import config as C
from bot import data as D
from bot import sentiment as S
from bot import indicators as ind
from bot.portfolio import Portfolio
from bot.risk import position_size, stop_levels
from bot.strategy import TrendMomentumStrategy


def _load_portfolio() -> Portfolio:
    if os.path.exists(C.STATE_FILE):
        return Portfolio.load(C.STATE_FILE)
    return Portfolio(
        starting_cash=C.STARTING_CASH,
        base_currency=C.BASE_CURRENCY,
        commission_rate=getattr(C, "COMMISSION_RATE", 0.0008),
        min_commission=getattr(C, "MIN_COMMISSION", 1.0),
    )


def run_once(verbose: bool = True) -> Portfolio:
    pf = _load_portfolio()
    strat = TrendMomentumStrategy(C.STRATEGY_PARAMS)
    usd_ils = D.usd_ils_rate()

    universe = D.get_universe_history(
        C.UNIVERSE, period=C.HISTORY_PERIOD, interval=C.HISTORY_INTERVAL
    )
    prices_now: dict[str, float] = {}
    fx_map: dict[str, float] = {}

    slip = getattr(C, "SLIPPAGE_PCT", 0.0)
    actions = []
    for sym, df in universe.items():
        if df.empty or len(df) < C.STRATEGY_PARAMS.trend_sma:
            continue
        # yfinance מחזיר לפעמים מחיר סגירה ריק (NaN) לנר האחרון.
        # משתמשים במחיר התקין האחרון, ומדלגים אם אין כזה.
        valid_close = df["close"].dropna()
        if valid_close.empty:
            continue
        price = float(valid_close.iloc[-1])
        if not np.isfinite(price) or price <= 0:
            continue
        prices_now[sym] = price
        rate = D.fx_to_usd(sym, usd_ils)
        fx_map[sym] = rate
        cur = D.currency_of(sym)

        sentiment = None
        if C.STRATEGY_PARAMS.use_sentiment:
            sentiment = S.sentiment_for(sym)

        # 1) stop-loss / take-profit על פוזיציה פתוחה, לפי טווח המסחר של היום.
        #    מדמה פקודת stop שיושבת אצל הברוקר: אם המחיר נגע ברמה - נמכר.
        #    אם המניה נפתחה כבר מעבר לרמה (gap), המכירה במחיר הפתיחה.
        if sym in pf.positions:
            pos = pf.positions[sym]
            if pos.stop <= 0 or pos.target <= 0:
                pos.stop, pos.target = stop_levels(pos.avg_price, C.RISK_PARAMS, None)
            last = df.iloc[-1]
            day_low = float(last["low"]) if np.isfinite(last["low"]) else price
            day_high = float(last["high"]) if np.isfinite(last["high"]) else price
            day_open = float(last["open"]) if np.isfinite(last["open"]) else price
            exit_px, reason = None, ""
            if day_low <= pos.stop:
                exit_px, reason = min(pos.stop, day_open), "STOP"
            elif day_high >= pos.target:
                exit_px, reason = max(pos.target, day_open), "TARGET"
            if exit_px is not None:
                fill = exit_px * (1 - slip)
                qty = pos.quantity
                if pf.sell(sym, qty, fill, rate, cur):
                    actions.append(f"{reason:<6} {qty:>8.4f} {sym:<6} @ {fill:,.2f} {cur}")
                continue

        signals = strat.generate_signals(df, sentiment=sentiment)
        sig = int(signals.iloc[-1])

        # 2) איתותים. כל ביצוע כולל החלקה (slippage): קונים מעט מעל המחיר,
        #    מוכרים מעט מתחתיו - כמו בשוק אמיתי עם מרווח קנייה/מכירה.
        if sig == 1 and sym not in pf.positions:
            fill = price * (1 + slip)
            equity = pf.total_value(prices_now, fx_map)
            atr_series = ind.atr(df["high"], df["low"], df["close"])
            a = float(atr_series.iloc[-1])
            a = a if not np.isnan(a) else None
            qty = position_size(equity, fill, rate, C.RISK_PARAMS, a,
                                fractional=getattr(C, "FRACTIONAL_SHARES", False))
            if qty > 0 and pf.buy(sym, qty, fill, rate, cur):
                stop, target = stop_levels(fill, C.RISK_PARAMS, a)
                pf.positions[sym].stop = stop
                pf.positions[sym].target = target
                actions.append(f"BUY    {qty:>8.4f} {sym:<6} @ {fill:,.2f} {cur}"
                               f"  (stop {stop:,.2f} / target {target:,.2f})")
        elif sig == -1 and sym in pf.positions:
            fill = price * (1 - slip)
            qty = pf.positions[sym].quantity
            if pf.sell(sym, qty, fill, rate, cur):
                actions.append(f"SELL   {qty:>8.4f} {sym:<6} @ {fill:,.2f} {cur}")

    benchmark = _update_benchmark(pf)
    pf.save(C.STATE_FILE)

    # ייצוא נתונים לדשבורד (PWA)
    from bot import dashboard as DASH
    DASH.export(
        pf, prices_now, fx_map, usd_ils,
        dashboard_path=C.DASHBOARD_FILE,
        equity_path=C.EQUITY_FILE,
        starting_cash=C.STARTING_CASH,
        benchmark=benchmark,
    )

    if verbose:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        print(f"\n=== Paper-trading run @ {ts} ===")
        print(f"USD/ILS: {usd_ils:.3f}")
        if actions:
            print("\nפעולות:")
            for a in actions:
                print("  " + a)
        else:
            print("\nאין פעולות חדשות בהרצה זו.")
        print_status(pf, prices_now, fx_map)
        if benchmark:
            print(f"השוואה: {benchmark['symbol']} באותו סכום = "
                  f"{benchmark['value']:,.2f} USD ({benchmark['change_pct']:+.2%})")
    return pf


def _update_benchmark(pf: Portfolio) -> dict | None:
    """
    מדד השוואה: כמה היה שווה אותו הון התחלתי אילו נקנה ב-S&P 500 (SPY)
    ביום שהתיק התחיל, והוחזק בלי לגעת. נשמר בתיק כדי שנקודת ההתחלה תישאר
    קבועה בין הרצות.
    """
    symbol = getattr(C, "BENCHMARK", None)
    if not symbol:
        return None
    try:
        bdf = D.get_history(symbol, period="5d", interval="1d")
        closes = bdf["close"].dropna()
        if closes.empty:
            return None
        px = float(closes.iloc[-1])
    except Exception as e:  # noqa: BLE001
        print(f"[warn] benchmark {symbol} failed: {e}")
        return None
    if not np.isfinite(px) or px <= 0:
        return None
    b = pf.meta.get("benchmark")
    if not b or b.get("symbol") != symbol:
        b = {
            "symbol": symbol,
            "start_price": px,
            "start_value": C.STARTING_CASH,
            "start_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        }
        pf.meta["benchmark"] = b
    value = b["start_value"] * px / b["start_price"]
    return {
        "symbol": symbol,
        "value": round(value, 2),
        "change_pct": round(value / b["start_value"] - 1.0, 4),
        "start_date": b["start_date"],
    }


def print_status(pf: Portfolio, prices: dict, fx: dict) -> None:
    total = pf.total_value(prices, fx)
    print(f"\n--- מצב התיק ---")
    print(f"מזומן:        {pf.cash:,.2f} {pf.base_currency}")
    if pf.positions:
        print("פוזיציות פתוחות:")
        for sym, pos in pf.positions.items():
            px = prices.get(sym, pos.avg_price)
            pnl = pos.unrealized_pnl(px)
            print(f"  {sym:<9} qty={pos.quantity:>10.4f} "
                  f"avg={pos.avg_price:,.2f} now={px:,.2f} "
                  f"P&L={pnl:+,.2f} {pos.currency}")
    else:
        print("אין פוזיציות פתוחות.")
    print(f"שווי כולל:     {total:,.2f} {pf.base_currency}")
    print(f"סה\"כ עסקאות:   {len(pf.trades)}")


if __name__ == "__main__":
    run_once()
