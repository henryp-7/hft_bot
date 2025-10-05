import asyncio
from hftbot.config import Settings
from hftbot.engine import Engine
from hftbot.storage import CSVStorage
from hftbot.strategies.strategy import Strategy
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
