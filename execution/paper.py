from __future__ import annotations
from typing import Dict, Optional
from main.models import MarketTick, OrderRequest, OrderType, OrderSide, Fill
from main.portfolio import Portfolio
from main.utils import now_ms

class PaperExecution:
    """Simulates order fills using best bid/ask from latest ticks."""
    def __init__(self, portfolio: Portfolio, slippage_bps: float = 0.0):
        self.portfolio = portfolio
        self.slippage_bps = slippage_bps
        self.books: Dict[str, MarketTick] = {}

    def on_tick(self, tick: MarketTick):
        self.books[tick.symbol] = tick

    def _apply_slippage(self, px: float, side: OrderSide) -> float:
        if self.slippage_bps <= 0:
            return px
        slip = px * (self.slippage_bps / 10000.0)
        return px + slip if side == OrderSide.BUY else px - slip

    def execute(self, order: OrderRequest) -> Optional[Fill]:
        book = self.books.get(order.symbol)
        if not book:
            return None
        if order.order_type == OrderType.MARKET:
            px = book.ask if order.side == OrderSide.BUY else book.bid
            px = self._apply_slippage(px, order.side)
        else:
            # LIMIT: naive - if price crosses, fill immediately at limit
            px = order.price or book.mid
            if order.side == OrderSide.BUY and px < book.ask:
                return None
            if order.side == OrderSide.SELL and px > book.bid:
                return None

        qty = order.qty if order.side == OrderSide.BUY else -abs(order.qty)
        fill = Fill(symbol=order.symbol, side=order.side, qty=qty, price=px, ts_ms=now_ms(), client_id=order.client_id)
        self.portfolio.on_fill(fill)
        return fill
