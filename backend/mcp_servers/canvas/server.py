"""
mcp-canvas — FastMCP server that lets Jeeves edit his own flow canvas.

The canvas (Tools page) wires tools to agent targets via ToolConnection rows;
these tools give the assistant real CRUD over that wiring, so "connect email
to the consultant" works from a chat message.

Provides:
- canvas_list_connections(client_id) — current canvas wiring
- canvas_list_available_tools(client_id) — what can be connected
- canvas_add_tool_connection(client_id, tool_slug, targets) — wire a tool
- canvas_remove_tool_connection(client_id, tool_slug, target) — detach an edge
"""
from __future__ import annotations

import json
import logging

from mcp_servers.common.django_setup import setup

setup()

from asgiref.sync import sync_to_async  # noqa: E402
from django.utils import timezone  # noqa: E402
from fastmcp import FastMCP  # noqa: E402

logger = logging.getLogger(__name__)

mcp = FastMCP(
    "mcp-canvas",
    description="Edit the client's flow canvas: connect/disconnect tools for the agents.",
)

VALID_TARGETS = ('assistant', 'manager', 'leads')


# ---------------------------------------------------------------------------
# Sync helpers (plain functions — unit-testable without MCP transport)
# ---------------------------------------------------------------------------

def _get_client(client_id):
    from Jeeves.clients.models import Client
    try:
        return Client.objects.get(pk=client_id)
    except Client.DoesNotExist:
        return None


def list_connections_sync(client_id):
    from Jeeves.tools.models import ToolConnection

    client = _get_client(client_id)
    if client is None:
        return {"error": f"Client {client_id} not found"}

    connections = (
        ToolConnection.objects.filter(client=client, enabled=True)
        .exclude(status='disconnected')
        .select_related('tool_card')
        .order_by('tool_card__slug', 'target')
    )
    return {
        "connections": [
            {
                "tool": conn.tool_card.slug,
                "name": conn.tool_card.name,
                "target": conn.target,
                "status": conn.status,
            }
            for conn in connections
        ]
    }


def list_available_tools_sync(client_id):
    from Jeeves.tools.models import ToolCard, ToolConnection

    client = _get_client(client_id)
    if client is None:
        return {"error": f"Client {client_id} not found"}

    connected = set(
        ToolConnection.objects.filter(client=client, enabled=True)
        .exclude(status='disconnected')
        .values_list('tool_card__slug', 'target')
    )
    tools = []
    for card in ToolCard.objects.filter(is_active=True).order_by('sort_order', 'name'):
        tools.append({
            "tool": card.slug,
            "name": card.name,
            "tagline": card.tagline,
            "needs_credentials": card.auth_type != 'none',
            "connected_targets": sorted(t for s, t in connected if s == card.slug),
        })
    return {"tools": tools}


def add_connection_sync(client_id, tool_slug, targets):
    from Jeeves.tools.models import ToolCard, ToolConnection

    client = _get_client(client_id)
    if client is None:
        return {"error": f"Client {client_id} not found"}

    targets = [t.strip().lower() for t in (targets or []) if t]
    invalid = [t for t in targets if t not in VALID_TARGETS]
    if not targets or invalid:
        return {"error": f"targets must be a non-empty subset of {list(VALID_TARGETS)}"}

    try:
        card = ToolCard.objects.get(slug=tool_slug, is_active=True)
    except ToolCard.DoesNotExist:
        return {"error": f"Unknown tool '{tool_slug}'. Use canvas_list_available_tools first."}

    # Credentials are shared per tool: if any existing connection of this card
    # is already authorized, new targets inherit that; otherwise tools with
    # auth stay 'pending' until the owner authorizes them in the portal.
    has_credentials = (
        card.auth_type == 'none'
        or ToolConnection.objects.filter(
            client=client, tool_card=card, status='connected').exists()
    )

    results = []
    for target in targets:
        conn, _created = ToolConnection.objects.get_or_create(
            client=client, tool_card=card, target=target)
        conn.enabled = True
        if has_credentials:
            conn.status = 'connected'
            if not conn.connected_at:
                conn.connected_at = timezone.now()
        elif conn.status in ('disconnected', 'error', 'expired'):
            conn.status = 'pending'
        conn.save()
        results.append({"target": target, "status": conn.status})

    out = {"tool": card.slug, "name": card.name, "results": results}
    if not has_credentials:
        out["needs_credentials"] = True
        out["note"] = (
            "The tool is wired on the canvas but needs the owner to authorize "
            "it (credentials) on the Tools page before it becomes active."
        )
    return out


