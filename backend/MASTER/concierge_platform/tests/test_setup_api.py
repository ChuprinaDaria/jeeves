import pytest
from rest_framework.test import APIClient

from MASTER.accounts.models import User, Roles


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def owner_payload():
    return {
        "email": "owner@example.com",
        "password": "strongpass123",
        "first_name": "Owner",
        "last_name": "One",
    }


@pytest.mark.django_db
class TestSetupOwner:
    url = "/api/setup/owner/"

    def test_happy_path(self, client, owner_payload):
        resp = client.post(self.url, owner_payload, format="json")
        assert resp.status_code == 201
        body = resp.json()
        assert "access" in body
        assert "refresh" in body
        assert body["user"]["email"] == "owner@example.com"
        user = User.objects.get(email="owner@example.com")
        assert user.role == Roles.OWNER
        assert user.is_superuser is True
        assert user.is_staff is True

    def test_rejects_second_owner(self, client, owner_payload):
        User.objects.create_user(
            username="first@test.com", email="first@test.com", password="x",
            first_name="f", last_name="o", role=Roles.OWNER,
        )
        resp = client.post(self.url, owner_payload, format="json")
        assert resp.status_code == 409
        assert resp.json()["error"] == "owner_exists"

    def test_rejects_taken_email(self, client, owner_payload):
        # Non-owner user with same email
        User.objects.create_user(
            username="owner@example.com", email="owner@example.com",
            password="x", first_name="x", last_name="y", role=Roles.CLIENT,
        )
        resp = client.post(self.url, owner_payload, format="json")
        assert resp.status_code == 400
        body = resp.json()
        # DRF nests field errors under the field name; our serializer
        # raises ValidationError("email_taken") which DRF wraps as
        # {"email": ["email_taken"]}. Accept either shape to be robust.
        assert "email" in body or body.get("error") == "email_taken"

    def test_rejects_weak_password(self, client, owner_payload):
        owner_payload["password"] = "short"
        resp = client.post(self.url, owner_payload, format="json")
        assert resp.status_code == 400

    def test_rejects_invalid_email(self, client, owner_payload):
        owner_payload["email"] = "not-an-email"
        resp = client.post(self.url, owner_payload, format="json")
        assert resp.status_code == 400


from unittest.mock import patch

from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

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
class TestSetupLicense:
    url = "/api/setup/license/"

    def test_requires_auth(self):
        c = APIClient()
        resp = c.post(self.url, {"license_key": "x"}, format="json")
        assert resp.status_code in (401, 403)

    def test_valid_key_saves_and_returns_valid(self):
        c, _ = _owner_client()
        result = GumroadResult(
            outcome="valid",
            data={
                "uses": 1,
                "purchase": {
                    "email": "buyer@example.com",
                    "product_id": "abc",
                },
            },
        )
        with patch(
            "MASTER.concierge_platform.views_setup.gumroad_client.verify_license",
            return_value=result,
        ):
            resp = c.post(self.url, {"license_key": "good-key"}, format="json")
        assert resp.status_code == 200
        assert resp.json()["status"] == "valid"
        lic = PlatformLicense.get()
        assert lic.license_key == "good-key"
        assert lic.status == "valid"
        assert lic.last_verified_at is not None
        assert lic.gumroad_purchase_email == "buyer@example.com"
        assert lic.gumroad_uses == 1

    def test_invalid_key_does_not_save(self):
        c, _ = _owner_client()
        result = GumroadResult(outcome="invalid", error="Not found")
        with patch(
            "MASTER.concierge_platform.views_setup.gumroad_client.verify_license",
            return_value=result,
        ):
            resp = c.post(self.url, {"license_key": "bad"}, format="json")
        assert resp.status_code == 400
        assert resp.json()["error"] == "invalid_key"
        lic = PlatformLicense.get()
        assert lic.license_key == ""
        assert lic.status == "missing"

    def test_network_error_saves_as_grace(self):
        c, _ = _owner_client()
        result = GumroadResult(outcome="network_error", error="timeout")
        with patch(
            "MASTER.concierge_platform.views_setup.gumroad_client.verify_license",
            return_value=result,
        ):
            resp = c.post(self.url, {"license_key": "key"}, format="json")
        assert resp.status_code == 200
        assert resp.json()["status"] == "grace"
        lic = PlatformLicense.get()
        assert lic.license_key == "key"
        assert lic.status == "grace"
        assert lic.last_error == "timeout"
        assert lic.last_attempt_at is not None
        assert lic.last_verified_at is None


@pytest.mark.django_db
class TestSetupComplete:
    url = "/api/setup/complete/"

    def test_requires_auth(self):
        c = APIClient()
        resp = c.post(self.url)
        assert resp.status_code in (401, 403)

    def test_rejects_when_license_missing(self):
        c, _ = _owner_client()
        resp = c.post(self.url)
        assert resp.status_code == 400
        assert resp.json()["error"] == "license_not_ready"

    def test_completes_with_valid_license(self):
        c, _ = _owner_client()
        lic = PlatformLicense.get()
        lic.license_key = "k"
        lic.status = PlatformLicense.LicenseStatus.VALID
        lic.last_verified_at = timezone.now()
        lic.save()
        resp = c.post(self.url)
        assert resp.status_code == 204
        assert PlatformLicense.get().setup_completed_at is not None

    def test_completes_with_grace_license(self):
        c, _ = _owner_client()
        lic = PlatformLicense.get()
        lic.license_key = "k"
        lic.status = PlatformLicense.LicenseStatus.GRACE
        lic.last_attempt_at = timezone.now()
        lic.save()
        resp = c.post(self.url)
        assert resp.status_code == 204

    def test_idempotent_second_call(self):
        c, _ = _owner_client()
        lic = PlatformLicense.get()
        lic.license_key = "k"
        lic.status = PlatformLicense.LicenseStatus.VALID
        lic.last_verified_at = timezone.now()
        lic.setup_completed_at = timezone.now()
        lic.save()
        first_ts = lic.setup_completed_at
        resp = c.post(self.url)
        assert resp.status_code == 204
        # timestamp is NOT overwritten
        assert PlatformLicense.get().setup_completed_at == first_ts
