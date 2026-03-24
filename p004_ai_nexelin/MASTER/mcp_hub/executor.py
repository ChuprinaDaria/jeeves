import importlib
import logging
import time

from MASTER.agents.models import AgentLog

logger = logging.getLogger(__name__)


class MCPExecutor:
    """Single entry point for calling any tool — builtin or external MCP server."""

    async def call_tool(self, tool_connection, tool_name, arguments, session):
        tool_card = tool_connection.tool_card
        log = await AgentLog.objects.acreate(
            session=session,
            tool_connection=tool_connection,
            call_type='tool',
            tool_name=tool_name,
            input_data=arguments,
            status='pending',
        )

        start = time.monotonic()
        try:
            if tool_card.transport_type == 'builtin':
                result = await self._call_builtin(tool_card, tool_connection, tool_name, arguments)
            else:
                result = await self._call_mcp(tool_card, tool_connection, tool_name, arguments)

            log.status = 'ok'
            log.output_data = result
            log.latency_ms = int((time.monotonic() - start) * 1000)
            await log.asave()
            return result

        except Exception as e:
            log.status = 'error'
            log.error_message = str(e)
            log.latency_ms = int((time.monotonic() - start) * 1000)
            await log.asave()

            # Update tool connection error count
            tool_connection.error_count += 1
            tool_connection.last_error = str(e)
            await tool_connection.asave(update_fields=['error_count', 'last_error'])

            logger.error(f'MCP tool call failed: {tool_card.slug}/{tool_name}: {e}')
            raise

    async def _call_builtin(self, tool_card, connection, tool_name, arguments):
        """Call internal Python handler.

        builtin_handler format: 'mcp_hub.builtin.xlsx_processor'
        Imports the module and calls the function with the same name as the
        last segment (e.g. xlsx_processor.xlsx_processor).
        """
        handler_path = tool_card.builtin_handler
        module = importlib.import_module(handler_path)
        func_name = handler_path.rsplit('.', 1)[1]
        handler = getattr(module, func_name)
        return await handler(connection=connection, tool_name=tool_name, **arguments)

    async def _call_mcp(self, tool_card, connection, tool_name, arguments):
        """Call external MCP server via SSE transport."""
        from mcp import ClientSession
        from mcp.client.sse import sse_client

        headers = {}
        # Pass credentials as auth header if available
        token = connection.credentials.get('access_token') or connection.credentials.get('api_key')
        if token:
            headers['Authorization'] = f'Bearer {token}'

        async with sse_client(tool_card.mcp_server_url, headers=headers) as (read, write):
            async with ClientSession(read, write) as mcp_session:
                await mcp_session.initialize()
                result = await mcp_session.call_tool(tool_name, arguments)
                return {'content': [c.model_dump() for c in result.content]}


# Singleton
executor = MCPExecutor()
