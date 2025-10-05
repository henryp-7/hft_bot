from __future__ import annotations
import time
from typing import Dict, List
from ..models import MarketTick, OrderRequest, OrderSide, OrderType
from ..portfolio import Portfolio

class Strategy:
    """Base strategy interface. Replace with your own logic.
    The default example implements a *very naive* equal-weight rebalancer.
    """
    def __init__(self, symbols: List[str], target_gross_notional: float):
        self.symbols = symbols
        self.target_gross = target_gross_notional
        self.last_action_ts: Dict[str, float] = {s: 0.0 for s in symbols}
        self.cooldown_sec = 5.0  # avoid spamming orders

    def generate_orders(self, tick: MarketTick, portfolio: Portfolio) -> List[OrderRequest]:
        now = time.time()
        s = tick.symbol
        if now - self.last_action_ts.get(s, 0) < self.cooldown_sec:
            return []

        # Equal-weight target: split target gross across symbols
        n = max(1, len(self.symbols))
        target_per_symbol = self.target_gross / n  # quote currency
        # current exposure
        pos = portfolio.positions.get(s)
        curr_notional = 0.0
        if pos:
            curr_notional = pos.qty * tick.mid

        # rebalance if drift > 10% of target
        drift = target_per_symbol - curr_notional
        if abs(drift) < 0.10 * target_per_symbol or target_per_symbol <= 0:
            return []

        # convert notional delta to quantity
        qty = abs(drift) / tick.mid
        side = OrderSide.BUY if drift > 0 else OrderSide.SELL
        self.last_action_ts[s] = now
        return [OrderRequest(symbol=s, side=side, order_type=OrderType.MARKET, qty=qty)]
