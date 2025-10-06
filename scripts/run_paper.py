import asyncio
from main.config import Settings
from main.engine import Engine
from main.storage import CSVStorage
from strategies.strategy import Strategy
from pathlib import Path

def main():
    cfg = Settings()
    storage = CSVStorage(Path("./data"))
    # Equal-weight example: aim to deploy half of total notional cap
    target_gross = min(cfg.max_total_notional, cfg.initial_cash) * 0.5
    strat = Strategy(cfg.symbols, target_gross_notional=target_gross)
    eng = Engine(cfg, strat, storage)
    asyncio.run(eng.run())

if __name__ == "__main__":
    main()
