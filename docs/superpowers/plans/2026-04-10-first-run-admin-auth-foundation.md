# First-run + Admin auth foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the existing Jeeves codebase into a white-label self-hosted platform by adding a first-run setup wizard, OWNER authentication, Gumroad license-key integration, and the admin panel shell at `/owner/*`.

**Architecture:** Extend the existing `MASTER/concierge_platform/` Django app with one new singleton model (`PlatformLicense`), a Gumroad HTTP client module, six new DRF endpoints, and a new `IsOwner` permission. On the frontend, add a `/setup` wizard, a new `/owner/*` route tree that reuses the existing `<Layout />` Concierge chrome, and a `<BootstrapGate>` component backed by a single `GET /api/platform/bootstrap` endpoint.

**Tech Stack:** Python 3.11, Django 5.x, Django REST Framework, djangorestframework_simplejwt, pytest-django, React 18, React Router v6, Tailwind (existing Concierge palette), axios.

**Spec:** `docs/superpowers/specs/2026-04-10-first-run-admin-auth-foundation-design.md`

---

## File Structure

### Backend files (new or modified)

| Action | Path | Responsibility |
|---|---|---|
| Modify | `MASTER/concierge_platform/models.py` | Append `PlatformLicense` model (singleton) |
| Create | `MASTER/concierge_platform/migrations/0007_platformlicense.py` | Migration for the new model |
| Create | `MASTER/concierge_platform/gumroad_client.py` | Isolated HTTP client for Gumroad license verify API |
| Create | `MASTER/concierge_platform/permissions.py` | `IsOwner` DRF permission class |
| Create | `MASTER/concierge_platform/serializers.py` | DRF serializers for setup/bootstrap/dashboard requests & responses |
| Create | `MASTER/concierge_platform/views_platform.py` | Public bootstrap view |
| Create | `MASTER/concierge_platform/views_setup.py` | Setup wizard endpoints (create owner, license, complete) |
| Create | `MASTER/concierge_platform/views_owner.py` | Dashboard stats + license reverify |
| Create | `MASTER/concierge_platform/urls.py` | URL patterns for the three view files |
| Modify | `MASTER/urls.py` | Mount `MASTER.concierge_platform.urls` at `/api/` |
| Modify | `MASTER/settings.py` | Add `GUMROAD_PRODUCT_ID` setting with startup check |
| Create | `MASTER/concierge_platform/tests/test_license_model.py` | Unit tests for `PlatformLicense` |
| Create | `MASTER/concierge_platform/tests/test_gumroad_client.py` | Unit tests for Gumroad client |
| Create | `MASTER/concierge_platform/tests/test_permissions.py` | Unit tests for `IsOwner` |
| Create | `MASTER/concierge_platform/tests/test_bootstrap_api.py` | Integration test for bootstrap endpoint |
| Create | `MASTER/concierge_platform/tests/test_setup_api.py` | Integration tests for setup endpoints |
| Create | `MASTER/concierge_platform/tests/test_dashboard_api.py` | Integration test for dashboard stats |
| Create | `MASTER/concierge_platform/tests/test_reverify_api.py` | Integration test for license reverify |

### Frontend files (new or modified)

| Action | Path | Responsibility |
|---|---|---|
| Create | `frontend/src/api/owner.js` | API client: `platformAPI`, `setupAPI`, `ownerAPI` |
| Create | `frontend/src/context/BootstrapContext.jsx` | Caches bootstrap response, provides `isSetupRequired`, `licenseStatus`, `refresh()` |
| Create | `frontend/src/components/owner/BootstrapGate.jsx` | Route guard + banner injection for `/owner/*` subtree |
| Create | `frontend/src/components/owner/RootRedirect.jsx` | Landing `/` redirects based on bootstrap + auth state |
| Create | `frontend/src/components/owner/OwnerLayout.jsx` | Thin wrapper around existing `<Layout />` + owner sidebar |
| Create | `frontend/src/components/owner/OwnerSidebar.jsx` | Sidebar with owner menu items (Dashboard / Branches / Specializations / Clients / AI Providers / Settings) |
| Create | `frontend/src/components/owner/GraceBanner.jsx` | Yellow grace-period banner |
| Create | `frontend/src/components/owner/ReadOnlyBanner.jsx` | Red expired-license banner |
| Create | `frontend/src/pages/owner/SetupWizard.jsx` | Two-step wizard on `/setup` |
| Create | `frontend/src/pages/owner/OwnerLoginPage.jsx` | Owner login form on `/owner/login` |
| Create | `frontend/src/pages/owner/OwnerDashboardPage.jsx` | Counters + config health + license card |
| Create | `frontend/src/pages/owner/OwnerSettingsPage.jsx` | License & account sections |
| Create | `frontend/src/pages/owner/StubPage.jsx` | "Coming soon" placeholder |
| Modify | `frontend/src/App.jsx` | Add `/setup`, `/owner/login`, `/owner/*` routes |
| Modify | `frontend/src/context/AuthContext.jsx` | Add `isOwner` getter (minimal) |

---

## Task 1: PlatformLicense model + migration + unit tests

**Files:**
- Modify: `MASTER/concierge_platform/models.py` (append at end)
- Create: `MASTER/concierge_platform/migrations/0007_platformlicense.py`
- Create: `MASTER/concierge_platform/tests/test_license_model.py`

- [ ] **Step 1: Write the failing tests**

Create `MASTER/concierge_platform/tests/test_license_model.py`:

```python
from datetime import timedelta

import pytest
from django.utils import timezone

from MASTER.concierge_platform.models import PlatformLicense


@pytest.mark.django_db
class TestPlatformLicense:
    def test_singleton_get_creates_if_missing(self):
        assert PlatformLicense.objects.count() == 0
        lic = PlatformLicense.get()
        assert lic.pk == 1
        assert PlatformLicense.objects.count() == 1
        assert lic.status == PlatformLicense.LicenseStatus.MISSING

    def test_singleton_save_always_pk_1(self):
        a = PlatformLicense()
        a.save()
        b = PlatformLicense()
        b.save()
        assert a.pk == 1
        assert b.pk == 1
        assert PlatformLicense.objects.count() == 1

    def test_is_setup_complete_false_by_default(self):
        lic = PlatformLicense.get()
        assert lic.is_setup_complete is False

    def test_is_setup_complete_true_when_set(self):
        lic = PlatformLicense.get()
        lic.setup_completed_at = timezone.now()
        lic.save()
        assert lic.is_setup_complete is True

    def test_grace_period_days_is_7(self):
        assert PlatformLicense.get().grace_period_days == 7

    def test_is_in_grace_period_false_when_valid(self):
        lic = PlatformLicense.get()
        lic.status = PlatformLicense.LicenseStatus.VALID
        lic.last_verified_at = timezone.now()
        lic.save()
        assert lic.is_in_grace_period is False

    def test_is_in_grace_period_true_within_window_using_last_verified(self):
        lic = PlatformLicense.get()
        lic.status = PlatformLicense.LicenseStatus.GRACE
        lic.last_verified_at = timezone.now() - timedelta(days=3)
        lic.save()
        assert lic.is_in_grace_period is True

    def test_is_in_grace_period_false_after_7_days(self):
        lic = PlatformLicense.get()
        lic.status = PlatformLicense.LicenseStatus.GRACE
        lic.last_verified_at = timezone.now() - timedelta(days=8)
        lic.save()
        assert lic.is_in_grace_period is False

    def test_is_in_grace_period_uses_last_attempt_when_last_verified_missing(self):
        lic = PlatformLicense.get()
        lic.status = PlatformLicense.LicenseStatus.GRACE
        lic.last_verified_at = None
        lic.last_attempt_at = timezone.now() - timedelta(days=2)
        lic.save()
        assert lic.is_in_grace_period is True

    def test_is_in_grace_period_false_when_no_anchors(self):
        lic = PlatformLicense.get()
        lic.status = PlatformLicense.LicenseStatus.GRACE
        lic.last_verified_at = None
        lic.last_attempt_at = None
        lic.save()
        assert lic.is_in_grace_period is False

    def test_grace_days_remaining_null_when_not_grace(self):
        lic = PlatformLicense.get()
        lic.status = PlatformLicense.LicenseStatus.VALID
        lic.save()
        assert lic.grace_days_remaining is None

    def test_grace_days_remaining_counts_down(self):
        lic = PlatformLicense.get()
        lic.status = PlatformLicense.LicenseStatus.GRACE
        lic.last_verified_at = timezone.now() - timedelta(days=2)
        lic.save()
        # 7 - 2 = 5 days remaining (floor to int days)
        assert lic.grace_days_remaining == 5
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec -T web pytest MASTER/concierge_platform/tests/test_license_model.py -v`
Expected: all tests fail with `ImportError` or `AttributeError` (PlatformLicense not defined).

- [ ] **Step 3: Add the PlatformLicense model**

Append to `MASTER/concierge_platform/models.py`:

```python
class PlatformLicense(models.Model):
    """Singleton. Holds Gumroad license key + validation state."""

    class LicenseStatus(models.TextChoices):
        MISSING = 'missing', 'Missing'
        VALID = 'valid', 'Valid'
        GRACE = 'grace', 'Grace'
        EXPIRED = 'expired', 'Expired'

    license_key = models.CharField(max_length=100, blank=True)
    status = models.CharField(
        max_length=10,
        choices=LicenseStatus.choices,
        default=LicenseStatus.MISSING,
    )

    setup_completed_at = models.DateTimeField(null=True, blank=True)

    last_verified_at = models.DateTimeField(null=True, blank=True)
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)

    gumroad_product_id = models.CharField(max_length=100, blank=True)
    gumroad_purchase_email = models.EmailField(blank=True)
    gumroad_uses = models.IntegerField(default=0)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Platform License'
        verbose_name_plural = 'Platform License'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    @property
    def is_setup_complete(self) -> bool:
        return self.setup_completed_at is not None

    @property
    def grace_period_days(self) -> int:
        return 7

    def _grace_anchor(self):
        """Return the datetime from which the grace window is measured."""
        return self.last_verified_at or self.last_attempt_at

    @property
    def is_in_grace_period(self) -> bool:
        if self.status != self.LicenseStatus.GRACE:
            return False
        anchor = self._grace_anchor()
        if anchor is None:
            return False
        from datetime import timedelta
        from django.utils import timezone
        return (timezone.now() - anchor) < timedelta(days=self.grace_period_days)

    @property
    def grace_days_remaining(self):
        """Integer days until grace window expires, or None if not in grace."""
        if self.status != self.LicenseStatus.GRACE:
            return None
        anchor = self._grace_anchor()
        if anchor is None:
            return 0
        from datetime import timedelta
        from django.utils import timezone
        remaining = (anchor + timedelta(days=self.grace_period_days)) - timezone.now()
        return max(0, remaining.days)
```

