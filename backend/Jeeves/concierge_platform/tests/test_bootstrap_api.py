from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from Jeeves.accounts.models import User, Roles
from Jeeves.concierge_platform.models import PlatformLicense


@pytest.fixture
def client():
    return APIClient()


@pytest.mark.django_db
class TestBootstrapEndpoint:
    def test_empty_db_returns_setup_required(self, client):
        resp = client.get("/api/platform/bootstrap/")
        assert resp.status_code == 200
        body = resp.json()
        assert body["setup_required"] is True
        assert body["license_status"] == "missing"
        assert body["license_last_verified_at"] is None
        assert body["grace_days_remaining"] is None

    def test_after_setup_returns_not_required(self, client):
        User.objects.create_user(
            username="o@test.com", email="o@test.com", password="x",
            first_name="o", last_name="w", role=Roles.OWNER,
        )
        lic = PlatformLicense.get()
        lic.license_key = "abc"
        lic.status = PlatformLicense.LicenseStatus.VALID
        lic.last_verified_at = timezone.now()
        lic.setup_completed_at = timezone.now()
        lic.save()

        resp = client.get("/api/platform/bootstrap/")
        assert resp.status_code == 200
        body = resp.json()
        assert body["setup_required"] is False
        assert body["license_status"] == "valid"
        assert body["license_last_verified_at"] is not None

    def test_grace_returns_days_remaining(self, client):
        User.objects.create_user(
            username="o@test.com", email="o@test.com", password="x",
            first_name="o", last_name="w", role=Roles.OWNER,
        )
        lic = PlatformLicense.get()
        lic.status = PlatformLicense.LicenseStatus.GRACE
        lic.last_verified_at = timezone.now() - timedelta(days=2)
        lic.setup_completed_at = timezone.now()
        lic.save()

        resp = client.get("/api/platform/bootstrap/")
        body = resp.json()
        assert body["license_status"] == "grace"
        assert body["grace_days_remaining"] == 5

    def test_owner_exists_but_setup_not_complete(self, client):
        """Aborted wizard: owner created, license not entered."""
        User.objects.create_user(
            username="o@test.com", email="o@test.com", password="x",
            first_name="o", last_name="w", role=Roles.OWNER,
        )
        resp = client.get("/api/platform/bootstrap/")
        body = resp.json()
        assert body["setup_required"] is True
