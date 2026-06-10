"""MCP Google Workspace server — Calendar, Sheets, Business Reviews.

Per-client OAuth tokens are stored in ``tools.ToolConnection.credentials`` for
``slug='google-workspace'`` and look like::

    {
      "client_id": "...apps.googleusercontent.com",
      "client_secret": "...",
      "token": "ya29...",
      "refresh_token": "1//...",
      "token_uri": "https://oauth2.googleapis.com/token",
      "expiry": "2026-06-10T12:00:00",
      "scopes": ["calendar.events", "spreadsheets", ...]
    }

Calendly logic from sloth was intentionally left out of this MVP — Calendly's
OAuth + webhook story is non-trivial and can land as a separate MCP later.
"""
from mcp_servers.common.django_setup import setup
setup()

from fastmcp import FastMCP  # noqa: E402

from mcp_servers.google_workspace.calendar import (  # noqa: E402
    list_events as _list_events,
    create_event as _create_event,
    suggest_time as _suggest_time,
)
from mcp_servers.google_workspace.sheets import (  # noqa: E402
    read_range as _read_range,
    append_row as _append_row,
)
from mcp_servers.google_workspace.reviews import (  # noqa: E402
    list_reviews as _list_reviews,
    reply_review as _reply_review,
)

mcp = FastMCP(
    "mcp-google-workspace",
    description="Concierge Google Workspace server. Calendar, Sheets and Business reviews.",
)


# ── Calendar ────────────────────────────────────────────────────────────────
@mcp.tool()
async def gcal_list_events(
    client_id: int,
    calendar_id: str = "primary",
    days_ahead: int = 7,
    max_results: int = 20,
) -> str:
    """List upcoming events on the user's Google Calendar."""
    return await _list_events(client_id, calendar_id, days_ahead, max_results)


@mcp.tool()
async def gcal_create_event(
    client_id: int,
    summary: str,
    start_iso: str,
    end_iso: str,
    description: str = "",
    attendees: list[str] | None = None,
    calendar_id: str = "primary",
) -> str:
    """Create a Google Calendar event.

    Args:
        summary: event title.
        start_iso: RFC3339 datetime (e.g. ``2026-06-12T10:00:00Z``).
        end_iso: RFC3339 datetime.
        description: optional body.
        attendees: list of attendee emails.
        calendar_id: calendar id (default ``primary``).
    """
    return await _create_event(client_id, summary, start_iso, end_iso, description, attendees, calendar_id)


@mcp.tool()
async def gcal_suggest_time(
    client_id: int,
    duration_minutes: int = 30,
    working_hours_start: int = 9,
    working_hours_end: int = 18,
    days_ahead: int = 5,
    calendar_id: str = "primary",
) -> str:
    """Suggest the first free working-hours slot of the given length."""
    return await _suggest_time(client_id, duration_minutes, working_hours_start, working_hours_end, days_ahead, calendar_id)


# ── Sheets ──────────────────────────────────────────────────────────────────
@mcp.tool()
async def sheets_read_range(client_id: int, spreadsheet_id: str, sheet_range: str) -> str:
    """Read a range from a Google Sheet, e.g. ``Sheet1!A1:C10``."""
    return await _read_range(client_id, spreadsheet_id, sheet_range)


@mcp.tool()
async def sheets_append_row(client_id: int, spreadsheet_id: str, sheet_range: str, values: list[str]) -> str:
    """Append a row to a sheet.

    Args:
        spreadsheet_id: Google Sheet id.
        sheet_range: target range (e.g. ``Sheet1!A:E``).
        values: flat list of cell values.
    """
    return await _append_row(client_id, spreadsheet_id, sheet_range, values)


# ── Reviews ─────────────────────────────────────────────────────────────────
@mcp.tool()
async def reviews_list(client_id: int, location_name: str, max_results: int = 20) -> str:
    """List recent Google Business reviews for a location (``accounts/X/locations/Y``)."""
    return await _list_reviews(client_id, location_name, max_results)


@mcp.tool()
async def reviews_reply(client_id: int, review_name: str, comment: str) -> str:
    """Reply to a single Google Business review by its full resource name."""
    return await _reply_review(client_id, review_name, comment)


if __name__ == "__main__":
    mcp.run(transport="stdio")
