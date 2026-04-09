"""MCP Coaching server — Nexy trains Consultant via knowledge base and prompt updates."""
import json
import logging
import uuid
from datetime import timedelta

from mcp_servers.common.django_setup import setup
setup()

from asgiref.sync import sync_to_async  # noqa: E402
from django.utils import timezone  # noqa: E402
from fastmcp import FastMCP  # noqa: E402

logger = logging.getLogger(__name__)

mcp = FastMCP(
    "mcp-coaching",
    description="AI Coaching: review consultant conversations, find gaps, "
    "update knowledge base and consultant instructions.",
)


def _resolve_embedding_model(client_id: int):
    """Resolve embedding model: AgentConfig -> Client -> PlatformDefaults."""
    from MASTER.clients.models import Client
    from MASTER.agents.models import AgentConfig
    from MASTER.nexelin_platform.models import PlatformDefaults

    client = Client.objects.select_related(
        'embedding_model', 'branch', 'specialization',
    ).get(pk=client_id)
    defaults = PlatformDefaults.get()

    try:
        agent_config = AgentConfig.objects.select_related(
            'embedding_model',
        ).get(client=client)
    except AgentConfig.DoesNotExist:
        agent_config = None

    embedding_model = (
        (agent_config.embedding_model if agent_config else None)
        or client.embedding_model
        or defaults.default_embedding_model
    )
    return client, embedding_model


# ---------------------------------------------------------------------------
# Exposed tools (visible to LLM)
# ---------------------------------------------------------------------------

@mcp.tool()
async def review_vasya_conversations(
    client_id: int,
    session_id: str,
    days_back: int = 7,
    min_messages: int = 3,
) -> str:
    """Review Consultant's (consultant AI) recent conversations and identify knowledge gaps.
    Finds conversations where Consultant couldn't answer, gave generic responses,
    or escalated unnecessarily.
    Use this to find areas where the consultant needs training."""

    def _review():
        from MASTER.agents.models import AgentSession, AgentLog

        cutoff = timezone.now() - timedelta(days=days_back)

        sessions = AgentSession.objects.filter(
            agent_config__client_id=client_id,
            started_at__gte=cutoff,
        ).exclude(channel='sandbox')

        gaps = []
        for sess in sessions[:50]:
            logs = list(AgentLog.objects.filter(session=sess).order_by('created_at'))

            llm_logs = [l for l in logs if l.call_type == 'llm']
            rag_logs = [l for l in logs if l.call_type == 'rag']
            esc_logs = [l for l in logs if l.call_type == 'escalation']

            if len(llm_logs) < min_messages:
                continue

            for rl in rag_logs:
                output = rl.output_data or {}
                result_text = output.get('result', '')
                if '"chunks": []' in result_text or '"chunks":[]' in result_text:
                    last_llm = llm_logs[-1] if llm_logs else None
                    snippet = ''
                    if last_llm:
                        snippet = (last_llm.output_data or {}).get('content', '')[:200]
                    gaps.append({
                        "session_id": str(sess.id),
                        "gap_type": "empty_rag",
                        "topic": (rl.input_data or {}).get('query', 'unknown'),
                        "vasya_response_snippet": snippet,
                    })

            for el in esc_logs:
                gaps.append({
                    "session_id": str(sess.id),
                    "gap_type": "escalation",
                    "topic": (el.input_data or {}).get('reason', 'unknown'),
                    "vasya_response_snippet": "",
                })

            unsure_patterns = [
                "i don't have information",
                "i'm not sure",
                "i cannot find",
                "no information available",
                "не маю інформації",
                "не знаю",
                "ich habe keine informationen",
            ]
            for ll in llm_logs:
                content = (ll.output_data or {}).get('content', '').lower()
                for pattern in unsure_patterns:
                    if pattern in content:
                        gaps.append({
                            "session_id": str(sess.id),
                            "gap_type": "unsure_response",
                            "topic": pattern,
                            "vasya_response_snippet": content[:200],
                        })
                        break

        return {"gaps": gaps[:30], "total_sessions_reviewed": min(sessions.count(), 50)}

    result = await sync_to_async(_review)()
    return json.dumps(result, ensure_ascii=False)


@mcp.tool()
async def suggest_knowledge_update(
    client_id: int,
    session_id: str,
    gap_topic: str,
    suggested_content: str,
    update_type: str = "knowledge",
) -> str:
    """Prepare a coaching suggestion for the user. Does NOT apply changes.
    Stores the suggestion as pending and returns formatted text for user confirmation.

    Args:
        gap_topic: What knowledge gap was found.
        suggested_content: The content to add to knowledge base or instructions.
        update_type: 'knowledge' (add to RAG), 'instructions' (update prompt), or 'both'.
    """

    def _suggest():
        from MASTER.agents.models import AgentSession

        suggestion_id = str(uuid.uuid4())[:8]

        try:
            session = AgentSession.objects.get(pk=session_id)
            meta = session.metadata or {}
            pending = meta.get('pending_suggestions', {})
            pending[suggestion_id] = {
                "gap_topic": gap_topic,
                "suggested_content": suggested_content,
                "update_type": update_type,
                "created_at": timezone.now().isoformat(),
            }
            meta['pending_suggestions'] = pending
            session.metadata = meta
            session.save(update_fields=['metadata'])
        except AgentSession.DoesNotExist:
            return {"error": f"Session {session_id} not found"}

        return {
            "status": "suggestion_stored",
            "suggestion_id": suggestion_id,
            "update_type": update_type,
            "message": (
                f"Suggestion stored (ID: {suggestion_id}). "
                f"Present this to the user and ask for confirmation before applying.\n\n"
                f"Topic: {gap_topic}\n"
                f"Proposed content: {suggested_content}\n"
                f"Type: {update_type}"
            ),
        }

    result = await sync_to_async(_suggest)()
    return json.dumps(result, ensure_ascii=False)