def remove_connection_sync(client_id, tool_slug, target):
    from Jeeves.tools.models import ToolConnection

    client = _get_client(client_id)
    if client is None:
        return {"error": f"Client {client_id} not found"}

    target = (target or '').strip().lower()
    if target not in VALID_TARGETS:
        return {"error": f"target must be one of {list(VALID_TARGETS)}"}

    conn = ToolConnection.objects.filter(
        client=client, tool_card__slug=tool_slug, target=target).select_related('tool_card').first()
    if conn is None or not conn.enabled:
        return {"error": f"'{tool_slug}' is not connected to '{target}'"}
    if conn.tool_card.is_system:
        return {"error": f"'{tool_slug}' is a system tool and cannot be detached"}

    # Detach the edge but keep credentials (same semantics as the canvas UI)
    conn.enabled = False
    conn.save(update_fields=['enabled', 'updated_at'])
    return {"tool": tool_slug, "target": target, "detached": True}


def list_skills_sync(client_id):
    from Jeeves.tools.models import Skill, SkillAssignment

    client = _get_client(client_id)
    if client is None:
        return {"error": f"Client {client_id} not found"}

    attached = {}
    for sa in SkillAssignment.objects.filter(
            client=client, enabled=True, skill__is_active=True).select_related('skill'):
        attached.setdefault(sa.skill.slug, []).append(sa.target)

    return {"skills": [
        {
            "skill": skill.slug,
            "name": skill.name,
            "description": skill.description,
            "allowed_targets": skill.allowed_targets or list(VALID_TARGETS),
            "attached_to": sorted(attached.get(skill.slug, [])),
        }
        for skill in Skill.objects.filter(is_active=True)
    ]}


def attach_skill_sync(client_id, skill_slug, target):
    from Jeeves.tools.models import Skill, SkillAssignment

    client = _get_client(client_id)
    if client is None:
        return {"error": f"Client {client_id} not found"}

    target = (target or '').strip().lower()
    if target not in VALID_TARGETS:
        return {"error": f"target must be one of {list(VALID_TARGETS)}"}

    try:
        skill = Skill.objects.get(slug=skill_slug, is_active=True)
    except Skill.DoesNotExist:
        return {"error": f"Unknown skill '{skill_slug}'. Use skill_list first."}

    allowed = skill.allowed_targets or list(VALID_TARGETS)
    if target not in allowed:
        return {"error": f"'{skill_slug}' can only be attached to: {allowed}"}

    assignment, _created = SkillAssignment.objects.get_or_create(
        client=client, skill=skill, target=target)
    if not assignment.enabled:
        assignment.enabled = True
        assignment.save(update_fields=['enabled'])
    return {
        "skill": skill.slug, "target": target, "attached": True,
        "note": "The skill is live: it now shapes that agent's behavior in every conversation.",
    }


def detach_skill_sync(client_id, skill_slug, target):
    from Jeeves.tools.models import SkillAssignment

    client = _get_client(client_id)
    if client is None:
        return {"error": f"Client {client_id} not found"}

    target = (target or '').strip().lower()
    deleted, _ = SkillAssignment.objects.filter(
        client=client, skill__slug=skill_slug, target=target).delete()
    if not deleted:
        return {"error": f"'{skill_slug}' is not attached to '{target}'"}
    return {"skill": skill_slug, "target": target, "detached": True}


# ---------------------------------------------------------------------------
# MCP tools
# ---------------------------------------------------------------------------

@mcp.tool()
async def canvas_list_connections(client_id: int, session_id: str = "", user_id: str = "") -> str:
    """List the current canvas wiring: which tools are connected to which
    agent target (assistant = Jeeves, manager = customer-facing consultant,
    leads = lead capture)."""
    result = await sync_to_async(list_connections_sync)(client_id)
    return json.dumps(result, ensure_ascii=False)


