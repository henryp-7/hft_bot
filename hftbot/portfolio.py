from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict
from .models import Fill, MarketTick

@dataclass
class Position:
    qty: float = 0.0  # base asset (e.g., BTC)
    avg_price: float = 0.0

@dataclass
class Portfolio:
    quote_ccy: str = "USDT"
    cash: float = 0.0
    positions: Dict[str, Position] = field(default_factory=dict)  # symbol -> Position

    def on_fill(self, fill: Fill):
        pos = self.positions.setdefault(fill.symbol, Position())
        # Simple average price update
        if fill.qty == 0:
            return
        notional = fill.qty * fill.price
        if fill.qty > 0:
            # buy: spend cash, increase qty
            total_cost = pos.avg_price * pos.qty + notional
            pos.qty += fill.qty
            pos.avg_price = total_cost / pos.qty if pos.qty != 0 else 0.0
            self.cash -= notional
        else:
            # sell: receive cash, decrease qty
            self.cash += -notional  # fill.qty negative, so -notional adds
            pos.qty += fill.qty  # reduces qty
            if pos.qty == 0:
                pos.avg_price = 0.0

    def mark_to_market(self, ticks: Dict[str, MarketTick]) -> float:
        # Return total equity in quote currency
        equity = self.cash
        for sym, pos in self.positions.items():
            if sym in ticks:
                equity += pos.qty * ticks[sym].mid
        return equity

    def exposure_notional(self, symbol: str, ticks: Dict[str, MarketTick]) -> float:
        pos = self.positions.get(symbol)
        if not pos or symbol not in ticks:
            return 0.0
        return abs(pos.qty * ticks[symbol].mid)

    def total_exposure(self, ticks: Dict[str, MarketTick]) -> float:
        s = 0.0
        for sym, pos in self.positions.items():
            if sym in ticks:
                s += abs(pos.qty * ticks[sym].mid)
        return s
