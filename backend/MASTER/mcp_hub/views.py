import json
import logging
import asyncio

from django.http import JsonResponse, StreamingHttpResponse
from django.views import View

from MASTER.agents.models import AgentConfig, AgentSession
from MASTER.nexelin_platform.models import FeatureFlag
from MASTER.tools.models import ToolConnection
from .executor import executor

logger = logging.getLogger(__name__)


class ChatSSEView(View):
    """POST /api/mcp/chat/ — SSE streaming chat endpoint.

    Gated by FeatureFlag 'mcp_sse_streaming'.
    Falls back to JSON response when flag is off.
    """

    async def post(self, request):
        client = getattr(request, 'client', None)
        if not client:
            return JsonResponse({'error': 'Client not found'}, status=401)

        if not FeatureFlag.is_enabled('mcp_sse_streaming', client):
            return JsonResponse({
                'error': 'SSE streaming not enabled for this client',
                'hint': 'Enable mcp_sse_streaming feature flag',
            }, status=403)

        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        message = data.get('message', '').strip()
        if not message:
            return JsonResponse({'error': 'Message is required'}, status=400)

        response = StreamingHttpResponse(
            self._stream(request, client, data),
            content_type='text/event-stream',
        )
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'
        return response

    async def _stream(self, request, client, data):
        """Generator — sends SSE events as data arrives."""
        message = data.get('message', '').strip()

        # MCP dual-mode: route to orchestrator for flagged clients
        if FeatureFlag.is_enabled('mcp_real_agent', client):
            async for event in self._stream_mcp(request, client, data):
                yield event
            return

        # Get or create agent config
        try:
            agent_config = await AgentConfig.objects.select_related(
                'llm_provider', 'embedding_model'
            ).aget(client=client)
        except AgentConfig.DoesNotExist:
            agent_config = await AgentConfig.objects.acreate(client=client)

        # Create session
        session = await AgentSession.objects.acreate(
            agent_config=agent_config,
            channel='api',
            metadata={'user_agent': request.META.get('HTTP_USER_AGENT', '')},
        )

        yield self._sse('status', {'step': 'thinking', 'session_id': str(session.id)})

        # RAG search if connected
        rag_conn = await self._get_tool_connection(client, 'rag-search')
        chunks = []
        if rag_conn:
            yield self._sse('status', {'step': 'searching'})
            try:
                result = await executor.call_tool(
                    rag_conn, 'search', {'query': message}, session)
                chunks = result.get('chunks', [])
                yield self._sse('sources', {'chunks': chunks[:5]})
            except Exception as e:
                logger.error(f'RAG search failed: {e}')
                yield self._sse('error', {'step': 'search', 'message': str(e)})

        # LLM generation (streaming)
        yield self._sse('status', {'step': 'generating'})
        try:
            async for token in self._stream_llm(agent_config, message, chunks):
                yield self._sse('token', {'text': token})
        except Exception as e:
            logger.error(f'LLM generation failed: {e}')
            yield self._sse('error', {'step': 'generate', 'message': str(e)})

        yield self._sse('done', {'session_id': str(session.id)})

    async def _stream_mcp(self, request, client, data):
        """MCP orchestrator path — returns full response as SSE events."""
        from MASTER.agents.orchestrator import AgentOrchestrator

        message = data.get('message', '').strip()
        channel = data.get('channel', 'api')

        try:
            agent_config = await AgentConfig.objects.select_related(
                'llm_provider', 'embedding_model'
            ).aget(client=client)
        except AgentConfig.DoesNotExist:
            agent_config = await AgentConfig.objects.acreate(client=client)

        session = await AgentSession.objects.acreate(
            agent_config=agent_config,
            channel=channel,
            metadata={'user_agent': request.META.get('HTTP_USER_AGENT', '')},
        )

        yield self._sse('status', {'step': 'thinking', 'session_id': str(session.id)})

        orchestrator = AgentOrchestrator(client, agent_config)
        await orchestrator.connect()
        try:
            yield self._sse('status', {'step': 'generating'})

            tool_event_queue: asyncio.Queue[tuple[str, dict]] = asyncio.Queue()

            async def tool_event_cb(event_type: str, event_data: dict):
                await tool_event_queue.put((event_type, event_data))

            process_task = asyncio.create_task(
                orchestrator.process(
                    message=message,
                    session=session,
                    conversation=None,
                    channel=channel,
                    external_user_id='',
                    tool_event_cb=tool_event_cb,
                )
            )

            # Drain tool events while the orchestrator is running.
            result = ""
            while True:
                get_task = asyncio.create_task(tool_event_queue.get())
                done, pending = await asyncio.wait(
                    {get_task, process_task},
                    return_when=asyncio.FIRST_COMPLETED,
                )

                if process_task in done:
                    try:
                        result = process_task.result()
                    finally:
                        get_task.cancel()
                    break

                # Queue item wins first.
                try:
                    event_type, event_data = get_task.result()
                    yield self._sse(event_type, event_data)
                finally:
                    # Ensure task is cleaned up.
                    if not get_task.done():
                        get_task.cancel()

            # Drain anything that arrived after process finished.
            while not tool_event_queue.empty():
                event_type, event_data = tool_event_queue.get_nowait()
                yield self._sse(event_type, event_data)

            yield self._sse('token', {'text': result})
        except Exception as e:
            logger.error(f'MCP orchestrator failed in SSE: {e}', exc_info=True)
            yield self._sse('error', {'step': 'generate', 'message': str(e)})
        finally:
            await orchestrator.disconnect()

        yield self._sse('done', {'session_id': str(session.id)})

    async def _get_tool_connection(self, client, tool_slug):
        """Get active tool connection for client."""
        try:
            return await ToolConnection.objects.select_related('tool_card').aget(
                client=client,
                tool_card__slug=tool_slug,
                status='connected',
                enabled=True,
            )
        except ToolConnection.DoesNotExist:
            return None

    async def _stream_llm(self, agent_config, message, chunks):
        """Stream LLM response tokens. Wraps existing LLMClient.generate_response()."""
        from asgiref.sync import sync_to_async

        context = '\n\n'.join(
            c.get('content', c.get('text', '')) if isinstance(c, dict) else str(c)
            for c in chunks[:5]
        ) if chunks else ''

        try:
            response = await sync_to_async(self._generate_sync, thread_sensitive=False)(
                agent_config, message, context)
            if isinstance(response, str):
                yield response
            elif isinstance(response, dict):
                yield response.get('content', '')
            else:
                # Generator from stream=True
                for chunk in response:
                    yield chunk
        except Exception as e:
            logger.error(f'LLM stream error: {e}')
            yield f'Error generating response: {e}'

    def _generate_sync(self, agent_config, message, context):
        """Sync LLM call — uses existing LLMClient."""
        from MASTER.rag.llm_client import LLMClient

        client_obj = agent_config.client
        llm_client = LLMClient()
        return llm_client.generate_response(
            user_query=message,
            context=context,
            client=client_obj,
            specialization=client_obj.specialization,
            branch=client_obj.branch,
            stream=False,
            language=agent_config.get_language(),
        )

    def _sse(self, event: str, data: dict) -> str:
        return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
