"""Google OAuth credentials loader for Jeeves clients.

Reads per-client tokens from ``tools.ToolConnection`` (slug=``google-workspace``)
and rebuilds a ``google.oauth2.credentials.Credentials`` object. Auto-refresh on
expiry is delegated to the Google client library; refreshed tokens are persisted
back to ``ToolConnection.credentials`` so the next call sees the new state.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any


class GoogleCredentialsError(RuntimeError):
    pass


def _get_connection(client_id: int):
    from Jeeves.tools.models import ToolConnection

    conn = (
        ToolConnection.objects.select_related("tool_card")
        .filter(client_id=client_id, tool_card__slug="google-workspace", enabled=True)
        .first()
    )
    if conn is None:
        raise GoogleCredentialsError(
            f"No enabled google-workspace ToolConnection for client {client_id}"
        )
    return conn


def get_credentials(client_id: int, scopes: list[str]):
    """Return refreshed ``google.oauth2.credentials.Credentials`` for the client."""
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
    except ImportError as exc:
        raise GoogleCredentialsError(
            "google-auth libraries are not installed. Add google-api-python-client and "
            "google-auth-oauthlib to requirements.txt."
        ) from exc

    conn = _get_connection(client_id)
    data: dict[str, Any] = dict(conn.credentials or {})
    if not data.get("refresh_token") and not data.get("token"):
        raise GoogleCredentialsError("Stored credentials have no token or refresh_token")

    creds = Credentials(
        token=data.get("token"),
        refresh_token=data.get("refresh_token"),
        token_uri=data.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=data.get("client_id"),
        client_secret=data.get("client_secret"),
        scopes=scopes,
    )
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        # Persist the new access token & expiry so other workers see it.
        data["token"] = creds.token
        if creds.expiry:
            data["expiry"] = creds.expiry.isoformat()
        conn.credentials = data
        conn.save(update_fields=["credentials", "updated_at"])
    return creds


def build_service(client_id: int, service_name: str, version: str, scopes: list[str]):
    """Build a Google API service for the client. Refreshes the token if expired."""
    from googleapiclient.discovery import build

    creds = get_credentials(client_id, scopes)
    return build(service_name, version, credentials=creds, cache_discovery=False)


def build_service_with(creds, service_name: str, version: str):
    """Build a Google API service from an already-resolved ``Credentials`` object.

    Useful when one call site needs two related sub-APIs (e.g.
    ``mybusinessbusinessinformation`` + ``mybusinessreviews``) and we don't
    want to refresh the token twice.
    """
    from googleapiclient.discovery import build

    return build(service_name, version, credentials=creds, cache_discovery=False)


__all__ = [
    "GoogleCredentialsError",
    "get_credentials",
    "build_service",
    "build_service_with",
]
