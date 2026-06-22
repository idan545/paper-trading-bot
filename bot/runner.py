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
    return Portfolio(starting_cash=C.STARTING_CASH, base_currency=C.BASE_CURRENCY)


def run_once(verbose: bool = True) -> Portfolio:
    pf = _load_portfolio()
    strat = TrendMomentumStrategy(C.STRATEGY_PARAMS)
    usd_ils = D.usd_ils_rate()

    universe = D.get_universe_history(
        C.UNIVERSE, period=C.HISTORY_PERIOD, interval=C.HISTORY_INTERVAL
    )
    prices_now: dict[str, float] = {}
    fx_map: dict[str, float] = {}

    actions = []
    for sym, df in universe.items():
        if df.empty or len(df) < C.STRATEGY_PARAMS.trend_sma:
            continue
        price = float(df["close"].iloc[-1])
        prices_now[sym] = price
        rate = D.fx_to_usd(sym, usd_ils)
        fx_map[sym] = rate
        cur = D.currency_of(sym)

        sentiment = None
        if C.STRATEGY_PARAMS.use_sentiment:
            sentiment = S.sentiment_for(sym)

        signals = strat.generate_signals(df, sentiment=sentiment)
        sig = int(signals.iloc[-1])

        if sig == 1 and sym not in pf.positions:
            equity = pf.total_value(prices_now, fx_map)
            atr_series = ind.atr(df["high"], df["low"], df["close"])
            a = float(atr_series.iloc[-1])
            a = a if not np.isnan(a) else None
            qty = position_size(equity, price, rate, C.RISK_PARAMS, a)
            if qty > 0 and pf.buy(sym, qty, price, rate, cur):
                stop, target = stop_levels(price, C.RISK_PARAMS, a)
                actions.append(f"BUY  {qty:>5} {sym:<9} @ {price:,.2f} {cur}"
                               f"  (stop {stop:,.2f} / target {target:,.2f})")
        elif sig == -1 and sym in pf.positions:
            qty = pf.positions[sym].quantity
            if pf.sell(sym, qty, price, rate, cur):
                actions.append(f"SELL {qty:>5} {sym:<9} @ {price:,.2f} {cur}")

    pf.save(C.STATE_FILE)

    # ייצוא נתונים לדשבורד (PWA)
    from bot import dashboard as DASH
    DASH.export(
        pf, prices_now, fx_map, usd_ils,
        dashboard_path=C.DASHBOARD_FILE,
        equity_path=C.EQUITY_FILE,
        starting_cash=C.STARTING_CASH,
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
    return pf


def print_status(pf: Portfolio, prices: dict, fx: dict) -> None:
    total = pf.total_value(prices, fx)
    print(f"\n--- מצב התיק ---")
    print(f"מזומן:        {pf.cash:,.0f} {pf.base_currency}")
    if pf.positions:
        print("פוזיציות פתוחות:")
        for sym, pos in pf.positions.items():
            px = prices.get(sym, pos.avg_price)
            pnl = pos.unrealized_pnl(px)
            print(f"  {sym:<9} qty={pos.quantity:>6.0f} "
                  f"avg={pos.avg_price:,.2f} now={px:,.2f} "
                  f"P&L={pnl:+,.2f} {pos.currency}")
    else:
        print("אין פוזיציות פתוחות.")
    print(f"שווי כולל:     {total:,.0f} {pf.base_currency}")
    print(f"סה\"כ עסקאות:   {len(pf.trades)}")


if __name__ == "__main__":
    run_once()
