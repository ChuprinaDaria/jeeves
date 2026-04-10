from unittest.mock import MagicMock

import pytest
from django.contrib.auth.models import AnonymousUser

from Jeeves.accounts.models import User, Roles
from Jeeves.concierge_platform.permissions import IsOwner


def _req(user):
    req = MagicMock()
    req.user = user
    return req


@pytest.mark.django_db
class TestIsOwner:
    def test_anonymous_denied(self):
        assert IsOwner().has_permission(_req(AnonymousUser()), None) is False

    def test_owner_allowed(self):
        u = User.objects.create_user(
            username="owner@test.com", email="owner@test.com",
            password="x", first_name="a", last_name="b",
            role=Roles.OWNER,
        )
        assert IsOwner().has_permission(_req(u), None) is True

    def test_admin_role_denied(self):
        u = User.objects.create_user(
            username="admin@test.com", email="admin@test.com",
            password="x", first_name="a", last_name="b",
            role=Roles.ADMIN,
        )
        assert IsOwner().has_permission(_req(u), None) is False

    def test_manager_denied(self):
        u = User.objects.create_user(
            username="mgr@test.com", email="mgr@test.com",
            password="x", first_name="a", last_name="b",
            role=Roles.MANAGER,
        )
        assert IsOwner().has_permission(_req(u), None) is False

    def test_client_denied(self):
        u = User.objects.create_user(
            username="client@test.com", email="client@test.com",
            password="x", first_name="a", last_name="b",
            role=Roles.CLIENT,
        )
        assert IsOwner().has_permission(_req(u), None) is False
