from __future__ import annotations
import asyncio
import json
import logging
from typing import AsyncIterator, Dict, List
import websockets
from ..models import MarketTick
from ..utils import now_ms

log = logging.getLogger(__name__)

class BinanceDataStream:
    """Stream best bid/ask (bookTicker) for symbols via Binance WebSocket.
    Uses combined streams: wss://stream.binance.com:9443/stream?streams=btcusdt@bookTicker/ethusdt@bookTicker
    For testnet data, you can switch the host; however, public mainnet is more liquid for data.
    """
    def __init__(self, symbols: List[str], testnet: bool = False):
        self.symbols = [s.lower() for s in symbols]
        self.base_wss = "wss://testnet.binance.vision/stream" if testnet else "wss://stream.binance.com:9443/stream"
        self._latest: Dict[str, MarketTick] = {}

    @property
    def latest(self) -> Dict[str, MarketTick]:
        return self._latest

    def _stream_url(self) -> str:
        streams = "/".join(f"{s}@bookTicker" for s in self.symbols)
        return f"{self.base_wss}?streams={streams}"

    async def stream(self) -> AsyncIterator[MarketTick]:
        url = self._stream_url()
        backoff = 1.0
        while True:
            try:
                log.info(f"Connecting to {url}")
                async with websockets.connect(url, ping_interval=20, ping_timeout=20) as ws:
                    backoff = 1.0
                    async for raw in ws:
                        try:
                            msg = json.loads(raw)
                            data = msg.get("data") or msg  # combined vs single
                            s = data["s"].lower()
                            bid = float(data["b"]); ask = float(data["a"])
                            bid_q = float(data.get("B", 0)); ask_q = float(data.get("A", 0))
                            tick = MarketTick(symbol=s, bid=bid, ask=ask, bid_qty=bid_q, ask_qty=ask_q, ts_ms=now_ms())
                            self._latest[s] = tick
                            yield tick
                        except Exception as e:
                            log.exception("Failed to parse tick: %s", e)
            except Exception as e:
                log.warning(f"WebSocket error: {e}. Reconnecting in {backoff:.1f}s...")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30.0)
