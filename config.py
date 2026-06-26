"""
הגדרות הבוט: יוניברס הסימבולים, הון התחלתי, ופרמטרים.
ערוך כאן בלי לגעת בלוגיקה.
"""
from bot.strategy import StrategyParams
from bot.risk import RiskParams

# --- יוניברס: ערבוב מניות אמריקאיות ו-TASE (סיומת .TA) ---
UNIVERSE = [
    # ארה"ב
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN",
    # ישראל (TASE)
    "TEVA.TA",   # טבע
    "POLI.TA",   # בנק הפועלים
    "LUMI.TA",   # בנק לאומי
    "NICE.TA",   # נייס
    "ESLT.TA",   # אלביט
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
<<<<<<< HEAD
    trend_sma=50,          # מגמה קצרה יותר (50 במקום 200) = יותר הזדמנויות
=======
    trend_sma=50,
>>>>>>> 88833c748c91e2694443d16913007584bba22ef6
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
