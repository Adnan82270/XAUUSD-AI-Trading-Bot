# XAUUSD-AI-Trading-Bot

An analysis-only, rule-based XAUUSD market analysis engine that reads OHLCV
data and produces explainable BUY, SELL, or WAIT classifications.

## Run & Operate

- `python -m xauusd_ai_trading_bot.main` — run analysis against bundled sample data
- `python -m xauusd_ai_trading_bot.main --csv path/to/xauusd.csv` — analyze a CSV
- `python -m xauusd_ai_trading_bot.import_data --csv path/to/xauusd.csv` — validate and summarize a user-supplied CSV
- `python -m xauusd_ai_trading_bot.backtest --csv path/to/xauusd.csv` — run a 500+ candle historical backtest
- `python -m xauusd_ai_trading_bot.analysis_service --interval 15` — run the dashboard analysis worker (fresh bridge candles when supplied, otherwise labeled sample data)
- `python scripts/mt5_market_data_uploader.py --file mt5_market_data.json --once` — forward a Windows JSON file over HTTPS
- `python -m pip install -r requirements.txt` — install Python dependencies
- `pnpm --filter @workspace/api-server run dev` — run the API server (port 8080)
- `pnpm --filter @workspace/xauusd-dashboard run dev` — run the mobile-friendly dashboard
- `python -m unittest discover -s tests -v` — run Python safety and analysis tests
- `pnpm run typecheck` — full typecheck across all packages
- `pnpm run build` — typecheck + build all packages
- `pnpm --filter @workspace/api-spec run codegen` — regenerate API hooks and Zod schemas from the OpenAPI spec
- `pnpm --filter @workspace/db run push` — push DB schema changes (dev only)
- Required env: `DATABASE_URL` — Postgres connection string

## Stack

- Python 3.10+, pandas, NumPy
- pnpm workspaces, Node.js 24, TypeScript 5.9
- API: Express 5
- DB: PostgreSQL + Drizzle ORM
- Validation: Zod (`zod/v4`), `drizzle-zod`
- API codegen: Orval (from OpenAPI spec)
- Build: esbuild (CJS bundle)

## Where things live

- `xauusd_ai_trading_bot/` — Python analysis package
- `xauusd_ai_trading_bot/data/sample_xauusd.csv` — deterministic sample OHLCV data
- `xauusd_ai_trading_bot/backtest.py` — sequential, next-candle-entry backtester
- `xauusd_ai_trading_bot/import_data.py` — historical CSV validation and summary
- `xauusd_ai_trading_bot/mt5_bridge.py` — future MT5 desktop bridge interfaces
- `xauusd_ai_trading_bot/broker_adapter.py` — safe DEMO/LIVE broker boundary
- `uploads/` — destination for user-uploaded historical CSV files
- `docs/mt5-desktop-bridge.md` — read-only Windows MT5 DEMO bridge setup and payload contract
- `requirements.txt` — Python runtime dependencies
- `README.md` — usage and safety boundary

## Architecture decisions

- CSV is the first market-data adapter so analysis can be developed without MT5.
- Indicators are calculated in pandas rather than a trading library to keep the
  formula inputs visible and the later MT5 adapter isolated.
- Strategy output is constrained to BUY, SELL, or WAIT and includes explainable
  evidence.
- Risk calculations return reference levels only; the default risk percentage
  is unset and no order-management code exists.
- Backtesting evaluates each strategy prefix independently so signal creation
  and next-candle entry timing remain explicit and look-ahead safe.
- Historical backtests require at least 500 validated candles; the bundled
  sample is synthetic and intentionally too short for backtesting.
- Broker mode defaults to DEMO, but the current bridge remains disconnected,
  market data is read-only, LIVE mode is locked, and order execution is
  hard-disabled.
- A CONNECTED market-data status means a fresh HMAC-authenticated Windows
  payload passed validation; Replit does not independently inspect the MT5
  terminal or verify the user's account mode.

## Product

The CLI loads XAUUSD candles, computes EMA/RSI/ATR/MACD and volatility,
classifies the latest market state, and prints a readable signal report with
reference risk levels.

## User preferences

Keep this project analysis-only until a later request explicitly expands the
scope after testing.

## Gotchas

- The bundled CSV is development sample data, not live or broker-verified data.
- Indicator warm-up requires at least 55 candles; insufficient history returns
  WAIT rather than guessing.
- The project intentionally does not import MetaTrader 5 or expose order calls.
- Replit cannot connect directly to an MT5 desktop terminal on Android; read-only
  market data must be forwarded by the separate Windows uploader.
- Never request or store Exness passwords, investor passwords, account
  credentials, or bridge tokens in chat or source files.
- Backtest costs are configured in XAUUSD price units, not broker-specific
  points or lot contracts.
- CSV import rejects duplicate timestamps and out-of-order candles rather than
  silently sorting or dropping them.
- Backtesting resolves and prints the absolute CSV path before running and
  never falls back to bundled data when a supplied path is missing.

## Pointers

- See the `pnpm-workspace` skill for workspace structure, TypeScript setup, and package details
