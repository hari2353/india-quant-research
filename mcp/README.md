# India Market-Data MCP Server

Read-only MCP server (stdio) exposing this repo's Yahoo research adapter:

- `get_quote(symbols)` — latest price, currency, market time per symbol
- `get_history(symbols, start, end)` — cleaned daily OHLCV rows (max 5 symbols, 3-year span)
- `list_universe()` — the research ETFs and their portfolio roles

Data policy: Yahoo Finance data is delayed and unlicensed. Personal research only;
not a production feed; the server has no order or broker surface.

## Run

```bash
python -m venv .venv
./.venv/bin/pip install -e ".[mcp]"
./.venv/bin/python mcp/server.py   # speaks MCP over stdio
```

## Client configuration

Claude Desktop / any MCP client with a JSON config:

```json
{
  "mcpServers": {
    "india-quant-research": {
      "command": "/absolute/path/to/india-quant-research/.venv/bin/python",
      "args": ["/absolute/path/to/india-quant-research/mcp/server.py"]
    }
  }
}
```

For WorkBuddy: add the same `command` + `args` pair in its MCP server settings
(WorkBuddy also reads standard Agent Skills folders under `~/.workbuddy/skills/`).

## Test

```bash
./.venv/bin/pip install -e ".[dev,mcp]"
./.venv/bin/pytest tests/test_mcp_server.py tests/test_mcp_integration.py tests/test_mcp_e2e.py -v
```

The E2E test launches the real server as a subprocess, runs a real MCP handshake
over stdio, and pulls live NIFTYBEES.NS data from Yahoo. It skips automatically
when offline. `mcp/evals/eval.xml` holds 10 stable question/answer pairs for
agent-level checks.