@mcp.tool()
async def canvas_list_available_tools(client_id: int, session_id: str = "", user_id: str = "") -> str:
    """List every tool in the catalog that can be wired on the canvas,
    including whether it needs credentials and where it is already connected."""
    result = await sync_to_async(list_available_tools_sync)(client_id)
    return json.dumps(result, ensure_ascii=False)


@mcp.tool()
async def canvas_add_tool_connection(
    client_id: int,
    tool_slug: str,
    targets: list[str],
    session_id: str = "",
    user_id: str = "",
) -> str:
    """Connect a tool to one or more agent targets on the canvas.

    targets: list of 'assistant' (Jeeves), 'manager' (customer-facing
    consultant) and/or 'leads' (lead capture). The node appears on the
    canvas immediately."""
    result = await sync_to_async(add_connection_sync)(client_id, tool_slug, targets)
    return json.dumps(result, ensure_ascii=False)


@mcp.tool()
async def canvas_remove_tool_connection(
    client_id: int,
    tool_slug: str,
    target: str,
    session_id: str = "",
    user_id: str = "",
) -> str:
    """Detach a tool from an agent target on the canvas. Credentials are
    kept, so reconnecting later does not require re-authorization."""
    result = await sync_to_async(remove_connection_sync)(client_id, tool_slug, target)
    return json.dumps(result, ensure_ascii=False)


def _build_endpoint_schema(endpoints):
    """Turn the LLM-friendly endpoint spec into ToolCard.tools_schema entries.

    Each endpoint: {name, description, method, path, params: [
        {name, type, location: 'path'|'query'|'body', required, description}]}
    """
    schema = []
    for ep in endpoints or []:
        name = (ep.get('name') or '').strip()
        if not name:
            continue
        props, required, query, body = {}, [], [], []
        for p in ep.get('params', []):
            pname = (p.get('name') or '').strip()
            if not pname:
                continue
            props[pname] = {
                'type': p.get('type', 'string'),
                'description': p.get('description', ''),
            }
            if p.get('required'):
                required.append(pname)
            loc = p.get('location', 'body')
            if loc == 'query':
                query.append(pname)
            elif loc == 'body':
                body.append(pname)
            # 'path' params are substituted into the path template by name
        entry = {
            'name': name,
            'description': ep.get('description', ''),
            'inputSchema': {'type': 'object', 'properties': props, 'required': required},
            'request': {
                'method': (ep.get('method') or 'GET').upper(),
                'path': ep.get('path') or '/',
                'query': query,
                'body': body,
            },
        }
        schema.append(entry)
    return schema


def create_http_integration_sync(client_id, name, base_url, endpoints,
                                 auth=None, api_key='', targets=None):
    """Create a per-client custom REST integration card + wire it.

    Owner-scope only (enforced by MCP_TOOL_SCOPES). The card is private to
    this client (owner_client). Secrets go into the encrypted ToolConnection.
    """
    from django.utils.text import slugify

    from Jeeves.tools.http_rest import validate_url_shallow, RestError
    from Jeeves.tools.models import ToolCard, ToolConnection

    client = _get_client(client_id)
    if client is None:
        return {"error": f"Client {client_id} not found"}

    name = (name or '').strip()
    base_url = (base_url or '').strip().rstrip('/')
    if not name or not base_url:
        return {"error": "name and base_url are required"}
    try:
        validate_url_shallow(base_url + '/')
    except RestError as exc:
        return {"error": str(exc)}

    targets = [t.strip().lower() for t in (targets or ['assistant']) if t]
    invalid = [t for t in targets if t not in VALID_TARGETS]
    if invalid:
        return {"error": f"targets must be a subset of {list(VALID_TARGETS)}"}

    schema = _build_endpoint_schema(endpoints)
    if not schema:
        return {"error": "at least one endpoint with a name is required"}

    auth = auth or {}
    auth_type = 'api_key' if (api_key or auth.get('type', 'none') != 'none') else 'none'

    # Namespaced, globally-unique slug for the per-client card.
    base_slug = f"ci-{client.pk}-{slugify(name) or 'integration'}"
    slug = base_slug
    n = 2
    while ToolCard.objects.filter(slug=slug).exists():
        slug = f"{base_slug}-{n}"
        n += 1

    card = ToolCard.objects.create(
        name=name, slug=slug,
        tagline=f"Custom REST integration ({len(schema)} endpoint(s))",
        description=', '.join(e['name'] for e in schema),
        icon='puzzle', color='#6366f1', category='custom',
        transport_type='http_rest',
        mcp_server_url=base_url,
        tools_schema=schema,
        auth_type=auth_type,
        auth_config={'base_url': base_url, 'auth': auth, 'fields': []},
        owner_client=client,
        is_active=True,
        skill_scopes={'scopes': targets},
    )

    creds = {auth.get('credential_key', 'api_key'): api_key} if api_key else {}
    status = 'connected' if (auth_type == 'none' or api_key) else 'pending'
    for target in targets:
        ToolConnection.objects.update_or_create(
            client=client, tool_card=card, target=target,
            defaults={'enabled': True, 'status': status, 'credentials': creds})

    out = {
        "integration": card.slug, "name": card.name,
        "endpoints": [e['name'] for e in schema],
        "targets": targets, "status": status,
    }
    if status == 'pending':
        out["note"] = ("Wired on the canvas but needs an API key — ask the owner "
                       "to authorize it on the Tools page, or provide the key.")
    return out


