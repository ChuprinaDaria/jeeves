"""Google Business Profile (formerly Google My Business) reviews.

Ported skeleton from sloth/google_reviews.py. Full review-fetching loops over
multiple accounts/locations stay TODO until we have a concrete client need —
the My Business API is gated behind a partner program approval, so MVP only
exposes the read path on a known location.
"""
from __future__ import annotations

import json
from typing import Any

from mcp_servers.google_workspace.credentials import build_service_with, get_credentials

SCOPES = ["https://www.googleapis.com/auth/business.manage"]


def _reviews_service(client_id: int):
    """Return a ``mybusinessreviews v1`` Resource for the client.

    The MyBusiness API is split into several sub-services — for now we only
    need the reviews one. Token refresh happens inside ``get_credentials``.
    """
    creds = get_credentials(client_id, SCOPES)
    return build_service_with(creds, "mybusinessreviews", "v1")


async def list_reviews(client_id: int, location_name: str, max_results: int = 20) -> str:
    """List recent reviews for ``locations/{id}``.

    ``location_name`` looks like ``accounts/123/locations/456``.
    """
    from asgiref.sync import sync_to_async

    def _run() -> dict[str, Any]:
        svc = _reviews_service(client_id)
        resp = (
            svc.accounts()
            .locations()
            .reviews()
            .list(parent=location_name, pageSize=max_results)
            .execute()
        )
        items = []
        for r in resp.get("reviews", []):
            items.append(
                {
                    "name": r.get("name"),
                    "reviewer": r.get("reviewer", {}).get("displayName"),
                    "stars": r.get("starRating"),
                    "comment": r.get("comment"),
                    "create_time": r.get("createTime"),
                }
            )
        return {"reviews": items}

    return json.dumps(await sync_to_async(_run)(), ensure_ascii=False)


async def reply_review(client_id: int, review_name: str, comment: str) -> str:
    """Reply to a single review. ``review_name`` is the full resource name."""
    from asgiref.sync import sync_to_async

    def _run() -> dict[str, Any]:
        svc = _reviews_service(client_id)
        resp = (
            svc.accounts()
            .locations()
            .reviews()
            .updateReply(name=review_name, body={"comment": comment})
            .execute()
        )
        return {"name": resp.get("name"), "comment": resp.get("comment")}

    return json.dumps(await sync_to_async(_run)(), ensure_ascii=False)
