"""Google Calendar operations. Logic ported from sloth/google_calendar.py.

Currently implements the minimum needed by Concierge agents: list/create events
and a basic free-slot suggester. More advanced features (Meet links, attendees,
recurring events, reminders) are wired into the schema but kept as TODOs until
ported from sloth.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

from mcp_servers.google_workspace.credentials import build_service

SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/calendar.readonly",
]


def _svc(client_id: int):
    return build_service(client_id, "calendar", "v3", SCOPES)


async def list_events(client_id: int, calendar_id: str = "primary", days_ahead: int = 7, max_results: int = 20) -> str:
    """List upcoming events on a calendar."""
    from asgiref.sync import sync_to_async

    def _run() -> dict[str, Any]:
        svc = _svc(client_id)
        now = datetime.utcnow().isoformat() + "Z"
        end = (datetime.utcnow() + timedelta(days=days_ahead)).isoformat() + "Z"
        resp = (
            svc.events()
            .list(
                calendarId=calendar_id,
                timeMin=now,
                timeMax=end,
                maxResults=max_results,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        items = []
        for ev in resp.get("items", []):
            items.append(
                {
                    "id": ev.get("id"),
                    "summary": ev.get("summary"),
                    "start": ev.get("start", {}).get("dateTime") or ev.get("start", {}).get("date"),
                    "end": ev.get("end", {}).get("dateTime") or ev.get("end", {}).get("date"),
                    "html_link": ev.get("htmlLink"),
                    "attendees": [a.get("email") for a in ev.get("attendees", [])],
                }
            )
        return {"events": items}

    return json.dumps(await sync_to_async(_run)(), ensure_ascii=False)


async def create_event(
    client_id: int,
    summary: str,
    start_iso: str,
    end_iso: str,
    description: str = "",
    attendees: list[str] | None = None,
    calendar_id: str = "primary",
) -> str:
    """Create a calendar event. ``start_iso``/``end_iso`` are RFC3339 strings."""
    from asgiref.sync import sync_to_async

    def _run() -> dict[str, Any]:
        svc = _svc(client_id)
        body: dict[str, Any] = {
            "summary": summary,
            "description": description,
            "start": {"dateTime": start_iso},
            "end": {"dateTime": end_iso},
        }
        if attendees:
            body["attendees"] = [{"email": e} for e in attendees]
        ev = svc.events().insert(calendarId=calendar_id, body=body).execute()
        return {"id": ev.get("id"), "html_link": ev.get("htmlLink"), "status": ev.get("status")}

    return json.dumps(await sync_to_async(_run)(), ensure_ascii=False)


async def suggest_time(
    client_id: int,
    duration_minutes: int = 30,
    working_hours_start: int = 9,
    working_hours_end: int = 18,
    days_ahead: int = 5,
    calendar_id: str = "primary",
) -> str:
    """Suggest the first free working-hours slot of ``duration_minutes`` length.

    Uses Calendar ``freeBusy`` API. Time zone: UTC for now (TODO: per-client TZ).
    """
    from asgiref.sync import sync_to_async

    def _run() -> dict[str, Any]:
        svc = _svc(client_id)
        now = datetime.utcnow().replace(microsecond=0)
        end = now + timedelta(days=days_ahead)
        body = {
            "timeMin": now.isoformat() + "Z",
            "timeMax": end.isoformat() + "Z",
            "items": [{"id": calendar_id}],
        }
        fb = svc.freebusy().query(body=body).execute()
        busy = fb.get("calendars", {}).get(calendar_id, {}).get("busy", [])
        # Walk forward through working hours looking for a free slot.
        cursor = now
        while cursor < end:
            if working_hours_start <= cursor.hour < working_hours_end:
                slot_end = cursor + timedelta(minutes=duration_minutes)
                if all(
                    not (cursor.isoformat() < b["end"] and slot_end.isoformat() > b["start"])
                    for b in busy
                ):
                    return {"suggested_start": cursor.isoformat() + "Z", "suggested_end": slot_end.isoformat() + "Z"}
            cursor += timedelta(minutes=15)
        return {"suggested_start": None, "reason": "no_free_slot_in_window"}

    return json.dumps(await sync_to_async(_run)(), ensure_ascii=False)
