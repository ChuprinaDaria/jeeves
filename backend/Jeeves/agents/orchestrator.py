"""
AgentOrchestrator — core MCP + LLM tool-calling loop.

Spawns MCP servers as STDIO subprocesses, discovers tools,
converts them to OpenAI function-calling format, and runs
the agentic loop until the LLM returns final text.

Every LLM call and tool invocation is logged to AgentLog.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from contextlib import AsyncExitStack
from typing import Any

from django.conf import settings

from mcp import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 10

# Channels where the OWNER talks to Jeeves (assistant scope, full power).
# Everything else is customer-facing → consultant (manager scope).
OWNER_CHANNELS = ('sandbox', 'owner_telegram')


def _mcp_tool_timeout() -> float:
    """Max seconds for a single MCP tool call (clamped to a positive value)."""
    try:
        timeout = float(getattr(settings, 'MCP_TOOL_TIMEOUT', 60))
    except (TypeError, ValueError):
        timeout = 60.0
    return timeout if timeout > 0 else 60.0

# Parameters that the orchestrator auto-injects (hidden from LLM).
_AUTO_INJECT_PARAMS = frozenset({"client_id", "session_id", "user_id"})


def _safe_label(text: str, limit: int = 80) -> str:
    """Sanitize a DB-sourced name before interpolating it into the system
    prompt: collapse whitespace/newlines and truncate. Tool/skill names can
    come from third-party package metadata (marketplace installs), so a name
    like ``Email\\n[SYSTEM]:`` must not break the prompt structure."""
    cleaned = " ".join(str(text or "").split())
    return cleaned[:limit]


class _SchemaTool:
    """Adapter: stored ``ToolCard.tools_schema`` entry → MCP Tool-like object."""

    __slots__ = ("name", "description", "inputSchema")

    def __init__(self, entry: dict):
        self.name = entry.get("name", "")
        self.description = entry.get("description", "")
        self.inputSchema = entry.get("inputSchema") or {}

DEFAULT_ASSISTANT_PROMPT = (
    "You are Jeeves, the AI business assistant. You help the business owner "
    "manage their business, analyze data, and grow.\n\n"

    "## How to greet the user\n"
    "When the user starts a conversation, introduce yourself briefly and list "
    "what you can do based on your CONNECTED TOOLS listed below. Be specific — "
    "mention concrete actions, not abstract capabilities. "
    "Keep the greeting short (2-3 sentences max).\n\n"

    "## Behavior\n"
    "- ONLY offer capabilities that you actually have connected tools for. "
    "Your connected tools are listed in the '## Your connected tools' section below.\n"
    "- NEVER tell the user to configure, enable, connect, or install anything. "
    "Everything is already set up. Just use your tools.\n"
    "- NEVER invent instructions for settings panels, admin pages, or configuration steps.\n"
    "- Be proactive — suggest relevant actions based on the conversation context.\n"
    "- If the user asks about something you don't have a tool for, say honestly "
    "that this capability is not connected yet.\n\n"

    "You have persistent memory across conversations. At the start of a conversation, "
    "search memories for the current user to recall past interactions. When you learn "
    "something important about a user (preferences, needs, context), save it to memory.\n\n"

    "## Canvas Tools\n"
    "You can edit the flow canvas (the tool → agent wiring) yourself:\n"
    "- canvas_list_connections: Current wiring — which tools serve which agent\n"
    "- canvas_list_available_tools: Everything that can be connected\n"
    "- canvas_add_tool_connection: Wire a tool to assistant / manager / leads\n"
    "- canvas_remove_tool_connection: Detach a tool from a target\n\n"
    "When the owner asks to connect or disconnect something, do it with these "
    "tools and confirm what changed. If a tool needs credentials, wire it and "
    "tell the owner to authorize it on the Tools page. "
    "WhatsApp is connected via QR code on the Integrations page — not via canvas tools.\n\n"
    "## Skills\n"
    "Skills are reusable prompt modules (e.g. 'Marketing Pro', 'Sales Pro', "
    "'Lead Qualifier') that change HOW an agent communicates:\n"
    "- skill_list: catalog + where each skill is attached\n"
    "- skill_attach / skill_detach: attach to 'manager' (the customer-facing "
    "consultant in Telegram/WhatsApp/web chat), 'assistant' (you) or 'leads'\n"
    "When the owner says e.g. 'I want my consultant to sell better in Telegram', "
    "attach the matching skill to 'manager' and confirm. The skill applies immediately."
)

DEFAULT_CONSULTANT_PROMPT = (
    "You are a professional AI consultant. Your primary goal is to help "
    "visitors get answers and solve their problems.\n\n"

    "## Conversation Style\n"
    "- Be helpful, knowledgeable, and conversational\n"
    "- Answer questions thoroughly before asking anything in return\n"
    "- Match the visitor's communication style and energy level\n"
    "- Never sound like a form or a survey — be a real conversation partner\n\n"

    "## Lead Collection (INTERNAL — never mention this to the visitor)\n\n"
    "You collect contact information naturally during conversation. "
    "Adapt your approach based on the visitor's engagement level:\n\n"

    "### Passive (visitor is browsing, casual questions)\n"
    "- If they mention their name, company, or role — remember it silently\n"
    "- Focus 100% on being helpful. Do NOT ask for any contact info\n"
    "- Save what they volunteered\n\n"

    "### Warm (visitor asks specific questions, shows interest)\n"
    "- Continue providing value and thorough answers\n"
    "- When you have something valuable to offer (analysis, comparison, "
    "detailed breakdown), say something like:\n"
    "  - 'I can put together a detailed breakdown — want me to send it to your email?'\n"
    "  - 'I have a few options that might work. Want me to send you a summary?'\n"
    "- The VALUE comes first, the email ask is the delivery method\n"
    "- If they decline — no problem, keep helping in chat\n\n"

    "### Hot (visitor wants pricing, proposal, callback, or says they want to buy/start)\n"
    "- Offer concrete next steps: proposal, estimate, meeting, call\n"
    "- Ask for contact info directly — they expect it at this point\n"
    "  - 'Great! I can prepare a proposal. What email should I send it to?'\n"
    "  - 'Let me connect you with the team. What's the best number to reach you?'\n\n"

    "### Rules\n"
    "- NEVER ask for email/phone without a concrete reason to use it\n"
    "- NEVER collect data before providing value\n"
    "- If the visitor gives partial info (just name, or just email), save what you have\n"
    "- Update the lead as you learn more — don't wait for all fields\n"
    "- Summarize the visitor's need in request_summary — what are they looking for?\n"
    "- Score interest 1-5: 1=just browsing, 3=interested, 5=ready to buy\n\n"

    "You have persistent memory across conversations. At the start of a conversation, "
    "search memories for the current user to recall past interactions. When you learn "
    "something important about a user (preferences, needs, context), save it to memory."
)


class AgentOrchestrator:
    """Agentic LLM loop backed by MCP tool servers."""

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def __init__(self, client, agent_config):
        """
        Args:
            client: ``Client`` model instance (has ``.pk``).
            agent_config: ``AgentConfig`` model instance.
        """
        self.client = client
        self.agent_config = agent_config

        # Pre-cache values with safe fallbacks (avoid sync DB in async context)
        self._language = agent_config.language or 'en'
        self._temperature = agent_config.temperature if agent_config.temperature is not None else 0.7
        self._max_tokens = agent_config.max_tokens if agent_config.max_tokens is not None else 4096

        # Filled by ``connect()``
        self._pool = None  # shared MCPSessionPool when MCP_POOL_ENABLED
        self._exit_stack: AsyncExitStack | None = None
        self._sessions: dict[str, ClientSession] = {}  # server_name -> session
        self._tools: list[dict[str, Any]] = []  # MCP Tool dicts
        self._tool_to_server: dict[str, str] = {}  # tool_name -> server_name

        # Catalog (DB-defined) MCP servers — owner-installed stdio packages
        # and remote SSE/HTTP servers. Opt-in per client via ToolConnection.
        self._dynamic_servers: set[str] = set()  # server_name (= ToolCard.slug)
        self._remote_cards: dict[str, Any] = {}  # slug -> ToolCard (sse/http)
        self._dynamic_descriptions: dict[str, tuple[str, str]] = {}

        # Scope filtering (set in process())
        self._scope = 'manager'  # default, set in process()
        self._deployment = None  # live topology snapshot, set in _build_scope_filter
        self._skills = []  # assigned markdown skills, set in _build_scope_filter
        self._tool_to_connection = {}  # server_name -> ToolConnection
        self._connected_server_names = set()
        self._session = None  # set in process()
        self._tool_scopes: dict[str, list[str]] = getattr(settings, 'MCP_TOOL_SCOPES', {})

    async def connect(self) -> None:
        """Attach to the shared MCP session pool (or spawn private servers).

        The pool spawns every server once per worker process; per-request
        spawning (the old behavior, ~seconds of latency per message) remains
        available via ``MCP_POOL_ENABLED=False`` as a fallback.
        """
        if getattr(settings, "MCP_POOL_ENABLED", True):
            from Jeeves.agents.mcp_pool import MCPSessionPool

            pool = MCPSessionPool.instance()
            try:
                # ensure_started blocks on first use — keep the loop free.
                await asyncio.to_thread(
                    pool.ensure_started, self._build_subprocess_env(),
                )
            except Exception:
                logger.exception(
                    "MCP pool failed to start — falling back to per-request spawn"
                )
            else:
                self._pool = pool
                self._sessions = dict(pool.sessions)
                self._tools = list(pool.tools)
                self._tool_to_server = dict(pool.tool_to_server)

        if self._pool is None:
            await self._connect_private()

        await self._attach_catalog_servers()

    async def _connect_private(self) -> None:
        """Spawn enabled MCP servers for this request only."""
        server_defs: dict[str, dict] = getattr(settings, "MCP_SERVERS", {})
        if not server_defs:
            logger.warning("settings.MCP_SERVERS is empty — no MCP tools available")
            return

        env = self._build_subprocess_env()

        for name, cfg in server_defs.items():
            if not cfg.get("enabled", True):
                continue
            await self._spawn_private_server(name, {**cfg, "env": cfg.get("env") or env})

        logger.info(
            "MCP connect complete — %d server(s) up, %d tool(s) discovered",
            len(self._sessions),
            len(self._tools),
        )
        if not self._tools:
            logger.warning(
                "No MCP tools discovered — agent will run without tools "
                "(check 'Failed to connect MCP server' errors above)"
            )

    async def _spawn_private_server(self, name: str, cfg: dict) -> None:
        """Spawn one stdio MCP server for this request only (non-pool mode)."""
        if self._exit_stack is None:
            self._exit_stack = AsyncExitStack()
            await self._exit_stack.__aenter__()

        params = StdioServerParameters(
            command=cfg["command"],
            args=cfg.get("args", []),
            env=cfg.get("env"),
        )

        try:
            transport = await self._exit_stack.enter_async_context(
                stdio_client(params),
            )
            read_stream, write_stream = transport
            session = await self._exit_stack.enter_async_context(
                ClientSession(read_stream, write_stream),
            )
            await session.initialize()
            self._sessions[name] = session

            # Discover tools
            result = await session.list_tools()
            for tool in result.tools:
                self._tools.append(tool)
                self._tool_to_server[tool.name] = name

            logger.info(
                "MCP server '%s' connected — %d tool(s): %s",
                name,
                len(result.tools),
                [t.name for t in result.tools],
            )

        except Exception:
            logger.exception("Failed to connect MCP server '%s'", name)

    async def _attach_catalog_servers(self) -> None:
        """Expose owner-added MCP servers from the tool catalog (DB).

        Two kinds, neither defined in ``settings.MCP_SERVERS``:
        - stdio packages (``InstalledMCPServer``) — spawned through the shared
          pool (or privately in non-pool mode) like platform servers;
        - remote SSE / streamable-HTTP servers — their tools come from the
          schema stored at install time (``ToolCard.tools_schema``) and each
          call opens a connection with the client's credentials.

        Unlike platform servers these are opt-in: only clients with an enabled
        ``ToolConnection`` for the card see the tools (``_build_scope_filter``).
        """
        from Jeeves.tools.models import ToolCard

        # --- Owner-installed stdio packages ---
        base_env = self._build_subprocess_env()
        stdio_defs: dict[str, dict] = {}
        async for card in ToolCard.objects.filter(
            is_active=True,
            transport_type='stdio',
            installed_server__status='installed',
        ).select_related('installed_server'):
            inst = card.installed_server
            stdio_defs[card.slug] = {
                "command": inst.run_command,
                "args": inst.run_args or [],
                "env": {**base_env, **(inst.env_config or {})},
            }
            self._dynamic_descriptions[card.slug] = (card.name, card.tagline)

        if stdio_defs:
            if self._pool is not None:
                try:
                    await asyncio.to_thread(
                        self._pool.ensure_extra_servers, stdio_defs,
                    )
                except Exception:
                    logger.exception("Failed to start catalog stdio MCP servers")
                # Refresh local views — pool may have new servers/tools now.
                self._sessions = dict(self._pool.sessions)
                self._tools = list(self._pool.tools)
                self._tool_to_server = dict(self._pool.tool_to_server)
            else:
                for name, cfg in stdio_defs.items():
                    await self._spawn_private_server(name, cfg)
            self._dynamic_servers |= set(stdio_defs)

        # --- Remote SSE / streamable-HTTP servers ---
        async for card in ToolCard.objects.filter(
            is_active=True,
            transport_type__in=('sse', 'streamable_http'),
        ).exclude(mcp_server_url=''):
            if not card.tools_schema:
                continue
            self._remote_cards[card.slug] = card
            self._dynamic_servers.add(card.slug)
            self._dynamic_descriptions[card.slug] = (card.name, card.tagline)
            for entry in card.tools_schema:
                tool = _SchemaTool(entry)
                if not tool.name or tool.name in self._tool_to_server:
                    continue
                self._tools.append(tool)
                self._tool_to_server[tool.name] = card.slug

    async def disconnect(self) -> None:
        """Detach from the pool / tear down private MCP subprocesses.

        Pooled sessions stay alive for the next request — only privately
        spawned servers (non-pool fallback) are terminated here.
        """
        self._pool = None
        if self._exit_stack:
            try:
                await self._exit_stack.aclose()
            except Exception:
                logger.exception("Error during MCP disconnect")
            finally:
                self._exit_stack = None
                self._sessions.clear()
                self._tools.clear()
                self._tool_to_server.clear()
        self._dynamic_servers.clear()
        self._remote_cards.clear()

    # ------------------------------------------------------------------
    # Main entry-point
    # ------------------------------------------------------------------

    async def process(
        self,
        message: str,
        session,  # AgentSession
        conversation: list[dict[str, str]],
        channel: str = "web",
        external_user_id: str = "",
        tool_event_cb=None,
    ) -> str:
        """
        Run the agentic loop: LLM ↔ MCP tools until final answer.

        Args:
            message: Current user message text.
            session: ``AgentSession`` ORM instance (for logging).
            conversation: Prior messages ``[{"role": ..., "content": ...}, ...]``.
            channel: Channel identifier.
            external_user_id: External user identifier (phone, chat_id, etc.).

        Returns:
            Final assistant text response.
        """
        self._scope = 'assistant' if channel in OWNER_CHANNELS else 'manager'
        self._session = session

        await self._build_scope_filter()

        system_prompt = self._build_system_prompt(channel)
        messages = self._build_messages(system_prompt, conversation, message)
        llm_tools = self._tools_to_llm_format()
        if not llm_tools:
            logger.warning(
                "No MCP tools available for client %s (scope=%s, channel=%s)",
                self.client.pk, self._scope, channel,
            )

        # Stream text deltas to SSE consumers through the same event channel
        # as tool_start/tool_result, so the UI shows the answer as it's typed.
        token_cb = None
        if tool_event_cb is not None:
            async def _emit_token(text: str) -> None:
                try:
                    await tool_event_cb("token", {"text": text})
                except Exception:
                    logger.exception("tool_event_cb(token) failed")
            token_cb = _emit_token

        for iteration in range(MAX_ITERATIONS):
            # --- LLM call ---
            t0 = time.monotonic()
            try:
                response = await self._call_llm(messages, llm_tools, token_cb=token_cb)
            except Exception as exc:
                await self._log(
                    session,
                    call_type="llm",
                    tool_name="",
                    input_data={"messages_count": len(messages)},
                    output_data={"error": str(exc)},
                    status="error",
                    latency_ms=int((time.monotonic() - t0) * 1000),
                )
                logger.exception("LLM call failed (iteration %d)", iteration)
                return "Sorry, I encountered an error processing your request."
            latency = int((time.monotonic() - t0) * 1000)

            assistant_msg = response["message"]
            tokens = response.get("tokens_used")

            await self._log(
                session,
                call_type="llm",
                tool_name=response.get("model", ""),
                input_data={"messages_count": len(messages), "iteration": iteration},
                output_data={
                    "content": (assistant_msg.get("content") or "")[:500],
                    "tool_calls_count": len(assistant_msg.get("tool_calls") or []),
                },
                status="ok",
                latency_ms=latency,
                tokens_used=tokens,
            )

            tool_calls = assistant_msg.get("tool_calls")

            # No tool calls → final answer
            if not tool_calls:
                return assistant_msg.get("content") or ""

            # Append assistant message (with tool_calls) to conversation
            messages.append(assistant_msg)

            # --- Execute each tool call ---
            for tc in tool_calls:
                func = tc["function"]
                tool_name = func["name"]
                try:
                    raw_args = json.loads(func["arguments"])
                except (json.JSONDecodeError, TypeError):
                    raw_args = {}

                # Inject agent scope for knowledge access filtering.
                if tool_name == 'search':
                    raw_args.setdefault('requesting_agent', self._scope)

                tool_call_id = tc.get("id", "")

                # Emit tool_start early so the frontend can display progress.
                if tool_event_cb:
                    try:
                        await tool_event_cb(
                            "tool_start",
                            {
                                "tool_call_id": tool_call_id,
                                "tool_name": tool_name,
                                "arguments": raw_args,
                            },
                        )
                    except Exception:
                        logger.exception("tool_event_cb(tool_start) failed")

                t0 = time.monotonic()
                try:
                    tool_result, tool_status = await self._execute_tool_with_middleware(
                        tool_name, raw_args
                    )
                except Exception as exc:
                    tool_result, tool_status = str(exc), "error"
                tool_latency = int((time.monotonic() - t0) * 1000)

                call_type = "rag" if tool_name == "search" else (
                    "escalation" if "escalat" in tool_name.lower() else "tool"
                )

                await self._log(
                    session,
                    call_type=call_type,
                    tool_name=tool_name,
                    input_data=raw_args,
                    output_data={"result": tool_result[:1000] if tool_result else ""},
                    status=tool_status,
                    latency_ms=tool_latency,
                )

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": tool_result,
                })

                # Emit tool_result/tool_error (SSE consumers).
                if tool_event_cb:
                    try:
                        truncated = tool_result[:4000] if isinstance(tool_result, str) else str(tool_result)[:4000]
                        if tool_status == "ok":
                            await tool_event_cb(
                                "tool_result",
                                {
                                    "tool_call_id": tool_call_id,
                                    "tool_name": tool_name,
                                    "result": truncated,
                                },
                            )
                        else:
                            await tool_event_cb(
                                "tool_error",
                                {
                                    "tool_call_id": tool_call_id,
                                    "tool_name": tool_name,
                                    "error": truncated,
                                },
                            )
                    except Exception:
                        logger.exception("tool_event_cb(tool_result/error) failed")

            # Separate streamed pre-tool text from the next iteration's text.
            if token_cb is not None and (assistant_msg.get("content") or "").strip():
                await token_cb("\n\n")

        # Exhausted iterations
        logger.warning("Orchestrator hit MAX_ITERATIONS (%d)", MAX_ITERATIONS)
        return "I wasn't able to complete this request. Please try again."

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_subprocess_env(self) -> dict[str, str]:
        """Environment for MCP subprocess: inherit os.environ + Django settings."""
        env = dict(os.environ)
        env["DJANGO_SETTINGS_MODULE"] = os.environ.get(
            "DJANGO_SETTINGS_MODULE", "Jeeves.settings"
        )
        # Propagate DATABASE_URL if set
        db_cfg = settings.DATABASES.get("default", {})
        if "DATABASE_URL" not in env and db_cfg:
            # Build from Django config
            user = db_cfg.get("USER", "")
            password = db_cfg.get("PASSWORD", "")
            host = db_cfg.get("HOST", "localhost")
            port = db_cfg.get("PORT", "5432")
            name = db_cfg.get("NAME", "")
            if user and name:
                env["DATABASE_URL"] = (
                    f"postgres://{user}:{password}@{host}:{port}/{name}"
                )
        return env

    def _build_system_prompt(self, channel: str) -> str:
        """Build the full system prompt from AgentConfig + channel routing."""
        client_custom = (getattr(self.client, 'custom_system_prompt', '') or '').strip()
        is_owner_channel = channel in OWNER_CHANNELS
        if is_owner_channel:
            default = DEFAULT_ASSISTANT_PROMPT
            custom = self.agent_config.assistant_prompt
            description = self.agent_config.assistant_description
        else:
            default = DEFAULT_CONSULTANT_PROMPT
            custom = (
                self.agent_config.consultant_prompt or client_custom
            )
            description = self.agent_config.consultant_description

        parts = [default]

        if custom:
            parts.append(f"\n\n## Business Context\n{custom}")

        if description:
            parts.append(f"\n\nYour capabilities:\n{description}")

        if self._tools:
            connected = self._get_connected_tool_descriptions()
            if connected:
                parts.append(
                    "\n\n## Your connected tools (ACTIVE — you can use these NOW)\n"
                    + "\n".join(f"- **{name}**: {desc}" for name, desc in connected)
                    + "\n\nThese tools are ALREADY connected and ready to use. "
                    "Do NOT tell the user to configure, enable, or connect anything — just use the tools directly. "
                    "When the user asks what you can do, describe these capabilities in plain language."
                    "\nDo NOT mention internal tool names to the user."
                    "\nNEVER fabricate file URLs or tool results from scratch. "
                    "If you need to CREATE a file — call the tool first, then use the URL it returns. "
                    "If a user asks for a link you already shared earlier in this conversation, "
                    "repeat the SAME link — do not claim the file doesn't exist. "
                    "When sharing download links, prepend the API base URL to the path from the tool "
                    "(e.g. /media/xlsx/...). "
                    "If a tool fails or is unavailable, say so honestly — never invent data."
                )

        if self._deployment is not None:
            wiring_lines = [
                f"- {name} → {', '.join(sorted(targets))}"
                for name, targets in sorted(self._deployment['wiring'].items())
            ]
            channels_str = ', '.join(self._deployment['channels'])
            if is_owner_channel:
                parts.append(
                    "\n\n## Your deployment (live)\n"
                    "- You are Jeeves — the owner's PRIVATE assistant. The owner reaches you "
                    "in the sandbox and, if linked, their private Telegram chat. Customers never talk to you.\n"
                    f"- Concierge (the customer-facing consultant agent) talks to customers on: {channels_str}.\n"
                    + ("- Canvas wiring (tool → agents):\n" + "\n".join(wiring_lines)
                       if wiring_lines else "- The canvas is empty — no tools wired yet.")
                )
            else:
                parts.append(
                    "\n\n## Your deployment (live)\n"
                    f"- You are the customer-facing consultant. Right now you are talking on the '{channel}' channel.\n"
                    "- Jeeves, the owner's private assistant, manages tools and configuration — you cannot "
                    "reconfigure anything. If asked about setup, say the owner handles it with Jeeves.\n"
                    f"- Customer channels connected: {channels_str}."
                )

        for skill_name, skill_target, skill_content in self._skills:
            suffix = " (lead handling)" if skill_target == 'leads' else ""
            parts.append(f"\n\n## Skill: {skill_name}{suffix}\n{skill_content.strip()}")

        if is_owner_channel:
            # Assistant detects user language and responds in it
            parts.append(
                "\nDetect the language of the user's message and respond in that same language. "
                "If you cannot determine the language, default to English."
            )
        else:
            language = self._language
            lang_names = {
                "uk": "Ukrainian", "de": "German", "fr": "French",
                "it": "Italian", "nl": "Dutch", "da": "Danish",
                "es": "Spanish", "ru": "Russian", "en": "English",
                "pl": "Polish", "sv": "Swedish", "no": "Norwegian",
            }
            lang_name = lang_names.get(language, "English")
            parts.append(f"\nYou MUST respond in {lang_name} (code: {language}). Do NOT mix languages.")
        parts.append(f"\nCurrent channel: {channel}.")

        if channel == 'sandbox':
            parts.append(
                "\nYou may use markdown formatting: headers, bold, lists, "
                "code blocks, tables, links. The UI renders markdown."
            )
        else:
            parts.append("\nDo NOT use markdown formatting. Respond in plain text only.")

        if not is_owner_channel and self._has_leads_tool():
            parts.append(
                "\n\nWhen you have contact info or understand the visitor's need, "
                "call save_lead to record it. Update as you learn more."
            )

        if is_owner_channel and self._has_coaching_tool():
            parts.append(
                "\n\nCOACHING: You can review Concierge's (concierge AI) recent conversations "
                "to find knowledge gaps. When you notice Concierge struggled with a topic, "
                "proactively suggest to the user: 'I noticed Concierge couldn't answer questions "
                "about X. Want me to add this to the knowledge base or update his instructions?'\n"
                "ALWAYS ask for user confirmation before making any changes. "
                "Never apply changes silently."
            )

        return "\n".join(parts)

    @staticmethod
    def _build_messages(
        system_prompt: str,
        conversation: list[dict[str, str]] | None,
        current_message: str,
    ) -> list[dict[str, Any]]:
        """Assemble the messages list for the LLM."""
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
        ]
        for msg in (conversation or []):
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": current_message})
        return messages

    async def _build_scope_filter(self):
        """Resolve which MCP servers the current scope may use.

        Platform servers (``settings.MCP_SERVERS``) are available by default
        (per-tool scope rules from ``MCP_TOOL_SCOPES`` still apply); a
        ``ToolConnection`` for this client/scope can opt one out
        (``enabled=False``) or attach per-client credentials and middleware
        (``status='connected'``). Catalog servers (owner-added, DB-defined)
        are the opposite — opt-in: they require an enabled ToolConnection.
        """
        from Jeeves.tools.models import ToolConnection

        self._tool_to_connection = {}
        known_servers = set(self._sessions) | self._dynamic_servers
        self._connected_server_names = set(self._sessions) - self._dynamic_servers

        connections = ToolConnection.objects.filter(
            client=self.client, target=self._scope,
        ).select_related('tool_card')

        async for conn in connections:
            slug = conn.tool_card.slug
            for server_name in known_servers:
                if slug == server_name or slug.startswith(server_name + '-'):
                    if not conn.enabled:
                        self._connected_server_names.discard(server_name)
                    else:
                        self._connected_server_names.add(server_name)
                        if conn.status == 'connected':
                            self._tool_to_connection[server_name] = conn
                    break

        # Live topology snapshot → "## Your deployment" prompt section,
        # so both agents know who works where and what's wired to whom.
        wiring = {}
        async for conn in ToolConnection.objects.filter(
            client=self.client, enabled=True, status='connected',
        ).select_related('tool_card'):
            wiring.setdefault(_safe_label(conn.tool_card.name), set()).add(conn.target)
        channels = []
        if getattr(self.client, 'telegram_bot_token', ''):
            channels.append('Telegram')
        if getattr(self.client, 'whatsapp_meta_enabled', False) or getattr(self.client, 'meta_phone_number_id', ''):
            channels.append('WhatsApp')
        channels.append('Web chat')
        self._deployment = {'wiring': wiring, 'channels': channels}

        # Assigned markdown skills (prompt modules) for the current scope.
        # Lead-handling skills ride with the consultant, who captures leads.
        from Jeeves.tools.models import SkillAssignment
        skill_targets = ['assistant'] if self._scope == 'assistant' else ['manager', 'leads']
        self._skills = []
        async for assignment in SkillAssignment.objects.filter(
            client=self.client, enabled=True, skill__is_active=True,
            target__in=skill_targets,
        ).select_related('skill').order_by('skill__name'):
            self._skills.append((_safe_label(assignment.skill.name), assignment.target, assignment.skill.content))

    def _get_scope_tool_names(self) -> list[str]:
        """Tool names visible to current scope."""
        names = []
        for t in self._tools:
            if self._tool_to_server.get(t.name) not in self._connected_server_names:
                continue
            tool_allowed = self._tool_scopes.get(t.name)
            if tool_allowed is not None and self._scope not in tool_allowed:
                continue
            names.append(t.name)
        return names

    # Human-readable descriptions for connected MCP server groups
    _SERVER_DESCRIPTIONS = {
        'leads': ('Lead Management', 'Search leads, view conversations, qualify leads, track stats and conversion rates'),
        'sales-intel': ('Company Research', 'Detect tech stacks of any website, extract structured data (pricing, team, products)'),
        'rag': ('Knowledge Base', 'Search the knowledge base for answers about the business'),
        'email': ('Email', 'Send emails, read inbox, search by sender/subject, send reports as attachments'),
        'xlsx': ('Excel Reports', 'Generate Excel/XLSX reports and spreadsheets from data'),
        'coaching': ('AI Coaching', 'Review customer-facing AI conversations, find knowledge gaps, suggest improvements'),
        'memory': ('Memory', 'Remember information about users across conversations'),
        'sequential-thinking': ('Deep Thinking', 'Complex multi-step analysis, planning, and reasoning'),
        'escalation': ('Escalation', 'Escalate conversations to human manager when needed'),
        'bridge': ('Platform Connections', 'Connect and manage messaging platforms (Facebook, Instagram, LinkedIn, WhatsApp)'),
    }

    def _get_connected_tool_descriptions(self) -> list[tuple[str, str]]:
        """Return (name, description) pairs for connected server groups."""
        result = []
        seen = set()
        for server_name in sorted(self._connected_server_names):
            if server_name in seen:
                continue
            seen.add(server_name)
            if server_name in self._SERVER_DESCRIPTIONS:
                result.append(self._SERVER_DESCRIPTIONS[server_name])
            elif server_name in self._dynamic_descriptions:
                result.append(self._dynamic_descriptions[server_name])
        return result

    def _has_leads_tool(self) -> bool:
        return 'leads' in self._connected_server_names

    def _has_coaching_tool(self) -> bool:
        return 'coaching' in self._connected_server_names

    def _tools_to_llm_format(self) -> list[dict[str, Any]] | None:
        """Convert MCP tool schemas → OpenAI function-calling tool defs.

        Only tools belonging to servers in ``_connected_server_names`` are
        included. Auto-injected parameters are stripped from the schema.
        """
        if not self._tools:
            return None

        llm_tools = []
        for tool in self._tools:
            server_name = self._tool_to_server.get(tool.name)
            if server_name not in self._connected_server_names:
                continue

            # Tool-level scope filter
            tool_allowed_scopes = self._tool_scopes.get(tool.name)
            if tool_allowed_scopes is not None and self._scope not in tool_allowed_scopes:
                continue

            schema = dict(tool.inputSchema) if tool.inputSchema else {}
            properties = dict(schema.get("properties", {}))
            required = list(schema.get("required", []))
            for param in _AUTO_INJECT_PARAMS:
                properties.pop(param, None)
                if param in required:
                    required.remove(param)

            clean_schema = {"type": "object", "properties": properties}
            if required:
                clean_schema["required"] = required

            llm_tools.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description or "",
                    "parameters": clean_schema,
                },
            })

        return llm_tools or None

    async def _call_llm(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        token_cb=None,
    ) -> dict[str, Any]:
        """Call the LLM provider. Returns dict with 'message' and 'tokens_used'.

        Uses OpenAI-compatible chat completion with function calling. When
        ``token_cb`` is provided, text deltas are streamed to it as they
        arrive. Falls back to plain generation if the provider doesn't
        support tools.
        """
        import asyncio
        from asgiref.sync import sync_to_async

        def _resolve_provider():
            """Sync helper — resolves LLM provider (triggers ORM lookups)."""
            from Jeeves.rag.llm_client import LLMClient
            from Jeeves.clients.models import Client
            # Re-fetch client with related fields to avoid lazy-load in async
            client = Client.objects.select_related(
                'llm_provider_model', 'branch', 'specialization',
            ).get(pk=self.client.pk)
            llm = LLMClient()
            return llm._get_provider(client)

        provider = await sync_to_async(_resolve_provider)()

        # Only OpenAI-compatible providers support tool calling natively
        from Jeeves.rag.providers.llm import OpenAILLMProvider

        if isinstance(provider, OpenAILLMProvider) and tools:
            if token_cb is not None:
                try:
                    return await self._stream_openai_with_tools(
                        provider, messages, tools, token_cb,
                    )
                except Exception:
                    # Some OpenAI-compatible providers reject streaming params —
                    # fall back to the non-streaming call.
                    logger.exception("Streaming LLM call failed — retrying without stream")
            return await self._call_openai_with_tools(provider, messages, tools)

        # Fallback: plain text generation (no tool calling)
        result = await asyncio.to_thread(
            provider.generate,
            messages=messages,
            temperature=self._temperature,
            max_tokens=self._max_tokens,
        )
        return {
            "message": {"role": "assistant", "content": result.get("content", "")},
            "tokens_used": result.get("usage", {}).get("total_tokens"),
            "model": result.get("model", ""),
        }

    async def _call_openai_with_tools(
        self,
        provider: Any,  # OpenAILLMProvider
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """OpenAI chat completion with tool definitions."""
        import asyncio

        def _sync_openai_call():
            """All ORM + OpenAI calls must run in sync thread."""
            model = provider.model_name
            temperature = self._temperature
            max_tokens = self._max_tokens

            model_lower = (model or "").lower()
            no_temp = model_lower.startswith(("o1", "o3", "gpt-5.1"))

            params = {
                "model": model,
                "messages": messages,
                "tools": tools,
                "max_completion_tokens": max_tokens,
                "stream": False,
            }
            if not no_temp:
                params["temperature"] = temperature

            return provider.client.chat.completions.create(**params)

        response = await asyncio.to_thread(_sync_openai_call)

        choice = response.choices[0]
        msg = choice.message

        # Build serialisable assistant message dict
        assistant_msg: dict[str, Any] = {
            "role": "assistant",
            "content": msg.content or "",
        }

        if msg.tool_calls:
            assistant_msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in msg.tool_calls
            ]

        tokens_used = None
        if response.usage:
            tokens_used = response.usage.total_tokens

        return {
            "message": assistant_msg,
            "tokens_used": tokens_used,
            "model": response.model,
        }

    async def _stream_openai_with_tools(
        self,
        provider: Any,  # OpenAILLMProvider
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        token_cb,
    ) -> dict[str, Any]:
        """Streaming OpenAI chat completion with tool definitions.

        Text deltas go to ``token_cb`` as they arrive; tool-call deltas are
        accumulated into the same message shape the non-streaming path
        returns, so the agentic loop is unaffected.
        """
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue = asyncio.Queue()

        def _sync_stream():
            """Iterate the sync OpenAI stream in a thread, feed the loop."""
            model = provider.model_name
            model_lower = (model or "").lower()
            no_temp = model_lower.startswith(("o1", "o3", "gpt-5.1"))

            params = {
                "model": model,
                "messages": messages,
                "tools": tools,
                "max_completion_tokens": self._max_tokens,
                "stream": True,
                "stream_options": {"include_usage": True},
            }
            if not no_temp:
                params["temperature"] = self._temperature

            try:
                for chunk in provider.client.chat.completions.create(**params):
                    loop.call_soon_threadsafe(queue.put_nowait, chunk)
                loop.call_soon_threadsafe(queue.put_nowait, None)
            except BaseException as exc:  # surfaced to the awaiting side
                loop.call_soon_threadsafe(queue.put_nowait, exc)

        stream_task = asyncio.create_task(asyncio.to_thread(_sync_stream))

        content_parts: list[str] = []
        tool_calls_acc: dict[int, dict] = {}  # index -> accumulated tool call
        tokens_used = None
        model_name = ""
        try:
            while True:
                chunk = await queue.get()
                if chunk is None:
                    break
                if isinstance(chunk, BaseException):
                    raise chunk

                model_name = getattr(chunk, "model", "") or model_name
                if getattr(chunk, "usage", None):
                    tokens_used = chunk.usage.total_tokens
                if not chunk.choices:
                    continue

                delta = chunk.choices[0].delta
                if delta is None:
                    continue

                if delta.content:
                    content_parts.append(delta.content)
                    await token_cb(delta.content)

                for tc in delta.tool_calls or []:
                    acc = tool_calls_acc.setdefault(tc.index, {
                        "id": "",
                        "type": "function",
                        "function": {"name": "", "arguments": ""},
                    })
                    if tc.id:
                        acc["id"] = tc.id
                    if tc.function:
                        if tc.function.name:
                            acc["function"]["name"] += tc.function.name
                        if tc.function.arguments:
                            acc["function"]["arguments"] += tc.function.arguments
        finally:
            await stream_task

        assistant_msg: dict[str, Any] = {
            "role": "assistant",
            "content": "".join(content_parts),
        }
        if tool_calls_acc:
            assistant_msg["tool_calls"] = [
                tool_calls_acc[idx] for idx in sorted(tool_calls_acc)
            ]

        return {
            "message": assistant_msg,
            "tokens_used": tokens_used,
            "model": model_name,
        }

    async def _execute_tool_with_middleware(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> tuple[str, str]:
        """Execute tool with pre/post middleware pipeline."""
        from asgiref.sync import sync_to_async
        from Jeeves.tools.models import EdgeMiddleware

        server_name = self._tool_to_server.get(tool_name)
        connection = self._tool_to_connection.get(server_name) if server_name else None

        if not connection:
            return await self._execute_tool(tool_name, arguments)

        middlewares = await sync_to_async(
            lambda: list(
                EdgeMiddleware.objects.filter(
                    connection=connection, enabled=True,
                ).select_related('skill_card').order_by('order')
            )
        )()

        if not middlewares:
            return await self._execute_tool(tool_name, arguments)

        pre = [m for m in middlewares if m.order < 0]
        post = [m for m in middlewares if m.order >= 0]

        # Pre-execution
        processed_args = dict(arguments)
        for mw in pre:
            try:
                result = await self._run_middleware(mw, json.dumps(processed_args), 'pre')
                if result:
                    processed_args = json.loads(result)
            except Exception:
                logger.warning("Pre-middleware '%s' failed, skipping", mw.skill_card.slug, exc_info=True)

        # Execute tool
        result_text, status = await self._execute_tool(tool_name, processed_args)

        # Post-execution
        for mw in post:
            try:
                transformed = await self._run_middleware(mw, result_text, 'post')
                if transformed:
                    result_text = transformed
            except Exception:
                logger.warning("Post-middleware '%s' failed, skipping", mw.skill_card.slug, exc_info=True)

        return result_text, status

    async def _run_middleware(
        self,
        middleware,
        data: str,
        stage: str,
    ) -> str | None:
        """Execute a single middleware skill via MCP tool call."""
        skill_slug = middleware.skill_card.slug
        for tool in self._tools:
            server_name = self._tool_to_server.get(tool.name)
            if server_name and (skill_slug == server_name or skill_slug.startswith(server_name + '-')):
                session = self._sessions.get(server_name)
                if session:
                    config = middleware.config or {}
                    mw_args = {
                        "data": data,
                        "stage": stage,
                        "client_id": self.client.pk,
                        **config,
                    }
                    result = await asyncio.wait_for(
                        session.call_tool(tool.name, mw_args),
                        timeout=_mcp_tool_timeout(),
                    )
                    texts = [item.text for item in result.content if hasattr(item, "text")]
                    return "\n".join(texts) if texts else None
        logger.warning("Middleware skill '%s' not found in MCP servers", skill_slug)
        return None

    async def _execute_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> tuple[str, str]:
        """Call an MCP tool, auto-injecting ``client_id``.

        Returns:
            (result_text, status) where status is 'ok' or 'error'.
        """
        server_name = self._tool_to_server.get(tool_name)
        if not server_name:
            return json.dumps({"error": f"Unknown tool: {tool_name}"}), "error"

        # Auto-inject client_id and session_id
        full_args = dict(arguments)
        full_args["client_id"] = self.client.pk
        full_args["session_id"] = str(self._session.id)
        full_args["user_id"] = self._session.external_user_id or str(self._session.id)

        # Remote (SSE / streamable HTTP) catalog servers connect per call.
        if server_name in self._remote_cards:
            return await self._execute_remote_tool(server_name, tool_name, full_args)

        if self._pool is None and not self._sessions.get(server_name):
            return json.dumps({"error": f"MCP server '{server_name}' not connected"}), "error"

        try:
            # Завислий MCP-сервер не повинен вішати весь агентський запит
            if self._pool is not None:
                result = await self._pool.call_tool(
                    server_name, tool_name, full_args, timeout=_mcp_tool_timeout(),
                )
            else:
                result = await asyncio.wait_for(
                    self._sessions[server_name].call_tool(tool_name, full_args),
                    timeout=_mcp_tool_timeout(),
                )

            # CallToolResult.content is a list of content items
            texts = []
            for item in result.content:
                if hasattr(item, "text"):
                    texts.append(item.text)
            result_text = "\n".join(texts) if texts else ""

            if result.isError:
                return result_text or "Tool returned an error", "error"

            return result_text, "ok"

        except Exception as exc:
            logger.exception("MCP tool '%s' execution failed", tool_name)
            return json.dumps({"error": str(exc)}), "error"

    async def _execute_remote_tool(
        self,
        server_name: str,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> tuple[str, str]:
        """Call a remote catalog MCP server (SSE / streamable HTTP).

        Credentials come from the client's ToolConnection when present
        (``access_token``/``api_key`` → Bearer header).
        """
        card = self._remote_cards[server_name]
        connection = self._tool_to_connection.get(server_name)
        credentials = (connection.credentials or {}) if connection else {}

        headers = {}
        token = credentials.get("access_token") or credentials.get("api_key")
        if token:
            headers["Authorization"] = f"Bearer {token}"

        try:
            result = await asyncio.wait_for(
                self._call_remote_server(card, tool_name, arguments, headers),
                timeout=_mcp_tool_timeout(),
            )
        except Exception as exc:
            logger.exception(
                "Remote MCP tool '%s' on '%s' failed", tool_name, server_name,
            )
            return json.dumps({"error": str(exc)}), "error"

        texts = [item.text for item in result.content if hasattr(item, "text")]
        result_text = "\n".join(texts)
        if result.isError:
            return result_text or "Tool returned an error", "error"
        return result_text, "ok"

    @staticmethod
    async def _call_remote_server(card, tool_name, arguments, headers):
        if card.transport_type == "streamable_http":
            from mcp.client.streamable_http import streamablehttp_client

            async with streamablehttp_client(
                card.mcp_server_url, headers=headers,
            ) as (read_stream, write_stream, _):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    return await session.call_tool(tool_name, arguments)

        from mcp.client.sse import sse_client

        async with sse_client(
            card.mcp_server_url, headers=headers,
        ) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                return await session.call_tool(tool_name, arguments)

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------

    @staticmethod
    async def _log(
        session,
        *,
        call_type: str,
        tool_name: str,
        input_data: dict,
        output_data: dict,
        status: str,
        latency_ms: int = 0,
        tokens_used: int | None = None,
    ) -> None:
        """Persist a log entry to AgentLog (non-blocking)."""
        from asgiref.sync import sync_to_async
        from Jeeves.agents.models import AgentLog

        try:
            await sync_to_async(AgentLog.objects.create)(
                session=session,
                call_type=call_type,
                tool_name=tool_name or "",
                input_data=input_data,
                output_data=output_data,
                status=status,
                latency_ms=latency_ms,
                tokens_used=tokens_used,
            )
        except Exception:
            logger.exception("Failed to write AgentLog")
