"""In-process MCP protocol integration tests via fastmcp.Client (offline)."""

import asyncio
import importlib.util
import sys
from pathlib import Path

import pytest

pytest.importorskip("fastmcp", reason="fastmcp not installed")
from fastmcp import Client  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
SERVER_PATH = REPO_ROOT / "mcp" / "server.py"


def _load_server():
    spec = importlib.util.spec_from_file_location("india_quant_mcp_server", SERVER_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


server = _load_server()

TOOL_NAMES = {"get_quote", "get_history", "list_universe"}


def _run(coro):
    return asyncio.run(coro)


def test_tools_are_read_only():
    async def main():
        async with Client(server.mcp) as client:
            tools = {tool.name: tool for tool in await client.list_tools()}
        return tools

    tools = _run(main())
    assert set(tools) == TOOL_NAMES
    for tool in tools.values():
        assert tool.annotations.read_only_hint is True


def test_list_universe_over_protocol():
    async def main():
        async with Client(server.mcp) as client:
            result = await client.call_tool("list_universe", {})
        return result

    result = _run(main())
    assert not result.is_error
    payload = result.data if hasattr(result, "data") else result.content[0].text
    text = payload if isinstance(payload, str) else str(payload)
    for symbol in ("NIFTYBEES.NS", "GOLDBEES.NS", "LIQUIDBEES.NS"):
        assert symbol in text


def test_invalid_call_returns_tool_error():
    async def main():
        async with Client(server.mcp) as client:
            return await client.call_tool(
                "get_quote", {"symbols": [""]}, raise_on_error=False
            )

    result = _run(main())
    assert result.is_error
    text = str(result.content)
    assert "symbol" in text
