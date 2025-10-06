from __future__ import annotations
import time
from collections import deque
from typing import Dict, List

from main.models import MarketTick, OrderRequest, OrderSide, OrderType
from main.portfolio import Portfolio

class Strategy:
    """
    OBI + Intraday Momentum Strategy for BTC/ETH (or any symbols with L1 sizes).
    - Uses top-of-book size imbalance and a short-horizon momentum filter.
    - Converts a target notional budget into trade quantity.
    - Respects a per-symbol cooldown and simple position caps.

    Parameters to tune:
      obi_thresh:      minimum |OBI| to act (e.g., 0.55)
      mom_lookback:    number of ticks for momentum lookback (e.g., 15)
      mom_thresh:      minimum absolute momentum (return) to confirm (e.g., 0.0005 = 5 bps)
      trade_frac:      fraction of per-symbol target gross used per trade (e.g., 0.20)
      cooldown_sec:    min seconds between orders per symbol
      max_pos_mult:    cap absolute position notional at (max_pos_mult * per-symbol target)
    """
    def __init__(
        self,
        symbols: List[str],
        target_gross_notional: float,
        obi_thresh: float = 0.55,
        mom_lookback: int = 15,
        mom_thresh: float = 0.0005,   # 5 bps momentum gate
        trade_frac: float = 0.20,
        cooldown_sec: float = 1.0,
        max_pos_mult: float = 1.50,
        min_trade_notional: float = 5.0,  # avoid dust / fees dominance
    ):
        self.symbols = [s.lower() for s in symbols]
        self.target_gross = float(target_gross_notional)
        self.obi_thresh = float(obi_thresh)
        self.mom_lookback = int(mom_lookback)
        self.mom_thresh = float(mom_thresh)
        self.trade_frac = float(trade_frac)
        self.cooldown_sec = float(cooldown_sec)
        self.max_pos_mult = float(max_pos_mult)
        self.min_trade_notional = float(min_trade_notional)

        self.last_action_ts: Dict[str, float] = {s: 0.0 for s in self.symbols}
        self.mid_hist: Dict[str, deque] = {s: deque(maxlen=self.mom_lookback) for s in self.symbols}

    def _obi(self, tick: MarketTick) -> float:
        # OBI = (bid_qty - ask_qty) / (bid_qty + ask_qty)
        b, a = (tick.bid_qty or 0.0), (tick.ask_qty or 0.0)
        denom = b + a
        if denom <= 0:
            return 0.0
        return (b - a) / denom

    def _momentum(self, s: str, mid: float) -> float:
        hist = self.mid_hist[s]
        if len(hist) < self.mom_lookback:
            return 0.0
        old = hist[0]
        if old <= 0:
            return 0.0
        return (mid - old) / old

    def _cap_qty_by_position(self, s: str, qty: float, mid: float, portfolio: Portfolio, per_symbol_budget: float) -> float:
        # Cap absolute position notional to max_pos_mult * per-symbol target
        pos = portfolio.positions.get(s)
        curr_notional = (pos.qty * mid) if pos else 0.0
        max_abs = self.max_pos_mult * per_symbol_budget
        # Desired new notional after this order:
        desired = curr_notional + (qty * mid)
        if abs(desired) > max_abs:
            # scale qty down to hit the cap
            allowed_delta = (max_abs * (1 if desired >= 0 else -1)) - curr_notional
            qty_cap = allowed_delta / mid
            return qty_cap
        return qty

    def generate_orders(self, tick: MarketTick, portfolio: Portfolio) -> List[OrderRequest]:
        s = tick.symbol
        now = time.time()

        # Maintain momentum history
        self.mid_hist[s].append(tick.mid)
        mom = self._momentum(s, tick.mid)
        obi = self._obi(tick)

        # Cooldown
        if (now - self.last_action_ts.get(s, 0.0)) < self.cooldown_sec:
            return []

        # Require alignment: OBI and momentum point the same way and exceed thresholds
        long_sig  = (obi >= self.obi_thresh) and (mom >= self.mom_thresh)
        short_sig = (obi <= -self.obi_thresh) and (mom <= -self.mom_thresh)
        if not (long_sig or short_sig):
            return []

        # Per-symbol budget and trade sizing
        n = max(1, len(self.symbols))
        per_symbol_budget = self.target_gross / n
        trade_notional = max(self.min_trade_notional, per_symbol_budget * self.trade_frac)

        side = OrderSide.BUY if long_sig else OrderSide.SELL
        raw_qty = trade_notional / max(tick.mid, 1e-12)
        qty = self._cap_qty_by_position(s, raw_qty if side == OrderSide.BUY else -raw_qty, tick.mid, portfolio, per_symbol_budget)

        # If capped to near-zero by risk cap, skip
        if abs(qty) * tick.mid < self.min_trade_notional:
            return []

        self.last_action_ts[s] = now
        return [OrderRequest(symbol=s, side=side, order_type=OrderType.MARKET, qty=abs(qty))]
