import json
import logging

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
            self._stream(request, client, message),
            content_type='text/event-stream',
        )
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'
        return response

    async def _stream(self, request, client, message):
        """Generator — sends SSE events as data arrives."""

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
