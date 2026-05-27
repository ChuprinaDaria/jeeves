# Jeeves Open-Source Transition — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform Jeeves from a commercial Gumroad product into a community open-source project under Elastic License 2.0.

**Architecture:** 8 sequential tasks, each producing one self-contained commit. Tasks go: security → license → gumroad removal → stripe removal → workflow removal → rename → community files → DX.

**Tech Stack:** Django 5, React 19, Docker Compose, GitHub Actions

---

### Task 1: Security Cleanup

**Files:**
- Modify: `backend/docker-compose.yml:63`
- Modify: `backend/Jeeves/settings.py:18`
- Modify: `backend/.env.example`

- [ ] **Step 1: Fix hardcoded WHATSAPP_QR_SECRET in docker-compose.yml**

In `backend/docker-compose.yml`, line 63, replace:
```yaml
      WHATSAPP_QR_SECRET: "super_secret_key_9283jd0923jd"
```
with:
```yaml
      WHATSAPP_QR_SECRET: "${WHATSAPP_QR_SECRET:-change-me}"
```

- [ ] **Step 2: Remove default FIELD_ENCRYPTION_KEY in settings.py**

In `backend/Jeeves/settings.py`, line 18, replace:
```python
FIELD_ENCRYPTION_KEY = env('FIELD_ENCRYPTION_KEY', default='ZF864sWF1B0QvMRbkRgDD_NzEP4GUqPogPbdqzuwjhU=')
```
with:
```python
FIELD_ENCRYPTION_KEY = env('FIELD_ENCRYPTION_KEY')
```

- [ ] **Step 3: Add missing variables to backend/.env.example**

Append after the existing `META_VERIFY_TOKEN=` line:
```env

# Encryption key for sensitive fields (generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
FIELD_ENCRYPTION_KEY=

# WhatsApp QR code signing secret
WHATSAPP_QR_SECRET=

# Twilio (optional — for WhatsApp bridge)
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886
```

- [ ] **Step 4: Run tests to verify nothing broke**

Run: `cd backend && docker compose exec web pytest Jeeves/concierge_platform/tests/ -v --timeout=30 2>/dev/null || cd Jeeves && python -m pytest concierge_platform/tests/ -v`

