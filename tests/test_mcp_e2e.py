"""End-to-end test: real server process over stdio, real MCP client, real Yahoo data.

Skipped automatically when Yahoo is unreachable.
"""

import asyncio
import sys
from pathlib import Path

import pytest

pytest.importorskip("fastmcp", reason="fastmcp not installed")
from mcp import ClientSession, StdioServerParameters  # noqa: E402
from mcp.client.stdio import stdio_client  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
SERVER_SCRIPT = REPO_ROOT / "mcp" / "server.py"


def _yahoo_reachable() -> bool:
    from urllib.request import Request, urlopen

    try:
        request = Request(
            "https://query1.finance.yahoo.com/v8/finance/chart/NIFTYBEES.NS?interval=1d",
            headers={"User-Agent": "india-quant-research/0.1"},
        )
        with urlopen(request, timeout=10):
            return True
    except OSError:
        return False


pytestmark = pytest.mark.skipif(not _yahoo_reachable(), reason="offline")

TOOL_NAMES = {"get_quote", "get_history", "list_universe"}


def test_stdio_server_end_to_end():
    params = StdioServerParameters(command=sys.executable, args=[str(SERVER_SCRIPT)])

    async def main():
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                assert {tool.name for tool in tools.tools} == TOOL_NAMES
                universe = await session.call_tool("list_universe", {})
                assert "NIFTYBEES.NS" in str(universe.content)
                quote = await session.call_tool("get_quote", {"symbols": ["NIFTYBEES.NS"]})
                assert not quote.isError
                assert '"price"' in str(quote.content)
                history = await session.call_tool(
                    "get_history",
                    {"symbols": ["NIFTYBEES.NS"], "start": "2026-10-01", "end": "2026-10-31"},
                )
                assert not history.isError
                rows = str(history.content)
                assert "adj_close" in rows and "2026-10" in rows

    asyncio.run(main())
