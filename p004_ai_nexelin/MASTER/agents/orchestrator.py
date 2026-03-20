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
_AUTO_INJECT_PARAMS = frozenset({"client_id"})


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

        # Filled by ``connect()``
        self._exit_stack: AsyncExitStack | None = None
        self._sessions: dict[str, ClientSession] = {}  # server_name -> session
        self._tools: list[dict[str, Any]] = []  # MCP Tool dicts
        self._tool_to_server: dict[str, str] = {}  # tool_name -> server_name

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

                t0 = time.monotonic()
                tool_result, tool_status = await self._execute_tool(tool_name, raw_args)
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
        """Build the full system prompt from AgentConfig + tool instructions."""
        base = self.agent_config.system_prompt or "You are a helpful AI assistant."
        language = self.agent_config.get_language()

        parts = [base]

        # Language instruction
        lang_names = {
            "uk": "Ukrainian", "de": "German", "fr": "French",
            "it": "Italian", "nl": "Dutch", "da": "Danish",
            "es": "Spanish", "ru": "Russian", "en": "English",
            "pl": "Polish", "sv": "Swedish", "no": "Norwegian",
        }
        lang_name = lang_names.get(language, "English")
        parts.append(
            f"\nYou MUST respond in {lang_name} (code: {language}). "
            "Do NOT mix languages."
        )

        # Tool usage hints (only if tools are available)
        if self._tools:
            tool_names = [t.name for t in self._tools]
            parts.append(
                "\n\nYou have access to the following tools: "
                + ", ".join(tool_names)
                + ".\nUse them when the user's question requires information "
                "from the knowledge base or an action like escalation. "
                "Do NOT mention tool names to the user."
            )

        # Channel context
        parts.append(f"\nCurrent channel: {channel}.")

        # No markdown
        parts.append(
            "\nDo NOT use markdown formatting. Respond in plain text only."
        )

        return "\n".join(parts)

    @staticmethod
    def _build_messages(
        system_prompt: str,
        conversation: list[dict[str, str]],
        current_message: str,
    ) -> list[dict[str, Any]]:
        """Assemble the messages list for the LLM."""
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
        ]
        for msg in conversation:
            messages.append({
                "role": msg["role"],
                "content": msg["content"],
            })
        messages.append({"role": "user", "content": current_message})
        return messages

    def _tools_to_llm_format(self) -> list[dict[str, Any]] | None:
        """Convert MCP tool schemas → OpenAI function-calling tool defs.

        ``client_id`` is stripped from the schema because the orchestrator
        injects it automatically.
        """
        if not self._tools:
            return None

        llm_tools = []
        for tool in self._tools:
            schema = dict(tool.inputSchema) if tool.inputSchema else {}

            # Strip auto-injected parameters from the schema
            properties = dict(schema.get("properties", {}))
            required = list(schema.get("required", []))
            for param in _AUTO_INJECT_PARAMS:
                properties.pop(param, None)
                if param in required:
                    required.remove(param)

            clean_schema = {
                "type": "object",
                "properties": properties,
            }
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

        return llm_tools

    async def _call_llm(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
    ) -> dict[str, Any]:
        """Call the LLM provider. Returns dict with 'message' and 'tokens_used'.

        Uses OpenAI-compatible chat completion with function calling.
        Falls back to plain generation if the provider doesn't support tools.
        """
        from MASTER.rag.llm_client import LLMClient

        llm = LLMClient()
        provider = llm._get_provider(self.client)

        # Only OpenAI-compatible providers support tool calling natively
        from MASTER.rag.providers.llm import OpenAILLMProvider

        if isinstance(provider, OpenAILLMProvider) and tools:
            return await self._call_openai_with_tools(provider, messages, tools)

        # Fallback: plain text generation (no tool calling)
        result = provider.generate(
            messages=messages,
            temperature=self.agent_config.get_temperature(),
            max_tokens=self.agent_config.get_max_tokens(),
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

        model = provider.model_name
        temperature = self.agent_config.get_temperature()
        max_tokens = self.agent_config.get_max_tokens()

        # Reasoning models don't support temperature
        model_lower = (model or "").lower()
        no_temp = model_lower.startswith(("o1", "o3", "gpt-5.1"))

        params: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "tools": tools,
            "max_completion_tokens": max_tokens,
            "stream": False,
        }
        if not no_temp:
            params["temperature"] = temperature

        # Run sync OpenAI client in a thread
        response = await asyncio.to_thread(
            provider.client.chat.completions.create, **params
        )

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

        # Auto-inject client_id
        full_args = dict(arguments)
        full_args["client_id"] = self.client.pk

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
