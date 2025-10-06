from __future__ import annotations

import asyncio
import csv
import heapq
import io
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncGenerator, Dict, Iterable, Iterator, List, Optional, Tuple
import zipfile

from main.models import MarketTick

log = logging.getLogger(__name__)

@dataclass
class _TickSource:
    symbol: str
    iterator: Iterator[MarketTick]

class VisionDataStream:
    """Replay Binance Vision historical bookTicker data as an async stream."""

    def __init__(
        self,
        symbols: Iterable[str],
        testnet: bool = False,
        data_dir: Optional[os.PathLike] = None,
        dataset: str = "bookTicker",
        speedup: float = 1.0,
        loop_forever: bool = True,
    ) -> None:
        self.symbols = [s.lower() for s in symbols]
        self.testnet = testnet
        self.dataset = dataset.lower()
        self.speedup = speedup if speedup and speedup > 0 else None
        self.loop_forever = loop_forever
        self.latest: Dict[str, MarketTick] = {}

        env_dir = os.getenv("BINANCE_VISION_DATA_DIR")
        if data_dir is not None:
            base = Path(data_dir)
        elif env_dir:
            base = Path(env_dir)
        else:
            base = Path("./data/binance_vision")
        self.base_dir = base

        # Provide a couple of sensible fallbacks for users migrating from older layouts.
        alt_dirs = [base, Path("./historical"), Path("./historical_data")]
        seen: Dict[str, Path] = {}
        for d in alt_dirs:
            if d.exists():
                seen[str(d.resolve())] = d
        self.search_paths: List[Path] = list(seen.values())
        if not self.search_paths:
            # It's useful to create the default directory so users know where to drop files.
            base.mkdir(parents=True, exist_ok=True)
            self.search_paths = [base]

        self._files: Dict[str, List[Path]] = {}
        for sym in self.symbols:
            files = self._collect_files(sym)
            if not files:
                raise FileNotFoundError(
                    f"No Binance Vision {self.dataset} files found for symbol '{sym}'. "
                    "Download e.g. https://data.binance.vision/ and place the archives under "
                    f"one of: {', '.join(str(p.resolve()) for p in self.search_paths)} (supports .csv or .zip)."
                )
            self._files[sym] = files

    async def stream(self) -> AsyncGenerator[MarketTick, None]:
        sources: Dict[str, _TickSource] = {}
        heap: List[Tuple[int, str, MarketTick]] = []

        for sym in self.symbols:
            iterator = self._open_iterator(sym)
            try:
                first = next(iterator)
            except StopIteration:
                log.warning("No tick data produced for %s", sym)
                continue
            sources[sym] = _TickSource(symbol=sym, iterator=iterator)
            heap.append((first.ts_ms, sym, first))

        if not heap:
            raise RuntimeError("VisionDataStream could not initialise any symbols - no ticks available.")

        heapq.heapify(heap)
        last_ts = heap[0][0]

        while heap:
            ts, sym, tick = heapq.heappop(heap)
            if self.speedup:
                delay_ms = max(0, ts - last_ts)
                if delay_ms > 0:
                    await asyncio.sleep(delay_ms / 1000.0 / self.speedup)
            last_ts = ts
            self.latest[sym] = tick
            yield tick

            source = sources.get(sym)
            next_tick = None
            if source:
                next_tick = self._next_tick(source)
            if next_tick:
                heapq.heappush(heap, (next_tick.ts_ms, sym, next_tick))

    def _next_tick(self, source: _TickSource) -> Optional[MarketTick]:
        try:
            return next(source.iterator)
        except StopIteration:
            if not self.loop_forever:
                return None
            # Restart iterator from the beginning.
            source.iterator = self._open_iterator(source.symbol)
            try:
                return next(source.iterator)
            except StopIteration:
                return None

    def _open_iterator(self, symbol: str) -> Iterator[MarketTick]:
        files = self._files.get(symbol)
        if not files:
            return iter(())
        return self._iter_symbol(symbol, files)

    def _iter_symbol(self, symbol: str, files: List[Path]) -> Iterator[MarketTick]:
        for path in files:
            yield from self._iter_file(symbol, path)

    def _iter_file(self, symbol: str, path: Path) -> Iterator[MarketTick]:
        if path.suffix.lower() == ".zip":
            with zipfile.ZipFile(path) as zf:
                names = sorted(n for n in zf.namelist() if n.lower().endswith(".csv"))
                for name in names:
                    with zf.open(name) as fh:
                        text = io.TextIOWrapper(fh, encoding="utf-8")
                        yield from self._iter_csv(symbol, text)
        else:
            with path.open("r", newline="", encoding="utf-8") as fh:
                yield from self._iter_csv(symbol, fh)

    def _iter_csv(self, symbol: str, handle: io.TextIOBase) -> Iterator[MarketTick]:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            return
        for row in reader:
            tick = self._row_to_tick(symbol, row)
            if tick:
                yield tick

    def _row_to_tick(self, default_symbol: str, row: Dict[str, str]) -> Optional[MarketTick]:
        norm = {k.strip().lower(): (v.strip() if isinstance(v, str) else v) for k, v in row.items() if k}

        symbol = norm.get("symbol", default_symbol) or default_symbol
        symbol = symbol.lower()

        bid = self._parse_float(norm, ["bestbidprice", "bidprice", "bid", "best_bid_price", "bestbid", "b"])
        ask = self._parse_float(norm, ["bestaskprice", "askprice", "ask", "best_ask_price", "bestask", "a"])
        bid_qty = self._parse_float(norm, ["bestbidqty", "bidqty", "bid_quantity", "best_bid_qty", "bqty", "b_volume"])
        ask_qty = self._parse_float(norm, ["bestaskqty", "askqty", "ask_quantity", "best_ask_qty", "aqty", "a_volume"])
        ts_val = self._parse_ts(norm)

        if None in (bid, ask, bid_qty, ask_qty, ts_val):
            return None

        return MarketTick(
            symbol=symbol,
            bid=bid,
            ask=ask,
            bid_qty=bid_qty,
            ask_qty=ask_qty,
            ts_ms=ts_val,
        )

    def _parse_float(self, data: Dict[str, str], keys: List[str]) -> Optional[float]:
        for key in keys:
            if key in data and data[key] not in (None, ""):
                try:
                    return float(data[key])
                except ValueError:
                    continue
        return None

    def _parse_ts(self, data: Dict[str, str]) -> Optional[int]:
        keys = [
            "eventtime",
            "event_time",
            "timestamp",
            "transacttime",
            "transact_time",
            "closetime",
            "close_time",
            "time",
        ]
        for key in keys:
            if key not in data or data[key] in (None, ""):
                continue
            value = data[key]
            ts = self._coerce_timestamp(value)
            if ts is not None:
                return ts
        return None

    def _coerce_timestamp(self, value: str) -> Optional[int]:
        if isinstance(value, (int, float)):
            ts = int(float(value))
            return ts if ts >= 1e12 else int(ts * 1000)

        text = str(value).strip()
        if not text:
            return None

        # Numeric string (potentially milliseconds already)
        try:
            numeric = float(text)
        except ValueError:
            numeric = None
        if numeric is not None and not (numeric != numeric):  # filter NaN
            if numeric >= 1e12:
                return int(numeric)
            # Treat sub-millisecond precision or seconds as seconds.
            return int(numeric * 1000)

        # Try ISO / datetime strings
        iso_candidate = text.replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(iso_candidate)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return int(dt.timestamp() * 1000)
        except ValueError:
            pass

        for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
            try:
                dt = datetime.strptime(text, fmt)
                dt = dt.replace(tzinfo=timezone.utc)
                return int(dt.timestamp() * 1000)
            except ValueError:
                continue
        return None

    def _collect_files(self, symbol: str) -> List[Path]:
        files: List[Path] = []
        sym = symbol.lower()
        for base in self.search_paths:
            for path in base.rglob("*"):
                if not path.is_file():
                    continue
                name = path.name.lower()
                if sym not in name:
                    continue
                if self.dataset and self.dataset not in name:
                    continue
                if not name.endswith((".csv", ".zip")):
                    continue
                files.append(path)
        files.sort()
        return files
