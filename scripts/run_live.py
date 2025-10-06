import asyncio
from main.config import Settings
from main.engine import Engine
from main.storage import CSVStorage
from strategies.strategy import Strategy
from pathlib import Path

def main():
    cfg = Settings()
    if not cfg.binance_api_key or not cfg.binance_api_secret:
        raise SystemExit("Provide BINANCE_API_KEY and BINANCE_API_SECRET in .env before running live trading.")
    storage = CSVStorage(Path("./data"))
    target_gross = min(cfg.max_total_notional, cfg.initial_cash) * 0.5
    strat = Strategy(cfg.symbols, target_gross_notional=target_gross)
    eng = Engine(cfg, strat, storage, live_trading=True)
    print("Starting live trading on Binance Spot (real funds)...")
    asyncio.run(eng.run())

if __name__ == "__main__":
    main()
