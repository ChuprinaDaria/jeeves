# First-run + Admin auth foundation — Design

**Date:** 2026-04-10
**Status:** Draft (pending user approval)
**Scope:** Spec #1 of 8 in the "White-label admin panel" roadmap

## Context

Jeeves is being productized for sale on Gumroad as a **white-label self-hosted
platform**. Each purchaser downloads the product, runs it on their own VPS,
and uses it to serve their own clients. Gumroad acts only as the sales
channel — the purchaser (OWNER) installs and runs the platform themselves.

Because each installation has exactly one purchaser, **multi-tenancy between
purchasers is achieved by physical isolation** (separate VPS, separate DB).
No per-row tenant scoping is needed inside the application. The existing data
model is already 80% ready — what is missing is the first-run experience that
turns a fresh docker-compose up into a working OWNER-controlled admin panel.

This spec covers the minimum viable foundation: first-run setup wizard,
OWNER authentication, admin panel shell, and Gumroad license-key integration
for setup-time validation. CRUD UI for branches, specializations, clients, AI
providers, payments, analytics, and custom-domain polish are explicitly out
of scope and are covered by subsequent specs in the roadmap.

### Roadmap position

| # | Subsystem | Status |
|---|---|---|
| 1 | **First-run + Admin auth foundation** | ← this spec |
| 2 | AI Providers management (EmbeddingModel + LLMProvider + ModelPair CRUD) | future |
| 3 | Branches + Specializations + Knowledge admin CRUD | future |
| 4 | Clients CRUD + webchat_domain | future |
| 5 | License key validation polish (Gumroad daily check + read-only enforcement) | future |
| 6 | Payment gateway settings | future |
| 7 | Analytics / Grafana embed | future |
| 8 | Custom domains production polish | future |

## Decisions (locked during brainstorming)

| # | Decision | Choice |
|---|---|---|
| 1 | Delivery model | **B** — self-host with Gumroad license key |
| 2 | First-run mechanism | **A** — web-based setup wizard at `/setup` |
| 3 | Wizard length | **A** — 2 steps (create OWNER, enter license key) |
| 4 | License validation failure behavior | **B** — soft grace period (7 days) on network/5xx failures, hard fail on explicit invalid |
| 5 | Admin panel URL | **B** — `/owner/*` (Django admin stays at `/admin/`) |
| 6 | Dashboard content | **B** — medium: 4 counters + config health checklist |
| 7 | License state storage | **B** — new `PlatformLicense` singleton in existing `concierge_platform` app |
| 8 | Frontend setup detection | **A** — explicit `GET /api/platform/bootstrap` endpoint |

## Non-goals

The following are explicitly **not** part of this spec:

