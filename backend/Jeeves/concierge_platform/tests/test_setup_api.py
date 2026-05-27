import pytest
from rest_framework.test import APIClient

from Jeeves.accounts.models import User, Roles


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
