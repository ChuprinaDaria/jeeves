"""MCP Content Planner server.

Editorial CRUD over ``content_planner.ContentPlan`` / ``ContentPost`` /
``ContentIdea``. Publishing happens by handing a post to the Matrix MCP
(``matrix_send_message``) — there are NO direct Meta Graph / Telegram Bot API
calls here. LLM-driven strategy generation will land in a follow-up iteration
(see ``TODO_strategy_generation`` below).
"""
from mcp_servers.common.django_setup import setup
setup()

import json  # noqa: E402
from datetime import datetime  # noqa: E402

from asgiref.sync import sync_to_async  # noqa: E402
from fastmcp import FastMCP  # noqa: E402

mcp = FastMCP(
    "mcp-content-planner",
    description="Concierge content planner. CRUD for content plans, posts, ideas. Publishes via mcp_matrix.",
)


def _parse_iso(value: str) -> datetime:
    # Accept "...Z" suffix too.
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


# ── Plans ───────────────────────────────────────────────────────────────────
@mcp.tool()
async def cp_create_plan(
    client_id: int,
    title: str,
    start_date: str,
    end_date: str,
    networks: list[str],
) -> str:
    """Create a content plan.

    Args:
        client_id: Jeeves Client id.
        title: plan title.
        start_date: ISO date ``YYYY-MM-DD``.
        end_date: ISO date.
        networks: list of network slugs (``instagram``, ``telegram_channel``, …).
    """

    def _run() -> dict:
        from Jeeves.content_planner.models import ContentPlan

        plan = ContentPlan.objects.create(
            client_id=client_id,
            title=title,
            start_date=start_date,
            end_date=end_date,
            networks=networks,
            status="pending_review",
        )
        return {"id": plan.id, "status": plan.status}

    return json.dumps(await sync_to_async(_run)(), ensure_ascii=False)


@mcp.tool()
async def cp_list_plans(client_id: int, status: str = "") -> str:
    """List a client's content plans, optionally filtered by status."""

    def _run() -> dict:
        from Jeeves.content_planner.models import ContentPlan

        qs = ContentPlan.objects.filter(client_id=client_id)
        if status:
            qs = qs.filter(status=status)
        return {
            "plans": [
                {
                    "id": p.id,
                    "title": p.title,
                    "status": p.status,
                    "start_date": p.start_date.isoformat(),
                    "end_date": p.end_date.isoformat(),
                    "networks": p.networks,
                }
                for p in qs[:100]
            ]
        }

    return json.dumps(await sync_to_async(_run)(), ensure_ascii=False)


@mcp.tool()
async def cp_approve_plan(plan_id: int) -> str:
    """Approve a plan — every ``draft`` post inside becomes ``scheduled``."""

    def _run() -> dict:
        from Jeeves.content_planner.models import ContentPlan

        plan = ContentPlan.objects.get(pk=plan_id)
        plan.approve()
        return {"id": plan.id, "status": plan.status}

    return json.dumps(await sync_to_async(_run)(), ensure_ascii=False)


# ── Posts ───────────────────────────────────────────────────────────────────
@mcp.tool()
async def cp_create_post(
    plan_id: int,
    network: str,
    scheduled_at: str,
    text: str,
    hashtags: list[str] | None = None,
    post_type: str = "text",
    matrix_room_id: str = "",
) -> str:
    """Create a draft post under a plan.

    Args:
        plan_id: ContentPlan id.
        network: ``instagram``, ``threads``, ``telegram_channel``, …
        scheduled_at: ISO datetime.
        text: post body.
        hashtags: optional list.
        post_type: ``text`` | ``image`` | ``video`` | ``carousel`` | ``story``.
        matrix_room_id: Matrix room id to publish into (optional).
    """

    def _run() -> dict:
        from Jeeves.content_planner.models import ContentPost

        post = ContentPost.objects.create(
            content_plan_id=plan_id,
            network=network,
            scheduled_at=_parse_iso(scheduled_at),
            text=text,
            hashtags=hashtags or [],
            post_type=post_type,
            matrix_room_id=matrix_room_id,
        )
        return {"id": post.id, "status": post.status}

    return json.dumps(await sync_to_async(_run)(), ensure_ascii=False)


