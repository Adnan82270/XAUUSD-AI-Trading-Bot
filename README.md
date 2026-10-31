# XAUUSD-AI-Trading-Bot

An analysis-only, rule-based XAUUSD market analysis engine designed for
development with Exness MT5 Demo data later.

## Safety boundary

Replit does **not** connect directly to MetaTrader 5 and does not place,
modify, or close real or demo trades. An authenticated Windows sender can
forward read-only MT5 DEMO quotes and candles. The app analyzes OHLCV candles and returns
`BUY`, `SELL`, or `WAIT` as an analysis classification. Stop-loss and
take-profit values are reference levels, not orders.

Live-account data, news analysis, and automated trading are intentionally out
of scope for this version. Historical backtesting is
available only for user-supplied CSV data with at least 500 candles.

## Modules

- `xauusd_ai_trading_bot/market_data.py` — validates OHLCV data and loads CSV
  or bundled sample candles.
- `xauusd_ai_trading_bot/indicators.py` — calculates EMA 20/50, RSI 14, ATR
  14, MACD, and basic volatility fields.
- `xauusd_ai_trading_bot/strategy.py` — explains trend, momentum, and basic
  breakout conditions using deterministic rules.
- `xauusd_ai_trading_bot/risk.py` — calculates ATR-based reference levels with
  safe, optional risk configuration.
- `xauusd_ai_trading_bot/signal.py` — returns a structured signal dataclass.
- `xauusd_ai_trading_bot/backtest.py` — runs a sequential historical
  backtest with next-candle entries, ATR exits, costs, and CSV trade output.
- `xauusd_ai_trading_bot/import_data.py` — validates and summarizes a
  user-supplied historical CSV before a backtest.
- `xauusd_ai_trading_bot/mt5_bridge.py` — disconnected MT5 desktop bridge
  protocols and hard-disabled safe placeholders.
- `xauusd_ai_trading_bot/broker_adapter.py` — DEMO/LIVE safety configuration
  and separated broker capabilities.
- `xauusd_ai_trading_bot/main.py` — prints the latest market analysis report.
- `xauusd_ai_trading_bot/analysis_service.py` — dashboard-only analysis worker
  that emits strategy snapshots without market prices.
- `artifacts/api-server/src/routes/analysis.ts` — analysis service status and
  Start/Stop API; it does not expose broker execution.
- `artifacts/api-server/src/routes/broker.ts` — read-only broker status API.
- `artifacts/api-server/src/routes/market-data.ts` — authenticated read-only
  Windows DEMO market-data ingestion endpoint.
- `scripts/mt5_market_data_uploader.py` — HTTPS uploader for the Windows JSON
  file; it does not connect to MT5 or submit orders.
- `artifacts/xauusd-dashboard/` — responsive web dashboard for Android and
  desktop.
- `artifacts/mockup-sandbox/src/XauusdSafetyDashboard.tsx` — safety dashboard
  showing connection and data-origin state.

## Run

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

Run against the bundled sample:

```bash
python -m xauusd_ai_trading_bot.main
```

Run against a CSV with columns `time,open,high,low,close,volume`:

```bash
python -m xauusd_ai_trading_bot.main --csv path/to/xauusd.csv --timeframe H1
```

## Web dashboard

The XAUUSD Bot Dashboard uses the existing analysis strategy and provides
Start/Stop controls for the analysis worker only. In the Replit workspace, start
the `artifacts/api-server: API Server` and `artifacts/xauusd-dashboard: web`
workflows, then open the dashboard preview on Android or desktop. Install Python
dependencies first if this project has not been set up yet:

```bash
python -m pip install -r requirements.txt
```

Tap **Start analysis** in the dashboard to run a snapshot every 15 seconds; tap
**Stop analysis** to stop only that worker. Fresh, authenticated Windows MT5
DEMO quotes are displayed as bridge-reported real data; Replit does not
independently inspect the terminal. Missing or stale data stays hidden and
shows `NOT_CONNECTED`. The existing bundled sample remains clearly labeled
synthetic when used for analysis and is never shown as a quote. LIVE and all
broker order execution remain disabled.

Check the app and safety tests with:

```bash
python -m unittest discover -s tests -v
pnpm --filter @workspace/api-server run typecheck
pnpm --filter @workspace/xauusd-dashboard run typecheck
PORT=20194 BASE_PATH=/ pnpm --filter @workspace/xauusd-dashboard run build
```

## Import historical CSV data

The bot does not download or invent market data. Provide your own historical
XAUUSD CSV file with these required columns:

```text
time,open,high,low,close,volume
```

Validate and summarize the file before backtesting:

```bash
python -m xauusd_ai_trading_bot.import_data \
  --csv path/to/xauusd.csv
```

The import workflow checks timestamps, missing/non-numeric values, duplicate
timestamps, strictly increasing candle order, positive OHLC prices, valid
high/low relationships, and non-negative volume. It prints the first candle
timestamp, last candle timestamp, total candle count, and whether the file
has the minimum 500 candles required for backtesting.

The bundled `xauusd_ai_trading_bot/data/sample_xauusd.csv` is synthetic
development data and is clearly labeled as such. It contains only 120 candles,
so it is not eligible for a meaningful backtest.

### Upload a CSV from Replit on Android

1. Open the Replit mobile app and open this project.
2. Open the **Project Editor** and show the file tree.
3. Open the file-tree menu and choose **Upload file**. Replit's mobile
   editor supports uploading files and folders from the file tree.
4. Select your historical CSV from the Android file picker.
5. Choose the project `uploads/` folder as the destination if Replit asks for
   a destination, then confirm the upload.
6. Confirm the uploaded filename in the file tree. For example, a file named
   `xauusd_h1.csv` will be available at:

   ```text
   uploads/xauusd_h1.csv
   ```

The commands below resolve and print the full absolute path before the
backtest starts. If the path does not exist, the command stops with an error;
it never falls back to the synthetic sample.

Run a historical backtest on the validated user-supplied CSV:

Configure execution costs and output path:

```bash
python -m xauusd_ai_trading_bot.backtest \
  --csv path/to/xauusd.csv \
  --spread 0.20 \
  --slippage 0.05 \
  --units 1 \
  --output reports/xauusd_trades.csv
```

The backtest prints total trades, wins/losses, win rate, net P/L, max
drawdown, profit factor, average win/loss, and writes the trade-by-trade CSV
report. Spread is the full bid/ask spread in XAUUSD price units; slippage is
adverse price movement per fill.

## MT5 bridge architecture

The read-only Windows MT5 DEMO data bridge and HTTPS setup are documented in
[`docs/mt5-desktop-bridge.md`](docs/mt5-desktop-bridge.md). Replit does not
connect directly to MT5; the authenticated feed exposes only XAUUSDm quotes
and exactly 100 M5 candles. The system does not accept trading credentials,
account data, LIVE trading, or broker orders.

Backtest details:

- Each strategy signal is evaluated using only the candle prefix ending at
  that candle's close.
- Entries execute at the next candle's open with configurable spread and
  slippage.
- Stop Loss and Take Profit are checked against the entry candle and later
  candle high/low values.
- If both levels are touched in one candle, Stop Loss is assumed to trigger
  first.
- A minimum of 500 candles is required before the backtest runs.
- This is a deterministic simulation only. It does not place real or demo
  trades.
- Historical results do not guarantee future performance. No result from
  synthetic or historical data should be treated as a profitability claim.