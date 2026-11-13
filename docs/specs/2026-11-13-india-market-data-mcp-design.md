# India Market-Data MCP Server — Design

Date: 2026-11-13. Status: approved by repo owner (approach A picked from three).

## Intent

Let MCP agents (WorkBuddy, Claude Desktop, Cursor) ask this repository for India ETF
market data with natural language, using the same read-only research adapter the repo
already ships. This exists so external agents can pull a quote, price history, or the
research universe without importing Python code.

## Why

The repo has auditable research + paper trading for NIFTYBEES.NS, GOLDBEES.NS and
LIQUIDBEES.NS. Futu/moomoo (the data source behind Tencent WorkBuddy) does not cover
NSE/BSE. A local MCP server gives agents India coverage through this repo instead.

## Goals

- 3 read-only tools over stdio: `get_quote`, `get_history`, `list_universe`.
- Reuse `india_quant.data.download_yahoo_daily` and the Yahoo chart endpoint. No new
  data code, no duplicate cleaning logic.
- Offline-safe test suite: unit + integration tests run with no network, using
  monkeypatched transport and `make_fixture_prices`.
- One true end-to-end test: real server process over stdio, real MCP client, real
  Yahoo call (skipped automatically when offline).
- Tool descriptions state the data policy: personal research only, Yahoo is delayed
  and unlicensed, no trading use.

## Non-goals / anti-goals

- No order placement, no broker surface, no Zerodha tools. Research data only.
- No hosted HTTP deployment in this change (approach B deferred until a consumer
  needs it).
- No new data-cleaning code. The server is a thin adapter over `data.py`.

## Constraints

- Python >= 3.10 (repo floor). Dependency added as extra: `mcp = ["fastmcp>=2"]`.
- Server lives in `mcp/server.py` per owner request; tests live in `tests/` per repo
  convention (`pythonpath` gains `mcp`).
- stdio transport only (house pattern from skills-mcp: `FastMCP`, plain functions,
  `mcp.tool(...)`, `mcp.run()`).

## Approaches considered

| Approach | Verdict |
|---|---|
| A. Local stdio FastMCP server wrapping data.py | Chosen: smallest complete change, works offline, no hosting. |
| B. Hosted streamable-HTTP server | Deferred: only if WorkBuddy proves HTTP-only or a remote consumer appears. |
| C. Wait for Futu India coverage | Rejected: no India feed announced; nothing to test meanwhile. |

## Interfaces (locked)

- `get_quote(symbols: list[str]) -> dict` — latest Yahoo chart meta per symbol:
  `{"symbol": {"price": float, "currency": str, "time": int}}`.
- `get_history(symbols: list[str], start: str, end: str) -> list[dict]` — cleaned daily
  OHLCV rows (`date, symbol, open, high, low, close, adj_close, volume`) via
  `download_yahoo_daily`; dates are `YYYY-MM-DD`; max 5 symbols, max 3 years span.
- `list_universe() -> dict` — the research universe with symbol roles
  (NIFTYBEES large-cap equity, GOLDBEES gold, LIQUIDBEES liquid parking).
- All tools get `readOnlyHint`; errors are `ValueError` with the valid universe in the
  message so the agent can self-correct.

## What is left to the builder

- Exact JSON shapes of list/dict returns beyond the keys named above.
- Whether `get_quote` also returns `previous_close` (optional, only if the meta has it).
