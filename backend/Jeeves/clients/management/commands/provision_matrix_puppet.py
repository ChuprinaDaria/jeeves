"""Provision a per-client Matrix puppet user and store its access token.

Creates ``@client-<id>:<MATRIX_DOMAIN>`` via the Synapse Admin API (using the
shared admin bot token), logs the puppet in to capture an access token, and
upserts a ``ToolConnection(slug='matrix')`` row with the credentials.

Usage::

    docker compose exec web python manage.py provision_matrix_puppet --client 7
    docker compose exec web python manage.py provision_matrix_puppet --client 7 --password '...'

Idempotent — re-running rotates the puppet password and refreshes the stored
access token.
"""
from __future__ import annotations

import secrets
from urllib.parse import urlparse

import httpx
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from Jeeves.clients.models import Client
from Jeeves.tools.models import ToolCard, ToolConnection


class Command(BaseCommand):
    help = "Provision a Matrix puppet user for a Jeeves Client and store its ToolConnection."

    def add_arguments(self, parser):
        parser.add_argument("--client", type=int, required=True, help="Jeeves Client id")
        parser.add_argument(
            "--password",
            type=str,
            default=None,
            help="Puppet password (auto-generated if omitted).",
        )
        parser.add_argument(
            "--target",
            type=str,
            default="assistant",
            choices=[c[0] for c in ToolConnection.TARGET_CHOICES],
            help="ToolConnection target (default: assistant).",
        )

    def handle(self, *args, **options):
        client_id: int = options["client"]
        password: str | None = options["password"]
        target: str = options["target"]

        homeserver = settings.MATRIX_HOMESERVER_URL
        admin_token = settings.MATRIX_BOT_TOKEN
        bot_user_id = settings.MATRIX_BOT_USER_ID
        if not (homeserver and admin_token and bot_user_id):
            raise CommandError(
                "MATRIX_HOMESERVER_URL / MATRIX_BOT_USER_ID / MATRIX_BOT_TOKEN must be set."
            )

        domain = bot_user_id.split(":", 1)[1] if ":" in bot_user_id else None
        if not domain:
            raise CommandError(f"Cannot extract domain from MATRIX_BOT_USER_ID={bot_user_id!r}")

        try:
            client = Client.objects.get(pk=client_id)
        except Client.DoesNotExist as exc:
            raise CommandError(f"Client {client_id} does not exist") from exc

        try:
            tool_card = ToolCard.objects.get(slug="matrix")
        except ToolCard.DoesNotExist as exc:
            raise CommandError("ToolCard(slug='matrix') is not seeded. Run migrations.") from exc

        puppet_localpart = f"client-{client_id}"
        puppet_mxid = f"@{puppet_localpart}:{domain}"
        password = password or secrets.token_urlsafe(24)

        self.stdout.write(f"Provisioning {puppet_mxid} on {homeserver}...")
        self._upsert_user_admin_api(homeserver, admin_token, puppet_mxid, password)

        access_token = self._login_puppet(homeserver, puppet_localpart, password)
        self.stdout.write(self.style.SUCCESS(f"Got access token: {access_token[:8]}...{access_token[-4:]}"))

        connection, created = ToolConnection.objects.update_or_create(
            client=client,
            tool_card=tool_card,
            target=target,
            defaults={
                "credentials": {
                    "homeserver_url": homeserver,
                    "user_id": puppet_mxid,
                    "access_token": access_token,
                },
                "status": "connected",
                "enabled": True,
            },
        )

        verb = "Created" if created else "Updated"
        self.stdout.write(self.style.SUCCESS(
            f"{verb} ToolConnection #{connection.pk} (client={client_id}, target={target})"
        ))

    @staticmethod
    def _admin_base(homeserver: str) -> str:
        parsed = urlparse(homeserver)
        if not parsed.scheme:
            return f"http://{homeserver.rstrip('/')}"
        return homeserver.rstrip("/")

    def _upsert_user_admin_api(
        self, homeserver: str, admin_token: str, mxid: str, password: str
    ) -> None:
        """PUT /_synapse/admin/v2/users/{mxid} — creates if absent, resets password if present."""
        url = f"{self._admin_base(homeserver)}/_synapse/admin/v2/users/{mxid}"
        payload = {
            "password": password,
            "admin": False,
            "deactivated": False,
        }
        with httpx.Client(timeout=10.0) as http:
            resp = http.put(url, headers={"Authorization": f"Bearer {admin_token}"}, json=payload)
        if resp.status_code not in (200, 201):
            raise CommandError(
                f"Synapse admin API rejected user provisioning ({resp.status_code}): {resp.text}"
            )

    def _login_puppet(self, homeserver: str, localpart: str, password: str) -> str:
        url = f"{self._admin_base(homeserver)}/_matrix/client/v3/login"
        payload = {
            "type": "m.login.password",
            "identifier": {"type": "m.id.user", "user": localpart},
            "password": password,
        }
        with httpx.Client(timeout=10.0) as http:
            resp = http.post(url, json=payload)
        if resp.status_code != 200:
            raise CommandError(f"Puppet login failed ({resp.status_code}): {resp.text}")
        data = resp.json()
        token = data.get("access_token")
        if not token:
            raise CommandError(f"Login response missing access_token: {data}")
        return token
