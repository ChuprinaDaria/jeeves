"""Dual-mode dispatch: MCP agent vs legacy pipeline."""
import logging
from asgiref.sync import async_to_sync
from MASTER.concierge_platform.models import FeatureFlag

logger = logging.getLogger(__name__)


def generate_response_dual(message, client, conversation=None, channel='web', external_user_id=''):
    """Route to MCP orchestrator or legacy pipeline based on FeatureFlag.

    Drop-in replacement for generate_response / ResponseGenerator.generate().
    Returns response text string.
    """
    if FeatureFlag.is_enabled('mcp_real_agent', client):
        return _mcp_generate(message, client, conversation, channel, external_user_id)
    return _legacy_generate(message, client)


def _mcp_generate(message, client, conversation, channel, external_user_id):
    """Run through MCP AgentOrchestrator with fallback to legacy on error."""
    try:
        return async_to_sync(_mcp_generate_async)(
            message, client, conversation, channel, external_user_id
        )
    except Exception as e:
        logger.error(f'MCP orchestrator failed for client {client.pk}: {e}', exc_info=True)
        logger.info(f'Falling back to legacy pipeline for client {client.pk}')
        return _legacy_generate(message, client)


async def _mcp_generate_async(message, client, conversation, channel, external_user_id):
    from MASTER.agents.models import AgentConfig, AgentSession
    from MASTER.agents.orchestrator import AgentOrchestrator

    try:
        agent_config = await AgentConfig.objects.select_related(
            'llm_provider', 'embedding_model'
        ).aget(client=client)
    except AgentConfig.DoesNotExist:
        agent_config = await AgentConfig.objects.acreate(client=client)

    session = await AgentSession.objects.acreate(
        agent_config=agent_config,
        channel=channel,
        external_user_id=external_user_id,
    )

    orchestrator = AgentOrchestrator(client, agent_config)
    await orchestrator.connect()
    try:
        return await orchestrator.process(
            message=message,
            session=session,
            conversation=conversation,
            channel=channel,
            external_user_id=external_user_id,
        )
    finally:
        await orchestrator.disconnect()


def _legacy_generate(message, client):
    """Existing RAG pipeline -- unchanged."""
    from MASTER.rag.response_generator import ResponseGenerator
    generator = ResponseGenerator()
    result = generator.generate(
        query=message,
        client=client,
        specialization=getattr(client, 'specialization', None),
        branch=getattr(client, 'branch', None),
        stream=False,
    )
    if hasattr(result, 'answer'):
        return result.answer
    return str(result)
