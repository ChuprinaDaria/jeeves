import pytest
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from Jeeves.accounts.models import User, Roles
from Jeeves.branches.models import Branch
from Jeeves.concierge_platform.models import PlatformLicense


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
class TestDashboardStats:
    url = "/api/owner/dashboard/stats/"

    def test_requires_owner(self):
        c = APIClient()
        resp = c.get(self.url)
        assert resp.status_code in (401, 403)

    def test_client_role_denied(self):
        u = User.objects.create_user(
            username="c@test.com", email="c@test.com", password="x",
            first_name="c", last_name="l", role=Roles.CLIENT,
        )
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(u).access_token}")
        resp = c.get(self.url)
        assert resp.status_code == 403

    def test_empty_db_returns_zeros(self):
        c, _ = _owner_client()
        resp = c.get(self.url)
        assert resp.status_code == 200
        body = resp.json()
        assert body["counters"] == {
            "branches": 0,
            "specializations": 0,
            "clients": 0,
            "documents": 0,
        }
        assert body["config_health"]["license_valid"] is False
        assert body["config_health"]["branches_exist"] is False
        assert body["license"]["status"] == "missing"

    def test_with_data(self):
        c, owner = _owner_client()
        Branch.objects.create(name="B1", slug="b1")
        Branch.objects.create(name="B2", slug="b2")
        lic = PlatformLicense.get()
        lic.status = PlatformLicense.LicenseStatus.VALID
        lic.last_verified_at = timezone.now()
        lic.save()

        resp = c.get(self.url)
        body = resp.json()
        assert body["counters"]["branches"] == 2
        assert body["config_health"]["branches_exist"] is True
        assert body["config_health"]["license_valid"] is True
        assert body["license"]["status"] == "valid"
