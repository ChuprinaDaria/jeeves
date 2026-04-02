from datetime import datetime
from zoneinfo import ZoneInfo

from .models_auto_reply import ChannelAutoReply


def should_vasya_respond(client, channel: str, contact_id: str) -> bool:
    """
    Check if Vasya should auto-respond to this message.
    Returns True if Vasya should respond, False to skip.
    """
    if channel in ('web', 'sandbox'):
        return True

    try:
        config = ChannelAutoReply.objects.get(client=client, channel=channel)
    except ChannelAutoReply.DoesNotExist:
        return True

    if not config.enabled:
        return False

    # Schedule check
    if config.schedule_mode == 'scheduled' and config.schedule:
        try:
            tz = ZoneInfo(config.timezone)
        except (KeyError, ValueError):
            tz = ZoneInfo('UTC')

        now = datetime.now(tz)
        current_time = now.strftime('%H:%M')

        day_entry = next(
            (d for d in config.schedule if d.get('day') == now.weekday()),
            None,
        )
        if not day_entry or not day_entry.get('enabled', False):
            return False

        start = day_entry.get('start', '00:00')
        end = day_entry.get('end', '23:59')
        if not (start <= current_time <= end):
            return False

    # Contact filter check
    if config.contact_mode == 'all':
        return True

    normalized = contact_id.lstrip('+')
    normalized_list = [c.lstrip('+') for c in (config.contact_list or [])]

    if config.contact_mode == 'all_except':
        if normalized in normalized_list:
            return False
    elif config.contact_mode == 'only':
        if normalized not in normalized_list:
            return False

    return True
