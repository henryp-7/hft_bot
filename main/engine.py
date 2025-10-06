from __future__ import annotations
import asyncio
import logging
import uuid
from typing import Dict, Optional

from .config import Settings
from main.datafeeds import LiveBinanceDataStream
from execution.paper import PaperExecution
from execution.binance_exec import BinanceRestExec
from main.models import MarketTick, OrderRequest, OrderType
from main.portfolio import Portfolio
from main.risk import check_risk
from main.storage import CSVStorage
from main.utils import setup_logging

log = logging.getLogger(__name__)

class Engine:
    def __init__(self, cfg: Settings, strategy, storage: CSVStorage, live_trading: bool = False):
        self.cfg = cfg
        self.strategy = strategy
        self.storage = storage
        self.live_trading = live_trading

        self.stream = LiveBinanceDataStream(cfg.symbols)
        self.portfolio = Portfolio(quote_ccy=cfg.quote_ccy, cash=cfg.initial_cash)
        self.paper_exec = PaperExecution(self.portfolio, slippage_bps=cfg.slippage_bps)
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

        # Update paper book
        self.paper_exec.on_tick(tick)

        # Strategy
        for order in self.strategy.generate_orders(tick, self.portfolio):
            # Add a client id
            order.client_id = order.client_id or str(uuid.uuid4())[:16]

            # Check risk
            if not check_risk(order, self.portfolio, self.stream.latest, self.cfg):
                log.info(f"Risk rejected order: {order}")
                continue

            # Execute (paper always; optionally live)
            fill = self.paper_exec.execute(order)
            if fill:
                self.storage.append_fill(fill)
                eq = self.portfolio.mark_to_market(self.stream.latest)
                log.info(f"Paper fill {fill.symbol} {fill.side} {abs(fill.qty):.6f} @ {fill.price:.4f} | Equity ~ {eq:.2f}")

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
