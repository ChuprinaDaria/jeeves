"""Single source of truth for channel → agent routing.

A channel is either OWNER-facing (the business owner talks to Jeeves, the
private assistant — full power) or CUSTOMER-facing (visitors talk to the
consultant). Scope and the canvas activity target derive from this one map,
so adding a channel (e.g. a future owner Slack) is a one-line change here
instead of edits scattered across the orchestrator and the views.
"""

# Channels where the OWNER talks to Jeeves (assistant scope).
OWNER_CHANNELS = ('sandbox', 'owner_telegram')


def is_owner_channel(channel: str) -> bool:
    return channel in OWNER_CHANNELS


def channel_scope(channel: str) -> str:
    """Agent scope for a channel: 'assistant' (Jeeves) or 'manager' (consultant)."""
    return 'assistant' if is_owner_channel(channel) else 'manager'


def customer_channels(client) -> list[dict]:
    """Customer-facing channels for a client, as [{id, name, active}].

    Single source for both the canvas channel pills (FlowChannelsView) and
    the consultant's deployment prompt section.
    """
    return [
        {'id': 'telegram', 'name': 'Telegram',
         'active': bool(getattr(client, 'telegram_bot_token', ''))},
        {'id': 'whatsapp', 'name': 'WhatsApp',
         'active': bool(getattr(client, 'whatsapp_meta_enabled', False)
                        or getattr(client, 'meta_phone_number_id', ''))},
        {'id': 'webchat', 'name': 'Web chat', 'active': True},
    ]
