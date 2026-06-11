"""Integration tests for the shared MCP session pool.

Spawns a real (tiny) FastMCP stdio server in a subprocess and exercises the
pool's spawn-once / reuse / call_tool flow across event loops.
"""

import sys

import pytest
from asgiref.sync import async_to_sync

from Jeeves.agents.mcp_pool import MCPSessionPool

# Minimal stdio MCP server (no Django) run via `python -c`.
DUMMY_SERVER = """
from fastmcp import FastMCP

mcp = FastMCP("dummy")


@mcp.tool()
def echo(text: str, client_id: int = 0, session_id: str = "", user_id: str = "") -> str:
    return f"echo:{text}:{client_id}"


mcp.run()
"""

POOL_SETTINGS = {
    "dummy": {
        "command": sys.executable,
        "args": ["-c", DUMMY_SERVER],
        "enabled": True,
    },
    "disabled-server": {
        "command": sys.executable,
        "args": ["-c", DUMMY_SERVER],
        "enabled": False,
    },
    "broken-server": {
        "command": sys.executable,
        "args": ["-c", "import sys; sys.exit(1)"],
        "enabled": True,
    },
}


@pytest.fixture
def pool(settings):
    settings.MCP_SERVERS = POOL_SETTINGS
    p = MCPSessionPool()
    yield p
    p.shutdown()


class TestMCPSessionPool:
    def test_spawns_enabled_servers_and_discovers_tools(self, pool):
        pool.ensure_started(env={})
        assert set(pool.sessions) == {"dummy"}  # broken/disabled skipped
        assert pool.tool_to_server.get("echo") == "dummy"
        assert [t.name for t in pool.tools] == ["echo"]

    def test_ensure_started_is_idempotent(self, pool):
        pool.ensure_started(env={})
        session = pool.sessions["dummy"]
        pool.ensure_started(env={})
        assert pool.sessions["dummy"] is session  # no respawn

    def test_call_tool_from_another_loop(self, pool):
        pool.ensure_started(env={})

        async def _call():
            return await pool.call_tool(
                "dummy",
                "echo",
                {"text": "hi", "client_id": 7},
                timeout=30,
            )

        result = async_to_sync(_call)()
        text = "".join(item.text for item in result.content if hasattr(item, "text"))
        assert text == "echo:hi:7"
        assert not result.isError

    def test_call_tool_unknown_server_raises(self, pool):
        pool.ensure_started(env={})

        async def _call():
            return await pool.call_tool("nope", "echo", {}, timeout=5)

        with pytest.raises(RuntimeError, match="not running"):
            async_to_sync(_call)()
