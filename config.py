"""
הגדרות הבוט: יוניברס הסימבולים, הון התחלתי, ופרמטרים.
ערוך כאן בלי לגעת בלוגיקה.
"""
from bot.strategy import StrategyParams
from bot.risk import RiskParams

# --- יוניברס: מניות אמריקאיות + חברות ישראליות ברישום אמריקאי (USD) ---
# כולן נסחרות בארה"ב ונמשכות אמין ב-yfinance (בלי סיבוכי אגורות/ת"א).
UNIVERSE = [
    # ארה"ב - טכנולוגיה גדולה
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "AMD", "AVGO",
    # ארה"ב - מגוון
    "JPM", "V", "WMT", "COST", "NFLX",
    # חברות ישראליות (רישום אמריקאי)
    "TEVA",   # טבע
    "NICE",   # נייס
    "ESLT",   # אלביט מערכות
    "MNDY",   # monday.com
    "CYBR",   # סייברארק
    "WIX",    # Wix
]

BASE_CURRENCY = "USD"
STARTING_CASH = 100_000.0

# נתונים
HISTORY_PERIOD = "2y"
HISTORY_INTERVAL = "1d"

# קובץ מצב התיק ל-paper trading
STATE_FILE = "portfolio_state.json"

# קבצי פלט לדשבורד (ה-PWA). dashboard.json נכתב לתוך webapp/ כדי
# שייקרא מאותו origin בלי CORS.
DASHBOARD_FILE = "docs/dashboard.json"
EQUITY_FILE = "equity_history.json"

STRATEGY_PARAMS = StrategyParams(
    rsi_window=14,
    rsi_overbought=75.0,
    rsi_oversold=30.0,
    trend_sma=50,          # מגמה קצרה יותר (50 במקום 200) = יותר הזדמנויות
    use_sentiment=False,   # הפעל True כדי לסנן קניות לפי סנטימנט חדשות
    sentiment_min=-0.2,
)

RISK_PARAMS = RiskParams(
    risk_per_trade=0.01,    # 1% מההון לכל עסקה
    stop_loss_pct=0.08,
    take_profit_pct=0.16,
    max_position_pct=0.20,
    atr_stop_mult=2.5,
)