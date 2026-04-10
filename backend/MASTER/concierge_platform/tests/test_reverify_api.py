from unittest.mock import patch

import pytest
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from MASTER.accounts.models import User, Roles
from MASTER.concierge_platform.gumroad_client import GumroadResult
from MASTER.concierge_platform.models import PlatformLicense


def _owner_client():
    user = User.objects.create_user(
        username="o@test.com", email="o@test.com", password="x",
        first_name="o", last_name="w", role=Roles.OWNER,
        is_staff=True, is_superuser=True,
    )
    c = APIClient()
    token = str(RefreshToken.for_user(user).access_token)
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return c, user


@pytest.mark.django_db
class TestReverify:
    url = "/api/owner/license/reverify/"

    def test_requires_owner(self):
        c = APIClient()
        resp = c.post(self.url)
        assert resp.status_code in (401, 403)

    def test_grace_to_valid(self):
        c, _ = _owner_client()
        lic = PlatformLicense.get()
        lic.license_key = "k"
        lic.status = PlatformLicense.LicenseStatus.GRACE
        lic.last_attempt_at = timezone.now()
        lic.save()

        result = GumroadResult(
            outcome="valid",
            data={"uses": 2, "purchase": {"email": "b@e", "product_id": "p"}},
        )
        with patch(
            "MASTER.concierge_platform.views_owner.gumroad_client.verify_license",
            return_value=result,
        ):
            resp = c.post(self.url)
        assert resp.status_code == 200
        assert resp.json()["status"] == "valid"
        assert PlatformLicense.get().status == "valid"

    def test_allowed_when_expired(self):
        """Expired licenses can still call reverify — that's how owners recover."""
        c, _ = _owner_client()
        lic = PlatformLicense.get()
        lic.license_key = "k"
        lic.status = PlatformLicense.LicenseStatus.EXPIRED
        lic.save()

        result = GumroadResult(outcome="invalid", error="Still rejected")
        with patch(
            "MASTER.concierge_platform.views_owner.gumroad_client.verify_license",
            return_value=result,
        ):
            resp = c.post(self.url)
        assert resp.status_code == 200
        assert resp.json()["status"] == "expired"
        # status unchanged — Gumroad still rejects
        assert PlatformLicense.get().status == "expired"

    def test_rejects_when_no_key_stored(self):
        c, _ = _owner_client()
        resp = c.post(self.url)
        assert resp.status_code == 400
        assert resp.json()["error"] == "no_license_key"
