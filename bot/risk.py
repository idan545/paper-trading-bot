"""
ניהול סיכונים: גודל פוזיציה, stop-loss ו-take-profit.

הרעיון המרכזי - fixed-fractional sizing: בכל עסקה מסכנים אחוז קבוע מההון
(למשל 1%). גודל הפוזיציה נגזר ממרחק ה-stop, כך שהפסד בסטופ ≈ הסכום שהוקצב
לסיכון. זה אחד הדברים שמבדילים בין בוט ששורד לבוט שמתפוצץ.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RiskParams:
    risk_per_trade: float = 0.01     # 1% מההון לכל עסקה
    stop_loss_pct: float = 0.08      # סטופ 8% מתחת לכניסה (אם אין ATR)
    take_profit_pct: float = 0.16    # יעד 16% (יחס סיכון/סיכוי 1:2)
    max_position_pct: float = 0.20   # לא יותר מ-20% מההון בפוזיציה אחת
    atr_stop_mult: float = 2.5       # אם יש ATR: סטופ = entry - mult*ATR


def position_size(
    equity_base: float,
    entry_price: float,
    fx_to_base: float,
    rp: RiskParams,
    atr: float | None = None,
) -> int:
    """
    מחשב כמות מניות (שלמה) לקנייה.
    equity_base - ההון הכולל במטבע הבסיס.
    entry_price - מחיר כניסה במטבע המקומי.
    fx_to_base  - שער המרה מטבע מקומי -> בסיס.
    """
    if entry_price <= 0 or equity_base <= 0:
        return 0

    # מרחק הסטופ במטבע המקומי
    if atr and atr > 0:
        stop_distance = rp.atr_stop_mult * atr
    else:
        stop_distance = entry_price * rp.stop_loss_pct
    if stop_distance <= 0:
        return 0

    risk_amount_base = equity_base * rp.risk_per_trade
    # כמות לפי סיכון: risk = qty * stop_distance(local) * fx
    qty_by_risk = risk_amount_base / (stop_distance * fx_to_base)

    # תקרה לפי גודל פוזיציה מקסימלי
    max_notional_base = equity_base * rp.max_position_pct
    qty_by_cap = max_notional_base / (entry_price * fx_to_base)

    qty = int(min(qty_by_risk, qty_by_cap))
    return max(qty, 0)


def stop_levels(
    entry_price: float, rp: RiskParams, atr: float | None = None
) -> tuple[float, float]:
    """מחזיר (stop_loss, take_profit) במטבע המקומי."""
    if atr and atr > 0:
        stop = entry_price - rp.atr_stop_mult * atr
        target = entry_price + 2 * rp.atr_stop_mult * atr
    else:
        stop = entry_price * (1 - rp.stop_loss_pct)
        target = entry_price * (1 + rp.take_profit_pct)
    return max(stop, 0.0), target
