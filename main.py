"""
נקודת כניסה. שימוש:
    python main.py run        # הרצת paper-trading אחת (שומר מצב)
    python main.py backtest   # בדיקה היסטורית של האסטרטגיה
    python main.py status     # הצגת מצב התיק הנוכחי
    python main.py reset      # איפוס התיק
"""
import os
import sys

import config as C


def cmd_run():
    from bot.runner import run_once
    run_once()


def cmd_backtest():
    from bot import data as D
    from bot.backtest import run_backtest
    from bot.strategy import TrendMomentumStrategy

    print("שולף נתונים היסטוריים...")
    universe = D.get_universe_history(
        C.UNIVERSE, period=C.HISTORY_PERIOD, interval=C.HISTORY_INTERVAL
    )
    if not universe:
        print("לא נשלפו נתונים. בדוק חיבור אינטרנט ושהסימבולים תקינים.")
        return

    usd_ils = D.usd_ils_rate()
    fx = {s: D.fx_to_usd(s, usd_ils) for s in universe}
    currencies = {s: D.currency_of(s) for s in universe}

    strat = TrendMomentumStrategy(C.STRATEGY_PARAMS)
    result = run_backtest(
        universe, strat,
        starting_cash=C.STARTING_CASH,
        base_currency=C.BASE_CURRENCY,
        risk=C.RISK_PARAMS,
        fx=fx, currencies=currencies,
    )
    print("\n" + result.summary())


def cmd_status():
    from bot.portfolio import Portfolio
    if not os.path.exists(C.STATE_FILE):
        print("אין עדיין מצב תיק. הרץ:  python main.py run")
        return
    pf = Portfolio.load(C.STATE_FILE)
    prices = {s: p.avg_price for s, p in pf.positions.items()}
    print(f"מזומן: {pf.cash:,.0f} {pf.base_currency}")
    for sym, pos in pf.positions.items():
        print(f"  {sym:<9} qty={pos.quantity:.0f} avg={pos.avg_price:,.2f} {pos.currency}")
    print(f"עסקאות: {len(pf.trades)}")


def cmd_reset():
    if os.path.exists(C.STATE_FILE):
        os.remove(C.STATE_FILE)
        print("התיק אופס.")
    else:
        print("אין מה לאפס.")


COMMANDS = {
    "run": cmd_run,
    "backtest": cmd_backtest,
    "status": cmd_status,
    "reset": cmd_reset,
}

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"
    fn = COMMANDS.get(cmd)
    if not fn:
        print(__doc__)
        sys.exit(1)
    fn()
