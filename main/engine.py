from __future__ import annotations
import asyncio
import logging
import uuid
from typing import Dict, Optional

from .config import Settings
from main.datafeeds.live_stream import LiveBinanceDataStream
from main.datafeeds.vision_stream import VisionDataStream
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

        self.stream = self._build_stream()
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

    def _build_stream(self):
        source = self.cfg.data_source
        if source == "vision":
            try:
                return VisionDataStream(
                    self.cfg.symbols,
                    testnet=self.cfg.use_testnet,
                    data_dir=self.cfg.vision_data_dir,
                    dataset=self.cfg.vision_dataset,
                    speedup=self.cfg.vision_speedup,
                    loop_forever=self.cfg.vision_loop_forever,
                )
            except FileNotFoundError as exc:
                default_dir = self.cfg.vision_data_dir or "./data/binance_vision"
                raise FileNotFoundError(
                    "Vision dataset not found. Download archives from https://data.binance.vision/ "
                    f"and place them under '{default_dir}'."
                ) from exc
        if source == "live":
            return LiveBinanceDataStream(self.cfg.symbols, testnet=self.cfg.use_testnet)
        raise ValueError(f"Unknown data source '{source}'. Set DATA_SOURCE to 'live' or 'vision'.")
