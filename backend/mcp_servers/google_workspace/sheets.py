"""Google Sheets operations. Logic ported from sloth/google_sheets.py.

MVP: read a range, append a row. Sheet templating + export pipelines (clients/
appointments) stay in sloth for now — Concierge will call these primitives
directly until we have a clear use-case in Jeeves.
"""
from __future__ import annotations

import json
from typing import Any

from mcp_servers.google_workspace.credentials import build_service

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def _svc(client_id: int):
    return build_service(client_id, "sheets", "v4", SCOPES)


async def read_range(client_id: int, spreadsheet_id: str, sheet_range: str) -> str:
    """Read a range (e.g. ``Sheet1!A1:C10``) and return rows."""
    from asgiref.sync import sync_to_async

    def _run() -> dict[str, Any]:
        svc = _svc(client_id)
        resp = (
            svc.spreadsheets()
            .values()
            .get(spreadsheetId=spreadsheet_id, range=sheet_range)
            .execute()
        )
        return {"range": resp.get("range"), "values": resp.get("values", [])}

    return json.dumps(await sync_to_async(_run)(), ensure_ascii=False)


async def append_row(client_id: int, spreadsheet_id: str, sheet_range: str, values: list[Any]) -> str:
    """Append a row to a sheet. ``values`` is a flat list of cell values."""
    from asgiref.sync import sync_to_async

    def _run() -> dict[str, Any]:
        svc = _svc(client_id)
        resp = (
            svc.spreadsheets()
            .values()
            .append(
                spreadsheetId=spreadsheet_id,
                range=sheet_range,
                valueInputOption="USER_ENTERED",
                insertDataOption="INSERT_ROWS",
                body={"values": [values]},
            )
            .execute()
        )
        return {"updates": resp.get("updates", {})}

    return json.dumps(await sync_to_async(_run)(), ensure_ascii=False)
