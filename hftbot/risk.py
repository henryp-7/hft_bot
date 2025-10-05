from __future__ import annotations
from typing import Dict
from .models import OrderRequest, OrderSide, MarketTick, OrderType
from .portfolio import Portfolio
from .config import Settings

def order_notional(order: OrderRequest, tick: MarketTick) -> float:
    px = tick.mid if order.order_type == OrderType.MARKET else (order.price or tick.mid)
    return abs(order.qty) * px

def check_risk(order: OrderRequest, portfolio: Portfolio, ticks: Dict[str, MarketTick], cfg: Settings) -> bool:
    # basic per-symbol and total notional caps
    sym = order.symbol
    if sym not in ticks:
        return False
    ord_notional = order_notional(order, ticks[sym])
    if ord_notional > cfg.max_notional_per_symbol:
        return False
    if portfolio.total_exposure(ticks) + ord_notional > cfg.max_total_notional:
        return False

    # cash check for buys (paper)
    if order.side == OrderSide.BUY and (portfolio.cash < ord_notional):
        return False

    return True
