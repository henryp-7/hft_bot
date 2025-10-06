from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import AsyncGenerator, Dict, Iterable, Optional

import websockets

from main.models import MarketTick

log = logging.getLogger(__name__)


class LiveBinanceDataStream:
    """Stream real-time bookTicker data from Binance public websockets."""

    def __init__(self, symbols: Iterable[str], testnet: bool = False) -> None:
        self.symbols = [s.lower() for s in symbols]
        if not self.symbols:
            raise ValueError("LiveBinanceDataStream requires at least one symbol")
        self.testnet = testnet
        self.latest: Dict[str, MarketTick] = {}
        host = "testnet.binance.vision" if testnet else "stream.binance.com:9443"
        stream_names = "/".join(f"{sym}@bookTicker" for sym in self.symbols)
        if testnet:
            self._url = f"wss://{host}/stream?streams={stream_names}"
        else:
            self._url = f"wss://{host}/stream?streams={stream_names}"

    async def stream(self) -> AsyncGenerator[MarketTick, None]:
        backoff = 1.0
        while True:
            try:
                async with websockets.connect(self._url, ping_interval=20, ping_timeout=20) as ws:
                    log.info("Connected to Binance %s stream for %s", "testnet" if self.testnet else "live", ", ".join(self.symbols))
                    backoff = 1.0
                    async for raw in ws:
                        payload = self._extract_payload(raw)
                        if not payload:
                            continue
                        tick = self._to_tick(payload)
                        if not tick:
                            continue
                        self.latest[tick.symbol] = tick
                        yield tick
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.warning("Binance stream error: %s", exc, exc_info=True)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30.0)

    def _extract_payload(self, raw: str) -> Optional[Dict[str, str]]:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return None
        if isinstance(data, dict):
            if "stream" in data and isinstance(data.get("data"), dict):
                return data["data"]
            return data
        return None

    def _to_tick(self, payload: Dict[str, str]) -> Optional[MarketTick]:
        symbol = payload.get("s")
        if not symbol:
            return None
        symbol = symbol.lower()
        try:
            bid = float(payload["b"])
            ask = float(payload["a"])
            bid_qty = float(payload.get("B", 0.0))
            ask_qty = float(payload.get("A", 0.0))
        except (KeyError, TypeError, ValueError):
            return None
        ts_ms = self._extract_ts(payload)
        return MarketTick(
            symbol=symbol,
            bid=bid,
            ask=ask,
            bid_qty=bid_qty,
            ask_qty=ask_qty,
            ts_ms=ts_ms,
        )

    def _extract_ts(self, payload: Dict[str, str]) -> int:
        for key in ("E", "T", "eventTime", "time"):
            if key in payload:
                try:
                    return int(payload[key])
                except (TypeError, ValueError):
                    continue
        return int(time.time() * 1000)