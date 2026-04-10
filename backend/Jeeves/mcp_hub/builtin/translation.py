"""Builtin translation middleware — auto-translate messages on edges.

Wraps existing translate_text() and detect_language(). Does not rewrite anything.
Bidirectional: translates inbound (client→agent) and outbound (agent→client).
"""
import logging

from asgiref.sync import sync_to_async

logger = logging.getLogger(__name__)


async def translation(connection, tool_name, text='', direction='inbound', **kwargs):
    """Translate message text on an edge.

    Args:
        text: message content to translate
        direction: 'inbound' (client→agent) or 'outbound' (agent→client)
        source_language: optional explicit source lang code (auto-detected if omitted)
        target_language: optional explicit target lang code

    Returns:
        dict with original, translated, source_language, target_language
    """
    if not text or not text.strip():
        return {'original': text, 'translated': text, 'skipped': True}

    client = connection.client
    config = connection.config or {}

    try:
        result = await sync_to_async(_translate_sync)(
            text=text,
            direction=direction,
            client=client,
            config=config,
            source_language=kwargs.get('source_language'),
            target_language=kwargs.get('target_language'),
        )
        return result
    except Exception as e:
        logger.error(f'Translation error for client {client.pk}: {e}')
        return {'original': text, 'translated': text, 'error': str(e)}


def _translate_sync(text, direction, client, config,
                    source_language=None, target_language=None):
    """Sync translation using existing infrastructure."""
    from Jeeves.concierge_platform.language import detect_language
    from Jeeves.clients.news_utils import translate_text

    # Detect source language if not provided
    if not source_language:
        source_language = detect_language(text, fallback='en')

    # Determine target language
    if not target_language:
        if direction == 'inbound':
            # Client→Agent: translate to agent's working language
            target_language = config.get('agent_language') or 'en'
        else:
            # Agent→Client: translate to client's language
            target_language = (
                config.get('client_language')
                or getattr(client, 'language', None)
                or 'en'
            )

    # Skip if same language
    if source_language == target_language:
        return {
            'original': text,
            'translated': text,
            'source_language': source_language,
            'target_language': target_language,
            'skipped': True,
        }

    translated = translate_text(text, target_language)

    return {
        'original': text,
        'translated': translated,
        'source_language': source_language,
        'target_language': target_language,
        'skipped': False,
    }
