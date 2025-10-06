import asyncio
from core.config import Settings
from core.engine import Engine
from core.storage import CSVStorage
from strategies.strategy import Strategy
from pathlib import Path

def main():
    cfg = Settings()
    if not cfg.use_testnet or not cfg.binance_api_key or not cfg.binance_api_secret:
        raise SystemExit("Set USE_TESTNET=true and provide BINANCE_API_KEY/SECRET in .env to use this script.")
    storage = CSVStorage(Path("./data"))
    target_gross = min(cfg.max_total_notional, cfg.initial_cash) * 0.5
    strat = Strategy(cfg.symbols, target_gross_notional=target_gross)
    eng = Engine(cfg, strat, storage)
    asyncio.run(eng.run())

if __name__ == "__main__":
    main()
