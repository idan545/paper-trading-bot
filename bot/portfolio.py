"""
סימולציית ברוקר ל-paper trading: מזומן, פוזיציות, עמלות, ורישום עסקאות.
תומך בריבוי מטבעות (USD למניות אמריקאיות, ILS למניות TASE) ומגלם הכל
למטבע בסיס אחד לצורך חישוב שווי תיק.

הערה חשובה על TASE: ב-Yahoo Finance הרבה מניות ישראליות מצוטטות באגורות
(ILA), כלומר 1/100 שקל. הטיפול בזה נעשה בשכבת הנתונים (data.py), כך
שכאן אנחנו מקבלים מחיר "נקי" במטבע שמוגדר לסימבול.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone


@dataclass
class Position:
    symbol: str
    quantity: float = 0.0
    avg_price: float = 0.0       # מחיר ממוצע במטבע המקומי של הסימבול
    currency: str = "USD"

    def market_value(self, price: float) -> float:
        return self.quantity * price

    def unrealized_pnl(self, price: float) -> float:
        return (price - self.avg_price) * self.quantity


@dataclass
class Trade:
    timestamp: str
    symbol: str
    side: str            # "BUY" / "SELL"
    quantity: float
    price: float
    currency: str
    commission: float
    cash_after: float


class Portfolio:
    """
    תיק paper-trading. כל הסכומים נשמרים במטבע הבסיס (ברירת מחדל USD).
    קנייה/מכירה מקבלות מחיר במטבע המקומי + שער המרה למטבע הבסיס.
    """

    def __init__(
        self,
        starting_cash: float = 100_000.0,
        base_currency: str = "USD",
        commission_rate: float = 0.0008,   # 0.08% לעסקה (קירוב סביר)
        min_commission: float = 1.0,
    ):
        self.base_currency = base_currency
        self.cash = float(starting_cash)        # במטבע הבסיס
        self.commission_rate = commission_rate
        self.min_commission = min_commission
        self.positions: dict[str, Position] = {}
        self.trades: list[Trade] = []

    # ----- עזרי עמלות -----
    def _commission(self, notional_base: float) -> float:
        return max(self.min_commission, notional_base * self.commission_rate)

    # ----- ביצוע פקודות -----
    def buy(self, symbol: str, quantity: float, price: float,
            fx_to_base: float = 1.0, currency: str = "USD",
            ts: str | None = None) -> bool:
        """
        קנייה. price במטבע המקומי, fx_to_base ממיר מטבע מקומי -> בסיס.
        מחזיר True אם בוצע, False אם אין מספיק מזומן.
        """
        if quantity <= 0:
            return False
        notional_base = quantity * price * fx_to_base
        commission = self._commission(notional_base)
        total_cost = notional_base + commission
        if total_cost > self.cash + 1e-9:
            return False

        self.cash -= total_cost
        pos = self.positions.get(symbol) or Position(symbol=symbol, currency=currency)
        new_qty = pos.quantity + quantity
        # עדכון מחיר ממוצע (במטבע המקומי)
        pos.avg_price = (pos.avg_price * pos.quantity + price * quantity) / new_qty
        pos.quantity = new_qty
        pos.currency = currency
        self.positions[symbol] = pos
        self._record(symbol, "BUY", quantity, price, currency, commission, ts)
        return True

    def sell(self, symbol: str, quantity: float, price: float,
             fx_to_base: float = 1.0, currency: str = "USD",
             ts: str | None = None) -> bool:
        """מכירה. לא תומך בשורט - לא נמכור יותר ממה שיש."""
        pos = self.positions.get(symbol)
        if not pos or quantity <= 0:
            return False
        quantity = min(quantity, pos.quantity)
        if quantity <= 0:
            return False
        notional_base = quantity * price * fx_to_base
        commission = self._commission(notional_base)
        self.cash += notional_base - commission
        pos.quantity -= quantity
        if pos.quantity <= 1e-9:
            del self.positions[symbol]
        else:
            self.positions[symbol] = pos
        self._record(symbol, "SELL", quantity, price, currency, commission, ts)
        return True

    def _record(self, symbol, side, qty, price, currency, commission, ts):
        self.trades.append(Trade(
            timestamp=ts or datetime.now(timezone.utc).isoformat(),
            symbol=symbol, side=side, quantity=qty, price=price,
            currency=currency, commission=commission, cash_after=self.cash,
        ))

    # ----- הערכת שווי -----
    def total_value(self, prices: dict[str, float], fx: dict[str, float] | None = None) -> float:
        """
        שווי כולל = מזומן + שווי כל הפוזיציות, הכל במטבע הבסיס.
        prices: סימבול -> מחיר נוכחי (מטבע מקומי).
        fx: סימבול -> שער המרה למטבע בסיס (ברירת מחדל 1.0).
        """
        fx = fx or {}
        total = self.cash
        for sym, pos in self.positions.items():
            px = prices.get(sym, pos.avg_price)
            rate = fx.get(sym, 1.0)
            total += pos.market_value(px) * rate
        return total

    # ----- שמירה/טעינה של מצב -----
    def to_dict(self) -> dict:
        return {
            "base_currency": self.base_currency,
            "cash": self.cash,
            "commission_rate": self.commission_rate,
            "min_commission": self.min_commission,
            "positions": {s: asdict(p) for s, p in self.positions.items()},
            "trades": [asdict(t) for t in self.trades],
        }

    def save(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, path: str) -> "Portfolio":
        with open(path, "r", encoding="utf-8") as f:
            d = json.load(f)
        p = cls(
            starting_cash=d["cash"],
            base_currency=d.get("base_currency", "USD"),
            commission_rate=d.get("commission_rate", 0.0008),
            min_commission=d.get("min_commission", 1.0),
        )
        p.positions = {
            s: Position(**pos) for s, pos in d.get("positions", {}).items()
        }
        p.trades = [Trade(**t) for t in d.get("trades", [])]
        return p
