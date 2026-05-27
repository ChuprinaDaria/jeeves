import pytest
from rest_framework.test import APIClient

from Jeeves.accounts.models import User, Roles


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

    def test_after_owner_created_returns_not_required(self, client):
        User.objects.create_user(
            username="o@test.com", email="o@test.com", password="x",
            first_name="o", last_name="w", role=Roles.OWNER,
        )
        resp = client.get("/api/platform/bootstrap/")
        assert resp.status_code == 200
        body = resp.json()
        assert body["setup_required"] is False
