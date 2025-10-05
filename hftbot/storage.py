from __future__ import annotations
import csv
from pathlib import Path
from typing import Optional
from .models import MarketTick, Fill

class CSVStorage:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._tick_files = {}  # symbol -> path

    def _tick_path(self, symbol: str) -> Path:
        p = self.root / f"ticks_{symbol}.csv"
        if symbol not in self._tick_files:
            if not p.exists():
                with p.open('w', newline='') as f:
                    w = csv.writer(f)
                    w.writerow(["ts_ms", "symbol", "bid", "ask", "bid_qty", "ask_qty"])
            self._tick_files[symbol] = p
        return p

    def append_tick(self, tick: MarketTick):
        p = self._tick_path(tick.symbol)
        with p.open('a', newline='') as f:
            w = csv.writer(f)
            w.writerow([tick.ts_ms, tick.symbol, tick.bid, tick.ask, tick.bid_qty, tick.ask_qty])

    def append_fill(self, fill: Fill):
        p = self.root / "fills.csv"
        if not p.exists():
            with p.open('w', newline='') as f:
                w = csv.writer(f)
                w.writerow(["ts_ms", "symbol", "side", "qty", "price", "client_id", "order_id"])
        with p.open('a', newline='') as f:
            w = csv.writer(f)
            w.writerow([fill.ts_ms, fill.symbol, fill.side, fill.qty, fill.price, fill.client_id or "", fill.order_id or ""])
