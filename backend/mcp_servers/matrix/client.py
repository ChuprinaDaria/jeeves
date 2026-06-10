"""Matrix client wrapper around matrix-nio.

Resolves credentials per Jeeves ``Client`` via ``ToolConnection`` (EncryptedJSONField).
Falls back to a service-account bot (``MATRIX_BOT_*`` settings) for system-level
operations like creating rooms or inviting managers for HITL escalation.

This module deliberately defers the ``nio`` import to call-time so the MCP server
process can boot even before ``matrix-nio[e2e]`` is installed in the venv.
"""
from __future__ import annotations

from typing import Any

from django.conf import settings


class MatrixClientError(RuntimeError):
    pass


def _resolve_credentials(client_id: int | None) -> dict[str, Any]:
    """Return ``{homeserver_url, user_id, access_token}`` for the given Jeeves client.

    When ``client_id`` is None, falls back to the service-account bot configured
    via ``MATRIX_HOMESERVER_URL``/``MATRIX_BOT_USER_ID``/``MATRIX_BOT_TOKEN``.
    """
    homeserver = getattr(settings, "MATRIX_HOMESERVER_URL", None)
    if not homeserver:
        raise MatrixClientError("MATRIX_HOMESERVER_URL is not configured")

    if client_id is None:
        return {
            "homeserver_url": homeserver,
            "user_id": getattr(settings, "MATRIX_BOT_USER_ID", None),
            "access_token": getattr(settings, "MATRIX_BOT_TOKEN", None),
        }

    from Jeeves.tools.models import ToolConnection

    conn = (
        ToolConnection.objects.select_related("tool_card", "client")
        .filter(client_id=client_id, tool_card__slug="matrix", enabled=True)
        .first()
    )
    if conn is None:
        raise MatrixClientError(f"No enabled matrix ToolConnection for client {client_id}")

    creds = dict(conn.credentials or {})
    return {
        "homeserver_url": creds.get("homeserver_url") or homeserver,
        "user_id": creds.get("user_id"),
        "access_token": creds.get("access_token"),
    }


async def get_async_client(client_id: int | None = None):
    """Return a ready-to-use ``nio.AsyncClient`` with token already set.

    Credential lookup hits Django ORM, so it is wrapped in ``sync_to_async`` —
    raw sync ORM access from a coroutine raises ``SynchronousOnlyOperation``
    under Django 4.1+.

    Caller is responsible for ``await client.close()``.
    """
    try:
        from nio import AsyncClient
    except ImportError as exc:
        raise MatrixClientError(
            "matrix-nio is not installed. Add `matrix-nio[e2e]` to requirements.txt."
        ) from exc

    from asgiref.sync import sync_to_async

    creds = await sync_to_async(_resolve_credentials)(client_id)
    if not creds["access_token"] or not creds["user_id"]:
        raise MatrixClientError("Matrix credentials missing user_id or access_token")

    client = AsyncClient(creds["homeserver_url"], creds["user_id"])
    client.access_token = creds["access_token"]
    client.user_id = creds["user_id"]
    return client