@mcp.tool()
async def apply_coaching_suggestion(
    client_id: int,
    session_id: str,
    suggestion_id: str,
) -> str:
    """Apply a previously stored coaching suggestion.
    ONLY call this AFTER the user has explicitly confirmed the suggestion.
    The system verifies that the user's last message was affirmative."""

    def _apply():
        from datetime import timedelta as td
        from MASTER.agents.models import AgentSession, AgentConfig
        from MASTER.clients.models import Client, ClientDocument
        from MASTER.processing.embedding_service import EmbeddingService

        # Resolve current session to find the agent_config (client)
        try:
            current_session = AgentSession.objects.get(pk=session_id)
            config = current_session.agent_config
        except AgentSession.DoesNotExist:
            return {"error": "Session not found"}

        # Search across recent sessions for this client (new session per message)
        suggestion = None
        source_session = None
        cutoff = timezone.now() - td(hours=24)
        recent_sessions = AgentSession.objects.filter(
            agent_config=config,
            started_at__gte=cutoff,
        ).order_by('-started_at')

        for sess in recent_sessions:
            meta = sess.metadata or {}
            pending = meta.get('pending_suggestions', {})
            if suggestion_id in pending:
                suggestion = pending[suggestion_id]
                source_session = sess
                break

        if not suggestion:
            return {"error": f"Suggestion {suggestion_id} not found or already applied"}

        update_type = suggestion['update_type']
        content = suggestion['suggested_content']
        topic = suggestion['gap_topic']
        results = []

        client, embedding_model = _resolve_embedding_model(client_id)

        if update_type in ('knowledge', 'both'):
            try:
                doc = ClientDocument.objects.create(
                    client=client,
                    title=f"Coaching: {topic}",
                    content=content,
                    source='coaching',
                )
                if embedding_model:
                    EmbeddingService.create_embedding(
                        content, embedding_model, client=client, document=doc,
                    )
                results.append(f"Knowledge base updated: document '{doc.title}' created")
            except Exception as e:
                results.append(f"Knowledge base update failed: {e}")

        if update_type in ('instructions', 'both'):
            try:
                agent_config = AgentConfig.objects.get(client=client)
                current = agent_config.consultant_prompt or ''
                agent_config.consultant_prompt = current.rstrip() + f"\n\n{content}"
                agent_config.save(update_fields=['consultant_prompt'])
                results.append("Consultant instructions updated")
            except AgentConfig.DoesNotExist:
                results.append("AgentConfig not found — cannot update instructions")
            except Exception as e:
                results.append(f"Instructions update failed: {e}")

        # Clean up suggestion from source session
        meta = source_session.metadata or {}
        pending = meta.get('pending_suggestions', {})
        del pending[suggestion_id]
        meta['pending_suggestions'] = pending
        source_session.metadata = meta
        source_session.save(update_fields=['metadata'])

        return {"status": "applied", "suggestion_id": suggestion_id, "results": results}

    result = await sync_to_async(_apply)()
    return json.dumps(result, ensure_ascii=False)


@mcp.tool()
async def get_consultant_prompt(
    client_id: int,
    session_id: str,
) -> str:
    """Read Consultant's current consultant_prompt from AgentConfig.
    Use before suggesting changes to understand the current state."""

    def _get():
        from MASTER.agents.models import AgentConfig
        try:
            config = AgentConfig.objects.get(client_id=client_id)
            return {
                "consultant_prompt": config.consultant_prompt or "(empty — using platform default)",
                "consultant_description": config.consultant_description or "",
            }
        except AgentConfig.DoesNotExist:
            return {"consultant_prompt": "(no AgentConfig found)", "consultant_description": ""}

    result = await sync_to_async(_get)()
    return json.dumps(result, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Internal tools — filtered by MCP_TOOL_SCOPES = [] (never exposed to LLM)
# ---------------------------------------------------------------------------

@mcp.tool()
async def update_knowledge_base(
    client_id: int,
    session_id: str,
    title: str,
    content: str,
) -> str:
    """Internal: Add content to RAG knowledge base. Called by apply_coaching_suggestion only."""
    return json.dumps({"error": "This tool is internal. Use apply_coaching_suggestion instead."})


@mcp.tool()
async def update_consultant_instructions(
    client_id: int,
    session_id: str,
    action: str = "append",
    section: str = "",
    content: str = "",
) -> str:
    """Internal: Update consultant prompt. Called by apply_coaching_suggestion only."""
    return json.dumps({"error": "This tool is internal. Use apply_coaching_suggestion instead."})


if __name__ == "__main__":
    mcp.run(transport="stdio")
