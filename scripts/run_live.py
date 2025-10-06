import asyncio
from main.config import Settings
from main.engine import Engine
from main.storage import CSVStorage
from strategies.strategy import Strategy
from pathlib import Path

def main():
    cfg = Settings()
    if not cfg.enable_live_trading:
        raise SystemExit("Set ENABLE_LIVE_TRADING=true in your environment to place live orders.")
    if not cfg.binance_api_key or not cfg.binance_api_secret:
        raise SystemExit("Provide BINANCE_API_KEY and BINANCE_API_SECRET in .env before running live mode.")
    storage = CSVStorage(Path("./data"))
    target_gross = min(cfg.max_total_notional, cfg.initial_cash) * 0.5
    strat = Strategy(cfg.symbols, target_gross_notional=target_gross)
    eng = Engine(cfg, strat, storage)
    venue = "Binance Spot Testnet" if cfg.use_testnet else "Binance Spot"
    print(f"Starting live trading against {venue}...")
    asyncio.run(eng.run())

if __name__ == "__main__":
    main()
