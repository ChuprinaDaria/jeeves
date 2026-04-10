# AI Providers admin + PlatformDefaults refactor — Design

**Date:** 2026-04-10
**Status:** Draft (pending user approval)
**Scope:** Spec B of the "Move Django admin to owner panel" roadmap (after Spec #1 — admin foundation)

## Context

Jeeves is sold on Gumroad as a white-label self-hosted platform. The admin
foundation (Spec #1) gave the purchaser a working `/owner/*` admin panel
with authentication, dashboard, and settings shell, but AI provider
configuration (API keys, local models, model pairs, platform defaults) is
still only editable via Django admin at `/admin/`. That is unacceptable for
a non-technical Gumroad purchaser.

This spec moves all AI provider configuration into the owner UI at
`/owner/ai-providers/*` and `/owner/settings/defaults`, encrypts API keys
at rest using the existing `EncryptedTextField` helper, and removes a
pre-existing architectural dupe in `PlatformDefaults` that carried FK
references to the default LLM/Embedding models in addition to an
`is_default` flag on the models themselves.

### Roadmap position

| # | Subsystem | Status |
|---|---|---|
| 1 | First-run + Admin auth foundation | done |
| **B** | **AI Providers admin + PlatformDefaults refactor** | ← **this spec** |
| A | Icon/emoji unification (Phosphor + Ubuntu) | future |
| C | MCP credentials admin | future |
| D | Grafana analytics | future |

(The lettered order was user-chosen during brainstorming: B first because
without it the platform is non-functional for a purchaser; A second
because it's easier to polish final forms; C and D after.)

## Decisions (locked during brainstorming)

| # | Decision | Choice |
|---|---|---|
| 1 | Page structure | **B** — three separate sub-pages (LLM/Embedding/Pairs) + separate `/owner/settings/defaults` |
| 2 | API key storage | **B** — encrypted at rest via existing `EncryptedTextField` + masked in UI |
| 3 | Key validation policy | **A** — optional `Test connection` button; Save always works |
| 4 | `is_default` enforcement | **B** — mutually exclusive per type via `save()` override; delete promotes next active |
| 5 | Delete safety | **A** — rely on Django `PROTECT` + 409 with explanation + `usage` badge in list |
| 6 | `PlatformDefaults` FK dupe | **B** — drop `default_llm_provider` and `default_embedding_model` FKs, use `is_default` flag as single source of truth |

## Non-goals

Explicitly out of scope for this spec:

- Icon/emoji replacement on existing `/owner/*` pages (Spec A)
- MCP credential management (Spec C)
- Grafana analytics (Spec D)
- Branches / Specializations / Clients CRUD (separate roadmap items)
- Encryption key rotation mechanism
- Audit log for who changed which API key when
- SMTP / email configuration
- Real OpenAI/Anthropic/Cohere calls in test suite (always mocked)
- Frontend unit tests (manual smoke checklist only)
- Data migration of existing plaintext `api_key` values (fresh installations
  are the target; the single known pre-existing installation has empty
  `api_key` columns so no migration is needed)

## Architecture overview

```
┌──────────────────────────────────────────────────────────────┐
│  React /owner/ai-providers/*  +  /owner/settings/defaults    │
└──────────────────────────────────┬───────────────────────────┘
                                   │
                  ┌────────────────┴─────────────────┐
                  │                                  │
                  ▼                                  ▼
   ┌─────────────────────────┐      ┌──────────────────────────────┐
   │ /api/owner/ai-providers │      │ /api/owner/settings/defaults │
   │   /llm/                 │      │                              │
   │   /llm/{id}/            │      └──────────────┬───────────────┘
   │   /llm/{id}/test/       │                     │
   │   /embeddings/          │                     │
   │   /embeddings/{id}/     │                     │
   │   /embeddings/{id}/test/│                     │
   │   /pairs/               │                     │
   │   /pairs/{id}/          │                     │
   └────────────┬────────────┘                     │
                │                                  │
                ▼                                  ▼
       ┌──────────────────┐              ┌──────────────────┐
       │ EmbeddingModel.  │              │ concierge_       │
       │   EmbeddingModel │              │   platform.      │
       │   LLMProvider    │              │   PlatformDefaults│
       │   ModelPair      │              │                  │
       └──────────────────┘              └──────────────────┘
                ▲
                │
                │ encrypts api_key via
                │ EncryptedTextField
                │ (existing in
                │  concierge_platform/fields.py)
```

**Key points:**

- Two groups of new endpoints: `/api/owner/ai-providers/*` (CRUD over three
  models) and `/api/owner/settings/defaults` (singleton get/put).
- Reuse existing `EncryptedTextField` for `api_key` encryption.
- Refactor `PlatformDefaults` to remove the duplicate FK fields; four
  existing readers (`mcp_hub/builtin/rag_search.py`, `agents/models.py`)
  get updated to the new classmethod API.
- Mutually-exclusive `is_default` flag enforced in `save()` overrides on
  `LLMProvider` and `EmbeddingModel`.
- "Test connection" is a separate action endpoint
  (`POST .../{id}/test/`) with provider-specific logic isolated in a new
  `concierge_platform/provider_test_client.py` module. Never changes state.

## Data model changes

No new models. Only changes to existing ones plus two small migrations.

### `EmbeddingModel.EmbeddingModel` — change `api_key` field type

Before:

```python
api_key = models.CharField(
    max_length=255, blank=True, null=True,
    help_text='API key for third-party services (Kimi, etc.)'
)
```

After:

```python
from MASTER.concierge_platform.fields import EncryptedTextField

api_key = EncryptedTextField(
    blank=True, null=True,
    help_text='API key (encrypted at rest)'
)
```

`EncryptedTextField` is a `models.TextField` subclass with Fernet
encryption in `get_prep_value` and decryption in `from_db_value`.
`max_length` goes away because Fernet ciphertext is longer than its
plaintext. Encryption key comes from `settings.FIELD_ENCRYPTION_KEY`
(already set in conftest for tests; must be set via environment variable
in production).

### `EmbeddingModel.LLMProvider` — same field type change

```python
api_key = EncryptedTextField(
    blank=True, null=True,
    help_text='API key (encrypted at rest)'
)
```

### Both models — `save()` override for `is_default` enforcement

Add the same pattern to `EmbeddingModel` and `LLMProvider`:

```python
def save(self, *args, **kwargs):
    # Existing slug auto-generation stays
    if not self.slug:
        self.slug = slugify(self.name)

    # Mutually-exclusive default: if this row is being set as default,
    # unset the flag on all other rows of the same model.
    if self.is_default:
        type(self).objects.exclude(pk=self.pk).filter(is_default=True).update(
            is_default=False,
        )

    super().save(*args, **kwargs)
```

And a `delete()` override that promotes the next active row if the
deleted one was the default:

```python
def delete(self, *args, **kwargs):
    was_default = self.is_default
    result = super().delete(*args, **kwargs)
    if was_default:
        next_active = type(self).objects.filter(is_active=True).order_by('created_at').first()
        if next_active:
            next_active.is_default = True
            next_active.save(update_fields=['is_default'])
    return result
```

### `concierge_platform.PlatformDefaults` — remove FK fields

Remove these two fields entirely:

```python
default_llm_provider = models.ForeignKey('EmbeddingModel.LLMProvider', ...)  # GONE
default_embedding_model = models.ForeignKey('EmbeddingModel.EmbeddingModel', ...)  # GONE
```

Keep all tunable parameters: `default_temperature`, `default_max_tokens`,
`default_similarity_threshold`, `default_max_context_chunks`,
`default_top_k`, `supported_languages`, `default_language`,
`language_detection_method`, `default_greeting`.

Add helper classmethods to replace the previous FK accessors:

```python
@classmethod
def get_default_llm_provider(cls):
    """Return the active LLMProvider flagged as default, or None."""
    from MASTER.EmbeddingModel.models import LLMProvider
    return LLMProvider.objects.filter(is_default=True, is_active=True).first()

@classmethod
def get_default_embedding_model(cls):
    """Return the active EmbeddingModel flagged as default, or None."""
    from MASTER.EmbeddingModel.models import EmbeddingModel
    return EmbeddingModel.objects.filter(is_default=True, is_active=True).first()
```

### Migrations

One migration in `EmbeddingModel`:

```python
# 0009_encrypted_api_keys.py
operations = [
    migrations.AlterField(
        model_name='embeddingmodel',
        name='api_key',
        field=EncryptedTextField(blank=True, null=True, help_text='...'),
    ),
    migrations.AlterField(
        model_name='llmprovider',
        name='api_key',
        field=EncryptedTextField(blank=True, null=True, help_text='...'),
    ),
]
```

One migration in `concierge_platform`:

```python
# 0008_drop_platformdefaults_fk_fields.py
operations = [
    migrations.RemoveField(model_name='platformdefaults', name='default_llm_provider'),
    migrations.RemoveField(model_name='platformdefaults', name='default_embedding_model'),
]
```

**Plaintext migration note.** On fresh installations the `api_key` columns
are empty, so the `AlterField` is a no-op. On any installation that had
plaintext values, the first ORM read would attempt `Fernet.decrypt(...)`
on plaintext and raise `InvalidToken`. We accept this as a breaking change
for this spec: owners re-enter their keys via the new UI after upgrading.
If a future installation has real production keys to preserve, a one-shot
`python manage.py reencrypt_api_keys` command can be added; it's out of
scope here.

### Reader refactor

Four pre-existing readers of the removed FK fields get updated in the
same commit as the `RemoveField` migration:

- `backend/MASTER/mcp_hub/builtin/rag_search.py` (2 usages) —
  `defaults.default_embedding_model` → `PlatformDefaults.get_default_embedding_model()`
- `backend/MASTER/agents/models.py` (2 usages) —
  `PlatformDefaults.get().default_llm_provider` → `PlatformDefaults.get_default_llm_provider()`

These are the only callers found via
`grep -rn "default_llm_provider\|default_embedding_model" backend/MASTER/ --include="*.py" | grep -v migrations | grep -v admin`.

## Backend API surface

All endpoints under `/api/owner/*`, all protected by
`authentication_classes = [JWTAuthentication]` and
`permission_classes = [IsOwner]` (following the pattern established in
Spec #1).

### LLM Providers — full CRUD

```
GET    /api/owner/ai-providers/llm/
POST   /api/owner/ai-providers/llm/
GET    /api/owner/ai-providers/llm/{id}/
PUT    /api/owner/ai-providers/llm/{id}/
DELETE /api/owner/ai-providers/llm/{id}/
POST   /api/owner/ai-providers/llm/{id}/test/     ← test stored key (or override via body)
POST   /api/owner/ai-providers/llm/test-unsaved/  ← test a new key before any save
```

The `test-unsaved` endpoint takes the full provider config in the body
(`provider_type`, `api_key`, `api_endpoint`, `model_name`) and calls
`provider_test_client.test_llm_provider()` without touching the database.
Used by the Create form so owner can validate a key before the first Save.

**List/detail response shape:**

```json
{
  "id": 1,
  "name": "GPT-4o Mini",
  "slug": "gpt-4o-mini",
  "provider_type": "openai",
  "model_name": "gpt-4o-mini",
  "api_endpoint": null,
  "api_key_masked": "sk-...****1234",
  "api_key_set": true,
  "cost_per_1k_input_tokens": "0.000150",
  "cost_per_1k_output_tokens": "0.000600",
  "max_tokens": 4096,
  "temperature": 0.7,
  "is_active": true,
  "is_default": true,
  "description": "",
  "usage": {
    "branches": 0,
    "specializations": 0,
    "clients": 3,
    "agents": 1
  },
  "can_delete": true,
  "created_at": "2026-04-10T..."
}
```

**`usage` counts** are computed via reverse FK relations at serialization
time:

```python
"usage": {
    "branches": obj.branches.count() if hasattr(obj, 'branches') else 0,
    "specializations": obj.specializations.count() if hasattr(obj, 'specializations') else 0,
    "clients": obj.clients.count(),
    "agents": obj.agents.count() if hasattr(obj, 'agents') else 0,
}
```

`can_delete` is `True` when all protected reverse relations
(`ClientEmbedding`, `BranchEmbedding`, `SpecializationEmbedding` for
`EmbeddingModel`; none for `LLMProvider`) have zero rows.

**Create body:**

```json
{
  "name": "GPT-4o",
  "provider_type": "openai",
  "model_name": "gpt-4o",
  "api_key": "sk-proj-realkey...",
  "max_tokens": 8192,
  "temperature": 0.5,
  "cost_per_1k_input_tokens": "0.0025",
  "cost_per_1k_output_tokens": "0.01",
  "is_active": true,
  "is_default": false,
  "description": ""
}
```

**Update body:** same shape; `api_key` is optional:

- Absent or `null` → keep existing encrypted value unchanged
- Non-empty string → re-encrypt with new value
- Empty string `""` → explicit clear (DB stores NULL)

**Test endpoint** `POST /api/owner/ai-providers/llm/{id}/test/`:

```json
// Request — both forms allowed
{}                               // use stored key
{"api_key": "sk-new-to-test"}    // test a new key before save

// Response — always 200, outcome in body
{"outcome": "success", "message": "Connected. 47 models available", "metadata": {"models_count": 47}}
{"outcome": "invalid_key", "message": "Invalid API key (HTTP 401)"}
{"outcome": "network_error", "message": "Connection timeout to api.openai.com"}
```

The test endpoint is **stateless** — it never writes to the DB, never
changes `api_key`, never flips `is_active`. Owner always has to Save
separately.

### Embedding Models — full CRUD

Symmetric to LLM Providers, with embedding-specific fields (`provider`,
`model_name`, `dimensions`, `api_endpoint`, `is_local`, `server_type`,
`api_key`, `cost_per_1k_tokens`, `is_active`, `is_default`,
`external_guid`).

```
GET    /api/owner/ai-providers/embeddings/
POST   /api/owner/ai-providers/embeddings/
GET    /api/owner/ai-providers/embeddings/{id}/
PUT    /api/owner/ai-providers/embeddings/{id}/
DELETE /api/owner/ai-providers/embeddings/{id}/
POST   /api/owner/ai-providers/embeddings/{id}/test/     ← test stored key
POST   /api/owner/ai-providers/embeddings/test-unsaved/  ← test before first save
```

**Test endpoint** for embeddings sends a real `POST /embeddings` call
with the text `"hello"` and verifies the returned vector has the expected
dimensions. Dimension mismatch is a warning (`success` with a warning
message), not a failure — because `pgvector` can still handle it via
truncation/padding the codebase already does.

**Validation added:** `dimensions > 2000` returns `400` with a helpful
message about pgvector's HNSW limit. `dimensions = 0` returns `400`.

### Model Pairs — simple CRUD

```
GET    /api/owner/ai-providers/pairs/
POST   /api/owner/ai-providers/pairs/
GET    /api/owner/ai-providers/pairs/{id}/
PUT    /api/owner/ai-providers/pairs/{id}/
DELETE /api/owner/ai-providers/pairs/{id}/
```

No `api_key`, no `test` endpoint. Write payload takes `llm_provider_id`
and `embedding_model_id`; read returns nested objects for convenience:

```json
{
  "id": 1,
  "name": "Production pair",
  "llm_provider": {"id": 1, "name": "GPT-4o Mini", "is_default": true},
  "embedding_model": {"id": 2, "name": "text-embedding-3-small", "is_default": true},
  "is_active": true,
  "created_at": "..."
}
```

### Platform Defaults — singleton

```
GET /api/owner/settings/defaults/
PUT /api/owner/settings/defaults/
```

**Response:**

```json
{
  "default_temperature": 0.7,
  "default_max_tokens": 4096,
  "default_similarity_threshold": 0.7,
  "default_max_context_chunks": 5,
  "default_top_k": 10,
  "supported_languages": ["en", "uk", "de"],
  "default_language": "en",
  "language_detection_method": "llm",
  "default_greeting": "Hello! How can I help you today?",
  "default_llm": {
    "id": 1,
    "name": "GPT-4o Mini",
    "is_default": true
  },
  "default_embedding": {
    "id": 2,
    "name": "text-embedding-3-small",
    "is_default": true
  }
}
```

`default_llm` and `default_embedding` are **read-only** derived fields
computed from `is_default=True` on the respective models; they are there
for the UI to display a card and link to the model's edit page. PUT
ignores any values supplied for these fields.

**PUT body:**

```json
{
  "default_temperature": 0.5,
  "default_max_tokens": 8192,
  "default_similarity_threshold": 0.75,
  "default_max_context_chunks": 6,
  "default_top_k": 8,
  "supported_languages": ["en", "uk", "de", "pl"],
  "default_language": "en",
  "language_detection_method": "llm",
  "default_greeting": "Hello."
}
```

**Validators:**

- `default_temperature` in `[0.0, 2.0]`
- `default_max_tokens` ≥ 1
- `default_similarity_threshold` in `[0.0, 1.0]`
- `default_max_context_chunks` ≥ 1
- `default_top_k` ≥ 1
- `default_language` must be in `supported_languages`
- `language_detection_method` in `{"llm", "library", "none"}`

### Provider test client module

New file `backend/MASTER/concierge_platform/provider_test_client.py`:

```python
from dataclasses import dataclass, field
from typing import Literal

Outcome = Literal["success", "invalid_key", "network_error"]


@dataclass
class TestResult:
    outcome: Outcome
    message: str = ""
    metadata: dict = field(default_factory=dict)


def test_llm_provider(
    provider_type: str,
    api_key: str,
    api_endpoint: str | None = None,
    model_name: str | None = None,
) -> TestResult:
    """Dispatches to provider-specific test logic. Never raises."""
    ...


def test_embedding_model(
    provider: str,
    api_key: str,
    model_name: str,
    dimensions: int,
    api_endpoint: str | None = None,
) -> TestResult:
    """Dispatches to provider-specific test logic. Never raises."""
    ...
```

Internally, each function dispatches on provider type:

| LLM `provider_type` | Test call |
|---|---|
| `openai` | `GET https://api.openai.com/v1/models` with `Authorization: Bearer <key>` |
| `anthropic` | `GET https://api.anthropic.com/v1/models` with `x-api-key: <key>` |
| `cohere` | `GET https://api.cohere.ai/v1/models` with `Authorization: Bearer <key>` |
| `kimi` | `GET https://api.moonshot.cn/v1/models` with `Authorization: Bearer <key>` |
| `ollama_main` / `ollama_light` / `custom` | `GET <api_endpoint>/api/tags` (no auth needed for local Ollama) |

| Embedding `provider` | Test call |
|---|---|
| `openai` | `POST https://api.openai.com/v1/embeddings` with `{"input":"hello","model":<model_name>}` |
| `anthropic` | not supported yet — returns `network_error` with `"Anthropic does not expose an embedding API test endpoint yet"` |
| `cohere` | `POST https://api.cohere.ai/v1/embed` with `{"texts":["hello"],"model":<model_name>}` |
| `huggingface` | `POST <api_endpoint>/embed` or `POST https://api-inference.huggingface.co/pipeline/feature-extraction/<model_name>` |

All HTTP calls use `requests.post`/`requests.get` with 10-second timeout
and try/except wrapping. Any exception maps to `network_error`. HTTP
`401`/`403` maps to `invalid_key`. HTTP `5xx` maps to `network_error`.
Unknown provider type maps to `network_error` with message
`"Unsupported provider for test"` — owner can still Save without testing.

### DRF serializers

Three serializers live in
`backend/MASTER/EmbeddingModel/serializers.py` (new file):

- `LLMProviderSerializer` — `ModelSerializer` with read-only
  `api_key_masked`, `api_key_set`, `usage`, `can_delete` fields; write-only
  handling of `api_key` with "absent means unchanged" semantics
- `EmbeddingModelSerializer` — same pattern
- `ModelPairSerializer` — nested read, ID-based write

And one in `backend/MASTER/concierge_platform/serializers.py` (extend
existing file):

- `PlatformDefaultsSerializer` — `ModelSerializer` on the tunable fields +
  two `SerializerMethodField` for `default_llm` and `default_embedding`
  (read-only derived cards)

### DRF views

Three `ModelViewSet` classes in
`backend/MASTER/EmbeddingModel/views.py` (extend existing file):

- `LLMProviderViewSet` — `ModelViewSet` with `@action(detail=True, methods=['post'])` for `test`
- `EmbeddingModelViewSet` — same pattern
- `ModelPairViewSet` — plain `ModelViewSet`

One `APIView` in
`backend/MASTER/concierge_platform/views_owner.py` (extend existing):

- `PlatformDefaultsView` — `get()` and `put()` on the singleton

### URL wiring

Extend `backend/MASTER/EmbeddingModel/urls.py`:

```python
from rest_framework.routers import DefaultRouter

from MASTER.EmbeddingModel import views

router = DefaultRouter()
router.register(r'owner/ai-providers/llm', views.LLMProviderViewSet, basename='llm-provider')
router.register(r'owner/ai-providers/embeddings', views.EmbeddingModelViewSet, basename='embedding-model')
router.register(r'owner/ai-providers/pairs', views.ModelPairViewSet, basename='model-pair')

urlpatterns = router.urls + [
    # existing routes
]
```

Extend `backend/MASTER/concierge_platform/urls.py`:

```python
urlpatterns += [
    path('owner/settings/defaults/', views_owner.PlatformDefaultsView.as_view(), name='owner-settings-defaults'),
]
```

## Frontend routing & components

### New routes in `App.jsx`

Add inside the existing `/owner/*` tree (all under `<BootstrapGate>` +
`<OwnerLayout>`):

```jsx
<Route path="ai-providers" element={<Navigate to="llm" replace />} />
<Route path="ai-providers/llm" element={<LLMProvidersPage />} />
<Route path="ai-providers/llm/new" element={<LLMProviderEditPage />} />
<Route path="ai-providers/llm/:id" element={<LLMProviderEditPage />} />
<Route path="ai-providers/embeddings" element={<EmbeddingModelsPage />} />
<Route path="ai-providers/embeddings/new" element={<EmbeddingModelEditPage />} />
<Route path="ai-providers/embeddings/:id" element={<EmbeddingModelEditPage />} />
<Route path="ai-providers/pairs" element={<ModelPairsPage />} />
<Route path="ai-providers/pairs/new" element={<ModelPairEditPage />} />
<Route path="ai-providers/pairs/:id" element={<ModelPairEditPage />} />
<Route path="settings/defaults" element={<PlatformDefaultsPage />} />
```

The current `<StubPage title="AI Providers" />` route is removed.

### OwnerSidebar update

Replace the single `AI Providers` stub link with an expandable section:

```jsx
{
  label: 'AI Providers',
  children: [
    { to: '/owner/ai-providers/llm', label: 'LLM Providers' },
    { to: '/owner/ai-providers/embeddings', label: 'Embedding Models' },
    { to: '/owner/ai-providers/pairs', label: 'Model Pairs' },
  ],
},
```

`Settings` stays a single link to `/owner/settings`; the Defaults page is
reached via a link on the existing Settings page (new card added there:
"AI behaviour defaults →").

### New components

| Path | Responsibility |
|---|---|
| `pages/owner/LLMProvidersPage.jsx` | List view: table of LLMProvider rows (name, model, default badge, usage badge, active toggle, Edit, Delete). `+ Add new LLM` button. Empty state. |
| `pages/owner/LLMProviderEditPage.jsx` | Create/edit form. Uses `useParams().id`; `new` vs numeric `id` decides mode. Fields: name, provider_type (dropdown), model_name, api_key (MaskedPasswordInput), api_endpoint, temperature, max_tokens, costs, is_active, is_default, description. Buttons: Save, Test connection, Cancel, Delete (edit only, disabled if `!can_delete`) |
| `pages/owner/EmbeddingModelsPage.jsx` | Symmetric list for Embedding models |
| `pages/owner/EmbeddingModelEditPage.jsx` | Symmetric edit form; extra fields: provider, dimensions, is_local, server_type |
| `pages/owner/ModelPairsPage.jsx` | List of pairs with FK references resolved |
| `pages/owner/ModelPairEditPage.jsx` | Form with two dropdowns (LLM, Embedding) + name |
| `pages/owner/PlatformDefaultsPage.jsx` | Singleton form for tunables + read-only cards for default LLM/Embedding |
| `components/owner/forms/MaskedPasswordInput.jsx` | Reusable input for API keys: placeholder shows `api_key_masked`, input empty means "keep", eye icon toggles visibility of just-typed value, separate "Clear" button |
| `components/owner/forms/UsageBadge.jsx` | Small badge rendering `usage` object: `3 clients · 2 branches` |

Total: **9 new components** (7 pages + 2 reusable form parts).

### API client extension

Extend `frontend/src/api/owner.js`:

```js
// AI Providers — LLM
export const llmProvidersAPI = {
  list: () => api.get('/owner/ai-providers/llm/'),
  detail: (id) => api.get(`/owner/ai-providers/llm/${id}/`),
  create: (data) => api.post('/owner/ai-providers/llm/', data),
  update: (id, data) => api.put(`/owner/ai-providers/llm/${id}/`, data),
  delete: (id) => api.delete(`/owner/ai-providers/llm/${id}/`),
  // Test a stored row (optionally override with a new key in the body)
  test: (id, apiKeyOverride) =>
    api.post(
      `/owner/ai-providers/llm/${id}/test/`,
      apiKeyOverride ? { api_key: apiKeyOverride } : {},
    ),
  // Test a key that hasn't been saved yet (create form flow)
  testUnsaved: (payload) =>
    api.post('/owner/ai-providers/llm/test-unsaved/', payload),
};

// AI Providers — Embedding (same shape)
export const embeddingModelsAPI = {
  list: () => api.get('/owner/ai-providers/embeddings/'),
  detail: (id) => api.get(`/owner/ai-providers/embeddings/${id}/`),
  create: (data) => api.post('/owner/ai-providers/embeddings/', data),
  update: (id, data) => api.put(`/owner/ai-providers/embeddings/${id}/`, data),
  delete: (id) => api.delete(`/owner/ai-providers/embeddings/${id}/`),
  test: (id, apiKeyOverride) =>
    api.post(
      `/owner/ai-providers/embeddings/${id}/test/`,
      apiKeyOverride ? { api_key: apiKeyOverride } : {},
    ),
  testUnsaved: (payload) =>
    api.post('/owner/ai-providers/embeddings/test-unsaved/', payload),
};

// AI Providers — Model Pairs (no test)
export const modelPairsAPI = {
  list: () => api.get('/owner/ai-providers/pairs/'),
  detail: (id) => api.get(`/owner/ai-providers/pairs/${id}/`),
  create: (data) => api.post('/owner/ai-providers/pairs/', data),
  update: (id, data) => api.put(`/owner/ai-providers/pairs/${id}/`, data),
  delete: (id) => api.delete(`/owner/ai-providers/pairs/${id}/`),
};

// Platform Defaults — singleton
export const platformDefaultsAPI = {
  get: () => api.get('/owner/settings/defaults/'),
  update: (data) => api.put('/owner/settings/defaults/', data),
};
```

### What the frontend does not change

- `BootstrapContext`, `BootstrapGate`, `RootRedirect` — unchanged
- `OwnerLayout`, `OwnerLoginPage`, `OwnerDashboardPage`,
  `OwnerSettingsPage` — OwnerSettingsPage adds one link card to
  `/owner/settings/defaults`, nothing else
- Existing stub pages (`Branches`, `Specializations`, `Clients`) —
  unchanged
- `AuthContext` — unchanged
- Legacy `/l/:tag/*`, `/client`, `/login`, legacy `<Layout />` block —
  all untouched

## Data flow sequences

### Owner adds a new LLM Provider (happy path)

1. Click "+ Add new LLM" → navigate to `/owner/ai-providers/llm/new`
2. Fill form: name, provider type, model name, api key, etc.
3. Click "Test connection" (optional)
4. Frontend `POST /api/owner/ai-providers/llm/test-unsaved/` with the full
   form payload (provider_type, api_key, api_endpoint, model_name). This
   endpoint does not touch the DB — it only dispatches to
   `provider_test_client`.
5. Backend calls `provider_test_client.test_llm_provider(...)` → real HTTP → result
6. Response `{outcome: success, message: "47 models"}` → green check in UI
7. Click Save → `POST /api/owner/ai-providers/llm/` with full payload
8. Backend serializer validates → `EncryptedTextField.get_prep_value()`
   encrypts the key → `save()` override unsets `is_default` on others if
   new row is default → row inserted
9. Response `201 {id, api_key_masked: "sk-...****1234", ...}`
10. Frontend navigates back to `/owner/ai-providers/llm` (list)
11. New row visible with default badge, usage `0 clients`, etc.

### Owner edits an existing LLM Provider's API key

Three cases depending on what's in the `api_key` field on Save:

**Case 1 — leave empty, change other field:** Frontend sends PUT without
`api_key` in the payload. Backend serializer's `update()` method detects
absence → does not touch the field. DB row's encrypted value unchanged.

**Case 2 — replace key:** User types new key. Frontend sends PUT with
`api_key: "sk-new-..."`. Serializer detects non-empty value → passes to
model → `EncryptedTextField.get_prep_value()` re-encrypts. DB value
replaced.

**Case 3 — clear key:** User clicks Clear button. Frontend sends PUT with
`api_key: ""`. Serializer detects empty string → passes through → model
`api_key = ""` → `EncryptedTextField.get_prep_value("")` returns
empty/None → DB stores NULL.

### Owner deletes a model with active embeddings (fail path)

1. Click Delete on an Embedding Model that has `BranchEmbedding` rows
2. Frontend modal: "Sure? This model is used by 234 embeddings. Delete anyway?"
3. User confirms → `DELETE /api/owner/ai-providers/embeddings/{id}/`
4. Backend tries `model.delete()` → Django raises `ProtectedError` (because `BranchEmbedding.embedding_model` is `on_delete=PROTECT`)
5. Backend catches `ProtectedError` → `409 {error: "has_protected_references", count: 234, references: "embeddings"}`
6. Frontend shows red toast: "Cannot delete — 234 embeddings reference this. Deactivate instead?" with a button that sets `is_active=False` via PUT

### Owner sets a new default LLM

1. Open edit form for LLM that is not currently default
2. Check "Set as default"
3. Click Save → `PUT /api/owner/ai-providers/llm/{id}/` with `is_default: true`
4. Backend `save()` override: first runs
   `LLMProvider.objects.exclude(pk=self.pk).filter(is_default=True).update(is_default=False)` → all other rows have `is_default=False`
5. Then `super().save()` persists the new row with `is_default=True`
6. Response includes the new row state
7. Frontend refetches list → old default row no longer shows badge, new one does

### Invariants

- `api_key` is write-only at the API layer. No GET endpoint returns plaintext — only `api_key_masked` (last 4 chars) + `api_key_set` boolean.
- `api_key` update semantics:
  - **absent or null** in payload → unchanged
  - **non-empty string** → re-encrypt and replace
  - **empty string `""`** → clear (DB NULL)
- `is_default` exclusivity is enforced in `save()` override on both `LLMProvider` and `EmbeddingModel`, independently — setting one type as default does not affect the other.
- `delete()` of a default row promotes the next active row (by `created_at` ASC) to default.
- Test endpoint is **stateless**. It never modifies the DB or the model. Owner must Save separately.
- Delete safety relies on existing Django `on_delete` constraints. `PROTECT`-ed deletes return 409; `SET_NULL`-ed deletes succeed and affected clients fall back to `get_default_embedding_model()`.

## Error handling

### Validation errors

| Case | Backend | Frontend |
|---|---|---|
| Required field empty | DRF `400 {field: ["This field is required."]}` | inline error under field |
| Slug collision | `400 {name: ["A model with this name exists."]}` | inline error under name |
| Cost / temperature out of range | DRF validator → `400` | inline error |
| `api_key` empty on create | Allowed (local Ollama models can skip it) | no error |
| `dimensions > 1536` on EmbeddingModel | `400 {dimensions: ["pgvector HNSW limit is 2000"]}` | inline error + docs link |
| `provider_type` not in allowed choices | DRF choice validator → `400` | dropdown prevents it; backend catches direct POSTs |

### Test connection outcomes

| Case | `TestResult` | Frontend UX |
|---|---|---|
| Provider returns `200` with expected body | `success`, `metadata.models_count=47` | green check + message |
| Provider returns `401`/`403` | `invalid_key`, `message="Invalid API key"` | red X + specific message |
| HTTP timeout, DNS fail, connection refused, 5xx | `network_error`, message includes cause | yellow warning + "Could not reach provider" |
| Unknown provider type | `network_error`, `"Unsupported provider for test"` | yellow warning; Save still available |
| Unexpected exception | caught in view → `500` | red toast "Test failed unexpectedly" + log |

Test endpoint **never modifies state**. Test → fail → fix → Test → success → Save is the flow. Nothing is persisted until Save.

### Save failures

| Case | Backend | Frontend |
|---|---|---|
| 401 (JWT expired) | DRF auth → `401` | axios interceptor refreshes → retries → if still 401, redirect `/owner/login` |
| 403 (non-owner role) | `IsOwner` → `403` | toast "Owner role required" + logout |
| 409 (slug collision on race) | Django `IntegrityError` caught → `409` | toast "Name conflict, please pick another" |
| 500 (encryption failed) | Fernet exception → `500` | toast "Server error, check logs" |

### Delete failures

| Case | Backend | Frontend |
|---|---|---|
| `ProtectedError` (embeddings reference model) | `409 {error: "has_protected_references", count, references}` | red toast + "Deactivate instead?" button |
| Delete the only default model with no other active models | `409 {error: "last_default"}` | "Set another model as default first" |
| Race — model already gone | `404` | toast "Model not found, refreshing" + auto refetch |

### PlatformDefaults edge cases

| Case | Behaviour |
|---|---|
| `default_temperature=10.0` | `400`, allowed range 0.0–2.0 |
| `default_max_tokens=0` | `400`, min=1 |
| `supported_languages=[]` | allowed, UI warns |
| `default_language` not in `supported_languages` | `400 {default_language: ["Must be in supported_languages"]}` |
| Concurrent PUTs | last write wins; singleton, owner is one, no optimistic locking |

### Migration edge cases

| Case | Behaviour |
|---|---|
| Existing DB has plaintext `api_key` | First ORM read throws `InvalidToken`. We accept this — owner re-enters keys via the new UI after upgrade. Not a blocker for fresh installations. |
| `concierge_platform.0008` runs on DB where FK fields are already NULL | `RemoveField` is a no-op for NULL values; runs cleanly. |
| `EmbeddingModel.0009` runs on DB where `api_key` is NULL | `AlterField` on nullable column, no data conversion, runs instantly. |
| Refactored `agents/models.py` and `mcp_hub/builtin/rag_search.py` import `default_llm_provider` | Both files are updated to use `PlatformDefaults.get_default_llm_provider()` classmethod in the same commit as the `RemoveField` migration. |

### What we don't try to handle

- Concurrent owner edits (single purchaser per installation)
- Provider API rate limits during Test (test is a single call)
- Encryption key rotation (out of scope)
- Audit log of API key changes (owner is one, low value for now)

## Testing strategy

### Backend — Django tests

**Encryption field tests** (`MASTER/concierge_platform/tests/test_encrypted_field.py`):
ensure it covers `EncryptedTextField` (not just `EncryptedJSONField`); if not,
add parallel test cases.

**Model tests** (new or extended `MASTER/EmbeddingModel/tests/test_models.py`):

| Test | Setup | Assert |
|---|---|---|
| `test_llm_api_key_encrypted_at_rest` | Save LLMProvider with `api_key="sk-test"` | raw DB read via cursor shows ciphertext, not plaintext |
| `test_llm_api_key_decrypted_on_read` | save → reload via ORM | `instance.api_key == "sk-test"` |
| `test_embedding_api_key_encrypted_at_rest` | same for EmbeddingModel | same |
| `test_setting_default_unsets_others` | create 2 LLMs with `is_default=True` via separate saves | only one has `is_default=True` after second save |
| `test_setting_default_unsets_only_same_type` | LLM `is_default=True` + Embedding `is_default=True` | both keep their flags (different tables) |
| `test_delete_default_promotes_next_active` | 3 active LLMs, delete the default one | next by `created_at` ASC gets `is_default=True` |
| `test_delete_default_no_other_active_leaves_no_default` | one active default + one inactive, delete active | inactive not promoted, no default remains |
| `test_save_clears_api_key_via_empty_string` | LLM with `api_key="sk-old"`, save with `api_key=""` | DB stores NULL |

**PlatformDefaults refactor tests** (extend `concierge_platform/tests/test_models.py`):

| Test | Assert |
|---|---|
| `test_get_default_llm_returns_active_default` | create 2 LLMs, one active+default, one inactive → classmethod returns the first |
| `test_get_default_llm_returns_none_when_no_default` | no models → None |
| `test_get_default_llm_skips_inactive` | `is_default=True is_active=False` → None |
| `test_get_default_embedding_*` | symmetric for embeddings |
| `test_default_temperature_validator` | save with `default_temperature=10.0` → `ValidationError` |
| `test_default_language_must_be_in_supported` | save with `default_language='zz', supported=['en','uk']` → `ValidationError` |

**Provider test client tests** (new `MASTER/concierge_platform/tests/test_provider_test_client.py`):

Mock `requests.get`/`requests.post` inside the module. One parametrised
test per provider type:

| Test | Mock | Expect |
|---|---|---|
| `test_openai_success` | `GET /models` → 200 with 47 models | `success`, `metadata.models_count=47` |
| `test_openai_invalid_key` | 401 | `invalid_key` |
| `test_openai_timeout` | `requests.Timeout` | `network_error`, message contains "timeout" |
| `test_anthropic_success` | 200 | `success` |
| `test_anthropic_invalid_key` | 401 | `invalid_key` |
| `test_cohere_success` | 200 | `success` |
| `test_cohere_invalid_key` | 401 | `invalid_key` |
| `test_kimi_success` | 200 | `success` |
| `test_ollama_success` | `GET /api/tags` → 200 | `success` |
| `test_ollama_connection_refused` | `requests.ConnectionError` | `network_error` |
| `test_unsupported_provider` | `provider_type='custom_xyz'` — no mock called | `network_error`, `"Unsupported provider for test"` |
| `test_embedding_openai_success` | `POST /embeddings` returns 1536-dim vector | `success` |
| `test_embedding_dimension_mismatch` | returns vector of different size | `success` with warning in message (not failure) |

**API integration tests** (new `MASTER/concierge_platform/tests/test_ai_providers_api.py` or split per model):

LLM endpoints (~17 tests) — all the scenarios listed in section 5.2, 5.3, 5.4.

Embedding endpoints — symmetric (~12 tests), plus `dimensions` validator.

Model Pair endpoints — simpler (~6 tests), no test action.

**PlatformDefaults endpoints** (new `test_platform_defaults_api.py` — ~7 tests):

| Test | Assert |
|---|---|
| `test_get_requires_owner` | 401/403 without auth |
| `test_get_returns_singleton_with_derived_defaults` | 2 LLMs, one default → `response.default_llm = {...}` |
| `test_get_returns_null_default_llm_when_none` | no LLMs → `default_llm: null` |
| `test_put_updates_tunables` | PUT `temperature=0.5` → DB updated |
| `test_put_ignores_default_llm_field` | PUT with `default_llm: {id:99}` → ignored (read-only) |
| `test_put_validates_temperature_range` | PUT `temperature=10` → 400 |
| `test_put_validates_language_in_supported` | PUT `default_language='zz'` → 400 |

Total: **~60 new backend tests**.

### Frontend — manual smoke checklist

No E2E framework is set up in this spec. Before merge, run through
this checklist on a fresh `docker compose up`:

- [ ] Sidebar shows "AI Providers ▾" expandable with 3 sub-links
- [ ] `/owner/ai-providers/llm` shows empty state with "+ Add new LLM"
- [ ] Click "+ Add new LLM" → form with all fields
- [ ] Provider type dropdown has all 7 options
- [ ] Test with empty `api_key` → backend returns `invalid_key`, UI shows error
- [ ] Test with a real OpenAI test key → green check
- [ ] Save → redirect to list → row visible
- [ ] Edit existing row → form pre-filled; `api_key` input shows `sk-...****1234` placeholder
- [ ] Edit → change temperature only → Save without touching `api_key` → reload → `api_key` still the same
- [ ] Edit → paste new `api_key` → Save → reload → `api_key` updated (masked of new value)
- [ ] Set another LLM as default → previous default row loses the badge
- [ ] Delete an LLM without references → 204, row gone
- [ ] Delete an Embedding with protected references → 409 toast with "Deactivate" button
- [ ] `/owner/settings/defaults` → form with all tunables
- [ ] PUT defaults with invalid temperature → inline error
- [ ] PUT defaults happy path → success toast
- [ ] Refactor smoke: `/api/owner/dashboard/stats` still returns
      `config_health.llm_providers_configured: true` when there is at least one active LLM
- [ ] Refactor smoke: chat with agent still works (default LLM now sourced via
      `get_default_llm_provider()`)
- [ ] Old `/l/:tag/dashboard` etc routes still work — no regression

### Refactor regression check

Run this grep in the repo and confirm zero hits outside migrations:

```
grep -rn "default_llm_provider\|default_embedding_model" backend/MASTER/ --include="*.py" \
  | grep -v migrations | grep -v admin
```

Every hit must be replaced with
`PlatformDefaults.get_default_llm_provider()` or
`PlatformDefaults.get_default_embedding_model()` in the same commit
that runs the `RemoveField` migration.

### What we don't test

- Real outbound calls to OpenAI/Anthropic/Cohere in tests (always mocked)
- Encryption security penetration (Fernet is standard)
- Frontend unit tests (no framework)
- Migration data integrity (no existing production data with api_keys)

## Acceptance criteria

This spec is complete when all of the following hold:

1. CRUD works end-to-end for `LLMProvider`, `EmbeddingModel`, `ModelPair`
   via `/owner/ai-providers/{llm,embeddings,pairs}`. Lists show usage
   badges. Empty state with "+ Add new" is visible on a fresh install.

2. API keys are encrypted at rest. Raw DB read via `psql` on
   `EmbeddingModel_llmprovider.api_key` shows Fernet ciphertext, not
   plaintext. ORM read returns the plaintext. Tests
   `test_llm_api_key_encrypted_at_rest` and
   `test_llm_api_key_decrypted_on_read` pass.

3. API keys are never returned in responses. No GET endpoint exposes
   the plaintext `api_key`; only `api_key_masked` (last 4 chars) and
   `api_key_set` boolean. `test_detail_masks_api_key` passes.

4. PUT without `api_key` in the payload preserves the stored value.
   `test_update_without_api_key_keeps_existing` passes.

5. Test connection works for the 7 LLM provider types and 4 embedding
   provider types. Each has a mocked unit test covering success,
   invalid_key, network_error. Owner can click "Test" before Save.

6. `is_default` is mutually exclusive per type. Setting it on one row
   automatically clears it on all others of the same model. Deleting a
   default row promotes the next active row by `created_at` ASC.
   Backing tests pass.

7. `PlatformDefaults` FK fields are removed. Existing readers in
   `mcp_hub/builtin/rag_search.py` and `agents/models.py` use the new
   `get_default_llm_provider()` / `get_default_embedding_model()`
   classmethods. Existing agent chat still works with no regression.

8. `/owner/settings/defaults` page works. Owner can set
   `default_temperature`, `default_max_tokens`,
   `default_similarity_threshold`, `default_top_k`,
   `default_max_context_chunks`, `supported_languages`,
   `default_language`, `language_detection_method`, `default_greeting`.
   Validation rejects out-of-range values inline.

9. Read-only `default_llm` / `default_embedding` cards show on the
   Defaults page with links to the edit pages of the currently-default
   models.

10. Delete with protected references returns `409` with count and
    reference type. UI shows a red toast with a "Deactivate instead"
    button that sets `is_active=False` via PUT.

11. OwnerSidebar shows AI Providers as an expandable section with three
    sub-links. Active route is highlighted. Settings page has a new
    card linking to `/owner/settings/defaults`.

12. Existing endpoints are not broken. Bootstrap, setup wizard,
    dashboard stats, license reverify — all continue to work. All 51
    existing tests in `concierge_platform/tests/` remain green.

13. ~60 new backend tests pass (model + provider test client + 4 API
    groups).

14. Frontend manual smoke checklist passes (17 items).

15. `npx vite build` succeeds with no errors related to new files.

16. `/api/owner/dashboard/stats` still returns correct
    `llm_providers_configured` / `embedding_models_configured` booleans
    (the underlying `LLMProvider.objects.filter(is_active=True).exists()`
    query is unchanged).

17. Nothing in legacy `/l/:tag/*` or `<Layout />` has been touched.
    Changes are confined to `/owner/*` UI, AI provider models, new
    serializers/viewsets, and the PlatformDefaults refactor across two
    legacy reader files.

## Open questions

None at time of writing. All structural decisions were made during
brainstorming.
