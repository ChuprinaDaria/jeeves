"""Generic REST executor for custom (``http_rest``) ToolCards.

A custom integration card declares, in ``auth_config``:
    {
      "base_url": "https://api.example.com",
      "auth": {"type": "bearer"|"header"|"query"|"none",
               "header": "Authorization", "prefix": "Bearer ",
               "param": "api_key", "credential_key": "api_key"},
      "fields": [ {auth form fields, as for any card} ]
    }

and, per tool, in ``tools_schema`` each entry adds:
    {
      "name": "post_message",
      "description": "...",
      "inputSchema": {json schema of LLM-visible args},
      "request": {"method": "POST", "path": "/chat.postMessage",
                  "query": ["channel"], "body": ["text"],
                  "headers": {"X-Extra": "v"}}
    }

The LLM-visible argument names map to path params (``{name}`` in path),
query params, or JSON body keys. Secrets live only in the per-client
``ToolConnection.credentials`` and are injected here, never exposed to the LLM.

SSRF protection is mandatory: only https to public hosts; private, loopback,
link-local and cloud-metadata addresses are refused.
"""
from __future__ import annotations

import ipaddress
import json
import socket
from urllib.parse import urlparse, urlencode

import httpx

HTTP_TIMEOUT = 30.0
_MAX_BODY = 100_000  # chars of response returned to the LLM


class RestError(Exception):
    pass


def _is_blocked_ip(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return True
    return (
        addr.is_private or addr.is_loopback or addr.is_link_local
        or addr.is_reserved or addr.is_multicast or addr.is_unspecified
    )


def validate_url_shallow(url: str) -> None:
    """Cheap creation-time check: https scheme + reject private IP literals.

    No DNS lookup (the host may not exist yet at creation time and we don't
    want to leak resolution / add latency). Full resolved-IP checking happens
    at call time in ``assert_safe_url``.
    """
    parsed = urlparse(url)
    if parsed.scheme != 'https':
        raise RestError("Only https:// URLs are allowed.")
    host = parsed.hostname
    if not host:
        raise RestError("URL has no host.")
    try:
        addr = ipaddress.ip_address(host)  # only checks literal IPs
    except ValueError:
        return  # a hostname — full resolution happens at call time
    if (addr.is_private or addr.is_loopback or addr.is_link_local
            or addr.is_reserved or addr.is_multicast or addr.is_unspecified):
        raise RestError(f"Refusing a private/internal address ({host}).")


def assert_safe_url(url: str) -> None:
    """Block SSRF: https only, public hosts only (all resolved IPs checked)."""
    parsed = urlparse(url)
    if parsed.scheme != 'https':
        raise RestError("Only https:// URLs are allowed.")
    host = parsed.hostname
    if not host:
        raise RestError("URL has no host.")
    try:
        infos = socket.getaddrinfo(host, parsed.port or 443, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise RestError(f"Cannot resolve host '{host}': {exc}")
    for info in infos:
        ip = info[4][0]
        if _is_blocked_ip(ip):
            raise RestError(
                f"Refusing to call a private/internal address ({ip}) — "
                "custom integrations may only reach public hosts.")


def _auth_apply(auth: dict, credentials: dict, headers: dict, query: dict) -> None:
    kind = (auth or {}).get('type', 'none')
    if kind == 'none':
        return
    cred_key = auth.get('credential_key', 'api_key')
    secret = (credentials or {}).get(cred_key, '')
    if not secret:
        return
    if kind == 'bearer':
        headers['Authorization'] = f"Bearer {secret}"
    elif kind == 'header':
        headers[auth.get('header', 'Authorization')] = f"{auth.get('prefix', '')}{secret}"
    elif kind == 'query':
        query[auth.get('param', 'api_key')] = secret


def _find_tool(card, tool_name: str) -> dict | None:
    for entry in (card.tools_schema or []):
        if entry.get('name') == tool_name:
            return entry
    return None


def _build_request(card, tool_entry: dict, arguments: dict, credentials: dict):
    cfg = card.auth_config or {}
    base_url = (cfg.get('base_url') or card.mcp_server_url or '').rstrip('/')
    req = tool_entry.get('request') or {}
    method = (req.get('method') or 'GET').upper()
    path = req.get('path') or '/'

    # Path params: {name} placeholders pulled from arguments
    used = set()
    for key, val in arguments.items():
        token = '{' + key + '}'
        if token in path:
            path = path.replace(token, str(val))
            used.add(key)

    query: dict = {}
    headers: dict = {'Accept': 'application/json'}
    headers.update(req.get('headers') or {})

    for key in req.get('query', []):
        if key in arguments:
            query[key] = arguments[key]
            used.add(key)

    body_keys = req.get('body')
    body = None
    if body_keys:
        body = {k: arguments[k] for k in body_keys if k in arguments}
    elif method in ('POST', 'PUT', 'PATCH'):
        # default: every not-yet-used argument goes into the JSON body
        body = {k: v for k, v in arguments.items() if k not in used}

    _auth_apply(cfg.get('auth') or {}, credentials, headers, query)

    url = f"{base_url}{path}"
    if query:
        url = f"{url}{'&' if '?' in url else '?'}{urlencode(query)}"
    return method, url, headers, body


async def call_http_rest(card, connection, tool_name: str, arguments: dict) -> str:
    """Execute one custom REST tool call. Returns response text for the LLM."""
    tool_entry = _find_tool(card, tool_name)
    if tool_entry is None:
        return json.dumps({"error": f"Unknown endpoint '{tool_name}'"})

    credentials = (getattr(connection, 'credentials', None) or {}) if connection else {}
    method, url, headers, body = _build_request(card, tool_entry, arguments, credentials)

    try:
        assert_safe_url(url)
    except RestError as exc:
        return json.dumps({"error": str(exc)})

    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, follow_redirects=False) as client:
            resp = await client.request(
                method, url, headers=headers,
                json=body if body is not None else None,
            )
    except httpx.HTTPError as exc:
        return json.dumps({"error": f"Request failed: {exc}"})

    text = resp.text[:_MAX_BODY]
    if resp.status_code >= 400:
        return json.dumps({"error": f"HTTP {resp.status_code}", "body": text})
    return text