@mcp.tool()
async def canvas_create_http_integration(
    client_id: int,
    name: str,
    base_url: str,
    endpoints: list,
    auth: dict = None,
    api_key: str = "",
    targets: list = None,
    session_id: str = "",
    user_id: str = "",
) -> str:
    """Create a CUSTOM REST API integration and put it on the canvas.

    Use this when the owner describes an external API to connect. Gather:
    - name: a short human name (e.g. 'Acme CRM')
    - base_url: the API root, https only (e.g. 'https://api.acme.com')
    - endpoints: list of actions the agent can call, each:
        {"name": "create_contact", "description": "...", "method": "POST",
         "path": "/v1/contacts", "params": [
            {"name": "email", "type": "string", "location": "body",
             "required": true, "description": "..."}]}
      'location' is 'path' (use {name} in path), 'query', or 'body'.
    - auth: {"type": "bearer"|"header"|"query"|"none", "credential_key": "api_key",
             "header": "...", "prefix": "...", "param": "..."}
    - api_key: the secret value, if the owner gave one (stored encrypted)
    - targets: which agents get it — ['assistant'] (you), ['manager'] (the
      customer consultant), ['leads']. Default ['assistant'].

    Ask the owner what each endpoint does, when it should be used, and which
    agent should have it BEFORE creating. The node appears on the canvas
    immediately and you can call its endpoints right after."""
    result = await sync_to_async(create_http_integration_sync)(
        client_id, name, base_url, endpoints, auth, api_key, targets)
    return json.dumps(result, ensure_ascii=False)


def list_triggers_sync(client_id):
    from Jeeves.tools.models import IntegrationTrigger

    client = _get_client(client_id)
    if client is None:
        return {"error": f"Client {client_id} not found"}
    return {"triggers": [
        {
            "id": t.pk, "name": t.name, "kind": t.kind, "target": t.target,
            "enabled": t.enabled, "interval_seconds": t.interval_seconds,
            "webhook_url": (f"/api/tools/triggers/webhook/{t.token}/"
                            if t.kind == 'webhook' else None),
            "fire_count": t.fire_count,
        }
        for t in IntegrationTrigger.objects.filter(client=client)
    ]}


def create_trigger_sync(client_id, name, kind, instruction,
                        target='assistant', interval_seconds=None, secret_value=''):
    import secrets

    from django.utils import timezone

    from Jeeves.tools.models import IntegrationTrigger
    from Jeeves.tools.triggers import MIN_INTERVAL

    client = _get_client(client_id)
    if client is None:
        return {"error": f"Client {client_id} not found"}

    name = (name or '').strip()
    instruction = (instruction or '').strip()
    if not name or not instruction:
        return {"error": "name and instruction are required"}
    if kind not in ('webhook', 'schedule'):
        return {"error": "kind must be 'webhook' or 'schedule'"}
    if target not in ('assistant', 'manager'):
        return {"error": "target must be 'assistant' or 'manager'"}

    fields = dict(client=client, name=name, kind=kind, target=target,
                  instruction=instruction)
    if kind == 'webhook':
        fields['token'] = secrets.token_urlsafe(24)
        if secret_value:
            fields['secret'] = {'header': 'X-Webhook-Secret', 'value': secret_value}
    else:
        interval = max(int(interval_seconds or MIN_INTERVAL), MIN_INTERVAL)
        fields['interval_seconds'] = interval
        fields['next_run_at'] = timezone.now() + timezone.timedelta(seconds=interval)

    trigger = IntegrationTrigger.objects.create(**fields)
    out = {"id": trigger.pk, "name": trigger.name, "kind": trigger.kind,
           "target": trigger.target}
    if kind == 'webhook':
        out["webhook_url"] = f"/api/tools/triggers/webhook/{trigger.token}/"
        out["note"] = ("Give this URL to the external system. POST events to it; "
                       "the agent runs on each call."
                       + (" Send the secret in the X-Webhook-Secret header."
                          if secret_value else ""))
    else:
        out["interval_seconds"] = trigger.interval_seconds
        out["note"] = f"The agent will run every {trigger.interval_seconds}s."
    return out