- [ ] **Step 4: Create the migration**

Create `MASTER/concierge_platform/migrations/0007_platformlicense.py`:

```python
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('concierge_platform', '0006_create_langflow_flag'),
    ]

    operations = [
        migrations.CreateModel(
            name='PlatformLicense',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('license_key', models.CharField(blank=True, max_length=100)),
                ('status', models.CharField(
                    choices=[
                        ('missing', 'Missing'),
                        ('valid', 'Valid'),
                        ('grace', 'Grace'),
                        ('expired', 'Expired'),
                    ],
                    default='missing',
                    max_length=10,
                )),
                ('setup_completed_at', models.DateTimeField(blank=True, null=True)),
                ('last_verified_at', models.DateTimeField(blank=True, null=True)),
                ('last_attempt_at', models.DateTimeField(blank=True, null=True)),
                ('last_error', models.TextField(blank=True)),
                ('gumroad_product_id', models.CharField(blank=True, max_length=100)),
                ('gumroad_purchase_email', models.EmailField(blank=True, max_length=254)),
                ('gumroad_uses', models.IntegerField(default=0)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Platform License',
                'verbose_name_plural': 'Platform License',
            },
        ),
    ]
```

- [ ] **Step 5: Apply migration**

Run: `docker compose exec -T web python manage.py migrate concierge_platform`
Expected: `Applying concierge_platform.0007_platformlicense... OK`

- [ ] **Step 6: Run tests to verify they pass**

Run: `docker compose exec -T web pytest MASTER/concierge_platform/tests/test_license_model.py -v`
Expected: all 12 tests pass.

- [ ] **Step 7: Commit**

```bash
git add MASTER/concierge_platform/models.py MASTER/concierge_platform/migrations/0007_platformlicense.py MASTER/concierge_platform/tests/test_license_model.py
git commit -m "feat(platform): add PlatformLicense singleton model

Singleton holding Gumroad license key + validation state. Includes
state machine (missing/valid/grace/expired), setup-completion flag,
and grace-period helpers used by bootstrap and dashboard endpoints."
```

---

## Task 2: Gumroad client module + unit tests

**Files:**
- Create: `MASTER/concierge_platform/gumroad_client.py`
- Create: `MASTER/concierge_platform/tests/test_gumroad_client.py`

- [ ] **Step 1: Write the failing tests**

Create `MASTER/concierge_platform/tests/test_gumroad_client.py`:

```python
from unittest.mock import patch, MagicMock

import pytest
import requests

from MASTER.concierge_platform import gumroad_client
from MASTER.concierge_platform.gumroad_client import GumroadResult, verify_license


@pytest.fixture(autouse=True)
def _product_id(settings):
    settings.GUMROAD_PRODUCT_ID = "test_product_id"


def _mock_response(status_code=200, json_data=None):
    m = MagicMock()
    m.status_code = status_code
    m.json.return_value = json_data or {}
    m.text = str(json_data)
    return m


class TestVerifyLicense:
    def test_valid_response(self):
        resp = _mock_response(200, {
            "success": True,
            "uses": 1,
            "purchase": {
                "email": "buyer@example.com",
                "product_id": "abc123",
            },
        })
        with patch.object(gumroad_client.requests, "post", return_value=resp):
            result = verify_license("test-key")
        assert result.outcome == "valid"
        assert result.data["uses"] == 1
        assert result.data["purchase"]["email"] == "buyer@example.com"
        assert result.error == ""

    def test_invalid_response(self):
        resp = _mock_response(200, {"success": False, "message": "Not found"})
        with patch.object(gumroad_client.requests, "post", return_value=resp):
            result = verify_license("bad-key")
        assert result.outcome == "invalid"
        assert "Not found" in result.error

    def test_timeout(self):
        with patch.object(
            gumroad_client.requests, "post",
            side_effect=requests.Timeout("timed out"),
        ):
            result = verify_license("any-key")
        assert result.outcome == "network_error"
        assert "timeout" in result.error.lower()

    def test_connection_error(self):
        with patch.object(
            gumroad_client.requests, "post",
            side_effect=requests.ConnectionError("dns"),
        ):
            result = verify_license("any-key")
        assert result.outcome == "network_error"

    def test_5xx_response(self):
        resp = _mock_response(503, {})
        with patch.object(gumroad_client.requests, "post", return_value=resp):
            result = verify_license("any-key")
        assert result.outcome == "network_error"
        assert "503" in result.error

    def test_unexpected_4xx_response(self):
        resp = _mock_response(400, {})
        with patch.object(gumroad_client.requests, "post", return_value=resp):
            result = verify_license("any-key")
        assert result.outcome == "network_error"
        assert "400" in result.error

    def test_malformed_json(self):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.side_effect = ValueError("bad json")
        resp.text = "not json"
        with patch.object(gumroad_client.requests, "post", return_value=resp):
            result = verify_license("any-key")
        assert result.outcome == "network_error"

    def test_sends_product_id_and_key(self):
        resp = _mock_response(200, {"success": True, "uses": 1, "purchase": {}})
        with patch.object(
            gumroad_client.requests, "post", return_value=resp,
        ) as mock_post:
            verify_license("the-key")
        args, kwargs = mock_post.call_args
        assert args[0] == gumroad_client.GUMROAD_VERIFY_URL
        sent = kwargs.get("data") or kwargs.get("json") or {}
        assert sent.get("product_id") == "test_product_id"
        assert sent.get("license_key") == "the-key"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec -T web pytest MASTER/concierge_platform/tests/test_gumroad_client.py -v`
Expected: `ModuleNotFoundError: No module named 'MASTER.concierge_platform.gumroad_client'`

- [ ] **Step 3: Write the Gumroad client**

Create `MASTER/concierge_platform/gumroad_client.py`:

```python
"""Isolated HTTP client for the Gumroad license verify API.

All HTTP access to Gumroad happens here so tests can mock a single
integration point. `verify_license()` never raises — it always returns
a `GumroadResult`.
"""
from dataclasses import dataclass, field
from typing import Literal

import requests
from django.conf import settings

GUMROAD_VERIFY_URL = "https://api.gumroad.com/v2/licenses/verify"
GUMROAD_TIMEOUT_SECONDS = 10


Outcome = Literal["valid", "invalid", "network_error"]


@dataclass
class GumroadResult:
    outcome: Outcome
    data: dict = field(default_factory=dict)
    error: str = ""


def verify_license(license_key: str) -> GumroadResult:
    """Call Gumroad verify API, never raises.

    Reads GUMROAD_PRODUCT_ID from Django settings. Returns a GumroadResult
    describing one of three outcomes:

    - valid:         Gumroad returned success=True. `data` contains uses + purchase.
    - invalid:       Gumroad returned success=False. `error` contains the message.
    - network_error: Any transport-level problem (timeout, DNS, 5xx, non-JSON).
    """
    product_id = settings.GUMROAD_PRODUCT_ID
    payload = {
        "product_id": product_id,
        "license_key": license_key,
    }
    try:
        response = requests.post(
            GUMROAD_VERIFY_URL,
            data=payload,
            timeout=GUMROAD_TIMEOUT_SECONDS,
        )
    except requests.Timeout:
        return GumroadResult(outcome="network_error", error="timeout")
    except requests.ConnectionError as exc:
        return GumroadResult(outcome="network_error", error=f"connection_error: {exc}")
    except requests.RequestException as exc:
        return GumroadResult(outcome="network_error", error=f"request_error: {exc}")

    if response.status_code != 200:
        return GumroadResult(
            outcome="network_error",
            error=f"HTTP {response.status_code}: {response.text[:200]}",
        )

    try:
        body = response.json()
    except ValueError:
        return GumroadResult(outcome="network_error", error="malformed_json")

    if body.get("success") is True:
        return GumroadResult(outcome="valid", data=body)

    message = body.get("message") or "Gumroad rejected the license key"
    return GumroadResult(outcome="invalid", error=message, data=body)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose exec -T web pytest MASTER/concierge_platform/tests/test_gumroad_client.py -v`
Expected: all 8 tests pass.

- [ ] **Step 5: Commit**

```bash
git add MASTER/concierge_platform/gumroad_client.py MASTER/concierge_platform/tests/test_gumroad_client.py
git commit -m "feat(platform): add Gumroad license verify client

Isolated HTTP client that calls Gumroad /v2/licenses/verify. Returns
a GumroadResult dataclass (valid/invalid/network_error). Never raises;
network problems and malformed responses become network_error so
callers can apply the soft grace-period policy."
```

---

## Task 3: IsOwner permission + unit tests

**Files:**
- Create: `MASTER/concierge_platform/permissions.py`
- Create: `MASTER/concierge_platform/tests/test_permissions.py`

- [ ] **Step 1: Write the failing tests**

Create `MASTER/concierge_platform/tests/test_permissions.py`:

