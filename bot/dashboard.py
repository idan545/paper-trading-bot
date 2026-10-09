"""
ייצוא מצב התיק ל-JSON שהדשבורד (PWA) קורא. מייצר שני קבצים:
  - dashboard.json    : תמונת מצב נוכחית (שווי, פוזיציות, עסקאות אחרונות).
  - equity_history.json : עקומת ההון - נקודה אחת לכל יום מסחר, מצטבר.

הקובץ dashboard.json נכתב לתוך תיקיית ה-webapp כדי שה-PWA יקרא אותו
מאותו origin (בלי CORS).
"""
from __future__ import annotations

import json
import math
import os
from datetime import datetime, timezone

from .portfolio import Portfolio


def _is_finite_number(v) -> bool:
    return isinstance(v, (int, float)) and math.isfinite(v)


def _clean(obj):
    """
    מחליף כל NaN/Infinity ב-None (null ב-JSON). NaN אינו JSON חוקי,
    והדפדפן מסרב לקרוא קובץ שמכיל אותו.
    """
    if isinstance(obj, float) and not math.isfinite(obj):
        return None
    if isinstance(obj, dict):
        return {k: _clean(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_clean(v) for v in obj]
    return obj


def _load_equity_history(path: str) -> list[dict]:
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                history = json.load(f)
        except (json.JSONDecodeError, OSError):
            return []
        # מסננים נקודות שבורות (NaN) שנכתבו בעבר
        return [p for p in history if _is_finite_number(p.get("value"))]
    return []


def _append_today(history: list[dict], total_value: float,
                  bench_value: float | None = None) -> list[dict]:
    """מוסיף/מעדכן את נקודת ההון של היום (לפי תאריך UTC)."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    point = {"date": today, "value": round(total_value, 2)}
    if _is_finite_number(bench_value):
        point["bench"] = round(bench_value, 2)
    if history and history[-1].get("date") == today:
        history[-1] = point
    else:
        history.append(point)
    return history[-365:]  # שומרים שנה אחרונה


def build_snapshot(
    pf: Portfolio,
    prices: dict[str, float],
    fx: dict[str, float],
    usd_ils: float,
    equity_history: list[dict],
    starting_cash: float,
    benchmark: dict | None = None,
) -> dict:
    total = pf.total_value(prices, fx)

    prev = equity_history[-2]["value"] if len(equity_history) >= 2 else starting_cash
    base = equity_history[0]["value"] if equity_history else starting_cash
    day_change = total - prev
    day_change_pct = (day_change / prev) if prev else 0.0
    total_change_pct = (total / base - 1.0) if base else 0.0

    positions = []
    for sym, pos in pf.positions.items():
        px = prices.get(sym, pos.avg_price)
        rate = fx.get(sym, 1.0)
        positions.append({
            "symbol": sym,
            "currency": pos.currency,
            "is_tase": sym.upper().endswith(".TA"),
            "quantity": round(pos.quantity, 4),
            "avg_price": round(pos.avg_price, 2),
            "current_price": round(px, 2),
            "unrealized_pnl": round(pos.unrealized_pnl(px), 2),
            "unrealized_pnl_pct": round((px / pos.avg_price - 1.0), 4) if pos.avg_price else 0.0,
            "value_base": round(pos.market_value(px) * rate, 2),
        })
    positions.sort(key=lambda p: p["value_base"], reverse=True)

    recent = [
        {
            "timestamp": t.timestamp,
            "symbol": t.symbol,
            "side": t.side,
            "quantity": round(t.quantity, 4),
            "price": round(t.price, 2),
            "currency": t.currency,
        }
        for t in pf.trades[-12:][::-1]
    ]

    return {
        "as_of": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "base_currency": pf.base_currency,
        "usd_ils": round(usd_ils, 4),
        "total_value": round(total, 2),
        "cash": round(pf.cash, 2),
        "invested": round(total - pf.cash, 2),
        "day_change": round(day_change, 2),
        "day_change_pct": round(day_change_pct, 4),
        "total_change_pct": round(total_change_pct, 4),
        "num_positions": len(positions),
        "num_trades": len(pf.trades),
        "positions": positions,
        "recent_trades": recent,
        "equity_history": equity_history,
        "starting_cash": starting_cash,
        "benchmark": benchmark,
    }


def export(
    pf: Portfolio,
    prices: dict[str, float],
    fx: dict[str, float],
    usd_ils: float,
    dashboard_path: str,
    equity_path: str,
    starting_cash: float,
    benchmark: dict | None = None,
) -> dict:
    history = _load_equity_history(equity_path)
    today_value = pf.total_value(prices, fx)
    bench_value = benchmark.get("value") if benchmark else None
    # לא מוסיפים נקודת הון שבורה; עדיף לדלג על יום מאשר לשבור את הקובץ
    if _is_finite_number(today_value):
        history = _append_today(history, today_value, bench_value)
    with open(equity_path, "w", encoding="utf-8") as f:
        json.dump(_clean(history), f, ensure_ascii=False, indent=2, allow_nan=False)

    snapshot = _clean(build_snapshot(pf, prices, fx, usd_ils, history,
                                     starting_cash, benchmark))
    os.makedirs(os.path.dirname(dashboard_path) or ".", exist_ok=True)
    with open(dashboard_path, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2, allow_nan=False)
    return snapshot