def remove_trigger_sync(client_id, trigger_id):
    from Jeeves.tools.models import IntegrationTrigger

    client = _get_client(client_id)
    if client is None:
        return {"error": f"Client {client_id} not found"}
    deleted, _ = IntegrationTrigger.objects.filter(
        client=client, pk=trigger_id).delete()
    if not deleted:
        return {"error": f"Trigger {trigger_id} not found"}
    return {"removed": True, "id": trigger_id}


@mcp.tool()
async def canvas_create_trigger(
    client_id: int,
    name: str,
    kind: str,
    instruction: str,
    target: str = "assistant",
    interval_seconds: int = None,
    secret_value: str = "",
    session_id: str = "",
    user_id: str = "",
) -> str:
    """Create an automation trigger that runs the agent on an external event.

    kind:
    - 'webhook': returns a secret URL; when an external system POSTs to it,
      the agent runs with the request body as the event. Optionally set
      secret_value to require an X-Webhook-Secret header.
    - 'schedule': the agent runs every interval_seconds (min 60).
    instruction: what the agent should DO when it fires (the event payload is
    appended automatically). target: 'assistant' (Jeeves) or 'manager'.

    Ask the owner WHEN it should fire, WHAT it should do, and WHICH agent
    before creating."""
    result = await sync_to_async(create_trigger_sync)(
        client_id, name, kind, instruction, target, interval_seconds, secret_value)
    return json.dumps(result, ensure_ascii=False)


@mcp.tool()
async def canvas_list_triggers(client_id: int, session_id: str = "", user_id: str = "") -> str:
    """List the client's automation triggers (webhook URLs + schedules)."""
    result = await sync_to_async(list_triggers_sync)(client_id)
    return json.dumps(result, ensure_ascii=False)


@mcp.tool()
async def canvas_remove_trigger(client_id: int, trigger_id: int,
                                session_id: str = "", user_id: str = "") -> str:
    """Delete an automation trigger by id."""
    result = await sync_to_async(remove_trigger_sync)(client_id, trigger_id)
    return json.dumps(result, ensure_ascii=False)


@mcp.tool()
async def skill_list(client_id: int, session_id: str = "", user_id: str = "") -> str:
    """List markdown skills (prompt modules like 'Marketing Pro' or 'Lead
    Qualifier') with where each is currently attached. Skills change HOW an
    agent communicates; tools change WHAT it can do."""
    result = await sync_to_async(list_skills_sync)(client_id)
    return json.dumps(result, ensure_ascii=False)


@mcp.tool()
async def skill_attach(
    client_id: int,
    skill_slug: str,
    target: str,
    session_id: str = "",
    user_id: str = "",
) -> str:
    """Attach a skill to an agent: 'manager' (customer-facing consultant —
    e.g. marketing/sales style in Telegram and WhatsApp), 'assistant'
    (Jeeves himself) or 'leads' (lead qualification discipline)."""
    result = await sync_to_async(attach_skill_sync)(client_id, skill_slug, target)
    return json.dumps(result, ensure_ascii=False)


@mcp.tool()
async def skill_detach(
    client_id: int,
    skill_slug: str,
    target: str,
    session_id: str = "",
    user_id: str = "",
) -> str:
    """Detach a skill from an agent target."""
    result = await sync_to_async(detach_skill_sync)(client_id, skill_slug, target)
    return json.dumps(result, ensure_ascii=False)


if __name__ == "__main__":
    mcp.run()
