# India Quant Research

An open-source, CPU-friendly research and paper-trading foundation for a small Indian ETF portfolio.

The default operating mode is **research and paper trading**. Live broker execution is an opt-in integration
behind a plan-review-approval gate and is not enabled by this repository. Never commit broker credentials, tokens,
market-data files, SQLite ledgers or generated reports.

This is **not financial advice** and it does not promise returns. The default configuration is deliberately
conservative:

- INR 50,000 starting capital
- long-only cash instruments
- no leverage, futures, options, margin or short selling
- whole-share quantities, with uninvested cash recorded explicitly
- monthly rebalance, using only information available before execution
- conservative transaction-cost and slippage assumptions
- walk-forward research and stress testing before any paper or live use

The first research universe is:

| Symbol | Role |
|---|---|
| `NIFTYBEES.NS` | Indian large-cap equity ETF |
| `GOLDBEES.NS` | Gold ETF |
| `LIQUIDBEES.NS` | Liquid/low-duration parking asset |

Yahoo Finance is used only as a research-data adapter. It is not an exchange data licence and should not be
treated as a production market-data feed. For Zerodha execution, use the official Kite Connect API and verify
the current pricing, data rights and SEBI/broker requirements before connecting an account.

## Run

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .[dev,data]
pytest
india-quant download --out data\prices.csv
india-quant backtest --prices data\prices.csv --out reports
india-quant paper-run --prices data\prices.csv --db paper\paper.db --out paper\reports --date 2026-09-18
```

If network access or Yahoo data is unavailable, the test suite still runs against deterministic fixtures:

```powershell
pytest
```

## Research rules

The optimizer is not allowed to select a strategy by in-sample return alone. A candidate is only considered
research-worthy when it is compared with simple baselines, uses walk-forward splits, includes costs, and reports
drawdown and stress outcomes.

## Paper trading

`paper-run` is local simulation only. It does not contact Zerodha, create API keys, or place orders. It uses the
same whole-share, no-leverage and cost model as the backtester and stores an append-only operational ledger in
SQLite. The default paper candidates are `equal_weight` and `balanced`.

Replay a historical dataset into a fresh paper ledger:

```powershell
Remove-Item -LiteralPath paper\replay.db -ErrorAction SilentlyContinue
$env:PYTHONPATH = "src"
python -m india_quant.cli paper-run --prices data\prices.csv --db paper\replay.db --out paper\replay-report --replay
```

For actual forward paper trading, download a fresh permitted research snapshot and run once per completed market
session. Do not run `--replay` on a live ledger. The process is idempotent for each strategy/date, so a retry does
not duplicate fills.

The system must complete at least three months of forward paper trading with no ledger/reconciliation errors,
no risk-limit violations caused by software defects, and results consistent with the historical risk envelope
before a first live order is considered. The Zerodha integration is implemented behind a plan-review-approval-live
execution gate. See [`LIVE-TRADING.md`](LIVE-TRADING.md). No credentials are required for testing.

Live commands are:

```powershell
india-quant live-plan --prices data\prices.csv --strategy balanced --plan live\plan.json
india-quant approve-plan --plan live\plan.json --approval live\plan.approved
india-quant live-execute --plan live\plan.json --approval live\plan.approved --db live\live.db
```

The last command refuses to run unless the explicit live acknowledgment, fresh access token, disabled kill switch,
matching approval hash and broker-position reconciliation all pass.

## License

MIT
