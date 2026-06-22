"""
בדיקות ללוגיקה הטהורה (אינדיקטורים, תיק, סיכון, backtest) עם דאטה סינתטי.
הרצה:  python -m tests.test_core   (מתיקיית השורש)
לא דורש רשת או yfinance.
"""
import numpy as np
import pandas as pd

from bot import indicators as ind
from bot.portfolio import Portfolio
from bot.risk import RiskParams, position_size, stop_levels
from bot.strategy import TrendMomentumStrategy, StrategyParams
from bot.backtest import run_backtest


def _synthetic_prices(n=400, seed=1, drift=0.0005, vol=0.015, start=100.0):
    rng = np.random.default_rng(seed)
    rets = rng.normal(drift, vol, n)
    close = start * np.exp(np.cumsum(rets))
    idx = pd.date_range("2022-01-01", periods=n, freq="B")
    df = pd.DataFrame({
        "open": close * (1 - rng.normal(0, 0.002, n)),
        "high": close * (1 + np.abs(rng.normal(0, 0.005, n))),
        "low":  close * (1 - np.abs(rng.normal(0, 0.005, n))),
        "close": close,
        "volume": rng.integers(1_000, 50_000, n),
    }, index=idx)
    return df


def test_indicators():
    df = _synthetic_prices()
    c = df["close"]
    assert ind.sma(c, 10).dropna().shape[0] == len(c) - 9
    rsi = ind.rsi(c, 14).dropna()
    assert (rsi >= 0).all() and (rsi <= 100).all(), "RSI מחוץ לטווח 0-100"
    m = ind.macd(c)
    assert list(m.columns) == ["macd", "signal", "hist"]
    a = ind.atr(df["high"], df["low"], df["close"], 14).dropna()
    assert (a > 0).all(), "ATR חייב להיות חיובי"
    # בדיקת חציות
    fast = ind.ema(c, 5)
    slow = ind.ema(c, 20)
    cu = ind.crossed_above(fast, slow)
    cd = ind.crossed_below(fast, slow)
    assert not (cu & cd).any(), "אי אפשר לחצות מעלה ומטה באותו נר"
    print("  ✓ indicators")


def test_portfolio_basic():
    pf = Portfolio(starting_cash=10_000, commission_rate=0.001, min_commission=1.0)
    assert pf.buy("AAPL", 10, 100.0)          # עלות 1000 + עמלה
    assert pf.cash < 9_000
    assert pf.positions["AAPL"].quantity == 10
    # מכירה ברווח
    assert pf.sell("AAPL", 10, 120.0)
    assert "AAPL" not in pf.positions
    assert pf.cash > 10_000, "מכירה ברווח צריכה להגדיל מזומן מעל ההתחלה"
    print("  ✓ portfolio buy/sell")


def test_portfolio_insufficient_cash():
    pf = Portfolio(starting_cash=500)
    assert not pf.buy("MSFT", 10, 100.0), "לא אמור לאפשר קנייה ללא מזומן"
    assert pf.cash == 500
    print("  ✓ portfolio rejects over-spend")


def test_portfolio_multicurrency():
    # מניה ישראלית: מחיר 30 ILS, שער 1 USD = 3.7 ILS => fx=1/3.7
    pf = Portfolio(starting_cash=10_000, base_currency="USD")
    fx = 1 / 3.7
    assert pf.buy("TEVA.TA", 100, 30.0, fx_to_base=fx, currency="ILS")
    # שווי במטבע בסיס ≈ 100*30/3.7 ≈ 810.8 (פחות עמלה)
    val = pf.total_value({"TEVA.TA": 30.0}, {"TEVA.TA": fx})
    assert 9_900 < val < 10_050, f"שווי לא הגיוני: {val}"
    print("  ✓ portfolio multi-currency")


def test_portfolio_save_load(tmp="/tmp/_pf_test.json"):
    pf = Portfolio(starting_cash=5_000)
    pf.buy("NVDA", 5, 200.0)
    pf.save(tmp)
    pf2 = Portfolio.load(tmp)
    assert pf2.cash == pf.cash
    assert pf2.positions["NVDA"].quantity == 5
    assert len(pf2.trades) == 1
    print("  ✓ portfolio save/load")


def test_risk_sizing():
    rp = RiskParams(risk_per_trade=0.01, stop_loss_pct=0.10, max_position_pct=0.25)
    # הון 100k, מחיר 50, סטופ 10% => מרחק 5 => סיכון 1000/5 = 200 מניות
    qty = position_size(100_000, 50.0, 1.0, rp)
    assert qty == 200, f"ציפיתי 200, קיבלתי {qty}"
    # בדיקת תקרת גודל פוזיציה: 25% מ-100k = 25k / 50 = 500 מניות מקס
    rp2 = RiskParams(risk_per_trade=0.50, stop_loss_pct=0.10, max_position_pct=0.25)
    qty2 = position_size(100_000, 50.0, 1.0, rp2)
    assert qty2 == 500, f"תקרת פוזיציה לא נאכפה: {qty2}"
    stop, target = stop_levels(50.0, rp)
    assert stop == 45.0 and abs(target - 58.0) < 1e-9
    print("  ✓ risk sizing & stops")


def test_backtest_runs():
    # שני נכסים עם מגמות שונות
    data = {
        "UP": _synthetic_prices(seed=2, drift=0.0015),
        "FLAT": _synthetic_prices(seed=7, drift=0.0),
    }
    strat = TrendMomentumStrategy(StrategyParams(trend_sma=100))
    res = run_backtest(data, strat, starting_cash=100_000)
    assert len(res.equity_curve) > 0
    assert res.metrics["final_value"] > 0
    assert -1.0 <= res.metrics["max_drawdown"] <= 0.0
    assert 0.0 <= res.metrics["win_rate"] <= 1.0
    print(f"  ✓ backtest runs (trades={res.metrics['num_trades']}, "
          f"return={res.metrics['total_return']:+.1%}, "
          f"maxDD={res.metrics['max_drawdown']:.1%})")


def main():
    print("Running core tests (synthetic data, no network):")
    test_indicators()
    test_portfolio_basic()
    test_portfolio_insufficient_cash()
    test_portfolio_multicurrency()
    test_portfolio_save_load()
    test_risk_sizing()
    test_backtest_runs()
    print("\nכל הבדיקות עברו ✓")


if __name__ == "__main__":
    main()
