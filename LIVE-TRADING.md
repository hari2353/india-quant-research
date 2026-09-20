# Zerodha Live Integration Runbook

The live path is implemented, but it is disabled by default. This document describes the controlled workflow.

## Safety Boundary

- Only NSE CNC long positions are supported.
- Managed universe: `NIFTYBEES`, `GOLDBEES`, `LIQUIDBEES`.
- No futures, options, margin, shorting or intraday product.
- The default order type is `LIMIT`.
- Market orders require a separate explicit environment flag.
- Each order is capped at `INDIA_QUANT_MAX_ORDER_VALUE`.
- The total plan is capped at `INDIA_QUANT_MAX_TOTAL_ORDER_VALUE`.
- Existing unmanaged NSE positions block execution by default.
- Broker positions are re-read immediately before order submission.
- Position drift invalidates the plan.
- Every order is recorded in a local SQLite audit ledger.
- A retry cannot submit the same plan leg twice.
- The kill switch is active unless explicitly disabled.

This software is not investment advice. Live trading can lose money, including through data errors, broker outages,
network failures, partial fills, rejected orders and market gaps.

## Install

```powershell
cd F:\trading-research
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .[dev,data,broker]
```

## Environment

Set these in the local process environment, not in source control:

```powershell
$env:KITE_API_KEY = "your_kite_api_key"
$env:KITE_ACCESS_TOKEN = "fresh_access_token"
$env:INDIA_QUANT_LIVE_CAPITAL = "50000"
$env:INDIA_QUANT_MAX_ORDER_VALUE = "15000"
$env:INDIA_QUANT_MAX_TOTAL_ORDER_VALUE = "50000"
$env:INDIA_QUANT_MAX_DATA_AGE_DAYS = "2"
$env:INDIA_QUANT_ORDER_TYPE = "LIMIT"
$env:INDIA_QUANT_PRODUCT = "CNC"
$env:INDIA_QUANT_KILL_SWITCH = "ON"
```

The access token is session-sensitive and must be regenerated according to the official Kite Connect login flow.
Do not paste it into chat, commit it, or put it into a `.env` file that could be uploaded.

## Plan First

Download a current permitted data snapshot. Do not use an old historical file for live planning.

```powershell
$env:PYTHONPATH = "src"
python -m india_quant.cli download --out data\prices.csv --years 3
```

Generate a plan. This reads broker positions and quotes but does not place orders.

```powershell
python -m india_quant.cli live-plan `
  --prices data\prices.csv `
  --strategy balanced `
  --plan live\balanced-plan.json
```

Review `live\balanced-plan.json` manually. Confirm:

- Symbol is one of the three managed ETFs
- Side and quantity are correct
- Limit prices are current enough
- Total order value is within the intended capital
- No unmanaged position warning was bypassed

## Approval

Approval writes only the plan hash to a local file.

```powershell
python -m india_quant.cli approve-plan `
  --plan live\balanced-plan.json `
  --approval live\balanced-plan.approved
```

If the plan changes, the hash changes and the old approval becomes invalid.

## Dry Run

There is no live API dry-run endpoint in this command. The safe dry run is to generate and review a plan without
setting the live execution gate. `live-execute` will refuse to proceed while the gate is disabled.

## Live Execution Gate

Only after reviewing the plan and approval file, disable the kill switch and enable the live acknowledgment in the
same process environment:

```powershell
$env:INDIA_QUANT_KILL_SWITCH = "OFF"
$env:INDIA_QUANT_LIVE_TRADING = "I_UNDERSTAND_LIVE_RISK"
python -m india_quant.cli live-execute `
  --plan live\balanced-plan.json `
  --approval live\balanced-plan.approved `
  --db live\live.db
```

For the first live run, use the smallest practical plan and remain present to monitor the broker order book and
fills. The command records submission IDs, but a submitted order is not the same as a filled order. Fill and position
reconciliation must be checked in the broker console after execution.

To immediately block execution again:

```powershell
$env:INDIA_QUANT_KILL_SWITCH = "ON"
```

## Required Before First Live Order

1. Complete at least three months of forward paper trading with current data.
2. Verify the current Kite Connect pricing, API limits and data-use terms.
3. Confirm all three managed instruments are liquid and tradable in the account.
4. Start with no unmanaged NSE positions or set aside an explicit reconciliation process.
5. Confirm broker positions and available funds manually.
6. Use a fresh plan and approval hash for every rebalance.
7. Review every submitted order and its final fill status.
8. Keep `live\live.db` backed up and access-controlled.

No live credentials are required to continue testing the system. If you later choose to activate it, provide the
credentials only through local environment variables on your machine.
