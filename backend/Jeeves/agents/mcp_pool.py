"""Shared MCP session pool — spawn servers once per worker, reuse across requests.

Spawning every MCP stdio server on each chat message (each subprocess running a
full ``django.setup()``) added tens of seconds of latency per response. The pool
keeps the subprocesses and their ``ClientSession`` objects alive in a dedicated
event-loop thread; orchestrator instances attach to it per request instead of
spawning their own servers.

MCP sessions are client-agnostic — ``client_id``/``session_id``/``user_id`` are
injected into every tool call by the orchestrator — so sharing them across
clients and requests is safe.
"""

from __future__ import annotations

import asyncio
import atexit
import logging
import threading
import time
from contextlib import AsyncExitStack
from typing import Any

from django.conf import settings
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

logger = logging.getLogger(__name__)

# How long the first request may wait for all servers to boot.
_POOL_START_TIMEOUT = 180.0

# Don't retry spawning a failed server more often than this (seconds),
# so a broken catalog server doesn't add spawn latency to every message.
_FAILED_RETRY_COOLDOWN = 120.0


class MCPSessionPool:
    """Keeps MCP stdio servers alive in a dedicated event-loop thread.

    All coroutines touching the sessions run on the pool's own loop; callers
    on other loops/threads go through ``call_tool`` / ``ensure_started``.
    """

    _instance: "MCPSessionPool | None" = None
    _instance_lock = threading.Lock()

    @classmethod
    def instance(cls) -> "MCPSessionPool":
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    pool = cls()
                    atexit.register(pool.shutdown)
                    cls._instance = pool
        return cls._instance

    def __init__(self):
        self.sessions: dict[str, ClientSession] = {}  # server_name -> session
        self.tool_to_server: dict[str, str] = {}  # tool_name -> server_name
        self._server_tools: dict[str, list[Any]] = {}  # server_name -> MCP Tools
        self._stacks: dict[str, AsyncExitStack] = {}
        self._configs: dict[str, dict] = {}  # server_name -> spawn config
        self._failed_at: dict[str, float] = {}  # server_name -> monotonic ts
        self._respawn_locks: dict[str, asyncio.Lock] = {}
        self._env: dict[str, str] = {}
        self._started = False
        self._start_lock = threading.Lock()
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._run_loop,
            name="mcp-session-pool",
            daemon=True,
        )
        self._thread.start()

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    @property
    def tools(self) -> list[Any]:
        """All discovered MCP tools across running servers."""
        return [t for tools in self._server_tools.values() for t in tools]

    # ------------------------------------------------------------------
    # Startup / shutdown
    # ------------------------------------------------------------------

    def ensure_started(self, env: dict[str, str]) -> None:
        """Spawn all enabled servers on first use. Blocking — call via
        ``asyncio.to_thread`` from async code."""
        if self._started:
            return
        with self._start_lock:
            if self._started:
                return
            future = asyncio.run_coroutine_threadsafe(
                self._connect_all(env),
                self._loop,
            )
            future.result(timeout=_POOL_START_TIMEOUT)
            self._started = True

    async def _connect_all(self, env: dict[str, str]) -> None:
        self._env = env
        server_defs: dict[str, dict] = getattr(settings, "MCP_SERVERS", {})
        if not server_defs:
            logger.warning("settings.MCP_SERVERS is empty — MCP pool has no servers")
            return

        enabled = {name: cfg for name, cfg in server_defs.items() if cfg.get("enabled", True)}
        await asyncio.gather(
            *(self._connect_one(name, cfg) for name, cfg in enabled.items()),
        )
        logger.info(
            "MCP pool started — %d/%d server(s) up, %d tool(s)",
            len(self.sessions),
            len(enabled),
            len(self.tools),
        )

    async def _connect_one(self, name: str, cfg: dict) -> None:
        """Spawn one server; failures are logged, never raised."""
        stack = AsyncExitStack()
        try:
            params = StdioServerParameters(
                command=cfg["command"],
                args=cfg.get("args", []),
                env=cfg.get("env") or self._env,
            )
            read_stream, write_stream = await stack.enter_async_context(
                stdio_client(params),
            )
            session = await stack.enter_async_context(
                ClientSession(read_stream, write_stream),
            )
            await session.initialize()
            result = await session.list_tools()
        except Exception:
            logger.exception("MCP pool: failed to start server '%s'", name)
            self._failed_at[name] = time.monotonic()
            try:
                await stack.aclose()
            except Exception:
                logger.exception("MCP pool: cleanup after failed start of '%s'", name)
            return

        self._failed_at.pop(name, None)
        self._configs[name] = cfg
        self._stacks[name] = stack
        self.sessions[name] = session
        self._server_tools[name] = list(result.tools)
        for tool in result.tools:
            self.tool_to_server[tool.name] = name
        logger.info(
            "MCP pool: server '%s' up — %d tool(s): %s",
            name,
            len(result.tools),
            [t.name for t in result.tools],
        )

    def ensure_extra_servers(self, defs: dict[str, dict]) -> None:
        """Spawn additional (catalog/DB-defined) servers not yet running.

        Blocking — call via ``asyncio.to_thread`` from async code. Recently
        failed servers are skipped until the retry cooldown expires.
        """
        now = time.monotonic()
        missing = {
            name: cfg for name, cfg in defs.items()
            if name not in self.sessions
            and now - self._failed_at.get(name, -_FAILED_RETRY_COOLDOWN) >= _FAILED_RETRY_COOLDOWN
        }
        if not missing:
            return
        future = asyncio.run_coroutine_threadsafe(
            self._connect_extra(missing),
            self._loop,
        )
        future.result(timeout=_POOL_START_TIMEOUT)

    async def _connect_extra(self, defs: dict[str, dict]) -> None:
        for name, cfg in defs.items():
            lock = self._respawn_locks.setdefault(name, asyncio.Lock())
            async with lock:
                if name not in self.sessions:
                    await self._connect_one(name, cfg)

    async def _teardown_one(self, name: str) -> None:
        self.sessions.pop(name, None)
        self._server_tools.pop(name, None)
        stack = self._stacks.pop(name, None)
        if stack is not None:
            try:
                await stack.aclose()
            except Exception:
                logger.exception("MCP pool: error closing server '%s'", name)

    def shutdown(self) -> None:
        """Best-effort teardown of all servers (atexit / tests)."""
        if not self._loop.is_running():
            return
        try:
            future = asyncio.run_coroutine_threadsafe(
                self._close_all(),
                self._loop,
            )
            future.result(timeout=15)
        except Exception:
            logger.warning("MCP pool: shutdown did not complete cleanly", exc_info=True)
        finally:
            self._loop.call_soon_threadsafe(self._loop.stop)
            self._started = False

    async def _close_all(self) -> None:
        for name in list(self._stacks):
            await self._teardown_one(name)

    # ------------------------------------------------------------------
    # Tool calls
    # ------------------------------------------------------------------

    async def call_tool(
        self,
        server_name: str,
        tool_name: str,
        arguments: dict[str, Any],
        timeout: float,
    ):
        """Call a tool on the pool's loop from any other running loop."""
        if server_name not in self.sessions:
            raise RuntimeError(f"MCP server '{server_name}' is not running")
        concurrent_future = asyncio.run_coroutine_threadsafe(
            self._call_tool_on_loop(server_name, tool_name, arguments, timeout),
            self._loop,
        )
        return await asyncio.wrap_future(concurrent_future)

    async def _call_tool_on_loop(
        self,
        server_name: str,
        tool_name: str,
        arguments: dict[str, Any],
        timeout: float,
    ):
        session = self.sessions.get(server_name)
        if session is None:
            raise RuntimeError(f"MCP server '{server_name}' is not running")
        try:
            return await asyncio.wait_for(
                session.call_tool(tool_name, arguments),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            # The server may just be busy — keep the session.
            raise
        except Exception:
            # Likely a dead subprocess / broken pipe: respawn so the next
            # call succeeds, then surface the error for this one.
            logger.exception(
                "MCP pool: call '%s' failed on server '%s' — respawning",
                tool_name,
                server_name,
            )
            await self._respawn(server_name)
            raise

    async def _respawn(self, name: str) -> None:
        lock = self._respawn_locks.setdefault(name, asyncio.Lock())
        if lock.locked():  # another call is already respawning this server
            return
        async with lock:
            await self._teardown_one(name)
            # Catalog servers aren't in settings — use the stored spawn config.
            cfg = self._configs.get(name) or getattr(settings, "MCP_SERVERS", {}).get(name)
            if cfg and cfg.get("enabled", True):
                await self._connect_one(name, cfg)


# Fallback tool_name → MCP server map, used when the shared pool hasn't
# started in this worker yet (the live pool.tool_to_server is the primary
# source). Single source of truth shared by FlowActivityView and any other
# caller that must resolve a logged tool name to its server.
_TOOL_NAME_TO_SERVER = {
    'search': 'rag',
    'send_email': 'email',
    'send_email_with_attachment': 'email',
    'read_emails': 'email',
    'search_emails': 'email',
    'analyze_emails': 'email',
    'send_commercial_email': 'email',
    'save_lead': 'leads',
}
_TOOL_PREFIX_TO_SERVER = {
    'matrix_': 'matrix',
    'gcal_': 'google-workspace',
    'sheets_': 'google-workspace',
    'reviews_': 'google-workspace',
    'cp_': 'content-planner',
    'pc_': 'hardware',
    'canvas_': 'canvas',
    'skill_': 'canvas',
}


def resolve_tool_server(tool_name: str) -> str:
    """Resolve a tool name to its MCP server name ('' when unknown).

    Prefers the live pool's discovered map; falls back to the static map
    above so canvas activity resolves even before the pool boots.
    """
    pool = MCPSessionPool._instance
    if pool is not None:
        server = pool.tool_to_server.get(tool_name)
        if server:
            return server
    if tool_name in _TOOL_NAME_TO_SERVER:
        return _TOOL_NAME_TO_SERVER[tool_name]
    for prefix, server in _TOOL_PREFIX_TO_SERVER.items():
        if tool_name.startswith(prefix):
            return server
    return ''
