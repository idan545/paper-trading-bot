"""
ייצוא מצב התיק ל-JSON שהדשבורד (PWA) קורא. מייצר שני קבצים:
  - dashboard.json    : תמונת מצב נוכחית (שווי, פוזיציות, עסקאות אחרונות).
  - equity_history.json : עקומת ההון - נקודה אחת לכל יום מסחר, מצטבר.

הקובץ dashboard.json נכתב לתוך תיקיית ה-webapp כדי שה-PWA יקרא אותו
מאותו origin (בלי CORS).
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from .portfolio import Portfolio


def _load_equity_history(path: str) -> list[dict]:
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return []
    return []


def _append_today(history: list[dict], total_value: float) -> list[dict]:
    """מוסיף/מעדכן את נקודת ההון של היום (לפי תאריך UTC)."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if history and history[-1].get("date") == today:
        history[-1]["value"] = round(total_value, 2)
    else:
        history.append({"date": today, "value": round(total_value, 2)})
    return history[-365:]  # שומרים שנה אחרונה


def build_snapshot(
    pf: Portfolio,
    prices: dict[str, float],
    fx: dict[str, float],
    usd_ils: float,
    equity_history: list[dict],
    starting_cash: float,
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
            "quantity": round(pos.quantity, 2),
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
            "quantity": round(t.quantity, 2),
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
    }


def export(
    pf: Portfolio,
    prices: dict[str, float],
    fx: dict[str, float],
    usd_ils: float,
    dashboard_path: str,
    equity_path: str,
    starting_cash: float,
) -> dict:
    history = _load_equity_history(equity_path)
    history = _append_today(history, pf.total_value(prices, fx))
    with open(equity_path, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

    snapshot = build_snapshot(pf, prices, fx, usd_ils, history, starting_cash)
    os.makedirs(os.path.dirname(dashboard_path) or ".", exist_ok=True)
    with open(dashboard_path, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)
    return snapshot
