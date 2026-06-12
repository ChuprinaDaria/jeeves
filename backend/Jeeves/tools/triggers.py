"""Integration triggers — run the owner's agent on external events.

A trigger fires (inbound webhook or schedule) → the assistant (or consultant)
is run with the trigger's instruction plus the event payload, so the agent can
react using its tools (including custom integrations). Per-client, isolated.
"""
from __future__ import annotations

import json
import logging

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)

MAX_PAYLOAD_CHARS = 20_000
MIN_INTERVAL = 60  # seconds — floor for scheduled triggers


def _target_channel(target: str) -> str:
    # assistant scope ⇐ an owner channel; consultant scope ⇐ a customer channel.
    return 'sandbox' if target == 'assistant' else 'web'


def run_trigger_sync(trigger_id: int, event: dict | None = None) -> dict:
    """Run the agent for one trigger. Returns {ok, reply?} or {error}."""
    from Jeeves.agents.dispatch import generate_response_dual
    from Jeeves.tools.models import IntegrationTrigger

    trigger = (IntegrationTrigger.objects
               .select_related('client').filter(pk=trigger_id, enabled=True).first())
    if trigger is None:
        return {"error": "trigger not found or disabled"}

    payload_text = ''
    if event:
        try:
            payload_text = json.dumps(event, ensure_ascii=False)[:MAX_PAYLOAD_CHARS]
        except (TypeError, ValueError):
            payload_text = str(event)[:MAX_PAYLOAD_CHARS]

    message = trigger.instruction.strip()
    if payload_text:
        message += f"\n\nEvent payload:\n{payload_text}"

    try:
        reply = generate_response_dual(
            message=message,
            client=trigger.client,
            conversation=None,
            channel=_target_channel(trigger.target),
            external_user_id=f'trigger-{trigger.pk}',
        )
        trigger.fire_count += 1
        trigger.last_run_at = timezone.now()
        trigger.last_error = ''
        trigger.save(update_fields=['fire_count', 'last_run_at', 'last_error', 'updated_at'])
        return {"ok": True, "reply": (reply or '')[:2000]}
    except Exception as exc:  # noqa: BLE001 — record and surface
        logger.exception("Trigger %s run failed", trigger_id)
        trigger.last_error = str(exc)[:500]
        trigger.save(update_fields=['last_error', 'updated_at'])
        return {"error": str(exc)}


@shared_task(bind=True, max_retries=2)
def run_trigger(self, trigger_id: int, event: dict | None = None):
    result = run_trigger_sync(trigger_id, event)
    if 'error' in result:
        raise self.retry(countdown=30, exc=RuntimeError(result['error']))
    return result


@shared_task
def dispatch_due_triggers():
    """Beat task (every minute): enqueue scheduled triggers that are due."""
    from datetime import timedelta

    from Jeeves.tools.models import IntegrationTrigger

    now = timezone.now()
    due = IntegrationTrigger.objects.filter(
        kind='schedule', enabled=True, next_run_at__lte=now)
    count = 0
    for trigger in due:
        interval = max(trigger.interval_seconds or MIN_INTERVAL, MIN_INTERVAL)
        # Advance next_run_at first (claim it) so a slow run isn't double-fired.
        trigger.next_run_at = now + timedelta(seconds=interval)
        trigger.save(update_fields=['next_run_at', 'updated_at'])
        run_trigger.delay(trigger.pk)
        count += 1
    return {"dispatched": count}
