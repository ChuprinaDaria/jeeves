# backend/Jeeves/tools/mcp_discovery.py
import asyncio
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

DISCOVERY_TIMEOUT = 10  # seconds


@dataclass
class DiscoveryResult:
    server_name: str
    tools: list  # [{"name": ..., "description": ..., "inputSchema": ...}]


class DiscoveryError(Exception):
    pass


async def _discover_sse(url: str) -> DiscoveryResult:
    from mcp import ClientSession
    from mcp.client.sse import sse_client

    async with sse_client(url) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.list_tools()
            tools = [
                {
                    "name": t.name,
                    "description": t.description or "",
                    "inputSchema": t.inputSchema if hasattr(t, "inputSchema") else {},
                }
                for t in result.tools
            ]
            server_name = getattr(session, "server_name", "") or ""
            return DiscoveryResult(server_name=server_name, tools=tools)


def discover_mcp_server(url: str) -> DiscoveryResult:
    """Connect to an MCP server via SSE, list its tools, return result.

    Raises DiscoveryError on any failure (timeout, connection, protocol).
    """
    try:
        result = asyncio.run(
            asyncio.wait_for(_discover_sse(url), timeout=DISCOVERY_TIMEOUT)
        )
        if not result.tools:
            raise DiscoveryError("Server returned zero tools.")
        return result
    except DiscoveryError:
        raise
    except asyncio.TimeoutError:
        raise DiscoveryError(f"Connection timed out after {DISCOVERY_TIMEOUT}s.")
    except Exception as e:
        raise DiscoveryError(f"Failed to connect: {e}")
