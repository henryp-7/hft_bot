# hft-bot-starter

*A minimal, modular “HFT-style” bot skeleton using real, free market data (Binance WebSocket) with a plug-in strategy interface.*

> **Important**: True HFT requires ultra‑low latency, colocated infrastructure and direct market access.
> This repo is an educational starter that streams **live public crypto data** for **paper trading** or optional **Binance Spot/Testnet** execution.
> Use at your own risk. No financial advice.

## Features
- **Live market data** via **Binance WebSocket `bookTicker`** (free, no API key for data).
- **Modular architecture**: data, engine, execution, strategy, risk, portfolio.
- **Strategy plug-in**: `strategies/strategy.py` includes a generic **EqualWeightStrategy** example; replace with your own.
- **Paper trading** execution (simulated fills on best bid/ask) + optional **Binance Spot/Testnet** order routing.
- **Simple persistence**: ticks and fills written to CSV under `./data/`.

## Quickstart

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env to choose symbols, risk limits, and whether to enable live trading.

# Run live paper-trading with real-time data
python scripts/run_paper.py

# Run live trading (Testnet or production, depending on USE_TESTNET and ENABLE_LIVE_TRADING)
python scripts/run_live.py
```

### What you get out-of-the-box
- A working event loop that streams `bookTicker` for each configured symbol.
- A **paper execution** engine that simulates fills at best bid/ask with simple slippage.
- A **strategy interface** that emits order requests. Default strategy is equal-weight rebalancing.
- **Risk checks** (position notional caps, per-symbol limits).
- **CSV logs** in `./data/ticks_*.csv` and `./data/fills.csv`.

### Notes
- **Symbols** are Binance spot symbols (e.g., `btcusdt`, `ethusdt`). They must be lowercase in the config.
- For **Testnet** trading, create keys at <https://testnet.binance.vision/> and set `USE_TESTNET=true`, `ENABLE_LIVE_TRADING=true`, and provide `BINANCE_API_KEY` / `BINANCE_API_SECRET` in `.env`.
- For **production** trading, leave `USE_TESTNET=false`, set `ENABLE_LIVE_TRADING=true`, and provide production keys. **Understand the risks before enabling this.**
- This code avoids paid / rate-limited REST feeds and uses the public WebSocket for real-time best bid/ask.
- This project is educational. Trading crypto or any asset involves significant risk.

## Repo Layout

```
hft-bot-starter/
  main/
    __init__.py
    engine.py
    config.py
    utils.py
    models.py
    portfolio.py
    risk.py
    storage.py
    datafeeds/
      __init__.py
      live_stream.py
  execution/
    paper.py
    binance_exec.py
  strategies/
    __init__.py
    strategy.py   # <- replace with your own logic
  scripts/
    run_paper.py
    run_live.py
  data/                # runtime CSV outputs (created automatically)
  .env.example
  requirements.txt
  README.md
```