- CRUD UI for Branches, Specializations, Clients, AI Providers, Documents
- Payment gateway configuration (Stripe, PayPal, etc.)
- Custom-domain management UI (the backend middleware already exists)
- Grafana embed / analytics dashboard
- Celery beat task for daily license re-verification (deferred to spec #5)
- Hard enforcement of read-only mode on write endpoints (deferred to spec #5;
  at this point there are no write endpoints from the owner panel to enforce
  against, except the license re-verify endpoint which must stay writable)
- SMTP configuration wizard (belongs in a later Settings spec)
- Branding / theming / locale configuration
- First-LLM-provider in the wizard (kept out by decision — banner on
  dashboard guides the purchaser to `/owner/ai-providers` instead)
- New frontend E2E test framework setup (manual smoke checklist used instead)

## Architecture overview

```
                    ┌────────────────────────────┐
                    │  purchaser opens browser   │
                    │    http://his-domain       │
                    └──────────────┬─────────────┘
                                   │
                                   ▼
                  ┌────────────────────────────────┐
                  │ React app boots                │
                  │ calls GET /api/platform/       │
                  │      bootstrap                 │
                  └────────────────┬───────────────┘
                                   │
                   {setup_required, license_status}
                                   │
              ┌────────────────────┴────────────────────┐
              │                                         │
    setup_required=true                      setup_required=false
              │                                         │
              ▼                                         ▼
      ┌──────────────┐                          ┌────────────────┐
      │ /setup       │                          │ /owner/login   │
      │ wizard       │                          │ (if no session)│
      │ 2 steps      │                          └────────┬───────┘
      │ 1. create    │                                   │
      │    OWNER     │                          JWT access/refresh
      │ 2. license   │                                   │
      │    key       │                                   ▼
      └──────┬───────┘                          ┌────────────────┐
             │                                  │ /owner/        │
             │                                  │   dashboard    │
             │                                  │   branches*    │
             │                                  │   specs*       │
             │ redirect                         │   clients*     │
             └─────────────────────────────────▶│   ai-providers*│
                                                │   settings     │
                                                │ (*stubs in #1) │
                                                └────────┬───────┘
                                                         │
                                                         │ banner if
                                                         │ license grace
                                                         ▼
                                                ┌────────────────┐
                                                │ license status │
                                                │ banner (grace  │
                                                │ or expired)    │
                                                └────────────────┘
```

**Key points:**

- No new Django app — extend the existing `MASTER/concierge_platform/` app.
- One new model: `PlatformLicense` (singleton).
- One new public bootstrap endpoint, three new setup endpoints, two new
  owner-authenticated endpoints.
- One new React route tree: `/setup` + `/owner/*`.
- Reuse existing `<Layout />` Concierge-style chrome (bg-cream, sidebar,
  header, JWT guard).
- Reuse existing JWT auth (`djangorestframework_simplejwt`).
- No Celery work in this spec. Validation at setup time is a synchronous
  Gumroad call from the Django view.

## Data model

A single new model lives in `MASTER/concierge_platform/models.py`. Nothing
else changes. No migrations for existing models.

```python
class PlatformLicense(models.Model):
    """Singleton. Holds Gumroad license key + validation state."""

    class LicenseStatus(models.TextChoices):
        MISSING = 'missing', 'Missing'      # setup not complete
        VALID   = 'valid',   'Valid'        # successfully verified via Gumroad
        GRACE   = 'grace',   'Grace'        # verification failed, still in grace period
        EXPIRED = 'expired', 'Expired'      # grace period exhausted → read-only

    license_key = models.CharField(max_length=100, blank=True)
    status = models.CharField(
        max_length=10,
        choices=LicenseStatus.choices,
        default=LicenseStatus.MISSING,
    )

    # First-run setup
    setup_completed_at = models.DateTimeField(null=True, blank=True)

    # Validation lifecycle
    last_verified_at = models.DateTimeField(null=True, blank=True)
    last_attempt_at  = models.DateTimeField(null=True, blank=True)
    last_error       = models.TextField(blank=True)

    # Gumroad metadata (populated on successful verification)
    gumroad_product_id     = models.CharField(max_length=100, blank=True)
    gumroad_purchase_email = models.EmailField(blank=True)
    gumroad_uses           = models.IntegerField(default=0)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Platform License'
        verbose_name_plural = 'Platform License'

    def save(self, *args, **kwargs):
        self.pk = 1  # singleton
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

    @property
    def is_in_grace_period(self) -> bool:
        if self.status != self.LicenseStatus.GRACE:
            return False
        if not self.last_verified_at:
            # Never successfully verified — grace window counts from
            # last_attempt_at instead
            if not self.last_attempt_at:
                return False
            anchor = self.last_attempt_at
        else:
            anchor = self.last_verified_at
        from django.utils import timezone
        from datetime import timedelta
        return (timezone.now() - anchor) < timedelta(days=self.grace_period_days)
```

**Field rationale:**

- `license_key` — stored plaintext. This is a self-hosted server owned by the
  purchaser; if an attacker has DB access, the key is the smallest concern.
- `status` — the canonical state the frontend reads.
- `setup_completed_at` — distinct from license status so we can recover from
  an aborted wizard (owner created, license not entered) without re-running
  Step 1.
- `last_verified_at` — anchor point for grace period when the license was
  previously valid.
- `last_attempt_at` — updated on every verification attempt (success or
  fail), used for "Verified X hours ago" in the UI.
- `last_error` — last error text from Gumroad or network layer, for debug
  display in Settings.
- `gumroad_*` — audit trail of what Gumroad returned on success; enables a
  future "your purchase email" display in Settings.

**State machine:**

```
missing ──(wizard finishes with valid key)────▶ valid
missing ──(wizard finishes, Gumroad unreach.)──▶ grace
valid   ──(daily check: Gumroad returns fail)──▶ grace
grace   ──(daily check succeeds again)────────▶ valid
grace   ──(7 days pass without success)───────▶ expired
expired ──(manual re-entry of valid key)──────▶ valid
```

Note: the `missing → grace` transition is used by the wizard when the initial
verification cannot reach Gumroad but the user provided a key. The daily
re-verify job (spec #5) handles `valid → grace → valid/expired` transitions.

**No changes to existing models.** The single-admin model uses the existing
`User.role='owner'` discriminator; `Branch`, `Specialization`, and `Client`
remain as-is.

## Backend API surface

All endpoints live under `/api/platform/*`, `/api/setup/*`, and
`/api/owner/*`. Reuse the existing JWT authentication.

### Public endpoints (no authentication)

**`GET /api/platform/bootstrap`**

Called by the React app at startup to decide routing. Public because it must
work before login.

Response body:

```json
{
  "setup_required": true,
  "license_status": "missing",
  "license_last_verified_at": null,
  "grace_days_remaining": null
}
```

Or after setup:

```json
{
  "setup_required": false,
  "license_status": "valid",
  "license_last_verified_at": "2026-04-10T12:34:56Z",
  "grace_days_remaining": null
}
```

`grace_days_remaining` is `null` unless `license_status='grace'`, in which
case it is an integer count of whole days remaining until expiry, computed
as `(anchor + 7 days) - now`, where `anchor` is `last_verified_at` if set,
otherwise `last_attempt_at`. A `PlatformLicense.grace_days_remaining`
helper property on the model is the single source of truth for this
computation and is used by both the bootstrap endpoint and the dashboard
stats endpoint.

**`POST /api/setup/owner`**

Creates the first `User` with `role='owner'`, `is_superuser=True`, and
`is_staff=True`. The superuser flags give the owner fallback access to
Django admin at `/admin/` for emergency DB inspection. Rejects if an owner
already exists (returns 409). Public because at this point the caller
cannot be authenticated. Request body:

```json
{ "email": "...", "password": "...", "first_name": "...", "last_name": "..." }
```

Returns 201 with a JWT pair (access + refresh) + user info, so the React app
is immediately authenticated for Step 2.

Error responses:

- `409 {error:'owner_exists'}` — owner already created
- `409 {error:'email_taken'}` — User with this email already exists
- `400 {error:'weak_password', message:'...'}` — password < 8 chars
- `400 {error:'invalid_email'}` — malformed email

### Setup endpoints (owner-authenticated)

**`POST /api/setup/license`**

Requires `IsOwner` permission. Accepts a license key, performs a synchronous
call to the Gumroad verify API, and persists the result. Request body:

```json
{ "license_key": "..." }
```

Behavior (delegated to `gumroad_client.verify_license`):

| Gumroad outcome | Action | Response |
|---|---|---|
| `valid` | Save key, `status='valid'`, `last_verified_at=now`, populate metadata | `200 {status:'valid', ...}` |
| `invalid` | **Do not save**, do not change status | `400 {error:'invalid_key', message:'...'}` |
| `network_error` (timeout / 5xx / connection) | Save key, `status='grace'`, `last_error=...`, `last_attempt_at=now`, `last_verified_at=null` | `200 {status:'grace', message:'...'}` |

**`POST /api/setup/complete`**

Requires `IsOwner`. Finalizes the wizard. Checks that `license_key` is
non-empty and `status ∈ {valid, grace}`. On success, sets
`setup_completed_at=now` and returns 204. Otherwise returns
`400 {error:'license_not_ready'}`.

**Idempotent:** if `setup_completed_at` is already set, returns 204 without
modification. This lets the frontend retry safely if the response is lost
in-flight.

### Owner-authenticated endpoints

**`GET /api/owner/dashboard/stats`**

Returns counters and configuration health for the dashboard. Reads existing
models; does not modify anything.

```json
{
  "counters": {
    "branches": 3,
    "specializations": 8,
    "clients": 12,
    "documents": 47
  },
  "config_health": {
    "license_valid": true,
    "llm_providers_configured": false,
    "embedding_models_configured": true,
    "branches_exist": true
  },
  "license": {
    "status": "valid",
    "last_verified_at": "2026-04-10T12:34:56Z",
    "grace_days_remaining": null
  }
}
```

Implementation:

```python
counters = {
    "branches": Branch.objects.count(),
    "specializations": Specialization.objects.count(),
    "clients": Client.objects.count(),
    "documents": BranchDocument.objects.count() + SpecializationDocument.objects.count(),
}
config_health = {
    "license_valid": license.status == LicenseStatus.VALID,
    "llm_providers_configured": LLMProvider.objects.filter(is_active=True).exists(),
    "embedding_models_configured": EmbeddingModel.objects.filter(is_active=True).exists(),
    "branches_exist": Branch.objects.exists(),
}
```

**`POST /api/owner/license/reverify`**

Triggers an immediate call to Gumroad using the currently stored key. Uses
the same `gumroad_client.verify_license` logic. Allowed even when the
license is expired (this is how the owner recovers). Response mirrors
`/api/setup/license` but also returns updated `license.status`.

### Existing endpoints

The existing JWT login (`POST /api/auth/login`), refresh
(`POST /api/auth/refresh`), and client tag-based authentication are not
modified. The owner logs in via the existing login endpoint; the frontend
simply routes them to `/owner/dashboard` if `user.role == 'owner'`.

### Permission class

New in `MASTER/concierge_platform/permissions.py`:

```python
class IsOwner(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == 'owner'
        )
```

Applied to all `/api/setup/license`, `/api/setup/complete`, and
`/api/owner/*` endpoints. `/api/platform/bootstrap` and `/api/setup/owner`
use `AllowAny`.

### Gumroad client module

`MASTER/concierge_platform/gumroad_client.py` — a single isolated module so
all HTTP to Gumroad happens in one place and is trivially mockable in tests.

```python
from dataclasses import dataclass, field
from typing import Literal

GUMROAD_VERIFY_URL = "https://api.gumroad.com/v2/licenses/verify"

@dataclass
class GumroadResult:
    outcome: Literal['valid', 'invalid', 'network_error']
    data: dict = field(default_factory=dict)
    error: str = ""

def verify_license(license_key: str) -> GumroadResult:
    """
    Call Gumroad license verify API. Never raises — always returns a result.
    Reads product_id internally from Django settings.
    """
    ...
```

The product ID is read from a new Django setting `GUMROAD_PRODUCT_ID`,
populated from the `GUMROAD_PRODUCT_ID` environment variable. This is a
build-time constant — the same value across all purchasers, baked into the
shipped product. Django startup must raise `ImproperlyConfigured` if the
variable is missing in non-DEBUG environments, so a broken container fails
loudly instead of silently.

## Frontend routing & components

### Route tree

```jsx
<BrowserRouter>
  <Routes>
    {/* PUBLIC */}
    <Route path="/setup" element={<SetupWizard />} />
    <Route path="/owner/login" element={<OwnerLoginPage />} />

    {/* CLIENT PORTAL — existing, untouched */}
    <Route path="/l" element={<ClientLoginPage />} />
    <Route path="/l/:tag" element={<ClientLayout />}>...</Route>
    <Route path="/client" element={<WebChatPage />} />

    {/* OWNER ADMIN — new */}
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

    {/* Legacy existing <Layout /> routes left untouched */}

    <Route path="/" element={<RootRedirect />} />
    <Route path="*" element={<Navigate to="/" replace />} />
  </Routes>
</BrowserRouter>
```

### New components

**`<BootstrapGate>`** — wraps the `/owner/*` subtree. On mount, calls
`GET /api/platform/bootstrap` once and caches in a React context. Logic:

```
if loading                      → full-screen spinner
if setup_required               → redirect /setup
if not authenticated as owner   → redirect /owner/login
if license.expired              → render children with <ReadOnlyBanner />
if license.grace                → render children with <GraceBanner />
otherwise                       → render children
```

**`<RootRedirect>`** — handles `/` based on bootstrap + JWT presence:

- `setup_required` → `/setup`
- authenticated owner → `/owner/dashboard`
- otherwise → `/owner/login`

**`<SetupWizard>`** — standalone component, does not use `<OwnerLayout />`.
Two steps:

- Step 1 — create OWNER form (email, password, first_name, last_name).
  On submit: `POST /api/setup/owner` → store JWT pair → advance to Step 2.
  Handles `409 owner_exists` by showing "Setup was not completed. Please log
  in to continue" with a mini login form that uses existing
  `/api/auth/login`.
- Step 2 — license key form. On submit: `POST /api/setup/license`.
  - `valid` → show green check, auto-advance
  - `grace` → show yellow warning + "Continue anyway" button
  - `invalid_key` → show red error, stay on Step 2
  After advancing: `POST /api/setup/complete` → redirect `/owner/dashboard`.
- Progress indicator "Step X of 2" at top.
- Back button between steps only (cannot go back from completion).

**`<OwnerLoginPage>`** — email/password form. Uses the existing
`authAPI.login`. On success, verifies `user.role === 'owner'` and routes to
`/owner/dashboard`. Non-owner users see "Access denied: owner role required"
and are logged out.

**`<OwnerLayout>`** — thin wrapper that reuses the existing `<Layout />`
chrome. Decisions about sidebar:

- If the existing `<Sidebar />` component accepts a menu-items prop (or is
  already configurable), reuse it with an owner-specific item list.
- If the existing `<Sidebar />` hardcodes client menu items, create
  `<OwnerSidebar />` as a new component and compose it into `<OwnerLayout />`
  without modifying the legacy `<Layout />`.

The choice is made during implementation after reading `Sidebar.jsx`. The
spec does not mandate one path.

Owner-specific sidebar items:

- Dashboard
- Branches (stub)
- Specializations (stub)
- Clients (stub)
- AI Providers (stub)
- Settings

**`<OwnerDashboardPage>`** — implements the "medium dashboard" design:

- Header "Welcome, {first_name}"
- License card (green valid / yellow grace with days-remaining / red expired)
- Four counter cards: Branches, Specializations, Clients, Documents
- Configuration health checklist card with four items:
  - License active
  - LLM Provider configured (link → `/owner/ai-providers`)
  - Embedding Model configured (link → `/owner/ai-providers`)
  - First Branch created (link → `/owner/branches`)
- No charts, no recent activity

**`<OwnerSettingsPage>`** — minimal for spec #1:

- License section: masked key (`gmrd_****1234`), status chip,
  `last_verified_at`, "Re-verify now" button (→ `POST /api/owner/license/reverify`)
- Account section: email, first/last name (display only), "Change password"
  button (uses existing auth endpoints)

**`<StubPage title>`** — placeholder with title and
"This section is coming soon" text. No skeleton, no fake data.

**`<GraceBanner>` / `<ReadOnlyBanner>`** — top-of-page banners inside the
owner layout:

- Grace (yellow): "License validation failed. We'll retry automatically.
  {days_remaining} days remaining. Re-verify now →"
- Expired (red): "License expired. Platform is in read-only mode. Update your
  license to restore full access →"

### Frontend API module

New file `frontend/src/api/owner.js`:

```js
import axios from './axios';

export const platformAPI = {
  bootstrap: () => axios.get('/api/platform/bootstrap'),
};

export const setupAPI = {
  createOwner: (data) => axios.post('/api/setup/owner', data),
  saveLicense: (license_key) => axios.post('/api/setup/license', { license_key }),
  complete: () => axios.post('/api/setup/complete'),
};

export const ownerAPI = {
  getDashboardStats: () => axios.get('/api/owner/dashboard/stats'),
  reverifyLicense: () => axios.post('/api/owner/license/reverify'),
};
```

### What the frontend does not change

- `AuthContext.jsx` — minimally extended with a `bootstrap` cache and
  `isOwner` getter. The existing client tag flow is untouched.
- Existing routes (`/l/:tag/*`, `/login`, `/client`) — unchanged.
- Existing pages (DashboardPage, TrainingPage, SandboxPage, etc.) —
  unchanged. They belong to the legacy `<Layout />` subtree and are used by
  the client portal.

## Data flow sequences

### First-run (fresh installation)

1. Purchaser opens the domain.
2. React calls `GET /api/platform/bootstrap` → `{setup_required: true, license_status: 'missing'}`.
3. Frontend redirects to `/setup`.
4. Purchaser fills Step 1 → `POST /api/setup/owner` → 201 with JWT pair.
5. Frontend stores JWT, advances to Step 2.
6. Purchaser fills Step 2 → `POST /api/setup/license`.
7. Django calls `gumroad_client.verify_license(...)`. On success, persists
   `PlatformLicense` with `status='valid'`, `last_verified_at=now`.
8. Frontend receives `200 {status:'valid'}` and calls
   `POST /api/setup/complete`.
9. Django sets `setup_completed_at=now`, returns 204.
10. Frontend redirects to `/owner/dashboard`.
11. Dashboard calls `GET /api/owner/dashboard/stats` and renders counters
    (all zero), license card (green), config health (license ✓, everything
    else ✗).

### Repeat login (setup already complete)

1. Owner opens the domain.
2. Bootstrap returns `{setup_required: false, license_status: 'valid'}`.
3. No JWT in localStorage → redirect to `/owner/login`.
4. Owner submits credentials → existing `POST /api/auth/login`.
5. Frontend checks `user.role === 'owner'`, stores JWT, redirects to
   `/owner/dashboard`.
6. Dashboard fetches stats and renders.

### Step 2 fail path — Gumroad explicit invalid

1. `POST /api/setup/license` with a wrong key.
2. Django calls Gumroad, receives `{success: false, message: 'Not found'}`.
3. Django returns `400 {error: 'invalid_key', message: 'Not found'}`
   **without saving the key**.
4. Frontend shows a red error under the license input. User retries.

### Step 2 fail path — Gumroad unreachable (grace)

1. `POST /api/setup/license` with a valid key, Gumroad API is down / timing
   out.
2. Django calls Gumroad → timeout (10 s).
3. Django saves the key with `status='grace'`, `last_error='timeout'`,
   `last_attempt_at=now`, `last_verified_at=null`.
4. Returns `200 {status: 'grace', message: "We couldn't reach Gumroad. Grace
   period: 7 days"}`.
5. Frontend shows a yellow warning and offers "Continue anyway".
6. On click: `POST /api/setup/complete` → Django allows it because
   `status='grace'` is acceptable.
7. Frontend redirects to `/owner/dashboard`.
8. Dashboard shows the grace banner.

### Aborted wizard (owner created, license not entered)

1. Purchaser closed the browser after Step 1.
2. On return, bootstrap still returns `setup_required=true` (because
   `setup_completed_at is null`).
3. Frontend redirects to `/setup`.
4. User starts Step 1 again → `POST /api/setup/owner` returns `409 owner_exists`.
5. Frontend shows a mini login form: "Setup was not completed. Log in to
   continue."
6. User logs in via existing `/api/auth/login`, receives JWT.
7. Frontend skips to Step 2.
8. Continues normally.

### Invariants

- The bootstrap endpoint response is cached on the frontend for the lifetime
  of the tab via React context. Cache is invalidated after `setup_complete`
  and after `reverify`.
- `/setup` is accessible only while `setup_completed_at is null`. After
  completion, navigation to `/setup` redirects to `/owner/dashboard` (or
  `/owner/login` if not authenticated).
- `POST /api/setup/owner` rejects with 409 if any `User` with `role='owner'`
  already exists. Protects against accidental double-registration.
- JWT is issued in Step 1, so Step 2 and `complete` use normal `IsOwner`
  permission — no special "setup mode" auth.

## Error handling

### Setup wizard input errors

| Situation | Response |
|---|---|
| Email already taken | `409 {error:'email_taken'}` → inline red text |
| Password < 8 chars | `400 {error:'weak_password'}` → inline red text |
| Owner already exists | `409 {error:'owner_exists'}` → wizard shows mini login form |
| License key empty | Client-side validation — submit disabled |

### Step 2 — Gumroad

| Situation | Django action | Frontend UX |
|---|---|---|
| Gumroad `{success:true}` | Save, `status='valid'` | Green check, advance |
| Gumroad `{success:false, message}` | **Do not save**, no state change | Red error with Gumroad message |
| HTTP timeout (>10 s) | Save key, `status='grace'`, `last_error='timeout'` | Yellow warning + "Continue anyway" |
| HTTP 5xx from Gumroad | Save key, `status='grace'`, `last_error=<body>` | Yellow warning + "Continue anyway" |
| Connection error / DNS fail | Save key, `status='grace'`, `last_error='network'` | Yellow warning + "Continue anyway" |
| Unexpected exception | Do not save, log exception | Generic "Something went wrong, try again" |

Rationale: an explicit `success:false` from Gumroad is a deliberate fail — we
never treat it as grace. Everything else is infrastructure noise and gets
grace treatment.

### Bootstrap edge cases

| Situation | Response |
|---|---|
| Fresh DB, migrations not run | Django returns a 500. Not our problem — means the container is broken, debug via logs |
| DB exists, no `PlatformLicense` row yet | `get_or_create` returns the default row, `setup_required=true` |
| Owner exists but `setup_completed_at is null` | `setup_required=true`; wizard handles via the aborted-wizard flow |

### Runtime — login and dashboard

| Situation | Handling |
|---|---|
| JWT expired → dashboard returns 401 | Existing axios interceptor calls `/api/auth/refresh` |
| Refresh token expired | Redirect to `/owner/login` |
| Non-owner user tries `/owner/*` | `IsOwner` returns 403. Frontend catches 403, shows "Access denied", logs out |
| License transitions to expired between requests | Next bootstrap refresh returns `status='expired'` → `<ReadOnlyBanner />` |
| `reverify` returns `invalid` | Status stays `expired`, Settings shows "Key was rejected by Gumroad" |

### Read-only mode

For spec #1, read-only mode is UI-only:

- Banner visible on all `/owner/*` pages.
- Dashboard renders normally (read operation).
- Settings remains writable so the owner can enter a new license key.
- License re-verify endpoint is explicitly allowed even when expired.

Hard enforcement of read-only on write endpoints is deferred to spec #5,
because there are no owner CRUD write endpoints in spec #1 to enforce
against (beyond the license reverify which stays writable).

### Out of scope for error handling

- Concurrent setup (two browsers creating owner at once) — race is protected
  by the DB unique constraint on `email` + the `role='owner'` exists check.
- Clock skew between the purchaser's server and Gumroad — we only compare
  `timezone.now()` against our own timestamps.
- License key leaked / stolen — not our problem for self-hosted; Gumroad
  handles blocking, and the next daily re-verify job (spec #5) will see it.

## Testing strategy

### Backend — Django tests

**Unit tests** (`MASTER/concierge_platform/tests/test_license_model.py`):

- `PlatformLicense.get()` creates a singleton with `pk=1`; subsequent calls
  return the same row.
- `is_in_grace_period` returns True when `status='grace'` and
  `last_verified_at` is within 7 days (use `freezegun` or time-mocking).
- `is_in_grace_period` returns False after 7 days.
- `is_in_grace_period` handles the `last_verified_at is null` case by using
  `last_attempt_at` as the anchor.
- `is_setup_complete` reflects `setup_completed_at`.

**Integration tests** (`MASTER/concierge_platform/tests/test_setup_api.py`),
using DRF `APITestCase` with a mock for `gumroad_client.verify_license`:

| Test | Setup | Assert |
|---|---|---|
| `test_bootstrap_empty_db` | empty DB | `setup_required=true`, `license_status='missing'` |
| `test_bootstrap_after_setup` | owner + valid license | `setup_required=false`, `license_status='valid'` |
| `test_create_owner_happy_path` | empty DB | 201, JWT pair, `user.role='owner'` in DB |
| `test_create_owner_rejects_second` | owner exists | 409 `owner_exists` |
| `test_create_owner_rejects_taken_email` | non-owner user with same email | 409 `email_taken` |
| `test_create_owner_weak_password` | — | 400 `weak_password` |
| `test_setup_license_valid` | mock outcome=valid, owner JWT | 200 `status:valid`, row persisted |
| `test_setup_license_invalid_key` | mock outcome=invalid | 400 `invalid_key`, **license not saved** |
| `test_setup_license_network_error` | mock outcome=network_error | 200 `status:grace`, key saved, `last_error` set |
| `test_setup_complete_requires_license` | `status='missing'` | 400 |
| `test_setup_complete_allows_valid` | `status='valid'` | 204, `setup_completed_at` set |
| `test_setup_complete_allows_grace` | `status='grace'` | 204 |
| `test_setup_license_requires_auth` | no JWT | 401/403 |
| `test_setup_complete_requires_auth` | no JWT | 401/403 |

**Permission tests** (`test_permissions.py`):

- `IsOwner` allows `role='owner'`
- `IsOwner` denies `role='admin'`, `manager`, `client`, anonymous

**Dashboard stats tests** (`test_dashboard_api.py`):

- `test_stats_empty` — all counters 0; config health all False except
  license (depends on fixture)
- `test_stats_populated` — create 2 branches, 3 clients, assert counters
- `test_stats_requires_owner` — client role → 403

**Re-verify tests** (`test_reverify_api.py`):

- `test_reverify_success_moves_grace_to_valid` — mock outcome=valid →
  `status='valid'`
- `test_reverify_fail_keeps_expired` — `status='expired'`, mock
  outcome=invalid, assert status unchanged
- `test_reverify_allowed_when_expired` — endpoint is not blocked by
  license-expired check

### Gumroad client — isolated tests

All HTTP is funneled through `MASTER/concierge_platform/gumroad_client.py`.
Mock `requests.post` at that module's import site.

**Unit tests** (`test_gumroad_client.py`):

- `test_valid_response` — mock 200 `{success:true, uses, purchase}` →
  `outcome='valid'`, `data` populated
- `test_invalid_response` — mock 200 `{success:false, message}` →
  `outcome='invalid'`, `error=message`
- `test_timeout` — mock `requests.Timeout` → `outcome='network_error'`,
  `error='timeout'`
- `test_connection_error` — mock `requests.ConnectionError` →
  `outcome='network_error'`
- `test_5xx` — mock 503 → `outcome='network_error'`
- `test_unexpected_status` — mock 400 → `outcome='network_error'`,
  `error` contains status code

### Frontend — manual smoke checklist

No E2E framework is stood up in this spec. Before merge, the implementer
runs through this checklist on a fresh `docker-compose up`:

- [ ] Fresh DB → `/` redirects to `/setup`
- [ ] Step 1: invalid email → inline error
- [ ] Step 1: weak password → inline error
- [ ] Step 1: valid data → advances to Step 2
- [ ] Step 2: invalid key → red error, stays on Step 2
- [ ] Step 2: valid key → green check, advances to dashboard
- [ ] Step 2: disable internet → yellow grace warning + "Continue anyway"
- [ ] After setup → `/setup` redirects to `/owner/dashboard`
- [ ] Abort after Step 1 → reopen → mini login form appears, can continue
- [ ] Logout → `/owner/login`
- [ ] Login with wrong password → inline error
- [ ] Login with existing owner → dashboard
- [ ] Dashboard: all counters zero, three red items in config health (LLM,
      Embedding, Branch)
- [ ] Dashboard: click sidebar "Branches" → stub page
- [ ] Settings: "Re-verify now" works, shows toast
- [ ] Manually set license status=`grace` in DB → reload dashboard → yellow
      banner with days-remaining
- [ ] Manually set license status=`expired` → red banner; sidebar items
      still navigable (read-only is UI-only in this spec)

**Optional stretch:** one Playwright E2E test for the first-run happy path
if the implementer wants to bootstrap Playwright during implementation. Not
mandatory.

### Out of scope for testing

- Real Gumroad API calls in tests — always mocked. Otherwise flaky and
  dependent on an external service.
- Load / performance — meaningless for a bootstrap endpoint serving one
  owner.
- Security penetration — relying on Django + DRF defaults; the payment
  subsystem (spec #6) is where a security review belongs.

## Acceptance criteria

This spec is considered complete when all of the following hold:

1. A fresh `docker compose up` on an empty database surfaces the setup
   wizard, and the wizard can be completed end-to-end with a valid Gumroad
   license key.
2. The same wizard recovers gracefully from Gumroad unreachability (grace
   path) and from explicit invalid-key responses (retry path).
3. The owner can log in, log out, and log back in via `/owner/login`.
4. The `/owner/dashboard` shows live counters and the config-health
   checklist computed from the current DB state.
5. The sidebar links to stub pages for Branches, Specializations, Clients,
   and AI Providers.
6. The Settings page shows masked license, status, last verified timestamp,
   and a working "Re-verify now" button.
7. All backend tests in the test matrix above pass.
8. The frontend manual smoke checklist passes.
9. No existing routes, endpoints, or pages are broken.

## Open questions

None at time of writing. All structural decisions were locked during
brainstorming.
