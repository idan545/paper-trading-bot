"""
מודול סנטימנט - "סקרי שוק" וחדשות. מפיק ציון ב-[-1, 1] לכל סימבול.

יש כאן שתי רמות:
  1) scorer מילוני (lexicon) פשוט שעובד מיד בלי תלות חיצונית - טוב
     להתחלה ולבדיקות.
  2) hook ל-scorer חזק יותר (FinBERT / מודל שפה / Claude API) שאפשר
     לחבר בהמשך - פשוט החלף את הפונקציה score_headlines.

שליפת כותרות: yfinance מספק news לכל טיקר. אפשר גם להוסיף RSS/NewsAPI.
"""
from __future__ import annotations

import re

try:
    import yfinance as yf
except ImportError:
    yf = None

# לקסיקון מינימלי - הרחב לפי הצורך
_POSITIVE = {
    "beat", "beats", "surge", "soar", "gain", "gains", "record", "growth",
    "upgrade", "upgraded", "bullish", "rally", "profit", "strong", "outperform",
    "raises", "raised", "buyback", "approval", "wins", "expansion",
}
_NEGATIVE = {
    "miss", "misses", "plunge", "drop", "falls", "fell", "loss", "losses",
    "downgrade", "downgraded", "bearish", "selloff", "weak", "underperform",
    "cuts", "cut", "lawsuit", "probe", "warning", "recall", "bankruptcy",
    "layoffs", "fraud", "decline",
}

_WORD_RE = re.compile(r"[a-zA-Z']+")


def score_text(text: str) -> float:
    """ציון מילוני פשוט ב-[-1, 1] עבור מחרוזת."""
    words = [w.lower() for w in _WORD_RE.findall(text)]
    if not words:
        return 0.0
    pos = sum(w in _POSITIVE for w in words)
    neg = sum(w in _NEGATIVE for w in words)
    if pos + neg == 0:
        return 0.0
    return (pos - neg) / (pos + neg)


def score_headlines(headlines: list[str]) -> float:
    """ממוצע ציוני הכותרות. נקודת ההחלפה למודל חזק יותר."""
    if not headlines:
        return 0.0
    scores = [score_text(h) for h in headlines]
    return sum(scores) / len(scores)


def fetch_headlines(symbol: str, limit: int = 10) -> list[str]:
    """שולף כותרות חדשות אחרונות לטיקר דרך yfinance."""
    if yf is None:
        return []
    try:
        news = yf.Ticker(symbol).news or []
    except Exception:  # noqa: BLE001
        return []
    titles = []
    for item in news[:limit]:
        # מבנה ה-news השתנה בין גרסאות yfinance - מטפלים בשתי הצורות
        title = item.get("title") or item.get("content", {}).get("title")
        if title:
            titles.append(title)
    return titles


def sentiment_for(symbol: str) -> float:
    """נוחות: שולף כותרות ומחזיר ציון. 0.0 אם אין נתונים."""
    return score_headlines(fetch_headlines(symbol))