```python
from unittest.mock import MagicMock

import pytest
from django.contrib.auth.models import AnonymousUser

from MASTER.accounts.models import User, Roles
from MASTER.concierge_platform.permissions import IsOwner


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec -T web pytest MASTER/concierge_platform/tests/test_permissions.py -v`
Expected: `ModuleNotFoundError: No module named 'MASTER.concierge_platform.permissions'`

- [ ] **Step 3: Write the permission class**

Create `MASTER/concierge_platform/permissions.py`:

```python
from rest_framework.permissions import BasePermission

from MASTER.accounts.models import Roles


class IsOwner(BasePermission):
    """Allow only authenticated users with role='owner'."""

    message = "Owner role required."

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        return bool(
            user
            and user.is_authenticated
            and getattr(user, "role", None) == Roles.OWNER
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose exec -T web pytest MASTER/concierge_platform/tests/test_permissions.py -v`
Expected: all 5 tests pass.

- [ ] **Step 5: Commit**

```bash
git add MASTER/concierge_platform/permissions.py MASTER/concierge_platform/tests/test_permissions.py
git commit -m "feat(platform): add IsOwner DRF permission

Used to gate all /api/owner/* endpoints and the authenticated setup
steps. Explicitly denies admin/manager/client roles — owner is the
single purchaser of a self-hosted installation."
```

---

## Task 4: GUMROAD_PRODUCT_ID setting with startup check

**Files:**
- Modify: `MASTER/settings.py`

- [ ] **Step 1: Read existing settings.py to find a good insertion point**

Run: `grep -n "^# " MASTER/settings.py | head -20`
Expected: section comments like `# Database`, `# Authentication`, etc.

Find a spot near the bottom of `MASTER/settings.py` (after any existing third-party service configuration). Insert the new block before the final `# ---` marker (or at EOF if none).

- [ ] **Step 2: Add the setting**

Append to `MASTER/settings.py`:

```python
# --- Gumroad license validation ---------------------------------------------
# The Jeeves platform is sold on Gumroad. Every installation validates the
# purchaser's license key against this product id. Must be baked into the
# shipped image via environment variable.
import os as _os

GUMROAD_PRODUCT_ID = _os.environ.get("GUMROAD_PRODUCT_ID", "")

if not DEBUG and not GUMROAD_PRODUCT_ID:
    from django.core.exceptions import ImproperlyConfigured
    raise ImproperlyConfigured(
        "GUMROAD_PRODUCT_ID environment variable is required in production"
    )
```

- [ ] **Step 3: Verify Django still boots**

Run: `docker compose exec -T web python manage.py check`
Expected: `System check identified no issues (0 silenced).`

- [ ] **Step 4: Commit**

```bash
git add MASTER/settings.py
git commit -m "feat(settings): add GUMROAD_PRODUCT_ID with startup check

Required in production; DEBUG installs allow empty (for local dev).
Baked into the shipped Docker image — the same product id for every
purchaser of Jeeves on Gumroad."
```

---

## Task 5: Serializers for setup/bootstrap/dashboard

**Files:**
- Create: `MASTER/concierge_platform/serializers.py`

- [ ] **Step 1: Write the serializers**

Create `MASTER/concierge_platform/serializers.py`:

```python
from rest_framework import serializers

from MASTER.accounts.models import User


class OwnerCreateSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    first_name = serializers.CharField(max_length=30)
    last_name = serializers.CharField(max_length=30)

    def validate_password(self, value):
        if len(value) < 8:
            raise serializers.ValidationError("weak_password")
        return value

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("email_taken")
        return value


class LicenseKeySerializer(serializers.Serializer):
    license_key = serializers.CharField(max_length=100, min_length=1)
```

- [ ] **Step 2: Quick import check**

Run: `docker compose exec -T web python -c "from MASTER.concierge_platform import serializers; print(serializers.OwnerCreateSerializer)"`
Expected: prints the serializer class, no ImportError.

- [ ] **Step 3: Commit**

```bash
git add MASTER/concierge_platform/serializers.py
git commit -m "feat(platform): add setup serializers

OwnerCreateSerializer validates email uniqueness + password length.
LicenseKeySerializer is a thin wrapper for the license key field."
```

---

## Task 6: Bootstrap endpoint + integration test

**Files:**
- Create: `MASTER/concierge_platform/views_platform.py`
- Create: `MASTER/concierge_platform/tests/test_bootstrap_api.py`

- [ ] **Step 1: Write the failing test**

Create `MASTER/concierge_platform/tests/test_bootstrap_api.py`:

```python
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from MASTER.accounts.models import User, Roles
from MASTER.concierge_platform.models import PlatformLicense


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec -T web pytest MASTER/concierge_platform/tests/test_bootstrap_api.py -v`
Expected: 404 or NoReverseMatch — the route does not exist yet.

- [ ] **Step 3: Write the view**

Create `MASTER/concierge_platform/views_platform.py`:

```python
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from MASTER.concierge_platform.models import PlatformLicense


class BootstrapView(APIView):
    """Public endpoint that tells the frontend whether setup is needed
    and what the current license status is. Called on every React boot."""

    permission_classes = [AllowAny]

    def get(self, request):
        lic = PlatformLicense.get()
        return Response({
            "setup_required": not lic.is_setup_complete,
            "license_status": lic.status,
            "license_last_verified_at": (
                lic.last_verified_at.isoformat() if lic.last_verified_at else None
            ),
            "grace_days_remaining": lic.grace_days_remaining,
        })
```

- [ ] **Step 4: Wire the URL (create urls.py skeleton)**

Create `MASTER/concierge_platform/urls.py`:

```python
from django.urls import path

from MASTER.concierge_platform import views_platform

urlpatterns = [
    path('platform/bootstrap/', views_platform.BootstrapView.as_view(), name='platform-bootstrap'),
]
```

- [ ] **Step 5: Mount urls in the project root**

Edit `MASTER/urls.py` and add to `urlpatterns` near the other API routes:

```python
    path('api/', include('MASTER.concierge_platform.urls')),
```

Place this line right after the existing `path('api/clients/', include(...))` entry.

- [ ] **Step 6: Run test to verify it passes**

Run: `docker compose exec -T web pytest MASTER/concierge_platform/tests/test_bootstrap_api.py -v`
Expected: all 4 tests pass.

- [ ] **Step 7: Commit**

```bash
git add MASTER/concierge_platform/views_platform.py MASTER/concierge_platform/urls.py MASTER/urls.py MASTER/concierge_platform/tests/test_bootstrap_api.py
git commit -m "feat(platform): add GET /api/platform/bootstrap endpoint

Public endpoint that drives frontend routing decisions. Returns
setup_required flag, license status, last verified timestamp, and
grace_days_remaining when in the grace window."
```

---

## Task 7: Setup — create owner endpoint + test

**Files:**
- Create: `MASTER/concierge_platform/views_setup.py`
- Create: `MASTER/concierge_platform/tests/test_setup_api.py` (first block)
- Modify: `MASTER/concierge_platform/urls.py`

- [ ] **Step 1: Write the failing tests**

Create `MASTER/concierge_platform/tests/test_setup_api.py`:

```python
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
        # Django REST framework nests field errors under the field name
        assert "email" in body or body.get("error") == "email_taken"

    def test_rejects_weak_password(self, client, owner_payload):
        owner_payload["password"] = "short"
        resp = client.post(self.url, owner_payload, format="json")
        assert resp.status_code == 400

    def test_rejects_invalid_email(self, client, owner_payload):
        owner_payload["email"] = "not-an-email"
        resp = client.post(self.url, owner_payload, format="json")
        assert resp.status_code == 400
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec -T web pytest MASTER/concierge_platform/tests/test_setup_api.py::TestSetupOwner -v`
Expected: 404 — endpoint not defined.

- [ ] **Step 3: Write the view**

Create `MASTER/concierge_platform/views_setup.py`:

```python
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from MASTER.accounts.models import User, Roles
from MASTER.concierge_platform.serializers import OwnerCreateSerializer


class CreateOwnerView(APIView):
    """Create the first (and only) OWNER user during the setup wizard.

    Rejects with 409 if an owner already exists. The owner also gets
    is_superuser/is_staff flags as a fallback path into Django admin.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        if User.objects.filter(role=Roles.OWNER).exists():
            return Response(
                {"error": "owner_exists"},
                status=status.HTTP_409_CONFLICT,
            )

        serializer = OwnerCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        user = User.objects.create_user(
            username=data["email"],
            email=data["email"],
            password=data["password"],
            first_name=data["first_name"],
            last_name=data["last_name"],
            role=Roles.OWNER,
            is_staff=True,
            is_superuser=True,
        )

        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "role": user.role,
                },
            },
            status=status.HTTP_201_CREATED,
        )
```

- [ ] **Step 4: Wire the URL**

Edit `MASTER/concierge_platform/urls.py` — append to `urlpatterns`:

```python
from MASTER.concierge_platform import views_setup

# ... existing patterns ...
urlpatterns += [
    path('setup/owner/', views_setup.CreateOwnerView.as_view(), name='setup-owner'),
]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `docker compose exec -T web pytest MASTER/concierge_platform/tests/test_setup_api.py::TestSetupOwner -v`
Expected: all 5 tests pass.

- [ ] **Step 6: Commit**

```bash
git add MASTER/concierge_platform/views_setup.py MASTER/concierge_platform/urls.py MASTER/concierge_platform/tests/test_setup_api.py
git commit -m "feat(setup): add POST /api/setup/owner endpoint

Creates the first User with role='owner' + superuser flags and
returns a JWT pair so the frontend can immediately call the next
wizard step. Rejects subsequent calls with 409 owner_exists."
```

---

## Task 8: Setup — license endpoint + tests

**Files:**
- Modify: `MASTER/concierge_platform/views_setup.py`
- Modify: `MASTER/concierge_platform/tests/test_setup_api.py`
- Modify: `MASTER/concierge_platform/urls.py`

- [ ] **Step 1: Add failing tests**

Append to `MASTER/concierge_platform/tests/test_setup_api.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec -T web pytest MASTER/concierge_platform/tests/test_setup_api.py::TestSetupLicense -v`
Expected: 404 / route-not-found errors.

- [ ] **Step 3: Add the view**

Append to `MASTER/concierge_platform/views_setup.py`:

```python
from django.utils import timezone

