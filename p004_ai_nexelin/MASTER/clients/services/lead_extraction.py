"""
Lead extraction service — parses LLM responses for lead data
and creates/updates Lead records.
"""
import json
import re
import logging

from MASTER.clients.models import Lead, Client, ClientWhatsAppConversation

logger = logging.getLogger(__name__)

LEAD_DATA_PATTERN = re.compile(r'\[LEAD_DATA\](.*?)\[/LEAD_DATA\]', re.DOTALL)


def extract_lead_data_from_response(response_text: str) -> dict | None:
    """
    Parse [LEAD_DATA]{...}[/LEAD_DATA] block from LLM response.
    Returns parsed dict or None if no lead data found.
    """
    match = LEAD_DATA_PATTERN.search(response_text)
    if not match:
        return None

    try:
        data = json.loads(match.group(1).strip())
        return data
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning(f"Failed to parse LEAD_DATA JSON: {e}")
        return None


def clean_response(response_text: str) -> str:
    """Remove [LEAD_DATA] block from response before sending to customer."""
    return LEAD_DATA_PATTERN.sub('', response_text).strip()


def save_lead_from_extraction(
    client: Client,
    conversation: ClientWhatsAppConversation,
    lead_data: dict,
    source: str = 'web',
) -> Lead | None:
    """
    Create or update Lead from extracted data.
    Updates existing lead for same conversation, creates new otherwise.
    """
    if not lead_data:
        return None

    # Find existing lead for this conversation
    lead, created = Lead.objects.get_or_create(
        client=client,
        conversation=conversation,
        defaults={
            'source': source,
        }
    )

    # Update fields if provided (don't overwrite with empty values)
    if lead_data.get('name'):
        lead.name = lead_data['name'][:255]
    if lead_data.get('email'):
        lead.email = lead_data['email'][:254]
    if lead_data.get('phone'):
        lead.phone = lead_data['phone'][:50]
    if lead_data.get('request_summary'):
        lead.request_summary = lead_data['request_summary'][:1000]
    if lead_data.get('interest_score'):
        score = int(lead_data['interest_score'])
        lead.interest_score = max(1, min(5, score))

    lead.save()

    action = "Created" if created else "Updated"
    logger.info(f"{action} lead id={lead.id} for client={client.tag}, conversation={conversation.id}")
    return lead