@mcp.tool()
async def cp_list_posts(plan_id: int, status: str = "") -> str:
    """List posts in a plan, optionally filtered by status."""

    def _run() -> dict:
        from Jeeves.content_planner.models import ContentPost

        qs = ContentPost.objects.filter(content_plan_id=plan_id)
        if status:
            qs = qs.filter(status=status)
        return {
            "posts": [
                {
                    "id": p.id,
                    "network": p.network,
                    "status": p.status,
                    "scheduled_at": p.scheduled_at.isoformat(),
                    "text": p.text,
                    "hashtags": p.hashtags,
                    "post_type": p.post_type,
                    "matrix_room_id": p.matrix_room_id,
                    "matrix_event_id": p.matrix_event_id,
                }
                for p in qs[:200]
            ]
        }

    return json.dumps(await sync_to_async(_run)(), ensure_ascii=False)


@mcp.tool()
async def cp_approve_post(post_id: int) -> str:
    """Move a draft/rescheduled post to ``approved``."""

    def _run() -> dict:
        from Jeeves.content_planner.models import ContentPost

        post = ContentPost.objects.get(pk=post_id)
        post.status = "approved"
        post.save(update_fields=["status", "updated_at"])
        return {"id": post.id, "status": post.status}

    return json.dumps(await sync_to_async(_run)(), ensure_ascii=False)


@mcp.tool()
async def cp_reschedule_post(post_id: int, scheduled_at: str) -> str:
    """Move a post to a new datetime, status becomes ``rescheduled``."""

    def _run() -> dict:
        from Jeeves.content_planner.models import ContentPost

        post = ContentPost.objects.get(pk=post_id)
        post.reschedule(_parse_iso(scheduled_at))
        return {"id": post.id, "status": post.status, "scheduled_at": post.scheduled_at.isoformat()}

    return json.dumps(await sync_to_async(_run)(), ensure_ascii=False)


@mcp.tool()
async def cp_reject_post(post_id: int, reason: str = "") -> str:
    """Reject a post."""

    def _run() -> dict:
        from Jeeves.content_planner.models import ContentPost

        post = ContentPost.objects.get(pk=post_id)
        post.status = "rejected"
        post.rejection_reason = reason
        post.save(update_fields=["status", "rejection_reason", "updated_at"])
        return {"id": post.id, "status": post.status}

    return json.dumps(await sync_to_async(_run)(), ensure_ascii=False)


@mcp.tool()
async def cp_mark_published(post_id: int, matrix_event_id: str = "") -> str:
    """Mark a post as published. Stores Matrix event id when delivery went through mcp_matrix."""

    def _run() -> dict:
        from Jeeves.content_planner.models import ContentPost

        post = ContentPost.objects.get(pk=post_id)
        post.status = "published"
        if matrix_event_id:
            post.matrix_event_id = matrix_event_id
        post.save(update_fields=["status", "matrix_event_id", "updated_at"])
        return {"id": post.id, "status": post.status, "matrix_event_id": post.matrix_event_id}

    return json.dumps(await sync_to_async(_run)(), ensure_ascii=False)


# ── Ideas ───────────────────────────────────────────────────────────────────
@mcp.tool()
async def cp_capture_idea(
    client_id: int,
    topic: str,
    details: str = "",
    network: str = "",
    source_message: str = "",
) -> str:
    """Capture a free-form content idea (e.g. from a chat with the client)."""

    def _run() -> dict:
        from Jeeves.content_planner.models import ContentIdea

        idea = ContentIdea.objects.create(
            client_id=client_id,
            topic=topic,
            details=details,
            network=network,
            source_message=source_message,
        )
        return {"id": idea.id, "topic": idea.topic}

    return json.dumps(await sync_to_async(_run)(), ensure_ascii=False)


@mcp.tool()
async def cp_list_ideas(client_id: int, status: str = "pending") -> str:
    """List captured content ideas."""

    def _run() -> dict:
        from Jeeves.content_planner.models import ContentIdea

        qs = ContentIdea.objects.filter(client_id=client_id)
        if status:
            qs = qs.filter(status=status)
        return {
            "ideas": [
                {
                    "id": i.id,
                    "topic": i.topic,
                    "details": i.details,
                    "network": i.network,
                    "status": i.status,
                    "created_at": i.created_at.isoformat(),
                }
                for i in qs[:200]
            ]
        }

    return json.dumps(await sync_to_async(_run)(), ensure_ascii=False)


# TODO_strategy_generation:
# Port ``sloth/apps/agent/agents/content_strategy/agent.py`` here as
# ``cp_generate_strategy(plan_id, business_context, knowledge_context?, trends?)``.
# Use ``Jeeves.rag.llm_client.LLMClient`` to pick the provider per client; the
# sloth prompt template (`_STRATEGY_SYSTEM`) is reusable as-is. Output is a
# JSON ``{topics: [...], posting_schedule, content_mix}`` that we then fan-out
# into ContentPost rows via ``cp_create_post``.

if __name__ == "__main__":
    mcp.run(transport="stdio")