from MASTER.concierge_platform import gumroad_client
from MASTER.concierge_platform.models import PlatformLicense
from MASTER.concierge_platform.permissions import IsOwner
from MASTER.concierge_platform.serializers import LicenseKeySerializer


class SetupLicenseView(APIView):
    """Save + verify the Gumroad license key during wizard Step 2.

    - valid:         persist key, status=valid, return 200 valid
    - invalid:       do NOT persist, return 400 invalid_key
    - network_error: persist key, status=grace, return 200 grace
    """

    permission_classes = [IsOwner]

    def post(self, request):
        serializer = LicenseKeySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        license_key = serializer.validated_data["license_key"]

        result = gumroad_client.verify_license(license_key)
        lic = PlatformLicense.get()
        now = timezone.now()

        if result.outcome == "valid":
            lic.license_key = license_key
            lic.status = PlatformLicense.LicenseStatus.VALID
            lic.last_verified_at = now
            lic.last_attempt_at = now
            lic.last_error = ""
            purchase = result.data.get("purchase", {}) or {}
            lic.gumroad_purchase_email = purchase.get("email", "") or ""
            lic.gumroad_product_id = purchase.get("product_id", "") or ""
            lic.gumroad_uses = int(result.data.get("uses", 0) or 0)
            lic.save()
            return Response({"status": "valid"})

        if result.outcome == "invalid":
            return Response(
                {"error": "invalid_key", "message": result.error},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # network_error — grace
        lic.license_key = license_key
        lic.status = PlatformLicense.LicenseStatus.GRACE
        lic.last_attempt_at = now
        lic.last_error = result.error
        lic.save()
        return Response({
            "status": "grace",
            "message": (
                "We couldn't reach Gumroad. Your key was saved and we'll retry "
                "automatically. Grace period: 7 days."
            ),
        })
```

- [ ] **Step 4: Wire the URL**

Edit `MASTER/concierge_platform/urls.py` — add to urlpatterns:

```python
    path('setup/license/', views_setup.SetupLicenseView.as_view(), name='setup-license'),
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `docker compose exec -T web pytest MASTER/concierge_platform/tests/test_setup_api.py::TestSetupLicense -v`
Expected: all 4 tests pass.

- [ ] **Step 6: Commit**

```bash
git add MASTER/concierge_platform/views_setup.py MASTER/concierge_platform/urls.py MASTER/concierge_platform/tests/test_setup_api.py
git commit -m "feat(setup): add POST /api/setup/license endpoint

Calls gumroad_client.verify_license synchronously. Valid outcome
saves the key + metadata; invalid outcome rejects without saving;
network_error outcome saves the key with status=grace so the
wizard can continue on flaky connectivity."
```

---

## Task 9: Setup — complete endpoint + tests

**Files:**
- Modify: `MASTER/concierge_platform/views_setup.py`
- Modify: `MASTER/concierge_platform/tests/test_setup_api.py`
- Modify: `MASTER/concierge_platform/urls.py`

- [ ] **Step 1: Add failing tests**

Append to `MASTER/concierge_platform/tests/test_setup_api.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec -T web pytest MASTER/concierge_platform/tests/test_setup_api.py::TestSetupComplete -v`
Expected: 404 or similar.

- [ ] **Step 3: Add the view**

Append to `MASTER/concierge_platform/views_setup.py`:

```python
class SetupCompleteView(APIView):
    """Finalize the setup wizard. Idempotent."""

    permission_classes = [IsOwner]

    def post(self, request):
        lic = PlatformLicense.get()
        if lic.is_setup_complete:
            return Response(status=status.HTTP_204_NO_CONTENT)

        ok_statuses = (
            PlatformLicense.LicenseStatus.VALID,
            PlatformLicense.LicenseStatus.GRACE,
        )
        if not lic.license_key or lic.status not in ok_statuses:
            return Response(
                {"error": "license_not_ready"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        lic.setup_completed_at = timezone.now()
        lic.save()
        return Response(status=status.HTTP_204_NO_CONTENT)
```

- [ ] **Step 4: Wire the URL**

Edit `MASTER/concierge_platform/urls.py` — add:

```python
    path('setup/complete/', views_setup.SetupCompleteView.as_view(), name='setup-complete'),
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `docker compose exec -T web pytest MASTER/concierge_platform/tests/test_setup_api.py::TestSetupComplete -v`
Expected: all 5 tests pass.

- [ ] **Step 6: Run the full setup_api test module**

Run: `docker compose exec -T web pytest MASTER/concierge_platform/tests/test_setup_api.py -v`
Expected: all 14 tests (5 owner + 4 license + 5 complete) pass.

- [ ] **Step 7: Commit**

```bash
git add MASTER/concierge_platform/views_setup.py MASTER/concierge_platform/urls.py MASTER/concierge_platform/tests/test_setup_api.py
git commit -m "feat(setup): add POST /api/setup/complete endpoint

Finalizes the wizard by setting setup_completed_at=now. Idempotent
on repeated calls so the frontend can retry safely. Rejects if
license is still missing."
```

---

## Task 10: Dashboard stats endpoint + tests

**Files:**
- Create: `MASTER/concierge_platform/views_owner.py`
- Create: `MASTER/concierge_platform/tests/test_dashboard_api.py`
- Modify: `MASTER/concierge_platform/urls.py`

- [ ] **Step 1: Write the failing tests**

Create `MASTER/concierge_platform/tests/test_dashboard_api.py`:

```python
import pytest
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from MASTER.accounts.models import User, Roles
from MASTER.branches.models import Branch
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec -T web pytest MASTER/concierge_platform/tests/test_dashboard_api.py -v`
Expected: 404.

- [ ] **Step 3: Write the view**

Create `MASTER/concierge_platform/views_owner.py`:

```python
from rest_framework.response import Response
from rest_framework.views import APIView

from MASTER.branches.models import Branch, BranchDocument
from MASTER.clients.models import Client
from MASTER.concierge_platform.models import PlatformLicense
from MASTER.concierge_platform.permissions import IsOwner
from MASTER.EmbeddingModel.models import EmbeddingModel, LLMProvider
from MASTER.specializations.models import Specialization, SpecializationDocument


class DashboardStatsView(APIView):
    """Counters + config-health checklist + license card for /owner/dashboard."""

    permission_classes = [IsOwner]

    def get(self, request):
        lic = PlatformLicense.get()

        counters = {
            "branches": Branch.objects.count(),
            "specializations": Specialization.objects.count(),
            "clients": Client.objects.count(),
            "documents": (
                BranchDocument.objects.count()
                + SpecializationDocument.objects.count()
            ),
        }

        config_health = {
            "license_valid": lic.status == PlatformLicense.LicenseStatus.VALID,
            "llm_providers_configured": LLMProvider.objects.filter(is_active=True).exists(),
            "embedding_models_configured": EmbeddingModel.objects.filter(is_active=True).exists(),
            "branches_exist": Branch.objects.exists(),
        }

        return Response({
            "counters": counters,
            "config_health": config_health,
            "license": {
                "status": lic.status,
                "last_verified_at": (
                    lic.last_verified_at.isoformat() if lic.last_verified_at else None
                ),
                "grace_days_remaining": lic.grace_days_remaining,
            },
        })
```

- [ ] **Step 4: Wire the URL**

Edit `MASTER/concierge_platform/urls.py` — add:

```python
from MASTER.concierge_platform import views_owner

urlpatterns += [
    path('owner/dashboard/stats/', views_owner.DashboardStatsView.as_view(), name='owner-dashboard-stats'),
]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `docker compose exec -T web pytest MASTER/concierge_platform/tests/test_dashboard_api.py -v`
Expected: all 4 tests pass.

- [ ] **Step 6: Commit**

```bash
git add MASTER/concierge_platform/views_owner.py MASTER/concierge_platform/urls.py MASTER/concierge_platform/tests/test_dashboard_api.py
git commit -m "feat(owner): add GET /api/owner/dashboard/stats endpoint

Returns counters (branches/specs/clients/documents), the 4-item
config-health checklist used by the dashboard card, and a license
summary including grace_days_remaining."
```

---

## Task 11: License reverify endpoint + tests

**Files:**
- Modify: `MASTER/concierge_platform/views_owner.py`
- Create: `MASTER/concierge_platform/tests/test_reverify_api.py`
- Modify: `MASTER/concierge_platform/urls.py`

- [ ] **Step 1: Write the failing tests**

Create `MASTER/concierge_platform/tests/test_reverify_api.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec -T web pytest MASTER/concierge_platform/tests/test_reverify_api.py -v`
Expected: 404.

- [ ] **Step 3: Add the view**

Append to `MASTER/concierge_platform/views_owner.py`:

```python
from django.utils import timezone
from rest_framework import status as drf_status

from MASTER.concierge_platform import gumroad_client


class ReverifyLicenseView(APIView):
    """Manual 'Re-verify now' button in Settings. Works even when expired."""

    permission_classes = [IsOwner]

    def post(self, request):
        lic = PlatformLicense.get()
        if not lic.license_key:
            return Response(
                {"error": "no_license_key"},
                status=drf_status.HTTP_400_BAD_REQUEST,
            )

        result = gumroad_client.verify_license(lic.license_key)
        now = timezone.now()
        lic.last_attempt_at = now

        if result.outcome == "valid":
            lic.status = PlatformLicense.LicenseStatus.VALID
            lic.last_verified_at = now
            lic.last_error = ""
            purchase = result.data.get("purchase", {}) or {}
            lic.gumroad_purchase_email = purchase.get("email", "") or ""
            lic.gumroad_product_id = purchase.get("product_id", "") or ""
            lic.gumroad_uses = int(result.data.get("uses", 0) or 0)
        elif result.outcome == "invalid":
            lic.last_error = result.error
            # leave status as-is: if it was expired it stays expired
        else:
            # network_error: do not change status on reverify, just record attempt
            lic.last_error = result.error

        lic.save()
        return Response({
            "status": lic.status,
            "last_verified_at": (
                lic.last_verified_at.isoformat() if lic.last_verified_at else None
            ),
            "grace_days_remaining": lic.grace_days_remaining,
        })
```

- [ ] **Step 4: Wire the URL**

Edit `MASTER/concierge_platform/urls.py` — add:

```python
    path('owner/license/reverify/', views_owner.ReverifyLicenseView.as_view(), name='owner-license-reverify'),
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `docker compose exec -T web pytest MASTER/concierge_platform/tests/test_reverify_api.py -v`
Expected: all 4 tests pass.

- [ ] **Step 6: Run full backend test suite for this module**

Run: `docker compose exec -T web pytest MASTER/concierge_platform/tests/ -v`
Expected: all tests from all 6 new test files pass (plus pre-existing concierge_platform tests).

- [ ] **Step 7: Commit**

```bash
git add MASTER/concierge_platform/views_owner.py MASTER/concierge_platform/urls.py MASTER/concierge_platform/tests/test_reverify_api.py
git commit -m "feat(owner): add POST /api/owner/license/reverify endpoint

Manual 'Re-verify now' trigger for the Settings page. Works even when
the license is expired so the owner has a recovery path. Invalid/
network-error outcomes do not flip a previously-valid license off."
```

---

## Task 12: Frontend API client module

**Files:**
- Create: `frontend/src/api/owner.js`

- [ ] **Step 1: Create the API client**

Create `frontend/src/api/owner.js`:

```js
import api from './axios';

// GET /api/platform/bootstrap — called on React boot, drives routing
export const platformAPI = {
  getBootstrap: () => api.get('/platform/bootstrap/'),
};

// POST /api/setup/* — used by the two-step SetupWizard
export const setupAPI = {
  createOwner: (data) => api.post('/setup/owner/', data),
  saveLicense: (license_key) => api.post('/setup/license/', { license_key }),
  complete: () => api.post('/setup/complete/'),
};

// GET /api/owner/* — used after login in the admin panel
export const ownerAPI = {
  getDashboardStats: () => api.get('/owner/dashboard/stats/'),
  reverifyLicense: () => api.post('/owner/license/reverify/'),
};
```

- [ ] **Step 2: Quick import check**

Run: `cd frontend && node -e "require('./src/api/owner.js')" 2>&1 | head -5`
(Note: ESM + import.meta.env makes a raw node require fail; this check is optional. Instead verify via `cd frontend && npx eslint src/api/owner.js` if eslint is configured, otherwise skip and rely on build.)

Run: `cd frontend && npx vite build 2>&1 | tail -20` (optional, slow)
Expected: no import errors related to owner.js.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/owner.js
git commit -m "feat(frontend): add owner API client module

Thin axios wrappers for platformAPI (bootstrap), setupAPI (wizard),
and ownerAPI (dashboard + reverify). Paths are relative to the
existing axios baseURL which already includes /api."
```

---

## Task 13: BootstrapContext — cached bootstrap state

**Files:**
- Create: `frontend/src/context/BootstrapContext.jsx`

- [ ] **Step 1: Create the context**

Create `frontend/src/context/BootstrapContext.jsx`:

```jsx
import { createContext, useCallback, useContext, useEffect, useState } from 'react';

import { platformAPI } from '../api/owner';

const BootstrapContext = createContext(null);

export const useBootstrap = () => {
  const ctx = useContext(BootstrapContext);
  if (!ctx) throw new Error('useBootstrap must be used inside BootstrapProvider');
  return ctx;
};

export const BootstrapProvider = ({ children }) => {
  const [state, setState] = useState({
    loading: true,
    setupRequired: null,
    licenseStatus: null,
    licenseLastVerifiedAt: null,
    graceDaysRemaining: null,
    error: null,
  });

  const load = useCallback(async () => {
    setState((s) => ({ ...s, loading: true, error: null }));
    try {
      const { data } = await platformAPI.getBootstrap();
      setState({
        loading: false,
        setupRequired: data.setup_required,
        licenseStatus: data.license_status,
        licenseLastVerifiedAt: data.license_last_verified_at,
        graceDaysRemaining: data.grace_days_remaining,
        error: null,
      });
    } catch (err) {
      setState((s) => ({
        ...s,
        loading: false,
        error: err?.message || 'bootstrap_failed',
      }));
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const value = {
    ...state,
    refresh: load,
  };

  return (
    <BootstrapContext.Provider value={value}>
      {children}
    </BootstrapContext.Provider>
  );
};
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/context/BootstrapContext.jsx
git commit -m "feat(frontend): add BootstrapContext

Caches the single GET /api/platform/bootstrap response for the tab's
lifetime and exposes a refresh() function called after setup completion
and license reverify."
```

---

## Task 14: BootstrapGate + RootRedirect

**Files:**
- Create: `frontend/src/components/owner/BootstrapGate.jsx`
- Create: `frontend/src/components/owner/RootRedirect.jsx`

- [ ] **Step 1: Create BootstrapGate**

Create `frontend/src/components/owner/BootstrapGate.jsx`:

```jsx
import { Navigate, useLocation } from 'react-router-dom';

import { useAuth } from '../../context/AuthContext';
import { useBootstrap } from '../../context/BootstrapContext';

const Spinner = () => (
  <div className="flex items-center justify-center min-h-screen bg-cream">
    <p className="label-mono">Loading…</p>
  </div>
);

const BootstrapGate = ({ children }) => {
  const { loading, setupRequired } = useBootstrap();
  const { user } = useAuth();
  const location = useLocation();

  if (loading) return <Spinner />;

  if (setupRequired) {
    return <Navigate to="/setup" replace state={{ from: location }} />;
  }

  const isOwner = user && user.role === 'owner';
  if (!isOwner) {
    return <Navigate to="/owner/login" replace state={{ from: location }} />;
  }

  return children;
};

export default BootstrapGate;
```

- [ ] **Step 2: Create RootRedirect**

Create `frontend/src/components/owner/RootRedirect.jsx`:

```jsx
import { Navigate } from 'react-router-dom';

import { useAuth } from '../../context/AuthContext';
import { useBootstrap } from '../../context/BootstrapContext';

const RootRedirect = () => {
  const { loading, setupRequired } = useBootstrap();
  const { user } = useAuth();

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-cream">
        <p className="label-mono">Loading…</p>
      </div>
    );
  }

  if (setupRequired) return <Navigate to="/setup" replace />;
  if (user && user.role === 'owner') return <Navigate to="/owner/dashboard" replace />;
  return <Navigate to="/owner/login" replace />;
};

export default RootRedirect;
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/owner/BootstrapGate.jsx frontend/src/components/owner/RootRedirect.jsx
git commit -m "feat(frontend): add BootstrapGate + RootRedirect

BootstrapGate wraps the /owner/* subtree and redirects to /setup or
/owner/login based on bootstrap state + auth. RootRedirect handles
the landing / route with the same logic."
```

---

## Task 15: Banner + StubPage components

**Files:**
- Create: `frontend/src/components/owner/GraceBanner.jsx`
- Create: `frontend/src/components/owner/ReadOnlyBanner.jsx`
- Create: `frontend/src/pages/owner/StubPage.jsx`

- [ ] **Step 1: Create GraceBanner**

Create `frontend/src/components/owner/GraceBanner.jsx`:

```jsx
import { Link } from 'react-router-dom';

import { useBootstrap } from '../../context/BootstrapContext';

const GraceBanner = () => {
  const { licenseStatus, graceDaysRemaining } = useBootstrap();
  if (licenseStatus !== 'grace') return null;

  const days = graceDaysRemaining ?? 0;
  return (
    <div className="bg-yellow-100 border-l-4 border-yellow-500 text-yellow-900 px-4 py-3 mb-4">
      <p className="text-sm">
        License validation failed — we'll retry automatically.{' '}
        <strong>{days} day{days === 1 ? '' : 's'} remaining</strong> before the
        platform enters read-only mode.{' '}
        <Link to="/owner/settings" className="underline font-medium">
          Re-verify now →
        </Link>
      </p>
    </div>
  );
};

export default GraceBanner;
```

- [ ] **Step 2: Create ReadOnlyBanner**

Create `frontend/src/components/owner/ReadOnlyBanner.jsx`:

```jsx
import { Link } from 'react-router-dom';

import { useBootstrap } from '../../context/BootstrapContext';

const ReadOnlyBanner = () => {
  const { licenseStatus } = useBootstrap();
  if (licenseStatus !== 'expired') return null;

  return (
    <div className="bg-red-100 border-l-4 border-red-500 text-red-900 px-4 py-3 mb-4">
      <p className="text-sm">
        <strong>License expired.</strong> Platform is in read-only mode.{' '}
        <Link to="/owner/settings" className="underline font-medium">
          Update your license →
        </Link>
      </p>
    </div>
  );
};

export default ReadOnlyBanner;
```

- [ ] **Step 3: Create StubPage**

Create `frontend/src/pages/owner/StubPage.jsx`:

```jsx
const StubPage = ({ title }) => (
  <div className="max-w-3xl">
    <h1 className="text-3xl font-semibold text-ink mb-4">{title}</h1>
    <div className="bg-paper border border-ink/10 rounded-sm p-8">
      <p className="text-ink/70">
        This section is coming soon. It will be built in a future
        implementation step.
      </p>
    </div>
  </div>
);

export default StubPage;
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/owner/GraceBanner.jsx frontend/src/components/owner/ReadOnlyBanner.jsx frontend/src/pages/owner/StubPage.jsx
git commit -m "feat(frontend): add owner banners + stub page

GraceBanner shows days remaining when license is in grace; ReadOnly
shows red banner when expired. StubPage is the 'coming soon'
placeholder used by Branches/Specs/Clients/AI-Providers routes."
```

---

## Task 16: OwnerSidebar + OwnerLayout

**Files:**
- Create: `frontend/src/components/owner/OwnerSidebar.jsx`
- Create: `frontend/src/components/owner/OwnerLayout.jsx`

- [ ] **Step 1: Read existing Sidebar to match the visual pattern**

Run: `head -40 frontend/src/components/layout/Sidebar.jsx`
(Purpose: see the existing class names, icons usage, and overall shape so the owner sidebar visually matches.)

- [ ] **Step 2: Create OwnerSidebar**

Create `frontend/src/components/owner/OwnerSidebar.jsx`:

```jsx
import { NavLink } from 'react-router-dom';

const NAV = [
  { to: '/owner/dashboard', label: 'Dashboard' },
  { to: '/owner/branches', label: 'Branches' },
  { to: '/owner/specializations', label: 'Specializations' },
  { to: '/owner/clients', label: 'Clients' },
  { to: '/owner/ai-providers', label: 'AI Providers' },
  { to: '/owner/settings', label: 'Settings' },
];

const linkClass = ({ isActive }) =>
  [
    'block px-4 py-2 text-sm rounded-sm transition-colors',
    isActive
      ? 'bg-ink text-cream font-medium'
      : 'text-ink hover:bg-ink/10',
  ].join(' ');

const OwnerSidebar = () => (
  <aside className="w-60 bg-paper border-r border-ink/10 min-h-screen p-4 flex flex-col">
    <div className="mb-6 px-2">
      <div className="label-mono text-ink/60">Jeeves Admin</div>
      <div className="text-lg font-semibold text-ink">Owner Panel</div>
    </div>
    <nav className="space-y-1">
      {NAV.map((item) => (
        <NavLink key={item.to} to={item.to} className={linkClass}>
          {item.label}
        </NavLink>
      ))}
    </nav>
  </aside>
);

export default OwnerSidebar;
```

- [ ] **Step 3: Create OwnerLayout**

Create `frontend/src/components/owner/OwnerLayout.jsx`:

```jsx
import { Outlet } from 'react-router-dom';

import GraceBanner from './GraceBanner';
import OwnerSidebar from './OwnerSidebar';
import ReadOnlyBanner from './ReadOnlyBanner';

const OwnerLayout = () => (
  <div className="flex min-h-screen bg-cream text-ink">
    <OwnerSidebar />
    <div className="flex-1 flex flex-col min-w-0">
      <main className="flex-1 px-4 py-6 md:px-8 md:py-8 overflow-x-hidden">
        <GraceBanner />
        <ReadOnlyBanner />
        <Outlet />
      </main>
    </div>
  </div>
);

export default OwnerLayout;
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/owner/OwnerSidebar.jsx frontend/src/components/owner/OwnerLayout.jsx
git commit -m "feat(frontend): add OwnerLayout + OwnerSidebar

Owner-specific chrome reusing the Concierge palette (cream/paper/ink)
from the existing Layout. Sidebar exposes Dashboard, Branches,
Specializations, Clients, AI Providers, and Settings nav items."
```

---

## Task 17: Setup wizard — Step 1 (create owner)

**Files:**
- Create: `frontend/src/pages/owner/SetupWizard.jsx`

- [ ] **Step 1: Create the wizard with Step 1 only**

Create `frontend/src/pages/owner/SetupWizard.jsx`:

```jsx
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { setupAPI } from '../../api/owner';
import { useAuth } from '../../context/AuthContext';

const inputClass =
  'w-full px-3 py-2 border border-ink/20 rounded-sm bg-paper focus:outline-none focus:border-iris';

const buttonClass =
  'px-4 py-2 bg-ink text-cream rounded-sm hover:bg-ink/90 disabled:opacity-50';

const SetupWizard = () => {
  const navigate = useNavigate();
  const { setUserDirect } = useAuth(); // added in Task 23 if not present — see note below
  const [step, setStep] = useState(1);
  const [form, setForm] = useState({
    email: '',
    password: '',
    first_name: '',
    last_name: '',
  });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmitStep1 = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const { data } = await setupAPI.createOwner(form);
      localStorage.setItem('access_token', data.access);
      localStorage.setItem('refresh_token', data.refresh);
      if (setUserDirect) setUserDirect(data.user);
      setStep(2);
    } catch (err) {
      const status = err?.response?.status;
      const body = err?.response?.data;
      if (status === 409 && body?.error === 'owner_exists') {
        setError('Setup already started. Please log in at /owner/login.');
      } else if (status === 409 && body?.error === 'email_taken') {
        setError('An account with this email already exists.');
      } else if (status === 400 && body?.password) {
        setError('Password must be at least 8 characters.');
      } else if (status === 400 && body?.email) {
        setError('Please enter a valid email address.');
      } else {
        setError('Could not create account. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-cream flex items-center justify-center p-4">
      <div className="max-w-md w-full">
        <div className="mb-6 text-center">
          <div className="label-mono text-ink/60">Jeeves setup</div>
          <h1 className="text-2xl font-semibold text-ink">
            Step {step} of 2
          </h1>
        </div>

        {step === 1 && (
          <form
            onSubmit={handleSubmitStep1}
            className="bg-paper border border-ink/10 rounded-sm p-6 space-y-4"
          >
            <h2 className="text-lg font-medium text-ink">
              Create your owner account
            </h2>

            <div>
              <label className="block text-sm mb-1">First name</label>
              <input
                className={inputClass}
                type="text"
                required
                value={form.first_name}
                onChange={(e) => setForm({ ...form, first_name: e.target.value })}
              />
            </div>
            <div>
              <label className="block text-sm mb-1">Last name</label>
              <input
                className={inputClass}
                type="text"
                required
                value={form.last_name}
                onChange={(e) => setForm({ ...form, last_name: e.target.value })}
              />
            </div>
            <div>
              <label className="block text-sm mb-1">Email</label>
              <input
                className={inputClass}
                type="email"
                required
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
              />
            </div>
            <div>
              <label className="block text-sm mb-1">
                Password (min 8 chars)
              </label>
              <input
                className={inputClass}
                type="password"
                required
                minLength={8}
                value={form.password}
                onChange={(e) => setForm({ ...form, password: e.target.value })}
              />
            </div>

            {error && (
              <p className="text-red-600 text-sm">{error}</p>
            )}

            <button type="submit" className={buttonClass} disabled={loading}>
              {loading ? 'Creating…' : 'Continue →'}
            </button>
          </form>
        )}

        {step === 2 && (
          <div className="bg-paper border border-ink/10 rounded-sm p-6">
            <p>Step 2 will be added in the next task.</p>
            <button className="underline text-sm" onClick={() => setStep(1)}>
              ← Back
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

export default SetupWizard;
```

**Note on `setUserDirect`:** AuthContext currently has `login` but no imperative setter. If `setUserDirect` does not exist, you can temporarily call `window.location.reload()` after setting the JWT instead — Task 23 handles adding `setUserDirect` properly to AuthContext. For now, ship the wizard with `setUserDirect` guarded (`if (setUserDirect)`) so the code compiles.

- [ ] **Step 2: Commit**

```bash
git add frontend/src/pages/owner/SetupWizard.jsx
git commit -m "feat(frontend): add SetupWizard Step 1 (create owner)

Two-step wizard scaffold with Step 1 implemented. Handles email_taken,
owner_exists, and weak_password errors inline. Step 2 is a
placeholder to be filled in next."
```

---

## Task 18: Setup wizard — Step 2 (license) + completion

**Files:**
- Modify: `frontend/src/pages/owner/SetupWizard.jsx`

- [ ] **Step 1: Replace Step 2 placeholder with license form**

In `frontend/src/pages/owner/SetupWizard.jsx`, replace the `{step === 2 && ...}` block with:

```jsx
{step === 2 && (
  <LicenseStep onDone={() => navigate('/owner/dashboard')} />
)}
```

Then add this subcomponent above the `SetupWizard` component (inside the same file):

```jsx
import { useBootstrap } from '../../context/BootstrapContext';

const LicenseStep = ({ onDone }) => {
  const [key, setKey] = useState('');
  const [status, setStatus] = useState(null); // 'valid' | 'grace' | null
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { refresh: refreshBootstrap } = useBootstrap();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setStatus(null);
    setLoading(true);
    try {
      const { data } = await setupAPI.saveLicense(key);
      setStatus(data.status);
    } catch (err) {
      const body = err?.response?.data;
      if (body?.error === 'invalid_key') {
        setError(`Gumroad rejected the key: ${body.message || 'not found'}.`);
      } else {
        setError('Something went wrong. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleContinue = async () => {
    setLoading(true);
    try {
      await setupAPI.complete();
      await refreshBootstrap();
      onDone();
    } catch (err) {
      setError('Could not complete setup. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="bg-paper border border-ink/10 rounded-sm p-6 space-y-4"
    >
      <h2 className="text-lg font-medium text-ink">Enter your Gumroad license key</h2>
      <p className="text-sm text-ink/70">
        You'll find this in the Gumroad email you received after purchase.
      </p>

      <div>
        <label className="block text-sm mb-1">License key</label>
        <input
          className={inputClass}
          type="text"
          required
          value={key}
          onChange={(e) => setKey(e.target.value)}
          disabled={status === 'valid' || status === 'grace'}
        />
      </div>

      {error && <p className="text-red-600 text-sm">{error}</p>}

      {status === 'valid' && (
        <p className="text-green-700 text-sm">
          ✓ License verified. Click Continue to finish setup.
        </p>
      )}

      {status === 'grace' && (
        <p className="text-yellow-700 text-sm">
          ⚠ We couldn't reach Gumroad right now. Your key was saved and we'll
          retry automatically. You have a 7-day grace period.
        </p>
      )}

      {!status && (
        <button type="submit" className={buttonClass} disabled={loading}>
          {loading ? 'Verifying…' : 'Verify key'}
        </button>
      )}

      {(status === 'valid' || status === 'grace') && (
        <button
          type="button"
          className={buttonClass}
          onClick={handleContinue}
          disabled={loading}
        >
          {loading ? 'Finishing…' : 'Continue →'}
        </button>
      )}
    </form>
  );
};
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/pages/owner/SetupWizard.jsx
git commit -m "feat(frontend): add SetupWizard Step 2 (license key)

Verify → show valid/grace/error state → Continue calls
/api/setup/complete, refreshes bootstrap context, and navigates to
/owner/dashboard. Inline error on explicit invalid_key from Gumroad."
```

---

## Task 19: OwnerLoginPage

**Files:**
- Create: `frontend/src/pages/owner/OwnerLoginPage.jsx`

- [ ] **Step 1: Create the login page**

Create `frontend/src/pages/owner/OwnerLoginPage.jsx`:

```jsx
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { useAuth } from '../../context/AuthContext';

const inputClass =
  'w-full px-3 py-2 border border-ink/20 rounded-sm bg-paper focus:outline-none focus:border-iris';

const buttonClass =
  'px-4 py-2 bg-ink text-cream rounded-sm hover:bg-ink/90 disabled:opacity-50';

const OwnerLoginPage = () => {
  const navigate = useNavigate();
  const { login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const data = await login(email, password);
      const role = data?.user?.role;
      if (role !== 'owner') {
        setError('Access denied: owner role required.');
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        setLoading(false);
        return;
      }
      navigate('/owner/dashboard');
    } catch (err) {
      setError('Invalid email or password.');
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-cream flex items-center justify-center p-4">
      <form
        onSubmit={handleSubmit}
        className="max-w-md w-full bg-paper border border-ink/10 rounded-sm p-6 space-y-4"
      >
        <div className="mb-4">
          <div className="label-mono text-ink/60">Jeeves Admin</div>
          <h1 className="text-2xl font-semibold text-ink">Owner login</h1>
        </div>

        <div>
          <label className="block text-sm mb-1">Email</label>
          <input
            className={inputClass}
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </div>
        <div>
          <label className="block text-sm mb-1">Password</label>
          <input
            className={inputClass}
            type="password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>

        {error && <p className="text-red-600 text-sm">{error}</p>}

        <button type="submit" className={buttonClass} disabled={loading}>
          {loading ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
    </div>
  );
};

export default OwnerLoginPage;
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/pages/owner/OwnerLoginPage.jsx
git commit -m "feat(frontend): add OwnerLoginPage

Reuses existing authAPI.login from AuthContext. Rejects non-owner
roles with 'Access denied' and clears the just-stored JWT pair."
```

---

## Task 20: OwnerDashboardPage (counters + config health)

**Files:**
- Create: `frontend/src/pages/owner/OwnerDashboardPage.jsx`

- [ ] **Step 1: Create the dashboard page**

Create `frontend/src/pages/owner/OwnerDashboardPage.jsx`:

```jsx
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';

import { ownerAPI } from '../../api/owner';
import { useAuth } from '../../context/AuthContext';

const CounterCard = ({ label, value }) => (
  <div className="bg-paper border border-ink/10 rounded-sm p-4">
    <div className="label-mono text-ink/60 text-xs uppercase">{label}</div>
    <div className="text-3xl font-semibold text-ink mt-1">{value}</div>
  </div>
);

const HealthItem = ({ ok, label, href }) => (
  <li className="flex items-center gap-2 text-sm py-1">
    <span className={ok ? 'text-green-700' : 'text-red-600'}>
      {ok ? '✓' : '✗'}
    </span>
    {href ? (
      <Link to={href} className="underline">{label}</Link>
    ) : (
      <span>{label}</span>
    )}
  </li>
);

const LicenseCard = ({ license }) => {
  if (!license) return null;
  const color =
    license.status === 'valid' ? 'bg-green-50 border-green-300 text-green-900' :
    license.status === 'grace' ? 'bg-yellow-50 border-yellow-300 text-yellow-900' :
    license.status === 'expired' ? 'bg-red-50 border-red-300 text-red-900' :
    'bg-paper border-ink/10 text-ink';
  return (
    <div className={`${color} border rounded-sm p-4`}>
      <div className="label-mono text-xs uppercase">License</div>
      <div className="text-lg font-medium mt-1 capitalize">{license.status}</div>
      {license.last_verified_at && (
        <div className="text-xs mt-1">
          Last verified: {new Date(license.last_verified_at).toLocaleString()}
        </div>
      )}
      {license.grace_days_remaining != null && (
        <div className="text-xs mt-1">
          {license.grace_days_remaining} day(s) remaining in grace period
        </div>
      )}
    </div>
  );
};

const OwnerDashboardPage = () => {
  const { user } = useAuth();
  const [stats, setStats] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    ownerAPI.getDashboardStats()
      .then(({ data }) => setStats(data))
      .catch(() => setError('Could not load dashboard.'));
  }, []);

  if (error) return <p className="text-red-600">{error}</p>;
  if (!stats) return <p className="label-mono">Loading…</p>;

  const c = stats.counters;
  const h = stats.config_health;

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-semibold text-ink">
        Welcome, {user?.first_name || 'Owner'}
      </h1>

      <LicenseCard license={stats.license} />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <CounterCard label="Branches" value={c.branches} />
        <CounterCard label="Specializations" value={c.specializations} />
        <CounterCard label="Clients" value={c.clients} />
        <CounterCard label="Documents" value={c.documents} />
      </div>

      <div className="bg-paper border border-ink/10 rounded-sm p-4 max-w-lg">
        <h2 className="text-lg font-medium text-ink mb-2">
          Required configuration
        </h2>
        <ul>
          <HealthItem ok={h.license_valid} label="License active" />
          <HealthItem
            ok={h.llm_providers_configured}
            label="LLM provider configured"
            href="/owner/ai-providers"
          />
          <HealthItem
            ok={h.embedding_models_configured}
            label="Embedding model configured"
            href="/owner/ai-providers"
          />
          <HealthItem
            ok={h.branches_exist}
            label="First branch created"
            href="/owner/branches"
          />
        </ul>
      </div>
    </div>
  );
};

export default OwnerDashboardPage;
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/pages/owner/OwnerDashboardPage.jsx
git commit -m "feat(frontend): add OwnerDashboardPage

Live counters (branches/specs/clients/docs), license card coloured by
status, and a 4-item config-health checklist that links to the
AI-providers and branches stubs."
```

---

## Task 21: OwnerSettingsPage (license + account)

**Files:**
- Create: `frontend/src/pages/owner/OwnerSettingsPage.jsx`

- [ ] **Step 1: Create the settings page**

Create `frontend/src/pages/owner/OwnerSettingsPage.jsx`:

```jsx
import { useEffect, useState } from 'react';

import { ownerAPI } from '../../api/owner';
import { useAuth } from '../../context/AuthContext';
import { useBootstrap } from '../../context/BootstrapContext';

const buttonClass =
  'px-4 py-2 bg-ink text-cream rounded-sm hover:bg-ink/90 disabled:opacity-50';

const Section = ({ title, children }) => (
  <section className="bg-paper border border-ink/10 rounded-sm p-4 max-w-2xl">
    <h2 className="text-lg font-medium text-ink mb-3">{title}</h2>
    {children}
  </section>
);

const mask = (key) => {
  if (!key) return '—';
  if (key.length <= 4) return '****';
  return `****${key.slice(-4)}`;
};

const OwnerSettingsPage = () => {
  const { user } = useAuth();
  const { licenseStatus, licenseLastVerifiedAt, refresh } = useBootstrap();
  const [stats, setStats] = useState(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');

  useEffect(() => {
    ownerAPI.getDashboardStats().then(({ data }) => setStats(data));
  }, []);

  const handleReverify = async () => {
    setBusy(true);
    setMessage('');
    try {
      const { data } = await ownerAPI.reverifyLicense();
      setMessage(`License status: ${data.status}`);
      await refresh();
      const fresh = await ownerAPI.getDashboardStats();
      setStats(fresh.data);
    } catch (err) {
      setMessage('Re-verification failed. Please try again.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-semibold text-ink">Settings</h1>

      <Section title="License">
        <dl className="text-sm space-y-1">
          <div className="flex gap-2">
            <dt className="label-mono text-ink/60 w-32">Status:</dt>
            <dd className="capitalize">{licenseStatus || '—'}</dd>
          </div>
          <div className="flex gap-2">
            <dt className="label-mono text-ink/60 w-32">Key:</dt>
            <dd>{mask(stats?.license_key_masked)}</dd>
          </div>
          <div className="flex gap-2">
            <dt className="label-mono text-ink/60 w-32">Last verified:</dt>
            <dd>
              {licenseLastVerifiedAt
                ? new Date(licenseLastVerifiedAt).toLocaleString()
                : '—'}
            </dd>
          </div>
        </dl>
        <button onClick={handleReverify} disabled={busy} className={`${buttonClass} mt-3`}>
          {busy ? 'Re-verifying…' : 'Re-verify now'}
        </button>
        {message && <p className="text-sm mt-2">{message}</p>}
      </Section>

      <Section title="Account">
        <dl className="text-sm space-y-1">
          <div className="flex gap-2">
            <dt className="label-mono text-ink/60 w-32">Email:</dt>
            <dd>{user?.email}</dd>
          </div>
          <div className="flex gap-2">
            <dt className="label-mono text-ink/60 w-32">Name:</dt>
            <dd>{user?.first_name} {user?.last_name}</dd>
          </div>
        </dl>
        <p className="text-xs text-ink/60 mt-2">
          Password change and additional account settings will be added in a
          future step.
        </p>
      </Section>
    </div>
  );
};

export default OwnerSettingsPage;
```

Note: The dashboard stats endpoint does not currently return `license_key_masked`. The `mask(stats?.license_key_masked)` call will render "—" on the first render — that's acceptable for this spec. Adding masked key to the backend response is trivial but deferred.

- [ ] **Step 2: Commit**

```bash
git add frontend/src/pages/owner/OwnerSettingsPage.jsx
git commit -m "feat(frontend): add OwnerSettingsPage

License section with status, last-verified timestamp, and a working
'Re-verify now' button that refreshes BootstrapContext. Account
section shows the owner's email and name (read-only in this spec)."
```

---

## Task 22: AuthContext — add `isOwner` + `setUserDirect`

**Files:**
- Modify: `frontend/src/context/AuthContext.jsx`

- [ ] **Step 1: Read the file**

Run: `wc -l frontend/src/context/AuthContext.jsx` and note the current line count.

- [ ] **Step 2: Add `setUserDirect` and expose it + `isOwner`**

Find the `AuthProvider` component in `frontend/src/context/AuthContext.jsx`. In the returned provider value object, add:

```jsx
// existing returned value, find where `user`, `login`, `logout` are listed
const value = {
  user,
  loading,
  login,
  logout,
  // ... existing ...
  isOwner: user?.role === 'owner',
  setUserDirect: setUser,
};
```

If the provider returns an object literal inline (`<AuthContext.Provider value={{ user, login, ... }}>`), convert it to a `value` variable first and then add `isOwner` and `setUserDirect`.

- [ ] **Step 3: Verify AuthContext still works**

Run: `cd frontend && npx vite build 2>&1 | tail -15`
Expected: build succeeds; no new errors related to AuthContext.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/context/AuthContext.jsx
git commit -m "feat(frontend): expose isOwner + setUserDirect in AuthContext

SetupWizard needs to set the freshly-created user imperatively after
POST /api/setup/owner. isOwner is the role guard used by
BootstrapGate and OwnerLoginPage."
```

---

## Task 23: Wire new routes in App.jsx

**Files:**
- Modify: `frontend/src/App.jsx`

- [ ] **Step 1: Read the file and find the `<Routes>` block**

Run: `grep -n "<Route" frontend/src/App.jsx`
Note the line numbers where existing routes are declared.

- [ ] **Step 2: Add imports**

Near the top of `frontend/src/App.jsx`, add:

```jsx
import { BootstrapProvider } from './context/BootstrapContext';
import BootstrapGate from './components/owner/BootstrapGate';
import OwnerLayout from './components/owner/OwnerLayout';
import RootRedirect from './components/owner/RootRedirect';
import SetupWizard from './pages/owner/SetupWizard';
import OwnerLoginPage from './pages/owner/OwnerLoginPage';
import OwnerDashboardPage from './pages/owner/OwnerDashboardPage';
import OwnerSettingsPage from './pages/owner/OwnerSettingsPage';
import StubPage from './pages/owner/StubPage';
```

- [ ] **Step 3: Wrap the app in `<BootstrapProvider>`**

Wrap the existing `<BrowserRouter>` contents with `<BootstrapProvider>`:

```jsx
<AuthProvider>
  <ThemeProvider>
    <BrowserRouter>
      <BootstrapProvider>
        <Routes>
          {/* ... existing + new routes below ... */}
        </Routes>
      </BootstrapProvider>
    </BrowserRouter>
  </ThemeProvider>
</AuthProvider>
```

- [ ] **Step 4: Add the new routes**

Inside the `<Routes>` block, after the existing `/l/:tag` block and before the root-redirect fallback, add:

```jsx
{/* OWNER ADMIN */}
<Route path="/setup" element={<SetupWizard />} />
<Route path="/owner/login" element={<OwnerLoginPage />} />
<Route
  path="/owner"
  element={
    <BootstrapGate>
      <OwnerLayout />
    </BootstrapGate>
  }
>
  <Route index element={<Navigate to="dashboard" replace />} />
  <Route path="dashboard" element={<OwnerDashboardPage />} />
  <Route path="branches" element={<StubPage title="Branches" />} />
  <Route path="specializations" element={<StubPage title="Specializations" />} />
  <Route path="clients" element={<StubPage title="Clients" />} />
  <Route path="ai-providers" element={<StubPage title="AI Providers" />} />
  <Route path="settings" element={<OwnerSettingsPage />} />
</Route>
```

Also replace the current default `/` route (or the existing root handler) with:

```jsx
<Route path="/" element={<RootRedirect />} />
```

Be careful: only replace the `/` route if nothing critical depends on the current landing behavior. If the existing `/` handler is important for the legacy flow, keep it and instead map `/owner` index separately.

- [ ] **Step 5: Build the frontend and confirm it compiles**

Run: `cd frontend && npx vite build 2>&1 | tail -20`
Expected: build completes without errors; output mentions the new chunks or just succeeds silently.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/App.jsx
git commit -m "feat(frontend): wire /setup and /owner/* routes

Adds BootstrapProvider around the router, the /setup wizard, the
/owner/login page, and the /owner/* subtree guarded by BootstrapGate.
RootRedirect drives the landing / route based on bootstrap state."
```

---

## Task 24: End-to-end manual smoke test

**Files:** none — this task is a verification pass, not code.

- [ ] **Step 1: Wipe and reset the database**

Run: `docker compose down -v && docker compose up -d`
Expected: fresh DB with only default migrations applied.

- [ ] **Step 2: Apply migrations**

Run: `docker compose exec -T web python manage.py migrate`
Expected: includes `concierge_platform.0007_platformlicense`.

- [ ] **Step 3: Open the frontend**

Run: `cd frontend && npm run dev` (or open the deployed dev URL)
Navigate: `http://localhost:5173/`
Expected: automatic redirect to `/setup`.

- [ ] **Step 4: Walk the happy path**

Fill Step 1 with valid details → Continue → expect Step 2.
Fill Step 2 with a **real Gumroad test license key** (use a Gumroad test product, or temporarily mock `GUMROAD_VERIFY_URL` to return success) → Verify key → "License verified" → Continue → land on `/owner/dashboard`.

Expected dashboard state:
- Welcome message with the owner's first name
- Green license card (`valid`)
- All 4 counters = 0
- Config health: License ✓, LLM ✗, Embedding ✗, Branch ✗

- [ ] **Step 5: Walk the invalid-key path**

Reset DB again. On Step 2, enter an obviously wrong key. Expected: red inline error, stays on Step 2.

- [ ] **Step 6: Walk the grace path**

Reset DB again. On Step 2, disable your network (`docker compose exec -T web sh -c "echo 'blocked' > /dev/null"` — or stop the backend's internet). Enter any key → expect yellow warning "Grace period: 7 days" → click Continue Anyway → land on `/owner/dashboard` with yellow grace banner at the top.

- [ ] **Step 7: Walk the aborted-wizard path**

Reset DB. Complete Step 1 only, then close the tab. Reopen. Expected: redirect to `/setup`, but the backend already has an owner so Step 1 returns 409 — the wizard should show the "Setup already started" error and ask to log in at `/owner/login`.

- [ ] **Step 8: Walk the read-only path**

With setup complete, connect to the DB and manually set status:

```sql
UPDATE concierge_platform_platformlicense SET status='expired' WHERE id=1;
```

Refresh the browser → expect red ReadOnly banner across all `/owner/*` pages. Reverify the license through Settings — if Gumroad mocks valid, banner disappears after refresh.

- [ ] **Step 9: Walk the sidebar stubs**

Navigate to Branches, Specializations, Clients, AI Providers — expect "Coming soon" placeholder on each.

- [ ] **Step 10: Walk the logout path**

Clear localStorage (dev tools) → refresh → expect `/owner/login`.

- [ ] **Step 11: Confirm acceptance criteria from the spec**

Check each of the 9 acceptance criteria in the spec file. All should pass based on the steps above.

- [ ] **Step 12: Commit the smoke-test completion note**

If the smoke test passes, no commit is needed — the feature is complete. If you discovered issues and had to patch them, commit each patch with `fix(setup): ...` or `fix(owner): ...` messages.

---

## Self-review (completed by author)

1. **Spec coverage:** Every section of the spec maps to at least one task:
   - Context/roadmap: plan header
   - Decisions table: implicit in tasks 1-23
   - Data model (§Data model): Task 1
   - Backend API (§Backend API surface): Tasks 5-11
   - Gumroad client: Task 2
   - Permission class: Task 3
   - Frontend routing & components (§Frontend): Tasks 12-23
   - Data flow sequences: covered by frontend components + Task 24 smoke test
   - Error handling: covered by tests in tasks 1-11 and smoke steps in Task 24
   - Testing strategy (§Testing): backend tests in tasks 1-11, manual checklist in Task 24
   - Acceptance criteria: Task 24 Step 11

2. **Placeholder scan:** No "TBD", "TODO", "add error handling", or "similar to Task N" references. All code blocks are actual code.

3. **Type/name consistency:**
   - `PlatformLicense.LicenseStatus.VALID` used consistently.
   - `GumroadResult.outcome` uses the same three strings (`valid`/`invalid`/`network_error`) in tests, client, and views.
   - URL paths are consistent: `/api/platform/bootstrap/`, `/api/setup/owner/`, `/api/setup/license/`, `/api/setup/complete/`, `/api/owner/dashboard/stats/`, `/api/owner/license/reverify/` — all with trailing slashes.
   - Frontend `setupAPI.saveLicense(license_key)` matches the backend `LicenseKeySerializer` field `license_key`.
   - `BootstrapContext` field names (`setupRequired`, `licenseStatus`, `licenseLastVerifiedAt`, `graceDaysRemaining`) stay stable across components.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-10-first-run-admin-auth-foundation.md`.
