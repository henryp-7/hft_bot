from __future__ import annotations
import asyncio
import logging
import time
import uuid
from typing import Dict, Optional
from colorama import init, Fore, Style
init(autoreset=True)

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

        self.stream = LiveBinanceDataStream(cfg.symbols, host=cfg.binance_ws_host)
        self.portfolio = Portfolio(quote_ccy=cfg.quote_ccy, cash=cfg.initial_cash)
        self.initial_equity = cfg.initial_cash
        self.paper_books: Dict[str, MarketTick] = {}
        self.slippage_bps = cfg.slippage_bps
        self.rest_exec: Optional[BinanceRestExec] = None
        self.performance_refresh_seconds = getattr(cfg, "performance_refresh_seconds", 5.0)
        self._last_performance_report = 0.0
        if self.live_trading:
            if not cfg.binance_api_key or not cfg.binance_api_secret:
                raise ValueError(
                    "Live trading requires BINANCE_API_KEY and BINANCE_API_SECRET to be configured."
                )
            self.rest_exec = BinanceRestExec(
                cfg.binance_api_key,
                cfg.binance_api_secret,
                base_url=cfg.binance_rest_base,
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
                    value = abs(fill.qty) * fill.price  # trade notional

                    # Colors: BUY/SELL in yellow/magenta, value in light blue
                    side_color = Fore.LIGHTYELLOW_EX if fill.side == OrderSide.BUY else Fore.LIGHTMAGENTA_EX
                    value_color = Fore.LIGHTBLUE_EX

                    log.info(
                        f"Paper fill {fill.symbol} "
                        f"{side_color}{fill.side}{Style.RESET_ALL} "
                        f"{abs(fill.qty):.6f} @ {fill.price:.4f} "
                        f"{value_color}= {value:.2f}{Style.RESET_ALL} "
                        f"| Equity ~ {eq:.2f}"
                    )
                    self._report_performance(force=True)

            if self.rest_exec:
                try:
                    live_fill = self.rest_exec.place_order(order)
                    if live_fill:
                        value = abs(live_fill.qty) * live_fill.price
                        side_color = Fore.LIGHTYELLOW_EX if live_fill.side == OrderSide.BUY else Fore.LIGHTMAGENTA_EX
                        value_color = Fore.LIGHTBLUE_EX

                        log.info(
                            f"Live order {live_fill.symbol} "
                            f"{side_color}{live_fill.side}{Style.RESET_ALL} "
                            f"{abs(live_fill.qty):.6f} @ {live_fill.price:.4f} "
                            f"{value_color}= {value:.2f}{Style.RESET_ALL} "
                            f"| Equity ~ {eq:.2f}"
                        )
                        self._report_performance(force=True)
                except Exception as e:
                    log.error(f"Live order error: {e}")

        self._report_performance()

    async def run(self):
        setup_logging()
        try:
            async for tick in self.stream.stream():
                await self.handle_tick(tick)
        finally:
            self._report_performance(force=True, final=True)

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

    def _report_performance(self, *, force: bool = False, final: bool = False) -> None:
        now = time.time()
        if not force and (now - self._last_performance_report) < self.performance_refresh_seconds:
            return

        equity = self.portfolio.mark_to_market(self.stream.latest) if self.stream.latest else self.portfolio.cash
        pnl = equity - self.initial_equity

        border_color = Fore.CYAN
        border = f"{border_color}{'=' * 60}{Style.RESET_ALL}"
        heading_prefix = "FINAL " if final else ""
        heading = f"{border_color}{heading_prefix}PORTFOLIO PERFORMANCE{Style.RESET_ALL}"
        pnl_color = Fore.GREEN if pnl > 0 else (Fore.RED if pnl < 0 else Fore.WHITE)

        lines = [
            "",
            border,
            heading,
            f"Initial Equity: {self.initial_equity:.2f} {self.cfg.quote_ccy}",
            f"Current Equity: {equity:.2f} {self.cfg.quote_ccy}",
            f"P/L: {pnl_color}{pnl:+.2f} {self.cfg.quote_ccy}{Style.RESET_ALL}",
            border,
            "",
        ]

        log.info("\n".join(lines))
        self._last_performance_report = now
