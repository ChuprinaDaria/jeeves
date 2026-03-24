"""
AgentOrchestrator — core MCP + LLM tool-calling loop.

Spawns MCP servers as STDIO subprocesses, discovers tools,
converts them to OpenAI function-calling format, and runs
the agentic loop until the LLM returns final text.

Every LLM call and tool invocation is logged to AgentLog.
"""

from __future__ import annotations

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

# Parameters that the orchestrator auto-injects (hidden from LLM).
_AUTO_INJECT_PARAMS = frozenset({"client_id", "session_id", "user_id"})

DEFAULT_ASSISTANT_PROMPT = (
    "You are Oleg, the AI business assistant. You help the business owner "
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
    "something important about a user (preferences, needs, context), save it to memory."
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
        self._exit_stack: AsyncExitStack | None = None
        self._sessions: dict[str, ClientSession] = {}  # server_name -> session
        self._tools: list[dict[str, Any]] = []  # MCP Tool dicts
        self._tool_to_server: dict[str, str] = {}  # tool_name -> server_name

        # Scope filtering (set in process())
        self._scope = 'manager'  # default, set in process()
        self._tool_to_connection = {}  # server_name -> ToolConnection
        self._connected_server_names = set()
        self._session = None  # set in process()
        self._tool_scopes: dict[str, list[str]] = getattr(settings, 'MCP_TOOL_SCOPES', {})

    async def connect(self) -> None:
        """Spawn enabled MCP servers and discover their tools."""
        server_defs: dict[str, dict] = getattr(settings, "MCP_SERVERS", {})
        if not server_defs:
            logger.warning("settings.MCP_SERVERS is empty — no MCP tools available")
            return

        self._exit_stack = AsyncExitStack()
        await self._exit_stack.__aenter__()

        env = self._build_subprocess_env()

        for name, cfg in server_defs.items():
            if not cfg.get("enabled", True):
                continue

            params = StdioServerParameters(
                command=cfg["command"],
                args=cfg.get("args", []),
                env=env,
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

    async def disconnect(self) -> None:
        """Tear down all MCP sessions and subprocesses."""
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
        self._scope = 'assistant' if channel == 'sandbox' else 'manager'
        self._session = session

        await self._build_scope_filter()

        system_prompt = self._build_system_prompt(channel)
        messages = self._build_messages(system_prompt, conversation, message)
        llm_tools = self._tools_to_llm_format()

        for iteration in range(MAX_ITERATIONS):
            # --- LLM call ---
            t0 = time.monotonic()
            try:
                response = await self._call_llm(messages, llm_tools)
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
            "DJANGO_SETTINGS_MODULE", "MASTER.settings"
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
        if channel == 'sandbox':
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
                    "When sharing download links, prepend https://api.nexelin.com to the path from the tool "
                    "(e.g. https://api.nexelin.com/media/xlsx/...). "
                    "If a tool fails or is unavailable, say so honestly — never invent data."
                )

        if channel == 'sandbox':
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

        if channel != 'sandbox' and self._has_leads_tool():
            parts.append(
                "\n\nWhen you have contact info or understand the visitor's need, "
                "call save_lead to record it. Update as you learn more."
            )

        if channel == 'sandbox' and self._has_coaching_tool():
            parts.append(
                "\n\nCOACHING: You can review Vasya's (consultant AI) recent conversations "
                "to find knowledge gaps. When you notice Vasya struggled with a topic, "
                "proactively suggest to the user: 'I noticed Vasya couldn't answer questions "
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
        """Build mapping of server_name -> ToolConnection for current scope."""
        from MASTER.tools.models import ToolCard, ToolConnection

        connections = ToolConnection.objects.filter(
            client=self.client, enabled=True, status='connected',
            target=self._scope,
        ).select_related('tool_card')

        self._tool_to_connection = {}
        self._connected_server_names = set()
        async for conn in connections:
            slug = conn.tool_card.slug
            for server_name in self._sessions:
                if slug == server_name or slug.startswith(server_name + '-'):
                    self._tool_to_connection[server_name] = conn
                    self._connected_server_names.add(server_name)
                    break

        # System tools are always available regardless of ToolConnection
        system_slugs = set()
        async for card in ToolCard.objects.filter(is_system=True, is_active=True):
            scopes = card.skill_scopes.get('scopes', ['assistant', 'manager'])
            if self._scope in scopes:
                system_slugs.add(card.slug)
        for server_name in self._sessions:
            if server_name in self._connected_server_names:
                continue
            for slug in system_slugs:
                if slug == server_name or slug.startswith(server_name + '-'):
                    self._connected_server_names.add(server_name)
                    break

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
    ) -> dict[str, Any]:
        """Call the LLM provider. Returns dict with 'message' and 'tokens_used'.

        Uses OpenAI-compatible chat completion with function calling.
        Falls back to plain generation if the provider doesn't support tools.
        """
        import asyncio
        from asgiref.sync import sync_to_async

        def _resolve_provider():
            """Sync helper — resolves LLM provider (triggers ORM lookups)."""
            from MASTER.rag.llm_client import LLMClient
            from MASTER.clients.models import Client
            # Re-fetch client with related fields to avoid lazy-load in async
            client = Client.objects.select_related(
                'llm_provider_model', 'branch', 'specialization',
            ).get(pk=self.client.pk)
            llm = LLMClient()
            return llm._get_provider(client)

        provider = await sync_to_async(_resolve_provider)()

        # Only OpenAI-compatible providers support tool calling natively
        from MASTER.rag.providers.llm import OpenAILLMProvider

        if isinstance(provider, OpenAILLMProvider) and tools:
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

    async def _execute_tool_with_middleware(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> tuple[str, str]:
        """Execute tool with pre/post middleware pipeline."""
        from asgiref.sync import sync_to_async
        from MASTER.tools.models import EdgeMiddleware

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
                    result = await session.call_tool(tool.name, mw_args)
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

        session = self._sessions.get(server_name)
        if not session:
            return json.dumps({"error": f"MCP server '{server_name}' not connected"}), "error"

        # Auto-inject client_id and session_id
        full_args = dict(arguments)
        full_args["client_id"] = self.client.pk
        full_args["session_id"] = str(self._session.id)
        full_args["user_id"] = self._session.external_user_id or str(self._session.id)

        try:
            result = await session.call_tool(tool_name, full_args)

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
        from MASTER.agents.models import AgentLog

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
