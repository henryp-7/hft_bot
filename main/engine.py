from __future__ import annotations
import asyncio
import logging
import uuid
from typing import Dict, Optional

from .config import Settings
#from data.binance import BinanceDataStream
from data.vision_stream import VisionDataStream as BinanceDataStream
from execution.paper import PaperExecution
from execution.binance_exec import BinanceRestExec
from main.models import MarketTick, OrderRequest, OrderType
from main.portfolio import Portfolio
from main.risk import check_risk
from main.storage import CSVStorage
from main.utils import setup_logging

log = logging.getLogger(__name__)

class Engine:
    def __init__(self, cfg: Settings, strategy, storage: CSVStorage):
        self.cfg = cfg
        self.strategy = strategy
        self.storage = storage

        self.stream = BinanceDataStream(cfg.symbols, testnet=False)  # use public mainnet for data
        self.portfolio = Portfolio(quote_ccy=cfg.quote_ccy, cash=cfg.initial_cash)
        self.paper_exec = PaperExecution(self.portfolio, slippage_bps=cfg.slippage_bps)
        self.rest_exec: Optional[BinanceRestExec] = None
        if cfg.use_testnet and cfg.binance_api_key and cfg.binance_api_secret:
            self.rest_exec = BinanceRestExec(cfg.binance_api_key, cfg.binance_api_secret, use_testnet=True)

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

            # Execute (paper always; and optionally live on testnet)
            fill = self.paper_exec.execute(order)
            if fill:
                self.storage.append_fill(fill)
                eq = self.portfolio.mark_to_market(self.stream.latest)
                log.info(f"Paper fill {fill.symbol} {fill.side} {abs(fill.qty):.6f} @ {fill.price:.4f} | Equity ~ {eq:.2f}")

            if self.rest_exec:
                try:
                    live_fill = self.rest_exec.place_order(order)
                    if live_fill:
                        log.info(f"Live order placed (testnet) id={live_fill.order_id}")
                except Exception as e:
                    log.error(f"Live order error: {e}")

    async def run(self):
        setup_logging()
        async for tick in self.stream.stream():
            await self.handle_tick(tick)
