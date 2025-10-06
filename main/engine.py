from __future__ import annotations
import asyncio
import logging
import uuid
from typing import Dict, Optional

from .config import Settings
from main.datafeeds import LiveBinanceDataStream
from execution.binance_exec import BinanceRestExec
from main.models import MarketTick, OrderRequest, OrderSide, OrderType, Fill
from main.portfolio import Portfolio
from main.risk import check_risk
from main.storage import CSVStorage
from main.utils import now_ms, setup_logging

log = logging.getLogger(__name__)

class Engine:
    def __init__(self, cfg: Settings, strategy, storage: CSVStorage, live_trading: bool = False):
        self.cfg = cfg
        self.strategy = strategy
        self.storage = storage
        self.live_trading = live_trading

        self.stream = LiveBinanceDataStream(cfg.symbols)
        self.portfolio = Portfolio(quote_ccy=cfg.quote_ccy, cash=cfg.initial_cash)
        self.paper_books: Dict[str, MarketTick] = {}
        self.slippage_bps = cfg.slippage_bps
        self.rest_exec: Optional[BinanceRestExec] = None
        if self.live_trading:
            if not cfg.binance_api_key or not cfg.binance_api_secret:
                raise ValueError(
                    "Live trading requires BINANCE_API_KEY and BINANCE_API_SECRET to be configured."
                )
            self.rest_exec = BinanceRestExec(
                cfg.binance_api_key,
                cfg.binance_api_secret,
            )

    async def handle_tick(self, tick: MarketTick):
        # Persist tick
        self.storage.append_tick(tick)

        # Update local book cache for paper simulation
        if not self.live_trading:
            self.paper_books[tick.symbol] = tick

        # Strategy
        for order in self.strategy.generate_orders(tick, self.portfolio):
            # Add a client id
            order.client_id = order.client_id or str(uuid.uuid4())[:16]

            # Check risk
            if not check_risk(order, self.portfolio, self.stream.latest, self.cfg):
                log.info(f"Risk rejected order: {order}")
                continue

            # Execute paper simulation if applicable
            if not self.live_trading:
                fill = self._simulate_paper_fill(order)
                if fill:
                    self.storage.append_fill(fill)
                    eq = self.portfolio.mark_to_market(self.stream.latest)
                    log.info(
                        "Paper fill %s %s %.6f @ %.4f | Equity ~ %.2f",
                        fill.symbol,
                        fill.side,
                        abs(fill.qty),
                        fill.price,
                        eq,
                    )

            if self.rest_exec:
                try:
                    live_fill = self.rest_exec.place_order(order)
                    if live_fill:
                        log.info("Live order placed on Binance id=%s", live_fill.order_id)
                except Exception as e:
                    log.error(f"Live order error: {e}")

    async def run(self):
        setup_logging()
        async for tick in self.stream.stream():
            await self.handle_tick(tick)

    def _simulate_paper_fill(self, order: OrderRequest) -> Optional[Fill]:
        book = self.paper_books.get(order.symbol)
        if not book:
            return None

        price: Optional[float]
        if order.order_type == OrderType.MARKET:
            price = book.ask if order.side == OrderSide.BUY else book.bid
        else:
            price = order.price or book.mid
            if order.side == OrderSide.BUY and price < book.ask:
                return None
            if order.side == OrderSide.SELL and price > book.bid:
                return None

        if price is None:
            return None

        if self.slippage_bps > 0:
            slip = price * (self.slippage_bps / 10000.0)
            price = price + slip if order.side == OrderSide.BUY else price - slip

        qty = abs(order.qty)
        qty = qty if order.side == OrderSide.BUY else -qty
        fill = Fill(
            symbol=order.symbol,
            side=order.side,
            qty=qty,
            price=price,
            ts_ms=now_ms(),
            client_id=order.client_id,
        )
        self.portfolio.on_fill(fill)
        return fill