Expected: All existing tests pass (note: Gumroad tests still exist at this point, they should still pass since we haven't touched that code).

- [ ] **Step 5: Commit**

```bash
git add backend/docker-compose.yml backend/Jeeves/settings.py backend/.env.example
git commit -m "security: remove hardcoded secrets, require FIELD_ENCRYPTION_KEY from env"
```

---

### Task 2: Add Elastic License 2.0

**Files:**
- Create: `LICENSE`
- Modify: `README.md:648-650`

- [ ] **Step 1: Create LICENSE file**

Create `LICENSE` at repo root with the full Elastic License 2.0 text. Set:
- Licensor: `Daria Chuprina / Lazysoft`
- Licensed Work: `Jeeves`
- The full ELv2 text is available at https://www.elastic.co/licensing/elastic-license — copy the complete text, filling in the Licensor and Licensed Work fields.

- [ ] **Step 2: Update README license section**

In `README.md`, replace lines 648-650:
```markdown
## License

MIT — See [LICENSE](LICENSE) for terms.
```
with:
```markdown
## License

Elastic License 2.0 — See [LICENSE](LICENSE) for full terms.

**In short:**
- **Free forever** — use, deploy, modify for yourself or your organization
- **Don't sell it** — you may not provide Jeeves as a hosted/managed service to third parties
- **Keep the branding** — the "Jeeves" name and attribution footer must remain intact

Jeeves — by Daria Chuprina & open-source community. Forever free.
```

- [ ] **Step 3: Update README line 355 — remove license mention from BootstrapGate description**

In `README.md`, find the line:
```
Platform-wide administration. Protected by `BootstrapGate` (checks setup completion + license).
```
Replace with:
```
Platform-wide administration. Protected by `BootstrapGate` (checks setup completion).
```

- [ ] **Step 4: Commit**

```bash
git add LICENSE README.md
git commit -m "license: add Elastic License 2.0, replace MIT reference"
```

---

### Task 3: Remove Gumroad Licensing System

This is the largest task. It touches backend models, views, serializers, URLs, settings, tests, and frontend components.

**Files:**
- Delete: `backend/Jeeves/concierge_platform/gumroad_client.py`
- Delete: `backend/Jeeves/concierge_platform/tests/test_gumroad_client.py`
- Delete: `backend/Jeeves/concierge_platform/tests/test_reverify_api.py`
- Delete: `backend/Jeeves/concierge_platform/tests/test_license_model.py`
- Delete: `frontend/src/components/owner/GraceBanner.jsx`
- Delete: `frontend/src/components/owner/ReadOnlyBanner.jsx`
- Modify: `backend/Jeeves/concierge_platform/models.py:121-198` — remove PlatformLicense
- Modify: `backend/Jeeves/concierge_platform/views_setup.py:59-145` — remove license views
- Modify: `backend/Jeeves/concierge_platform/views_owner.py` — remove license views
- Modify: `backend/Jeeves/concierge_platform/views_platform.py` — simplify bootstrap
- Modify: `backend/Jeeves/concierge_platform/serializers.py:31-38` — remove LicenseKeySerializer
- Modify: `backend/Jeeves/concierge_platform/urls.py:61,64` — remove license URLs
- Modify: `backend/Jeeves/settings.py:468-478` — remove Gumroad block
- Modify: `backend/docker-compose.yml:64,102,137` — remove GUMROAD_PRODUCT_ID
- Modify: `backend/Jeeves/concierge_platform/tests/test_setup_api.py:72-208` — remove license tests
- Modify: `backend/Jeeves/concierge_platform/tests/test_bootstrap_api.py` — simplify
- Modify: `backend/Jeeves/concierge_platform/tests/test_dashboard_api.py` — remove license assertions
- Modify: `frontend/src/context/BootstrapContext.jsx:17-19,30-32` — remove license state
- Modify: `frontend/src/components/owner/OwnerLayout.jsx:3,5,12-13` — remove banners
- Modify: `frontend/src/pages/owner/SetupWizard.jsx:14-109,296-303` — remove license step
- Modify: `frontend/src/pages/owner/OwnerDashboardPage.jsx:27-50,75,89` — remove LicenseCard
- Modify: `frontend/src/pages/owner/OwnerSettingsPage.jsx:6,26,27-49,55-78` — remove license section
- Modify: `frontend/src/api/owner.js:11,18` — remove license API calls
- Create: `backend/Jeeves/concierge_platform/migrations/NNNN_delete_platformlicense.py`

#### Part A: Backend model + settings removal

- [ ] **Step 1: Delete gumroad_client.py**

```bash
rm backend/Jeeves/concierge_platform/gumroad_client.py
```

- [ ] **Step 2: Remove PlatformLicense model from models.py**

In `backend/Jeeves/concierge_platform/models.py`, delete lines 121-198 (the entire `PlatformLicense` class, from `class PlatformLicense(models.Model):` through the last line of `grace_days_remaining` property). The file should end after the `SystemMessage` class (after line 119).

- [ ] **Step 3: Remove LicenseKeySerializer from serializers.py**

In `backend/Jeeves/concierge_platform/serializers.py`, delete lines 31-38 (the `LicenseKeySerializer` class).

- [ ] **Step 4: Remove Gumroad settings block**

In `backend/Jeeves/settings.py`, delete lines 468-478 (from `# --- Gumroad license validation` through the `raise ImproperlyConfigured` block and trailing blank line).

- [ ] **Step 5: Remove GUMROAD_PRODUCT_ID from docker-compose.yml**

In `backend/docker-compose.yml`, delete these three lines:
- Line 64: `GUMROAD_PRODUCT_ID: "${GUMROAD_PRODUCT_ID:-dev_placeholder}"` (web service)
- Line 102: `GUMROAD_PRODUCT_ID: "${GUMROAD_PRODUCT_ID:-dev_placeholder}"` (celery_worker)
- Line 137: `GUMROAD_PRODUCT_ID: "${GUMROAD_PRODUCT_ID:-dev_placeholder}"` (celery_beat)

#### Part B: Backend views + URLs

- [ ] **Step 6: Rewrite views_setup.py — remove license views, simplify SetupComplete**

Replace the entire file content of `backend/Jeeves/concierge_platform/views_setup.py` with:

```python
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.tokens import RefreshToken

from Jeeves.accounts.models import User, Roles
from Jeeves.concierge_platform.permissions import IsOwner
from Jeeves.concierge_platform.serializers import OwnerCreateSerializer


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


class SetupCompleteView(APIView):
    """Finalize the setup wizard. Creating the owner is the only step now."""

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsOwner]

    def post(self, request):
        return Response(status=status.HTTP_204_NO_CONTENT)
```

- [ ] **Step 7: Rewrite views_owner.py — remove license views**

Replace the entire file content of `backend/Jeeves/concierge_platform/views_owner.py` with:

```python
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from Jeeves.branches.models import Branch, BranchDocument
from Jeeves.clients.models import Client
from Jeeves.concierge_platform.permissions import IsOwner
from Jeeves.EmbeddingModel.models import EmbeddingModel, LLMProvider
from Jeeves.specializations.models import Specialization, SpecializationDocument


class DashboardStatsView(APIView):
    """Counters + config-health checklist for /owner/dashboard."""

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsOwner]

    def get(self, request):
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
            "llm_providers_configured": LLMProvider.objects.filter(is_active=True).exists(),
            "embedding_models_configured": EmbeddingModel.objects.filter(is_active=True).exists(),
            "branches_exist": Branch.objects.exists(),
        }

        return Response({
            "counters": counters,
            "config_health": config_health,
        })


from Jeeves.concierge_platform.models import PlatformDefaults
from Jeeves.concierge_platform.serializers import PlatformDefaultsSerializer


class PlatformDefaultsView(APIView):
    """Singleton get/put for /owner/settings/defaults."""

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsOwner]

    def get(self, request):
        obj = PlatformDefaults.get()
        return Response(PlatformDefaultsSerializer(obj).data)

    def put(self, request):
        obj = PlatformDefaults.get()
        serializer = PlatformDefaultsSerializer(
            obj, data=request.data, partial=False,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
```

- [ ] **Step 8: Rewrite views_platform.py — simplify bootstrap**

Replace `backend/Jeeves/concierge_platform/views_platform.py` with:

```python
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from Jeeves.accounts.models import User, Roles


class BootstrapView(APIView):
    """Public endpoint that tells the frontend whether setup is needed.
    Called on every React boot.
    """

    permission_classes = [AllowAny]

    def get(self, request):
        setup_required = not User.objects.filter(role=Roles.OWNER).exists()
        return Response({
            "setup_required": setup_required,
        })
```

- [ ] **Step 9: Update urls.py — remove license URLs**

In `backend/Jeeves/concierge_platform/urls.py`, replace lines 58-66:
```python
urlpatterns = [
    path('platform/bootstrap/', views_platform.BootstrapView.as_view(), name='platform-bootstrap'),
    path('setup/owner/', views_setup.CreateOwnerView.as_view(), name='setup-owner'),
    path('setup/license/', views_setup.SetupLicenseView.as_view(), name='setup-license'),
    path('setup/complete/', views_setup.SetupCompleteView.as_view(), name='setup-complete'),
    path('owner/dashboard/stats/', views_owner.DashboardStatsView.as_view(), name='owner-dashboard-stats'),
    path('owner/license/reverify/', views_owner.ReverifyLicenseView.as_view(), name='owner-license-reverify'),
    path('owner/settings/defaults/', views_owner.PlatformDefaultsView.as_view(), name='owner-settings-defaults'),
]
```
with:
```python
urlpatterns = [
    path('platform/bootstrap/', views_platform.BootstrapView.as_view(), name='platform-bootstrap'),
    path('setup/owner/', views_setup.CreateOwnerView.as_view(), name='setup-owner'),
    path('setup/complete/', views_setup.SetupCompleteView.as_view(), name='setup-complete'),
    path('owner/dashboard/stats/', views_owner.DashboardStatsView.as_view(), name='owner-dashboard-stats'),
    path('owner/settings/defaults/', views_owner.PlatformDefaultsView.as_view(), name='owner-settings-defaults'),
]
```

- [ ] **Step 10: Create migration to drop PlatformLicense table**

```bash
cd backend/Jeeves && python manage.py makemigrations concierge_platform --name delete_platformlicense
```

If makemigrations can't run (missing env), create the migration manually at `backend/Jeeves/concierge_platform/migrations/0009_delete_platformlicense.py` (or next available number):

```python
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('concierge_platform', '0008_alter_platformlicense_id'),
    ]

    operations = [
        migrations.DeleteModel(
            name='PlatformLicense',
        ),
    ]
```

Note: Check the latest migration number in `backend/Jeeves/concierge_platform/migrations/` and use the next sequential number. The `dependencies` should reference the most recent migration in that app.

#### Part C: Delete backend test files

- [ ] **Step 11: Delete Gumroad/license test files**

```bash
rm backend/Jeeves/concierge_platform/tests/test_gumroad_client.py
rm backend/Jeeves/concierge_platform/tests/test_reverify_api.py
rm backend/Jeeves/concierge_platform/tests/test_license_model.py
```

- [ ] **Step 12: Clean test_setup_api.py — remove license test classes**

In `backend/Jeeves/concierge_platform/tests/test_setup_api.py`, delete everything from line 72 to end of file (lines 72-208). This removes:
- The `from unittest.mock import patch` import
- The `from django.utils import timezone` import
- The `from rest_framework_simplejwt.tokens import RefreshToken` import
- The `from Jeeves.concierge_platform.gumroad_client import GumroadResult` import
- The `from Jeeves.concierge_platform.models import PlatformLicense` import
- The `_owner_client()` helper
- The `TestSetupLicense` class
- The `TestSetupComplete` class

The file should end after `TestSetupOwner` (line 70).

- [ ] **Step 13: Rewrite test_bootstrap_api.py — remove license assertions**

Replace entire content of `backend/Jeeves/concierge_platform/tests/test_bootstrap_api.py` with:

```python
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
```

- [ ] **Step 14: Rewrite test_dashboard_api.py — remove license assertions**

Replace entire content of `backend/Jeeves/concierge_platform/tests/test_dashboard_api.py` with:

```python
import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from Jeeves.accounts.models import User, Roles
from Jeeves.branches.models import Branch


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
        assert body["config_health"]["branches_exist"] is False

    def test_with_data(self):
        c, owner = _owner_client()
        Branch.objects.create(name="B1", slug="b1")
        Branch.objects.create(name="B2", slug="b2")

        resp = c.get(self.url)
        body = resp.json()
        assert body["counters"]["branches"] == 2
        assert body["config_health"]["branches_exist"] is True
```

#### Part D: Frontend cleanup

- [ ] **Step 15: Delete frontend license components**

```bash
rm frontend/src/components/owner/GraceBanner.jsx
rm frontend/src/components/owner/ReadOnlyBanner.jsx
```

- [ ] **Step 16: Simplify BootstrapContext.jsx**

Replace `frontend/src/context/BootstrapContext.jsx` with:

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
    error: null,
  });

  const load = useCallback(async () => {
    setState((s) => ({ ...s, loading: true, error: null }));
    try {
      const { data } = await platformAPI.getBootstrap();
      setState({
        loading: false,
        setupRequired: data.setup_required,
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

- [ ] **Step 17: Simplify OwnerLayout.jsx — remove banners**

Replace `frontend/src/components/owner/OwnerLayout.jsx` with:

```jsx
import { Outlet } from 'react-router-dom';

import OwnerSidebar from './OwnerSidebar';

const OwnerLayout = () => (
  <div className="flex min-h-screen bg-cream text-ink">
    <OwnerSidebar />
    <div className="flex-1 flex flex-col min-w-0">
      <main className="flex-1 px-4 py-6 md:px-8 md:py-8 overflow-x-hidden">
        <Outlet />
      </main>
    </div>
  </div>
);

export default OwnerLayout;
```

- [ ] **Step 18: Simplify SetupWizard.jsx — remove license step**

In `frontend/src/pages/owner/SetupWizard.jsx`:

1. Delete the entire `LicenseStep` component (lines 14-109)
2. Remove the `useBootstrap` import (line 6)
3. In `SetupWizard` component, change `handleSubmitStep1` to navigate directly to `/owner/dashboard` after owner creation instead of going to step 2. Replace the line `setStep(2);` (line 200) with:
```jsx
      await setupAPI.complete();
      navigate('/owner/dashboard');
```
4. Delete the step 2 render block (lines 296-303):
```jsx
        {step === 2 && (
          <>
            <h1 className="text-2xl font-semibold text-ink text-center mb-6">
              Step 2 of 2
            </h1>
            <LicenseStep onDone={() => navigate('/owner/dashboard')} />
          </>
        )}
```
5. Remove `step` and `setStep` state since it's no longer needed.

- [ ] **Step 19: Simplify OwnerDashboardPage.jsx — remove LicenseCard**

Replace `frontend/src/pages/owner/OwnerDashboardPage.jsx` with:

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

- [ ] **Step 20: Simplify OwnerSettingsPage.jsx — remove license section**

Replace `frontend/src/pages/owner/OwnerSettingsPage.jsx` with:

```jsx
import { Link } from 'react-router-dom';

import { useAuth } from '../../context/AuthContext';

const Section = ({ title, children }) => (
  <section className="bg-paper border border-ink/10 rounded-sm p-4 max-w-2xl">
    <h2 className="text-lg font-medium text-ink mb-3">{title}</h2>
    {children}
  </section>
);

const OwnerSettingsPage = () => {
  const { user } = useAuth();

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-semibold text-ink">Settings</h1>

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

      <Section title="AI behaviour defaults">
        <p className="text-sm text-ink/70 mb-2">
          Edit temperature, max tokens, context chunks, supported languages
          and the default greeting.
        </p>
        <Link
          to="/owner/settings/defaults"
          className="text-ink underline text-sm"
        >
          Open defaults editor →
        </Link>
      </Section>
    </div>
  );
};

export default OwnerSettingsPage;
```

- [ ] **Step 21: Clean up owner API — remove license calls**

In `frontend/src/api/owner.js`, replace lines 8-18:
```javascript
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
with:
```javascript
// POST /api/setup/* — used by the SetupWizard
export const setupAPI = {
  createOwner: (data) => api.post('/setup/owner/', data),
  complete: () => api.post('/setup/complete/'),
};

// GET /api/owner/* — used after login in the admin panel
export const ownerAPI = {
  getDashboardStats: () => api.get('/owner/dashboard/stats/'),
};
```

#### Part E: Verify and commit

- [ ] **Step 22: Run backend tests**

```bash
cd backend/Jeeves && python -m pytest concierge_platform/tests/ -v
```

Expected: All remaining tests pass. The license-related tests are deleted, bootstrap and dashboard tests rewritten.

- [ ] **Step 23: Run frontend lint + build**

```bash
cd frontend && npm run lint && npm run build
```

Expected: No lint errors, build succeeds.

- [ ] **Step 24: Commit**

```bash
git add -A
git commit -m "feat: remove Gumroad licensing system, simplify setup to single-step"
```

---

### Task 4: Remove Stripe Dependencies

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/.env.example`

- [ ] **Step 1: Remove Stripe packages from package.json**

In `frontend/package.json`, remove these two lines from `dependencies`:
```json
    "@stripe/react-stripe-js": "^5.3.0",
    "@stripe/stripe-js": "^8.2.0",
```

- [ ] **Step 2: Remove Stripe env var from frontend/.env.example**

In `frontend/.env.example`, delete lines 4-5:
```env
# Stripe (for payments)
VITE_STRIPE_PUBLIC_KEY=your_stripe_public_key_here
```

- [ ] **Step 3: Reinstall to update lockfile**

```bash
cd frontend && npm install
```

- [ ] **Step 4: Verify build still works**

```bash
cd frontend && npm run build
```

- [ ] **Step 5: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/.env.example
git commit -m "chore: remove unused Stripe dependencies"
```

---

### Task 5: Remove dev-deploy Workflow

**Files:**
- Delete: `.github/workflows/dev-deploy.yml`

- [ ] **Step 1: Delete the workflow file**

```bash
rm .github/workflows/dev-deploy.yml
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/dev-deploy.yml
git commit -m "chore: remove private dev-deploy workflow"
```

---

### Task 6: Rename concierge → jeeves

**Files:**
- Modify: `backend/docker-compose.yml` — container names and network
- Modify: `backend/.env.example` — DB name and Qdrant collection
- Modify: `backend/Jeeves/settings.py:300,302` — Qdrant defaults
- Modify: `SETUP.md` — product name

- [ ] **Step 1: Rename Docker containers and network in docker-compose.yml**

In `backend/docker-compose.yml`, replace all occurrences:
- `concierge_db` → `jeeves_db`
- `concierge_redis` → `jeeves_redis`
- `concierge_web` → `jeeves_web`
- `concierge_celery_worker` → `jeeves_celery_worker`
- `concierge_celery_beat` → `jeeves_celery_beat`
- `concierge_nginx` → `jeeves_nginx`
- `concierge_network` → `jeeves_network`

- [ ] **Step 2: Update .env.example defaults**

In `backend/.env.example`:
- Replace `DB_NAME=concierge` with `DB_NAME=jeeves`
- Replace `QDRANT_COLLECTION=concierge_embeddings` with `QDRANT_COLLECTION=jeeves_embeddings`

- [ ] **Step 3: Update Qdrant defaults in settings.py**

In `backend/Jeeves/settings.py`:
- Line 300: Replace `QDRANT_HOST = env("QDRANT_HOST", default="concierge_qdrant")` with `QDRANT_HOST = env("QDRANT_HOST", default="qdrant")`
- Line 302: Replace `QDRANT_COLLECTION = env("QDRANT_COLLECTION", default="concierge_embeddings")` with `QDRANT_COLLECTION = env("QDRANT_COLLECTION", default="jeeves_embeddings")`

- [ ] **Step 4: Update SETUP.md**

In `SETUP.md`, replace "Concierge AI Platform" with "Jeeves" (line 1):
```markdown
# Jeeves — Setup Guide
```

- [ ] **Step 5: Commit**

```bash
git add backend/docker-compose.yml backend/.env.example backend/Jeeves/settings.py SETUP.md
git commit -m "chore: rename concierge → jeeves in Docker, env, and docs"
```

---

### Task 7: Community Files

**Files:**
- Create: `CONTRIBUTING.md`
- Create: `CODE_OF_CONDUCT.md`
- Create: `SECURITY.md`
- Create: `.github/ISSUE_TEMPLATE/bug_report.md`
- Create: `.github/ISSUE_TEMPLATE/feature_request.md`
- Create: `.github/PULL_REQUEST_TEMPLATE.md`

- [ ] **Step 1: Create CONTRIBUTING.md**

Create `CONTRIBUTING.md` at repo root:

```markdown
# Contributing to Jeeves

Thank you for your interest in contributing! Jeeves is free and open-source, and we welcome pull requests, bug reports, and feature ideas.

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/<you>/jeeves.git`
3. Set up locally: see [SETUP.md](SETUP.md) or run `make setup && make up`
4. Create a feature branch: `git checkout -b feat/my-feature`
5. Make your changes
6. Run tests: `make test && make lint`
7. Push and open a Pull Request

## Code Style

### Backend (Python)
- **Black** — 120 character line length
- **isort** — black profile
- **flake8** — 120 chars, complexity 10
- Config in `pyproject.toml` and `.flake8`

### Frontend (JavaScript)
- **JSX** — no TypeScript
- **ESLint** with react-hooks and react-refresh plugins
- Run: `cd frontend && npm run lint`

## Tests

- Backend: `pytest` with `pytest-django`. Run from `backend/Jeeves/`
- Frontend: ESLint + production build check
- All PRs must pass CI before merge

## Branding

Jeeves is licensed under Elastic License 2.0. The attribution footer ("Jeeves — by Daria Chuprina & open-source community") must remain in the UI. You may customize colors, logos, and other visual elements, but please keep the footer and project name intact.

## Communication

- Language: **English** for all code, comments, issues, and PRs
- Be direct and constructive
- If something is unclear, ask — we'd rather answer a question than review a confused PR

## Reporting Bugs

[Open an issue](https://github.com/ChuprinaDaria/jeeves/issues) with:
- Steps to reproduce
- Expected vs actual behavior
- Environment (OS, Docker version, browser)

## Security

Found a vulnerability? **Do not open a public issue.** See [SECURITY.md](SECURITY.md).
```

- [ ] **Step 2: Create CODE_OF_CONDUCT.md**

Create `CODE_OF_CONDUCT.md` with the standard [Contributor Covenant v2.1](https://www.contributor-covenant.org/version/2/1/code_of_conduct/) text. Set contact email to `chuprina.dariia@gmail.com`.

- [ ] **Step 3: Create SECURITY.md**

Create `SECURITY.md`:

```markdown
# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in Jeeves, please report it responsibly.

**Do not open a public GitHub issue.**

Email: **chuprina.dariia@gmail.com**

Include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if you have one)

We will acknowledge your report within 48 hours and work on a fix. Once resolved, we'll credit you in the release notes (unless you prefer to remain anonymous).

## Supported Versions

Only the latest release on the `main` branch receives security updates.
```

- [ ] **Step 4: Create issue templates**

Create `.github/ISSUE_TEMPLATE/bug_report.md`:

```markdown
---
name: Bug Report
about: Report a bug in Jeeves
title: "[Bug] "
labels: bug
---

## Describe the bug

A clear description of what the bug is.

## Steps to reproduce

1. Go to ...
2. Click on ...
3. See error

## Expected behavior

What you expected to happen.

## Actual behavior

What actually happened.

## Environment

- OS: [e.g., Ubuntu 24.04]
- Docker version: [e.g., 24.0]
- Browser: [e.g., Chrome 120]
- Jeeves version/commit: [e.g., main@abc1234]

## Screenshots / logs

If applicable, add screenshots or relevant log output.
```

Create `.github/ISSUE_TEMPLATE/feature_request.md`:

```markdown
---
name: Feature Request
about: Suggest a new feature for Jeeves
title: "[Feature] "
labels: enhancement
---

## Problem

What problem does this solve? Why do you need it?

## Proposed solution

How do you think this should work?

## Alternatives considered

Any other approaches you've thought about.

## Additional context

Screenshots, mockups, links, or other relevant info.
```

- [ ] **Step 5: Create PR template**

Create `.github/PULL_REQUEST_TEMPLATE.md`:

```markdown
## What changed

Brief description of the changes.

## Why

What problem does this solve or what feature does it add?

## How to test

Steps to verify the changes work correctly.

## Checklist

- [ ] Tests pass (`make test`)
- [ ] Linting passes (`make lint`)
- [ ] Frontend builds (`cd frontend && npm run build`)
- [ ] No sensitive data committed
```

- [ ] **Step 6: Commit**

```bash
git add CONTRIBUTING.md CODE_OF_CONDUCT.md SECURITY.md .github/ISSUE_TEMPLATE/ .github/PULL_REQUEST_TEMPLATE.md
git commit -m "docs: add CONTRIBUTING, CODE_OF_CONDUCT, SECURITY, issue and PR templates"
```

---

### Task 8: Developer Experience — Makefile + Footer + README

**Files:**
- Create: `Makefile`
- Modify: `frontend/src/components/owner/OwnerLayout.jsx` — add footer
- Modify: `frontend/src/components/layout/Layout.jsx` — add footer
- Modify: `frontend/src/components/layout/ClientLayout.jsx` — add footer
- Modify: `README.md` — update contributing section with links
- Modify: `SETUP.md` — add make commands and contributor section

- [ ] **Step 1: Create Makefile**

Create `Makefile` at repo root:

```makefile
.PHONY: setup up down test lint migrate superuser logs build

setup:
	@echo "Setting up environment files..."
	@test -f backend/.env || cp backend/.env.example backend/.env
	@test -f frontend/.env || cp frontend/.env.example frontend/.env
	@echo "Done. Edit backend/.env to add your API keys and FIELD_ENCRYPTION_KEY."

up:
	cd backend && docker compose up -d

down:
	cd backend && docker compose down

test:
	cd backend && docker compose exec web pytest -v

lint:
	cd backend && docker compose exec web sh -c "black --check . && isort --check-only . && flake8"

migrate:
	cd backend && docker compose exec web python manage.py migrate

superuser:
	cd backend && docker compose exec web python manage.py createsuperuser

logs:
	cd backend && docker compose logs -f web

build:
	cd frontend && npm run build
```

- [ ] **Step 2: Add footer to OwnerLayout.jsx**

In `frontend/src/components/owner/OwnerLayout.jsx`, add a footer inside the flex column, after `</main>`:

```jsx
import { Outlet } from 'react-router-dom';

import OwnerSidebar from './OwnerSidebar';

const OwnerLayout = () => (
  <div className="flex min-h-screen bg-cream text-ink">
    <OwnerSidebar />
    <div className="flex-1 flex flex-col min-w-0">
      <main className="flex-1 px-4 py-6 md:px-8 md:py-8 overflow-x-hidden">
        <Outlet />
      </main>
      <footer className="px-4 py-3 text-center text-xs text-ink/40">
        Jeeves — by Daria Chuprina &amp; open-source community. Forever free.
      </footer>
    </div>
  </div>
);

export default OwnerLayout;
```

- [ ] **Step 3: Add footer to legacy Layout.jsx**

Read `frontend/src/components/layout/Layout.jsx` first. Add the same footer pattern after `</main>` inside the flex column wrapper (the `flex-1 flex flex-col` div):

```jsx
<footer className="px-4 py-3 text-center text-xs text-ink/40">
  Jeeves — by Daria Chuprina &amp; open-source community. Forever free.
</footer>
```

- [ ] **Step 4: Add footer to ClientLayout.jsx**

Read `frontend/src/components/layout/ClientLayout.jsx` first. Add the same footer pattern after `</main>` inside the main content wrapper:

```jsx
<footer className="px-4 py-3 text-center text-xs text-ink/40 dark:text-gray-500">
  Jeeves — by Daria Chuprina &amp; open-source community. Forever free.
</footer>
```

- [ ] **Step 5: Update SETUP.md with make commands**

After the "Clone the repository" section in `SETUP.md`, add:

```markdown
## Quick start (recommended)

```bash
make setup     # copies .env.example files
# Edit backend/.env — add your API keys and FIELD_ENCRYPTION_KEY
make up        # starts all services
make migrate   # runs database migrations
make superuser # creates your admin account
```

See `make help` for all available commands.
```

- [ ] **Step 6: Update README contributing section**

In `README.md`, replace the Contributing section (lines 634-644) with:

```markdown
## Contributing

Jeeves is free forever and actively developed. Pull requests, bug reports, and feature ideas are welcome.

- **[CONTRIBUTING.md](CONTRIBUTING.md)** — how to set up, code style, PR process
- **[SETUP.md](SETUP.md)** — local development setup
- **[SECURITY.md](SECURITY.md)** — reporting vulnerabilities
- **[Code of Conduct](CODE_OF_CONDUCT.md)** — community standards

Found a bug? [Open an issue.](https://github.com/ChuprinaDaria/jeeves/issues)
```

- [ ] **Step 7: Run frontend lint + build**

```bash
cd frontend && npm run lint && npm run build
```

- [ ] **Step 8: Commit**

```bash
git add Makefile frontend/src/components/owner/OwnerLayout.jsx frontend/src/components/layout/Layout.jsx frontend/src/components/layout/ClientLayout.jsx README.md SETUP.md
git commit -m "feat: add Makefile, branding footer, update docs for contributors"
```

---

## Post-completion Checklist

After all 8 tasks are committed:

- [ ] Run full backend test suite: `make test`
- [ ] Run frontend build: `make build`
- [ ] Verify `make setup && make up` works from a clean state
- [ ] Manually check the `/owner/dashboard` page loads without license errors
- [ ] Manually check the `/setup` wizard works without license step
- [ ] Remind user to rotate OpenAI API key at https://platform.openai.com/account/api-keys
