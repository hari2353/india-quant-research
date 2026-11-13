# India Market-Data MCP Server Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose the repo's Yahoo research adapter as 3 read-only MCP tools over stdio.

**Architecture:** `mcp/server.py` defines a `FastMCP` server whose tool functions call
`india_quant.data.download_yahoo_daily` and the Yahoo chart endpoint. Tests monkeypatch
the transport so the suite runs offline; one subprocess-based E2E test exercises the
real stdio server with a real MCP client.

**Tech Stack:** Python 3.10+, `fastmcp>=2` (extra `mcp`), pandas, pytest.

**Spec:** `docs/specs/2026-11-13-india-market-data-mcp-design.md`

## Global Constraints

- Read-only tools only; no broker or order surface (spec Non-goals).
- Tool descriptions carry the data policy: personal research only, Yahoo delayed/unlicensed (spec Goals).
- Server file: `mcp/server.py`, no `__init__.py` in `mcp/` (avoids shadowing the `mcp` SDK package; tests import it by file path).
- House pattern: `FastMCP`, plain functions registered with `mcp.tool(...)`, `mcp.run()` under `__main__`.
- Caps locked by spec: max 5 symbols, max 3-year span for `get_history`.
- Errors are `ValueError` and name the valid universe so agents can self-correct.

## Review Focus

- Unknown/invalid symbol → `ValueError` listing NIFTYBEES.NS, GOLDBEES.NS, LIQUIDBEES.NS (test: `test_get_quote_rejects_unknown_symbol`).
- `start > end` or malformed date → `ValueError`, not a silent empty list (test: `test_get_history_rejects_bad_dates`).
- 6 symbols requested → `ValueError` stating the 5-symbol cap (test: `test_get_history_enforces_symbol_cap`).
- Yahoo returns no data → `ValueError` naming the symbol, propagated as a tool error not a crash (test: `test_get_history_empty_yahoo_result`).
- Offline machine → E2E skips with `offline`, suite still green (checked by running `pytest` without network).

---

### Task 1: Tool functions, TDD

**Files:**
- Create: `mcp/server.py`
- Test: `tests/test_mcp_server.py`

**Interfaces:**
- Consumes: `india_quant.data.download_yahoo_daily(symbols, start: date, end: date) -> pd.DataFrame`, `india_quant.data.PRICE_COLUMNS`.
- Produces: `mcp = FastMCP("india-quant-research", instructions=...)`; `get_quote(symbols: list[str]) -> dict`; `get_history(symbols: list[str], start: str, end: str) -> list[dict]`; `list_universe() -> dict`; `_fetch_chart(symbol: str) -> dict` (transport seam for tests).

- [ ] **Step 1: Write failing tests** — unit tests in `tests/test_mcp_server.py`: load module by file path with `importlib.util.spec_from_file_location`; monkeypatch `_fetch_chart` / `download_yahoo_daily`; assert quote mapping shape `{"NIFTYBEES.NS": {"price": float, "currency": "INR", "time": int}}`, history row keys `date/symbol/open/high/low/close/adj_close/volume`, universe returns exactly the 3 spec symbols with roles, and all four Review-Focus error paths.
- [ ] **Step 2: Run** `pytest tests/test_mcp_server.py -v` → expected FAIL (module file missing).
- [ ] **Step 3: Implement** `mcp/server.py`: constants `UNIVERSE`, `MAX_SYMBOLS = 5`, `MAX_SPAN_DAYS = 1100`; `get_quote` parses one chart call per symbol from meta (`regularMarketPrice`, `currency`, `regularMarketTime`); `get_history` parses dates, enforces caps, calls `download_yahoo_daily`, returns `df.to_dict("records")` with dates as `YYYY-MM-DD`; register all three with `mcp.tool(...)`, `if __name__ == "__main__": mcp.run()`.
- [ ] **Step 4: Run** `pytest tests/test_mcp_server.py -v` → expected PASS.
- [ ] **Step 5: Commit** `feat: add MCP server with read-only market-data tools`.

### Task 2: In-process protocol integration test

**Files:**
- Test: `tests/test_mcp_integration.py`

**Interfaces:**
- Consumes: `mcp.server.mcp` (Task 1), `fastmcp.Client` (in-memory).

- [ ] **Step 1: Write failing test** — with `pytest.importorskip("fastmcp")`: `asyncio.run` a `Client(server.mcp)` session; assert `list_tools()` returns exactly `get_quote`, `get_history`, `list_universe`, each with `readOnlyHint=True`; `call_tool("list_universe")` returns the 3 symbols; `call_tool("get_quote", {"symbols": ["BOGUS.NS"]})` returns `isError` content.
- [ ] **Step 2: Run** `pytest tests/test_mcp_integration.py -v` → expected FAIL (fastmcp not in venv yet → install first: `pip install -e ".[dev,mcp]"`; if still failing, fix per error).
- [ ] **Step 3: Run to PASS**, then full `pytest` → all green, offline.
- [ ] **Step 4: Commit** `test: add in-process MCP protocol integration tests`.

### Task 3: End-to-end stdio test (real process, real Yahoo)

**Files:**
- Test: `tests/test_mcp_e2e.py`

**Interfaces:**
- Consumes: Task 1 server as subprocess: `StdioServerParameters(command=sys.executable, args=["mcp/server.py"])`; official `mcp.client.stdio` + `ClientSession`.

- [ ] **Step 1: Write test** — pre-check Yahoo reachability (1s timeout HEAD-less chart request); `pytest.skip("offline")` when unreachable. Over stdio: initialize session, list tools (expect 3), call `list_universe`, call `get_quote(["NIFTYBEES.NS"])` and assert a positive float price.
- [ ] **Step 2: Run** `pytest tests/test_mcp_e2e.py -v` → expected PASS (online) or SKIP (offline).
- [ ] **Step 3: Commit** `test: add end-to-end stdio MCP test against real Yahoo data`.

### Task 4: Docs, wiring, evals

**Files:**
- Modify: `pyproject.toml` (add `mcp = ["fastmcp>=2"]` extra), `README.md` (add "MCP server" section: run command, client JSON config, tool list, data disclaimer)
- Create: `mcp/README.md` (setup + WorkBuddy/Claude config snippets), `mcp/evals/eval.xml` (10 stable QA pairs: universe roles, tool count, caps, data policy — verifiable by string compare)

- [ ] **Step 1: Add pyproject extra + README sections.**
- [ ] **Step 2: Run** full `pytest` + `ruff check .` → green, no warnings.
- [ ] **Step 3: Manual smoke** with MCP Inspector: `npx @modelcontextprotocol/inspector .venv/bin/python mcp/server.py` — connect, call `get_quote`.
- [ ] **Step 4: Commit + push** `docs: MCP server setup, evals, README wiring`.
