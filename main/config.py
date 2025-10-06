from __future__ import annotations
from pydantic import BaseModel, Field
from typing import List, Optional
import os
from dotenv import load_dotenv

load_dotenv()

def _env_list(key: str, default: List[str]) -> List[str]:
    raw = os.getenv(key)
    if not raw:
        return default
    return [s.strip().lower() for s in raw.split(",") if s.strip()]


def _env_bool(key: str, default: bool = False) -> bool:
    raw = os.getenv(key)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}

class Settings(BaseModel):
    symbols: List[str] = Field(default_factory=lambda: _env_list("SYMBOLS", ["btcusdt", "ethusdt"]))
    quote_ccy: str = os.getenv("QUOTE_CCY", "USDT")
    initial_cash: float = float(os.getenv("INITIAL_CASH", "10000"))
    slippage_bps: float = float(os.getenv("SLIPPAGE_BPS", "1"))

    max_notional_per_symbol: float = float(os.getenv("MAX_NOTIONAL_PER_SYMBOL", "5000"))
    max_total_notional: float = float(os.getenv("MAX_TOTAL_NOTIONAL", "10000"))

    # API keys (required when submitting live orders)
    binance_api_key: Optional[str] = os.getenv("BINANCE_API_KEY") or None
    binance_api_secret: Optional[str] = os.getenv("BINANCE_API_SECRET") or None
    binance_us: bool = Field(default_factory=lambda: _env_bool("BINANCE_US", False))

    @property
    def binance_rest_base(self) -> str:
        return "https://api.binance.us" if self.binance_us else "https://api.binance.com"

    @property
    def binance_ws_host(self) -> str:
        return "stream.binance.us:9443" if self.binance_us else "stream.binance.com:9443"
