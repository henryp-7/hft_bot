from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Optional

class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"

class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"

@dataclass
class MarketTick:
    symbol: str            # e.g., 'btcusdt'
    bid: float
    ask: float
    bid_qty: float
    ask_qty: float
    ts_ms: int

    @property
    def mid(self) -> float:
        return (self.bid + self.ask) / 2.0

@dataclass
class OrderRequest:
    symbol: str
    side: OrderSide
    order_type: OrderType = OrderType.MARKET
    qty: float = 0.0                      # base asset quantity (e.g., BTC for BTCUSDT)
    price: Optional[float] = None         # for LIMIT only
    client_id: Optional[str] = None

@dataclass
class Fill:
    symbol: str
    side: OrderSide
    qty: float
    price: float
    ts_ms: int
    client_id: Optional[str] = None
    order_id: Optional[str] = None

