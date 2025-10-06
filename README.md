# hft-bot-starter

*A minimal, modular “HFT-style” bot skeleton using real, free market data (Binance WebSocket) with a plug-in strategy interface.*

> **Important**: True HFT requires ultra‑low latency, colocated infrastructure and direct market access.  
> This repo is an educational starter that streams **live public crypto data** for **paper trading** or **Binance Spot Testnet** trading.
> Use at your own risk. No financial advice.

## Features
- **Live market data** via **Binance WebSocket `bookTicker`** (free, no API key for data) with opt-in historical replays.
- **Modular architecture**: data, engine, execution, strategy, risk, portfolio.
- **Strategy plug-in**: `strategies/strategy.py` includes a generic **EqualWeightStrategy** example; replace with your own.
- **Paper trading** execution (simulated fills on best bid/ask) + optional **Binance Spot Testnet** execution.
- **Simple persistence**: ticks and fills written to CSV under `./data/`.

## Quickstart

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# (Optionally) edit .env to change symbols, initial cash, and enable testnet keys.

# Run live paper-trading with real-time data
python scripts/run_paper.py

# Optionally: run against Binance Spot Testnet (requires keys in .env)
python scripts/run_live_testnet.py
```

### What you get out-of-the-box
- A working event loop that streams `bookTicker` for each configured symbol.
- A **paper execution** engine that simulates fills at best bid/ask with simple slippage.
- A **strategy interface** that emits order requests. Default strategy is equal-weight rebalancing.
- **Risk checks** (position notional caps, per-symbol limits).
- **CSV logs** in `./data/ticks_*.csv` and `./data/fills.csv`.

### Notes
- **Symbols** are Binance spot symbols (e.g., `btcusdt`, `ethusdt`). They must be lowercase in the config.
- For **Testnet** trading, create keys at <https://testnet.binance.vision/> and set `BINANCE_API_KEY`, `BINANCE_API_SECRET` and `USE_TESTNET=true` in `.env`.
- This code avoids paid / rate-limited REST feeds and uses the public WebSocket for real-time best bid/ask.
- This project is educational. Trading crypto or any asset involves significant risk.

### Switching between live data and Binance Vision replays

If you are waiting on Binance API approval (or just want to backtest), you can replay archived
`bookTicker` data from <https://data.binance.vision/>.

Set the following environment variables (e.g. in `.env`) to enable the replay stream:

```
DATA_SOURCE=vision
BINANCE_VISION_DATA_DIR=./data/binance_vision   # optional, defaults to ./data/binance_vision
BINANCE_VISION_SPEEDUP=4                        # optional, speeds up playback
BINANCE_VISION_LOOP=false                       # optional, stop at end of dataset
```

Then download the desired monthly archives (e.g. `BTCUSDT-bookTicker-2024-01.zip`) and place the
`.zip` or `.csv` files inside the folder referenced by `BINANCE_VISION_DATA_DIR`. The loader matches
files that contain both the symbol name and dataset name (`bookTicker` by default).

Run the paper engine as usual:

```
python scripts/run_paper.py
```

The engine will consume the historical ticks locally instead of the live WebSocket feed, keeping the
rest of the pipeline identical. Set `DATA_SOURCE=live` (or remove the variable) to switch back to
real-time streaming.

## Repo Layout

```
  hft_bot/
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
        vision_stream.py
    execution/
      paper.py
      binance_exec.py
    strategies/
      __init__.py
      strategy.py   # <- replace with your own logic
  scripts/
    run_paper.py
    run_live_testnet.py
  data/                # runtime CSV outputs (created automatically)
  .env.example
  requirements.txt
  README.md
```
