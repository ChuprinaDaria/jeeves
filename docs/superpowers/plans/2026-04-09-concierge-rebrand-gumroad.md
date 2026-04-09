# Concierge AI Platform — Rebrand & Gumroad Preparation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform internal AI Nexelin project into a sellable Gumroad product called Concierge AI Platform with Jeeves as the default AI assistant.

**Architecture:** Phased cleanup — first remove dead modules (restaurant, matrix, langflow, client_portal), then rename directories, then rebrand all references, then write buyer-facing docs.

**Tech Stack:** Django 5 + DRF, React 18 + Vite + Tailwind, PostgreSQL + pgvector, Redis + Celery, MCP servers

---

## Task 1: Remove restaurant module

**Files:**
- Delete: `p004_ai_nexelin/MASTER/restaurant/` (entire directory)
- Modify: `p004_ai_nexelin/MASTER/settings.py:112` (remove from INSTALLED_APPS)
- Modify: `p004_ai_nexelin/MASTER/urls.py:38,41` (remove restaurant URL patterns)
- Modify: `p004_ai_nexelin/MASTER/rag/vector_search.py` (remove MenuItemEmbedding import)
- Modify: `p004_ai_nexelin/MASTER/clients/views.py` (remove RestaurantTable, RestaurantConversation imports/usage)
- Modify: `p004_ai_nexelin/MASTER/clients/views_meta_whatsapp.py` (remove restaurant imports)
- Modify: `p004_ai_nexelin/MASTER/clients/views_telegram.py` (remove restaurant imports)
- Modify: `p004_ai_nexelin/MASTER/clients/views_whatsapp.py` (remove restaurant imports)
- Modify: `p004_ai_nexelin/MASTER/clients/tasks.py` (remove RestaurantTable import)
- Modify: `p004_ai_nexelin/MASTER/clients/signals.py` (remove RestaurantTable import)

- [ ] **Step 1: Remove restaurant from INSTALLED_APPS**

In `p004_ai_nexelin/MASTER/settings.py`, remove line:
```python
"MASTER.restaurant",
```

- [ ] **Step 2: Remove restaurant URL patterns**

In `p004_ai_nexelin/MASTER/urls.py`, remove these lines:
```python
path('api/restaurant/', include('MASTER.restaurant.urls')),
```
and:
```python
path('restaurant/', include(('MASTER.restaurant.urls', 'restaurant'), namespace='restaurant-public')),
```

- [ ] **Step 3: Clean restaurant imports from clients/views.py**

Open `p004_ai_nexelin/MASTER/clients/views.py` and remove all imports from `MASTER.restaurant.models` (RestaurantTable, RestaurantConversation). Remove any code blocks that use these models — replace with pass or remove the entire view/function if it's restaurant-only.

- [ ] **Step 4: Clean restaurant imports from views_meta_whatsapp.py, views_telegram.py, views_whatsapp.py**

Same approach — remove RestaurantTable/RestaurantConversation imports and usage from:
- `p004_ai_nexelin/MASTER/clients/views_meta_whatsapp.py`
- `p004_ai_nexelin/MASTER/clients/views_telegram.py`
- `p004_ai_nexelin/MASTER/clients/views_whatsapp.py`

- [ ] **Step 5: Clean restaurant imports from tasks.py, signals.py**

Remove RestaurantTable imports and related code from:
- `p004_ai_nexelin/MASTER/clients/tasks.py`
- `p004_ai_nexelin/MASTER/clients/signals.py`

- [ ] **Step 6: Clean MenuItemEmbedding from vector_search.py**

In `p004_ai_nexelin/MASTER/rag/vector_search.py`, remove the MenuItemEmbedding import and any search logic that references it.

- [ ] **Step 7: Delete restaurant directory**

```bash
rm -rf p004_ai_nexelin/MASTER/restaurant/
```

- [ ] **Step 8: Verify Django starts**

```bash
cd p004_ai_nexelin && python manage.py check --deploy 2>&1 | head -30
```

Expected: no import errors related to restaurant.

- [ ] **Step 9: Commit**

```bash
git add -A && git commit -m "remove: restaurant module and all references"
```

---

## Task 2: Remove client_portal

**Files:**
- Delete: `p004_ai_nexelin/MASTER/client_portal/` (entire directory)

- [ ] **Step 1: Delete client_portal directory**

```bash
rm -rf p004_ai_nexelin/MASTER/client_portal/
```

- [ ] **Step 2: Check for any imports of client_portal in Django code**

```bash
grep -r "client_portal" p004_ai_nexelin/ --include="*.py" -l
```

Remove any found references.

- [ ] **Step 3: Commit**

```bash
git add -A && git commit -m "remove: client_portal React app (restaurant admin)"
```

---

## Task 3: Remove Matrix/WhatsApp bridge infrastructure

**Files:**
- Delete: `services/` (entire directory — Go integration-service)
- Delete: `matrix-stack/` (entire directory)
- Delete: `матрікс/` (entire directory)
- Delete: `matrix/` (entire directory)
- Delete: `p004_ai_nexelin/mcp_servers/bridge/` (bridge MCP server)
- Delete: `p004_ai_nexelin/matrix-bridge/` (if exists)
- Modify: `p004_ai_nexelin/MASTER/settings.py` (remove WhatsApp Celery beats, INTEGRATION_SERVICE_URL)
- Modify: `p004_ai_nexelin/MASTER/clients/services/bridge_service.py` (remove or gut matrix references)
- Modify: `p004_ai_nexelin/MASTER/clients/views_meta_whatsapp.py` (remove send_matrix_escalation)
- Modify: `p004_ai_nexelin/MASTER/clients/views_telegram.py` (remove send_matrix_escalation)
- Modify: `p004_ai_nexelin/MASTER/clients/views_whatsapp.py` (remove send_matrix_escalation)
- Modify: `p004_ai_nexelin/MASTER/clients/signals.py` (remove onboard_matrix_manager)
- Modify: `p004_ai_nexelin/docker-compose.yml` (remove mautrix, matrix, integration-service services)

- [ ] **Step 1: Remove WhatsApp bridge Celery beat tasks from settings.py**

In `p004_ai_nexelin/MASTER/settings.py`, remove from CELERY_BEAT_SCHEDULE:
```python
'poll-whatsapp-bridge': {
    ...
},
'check-whatsapp-bridge-status': {
    ...
},
```

Also remove `INTEGRATION_SERVICE_URL` setting.

- [ ] **Step 2: Clean matrix/bridge references from clients/ Python files**

Remove `send_matrix_escalation`, `create_matrix_user`, `onboard_matrix_manager` imports and usage from:
- `p004_ai_nexelin/MASTER/clients/services/bridge_service.py`
- `p004_ai_nexelin/MASTER/clients/views_meta_whatsapp.py`
- `p004_ai_nexelin/MASTER/clients/views_telegram.py`
- `p004_ai_nexelin/MASTER/clients/views_whatsapp.py`
- `p004_ai_nexelin/MASTER/clients/signals.py`
- `p004_ai_nexelin/MASTER/clients/tasks.py` (WhatsApp bridge polling tasks)

- [ ] **Step 3: Remove matrix/bridge Docker services from docker-compose.yml**

In `p004_ai_nexelin/docker-compose.yml`, remove these services:
- `ai_nexelin_postgres_mautrix`
- `ai_nexelin_mautrix_whatsapp`
- `ai_nexelin_integration_service`

And any matrix-related environment variables from the `web` service.

- [ ] **Step 4: Delete all matrix/bridge directories**

```bash
rm -rf services/
rm -rf matrix-stack/
rm -rf матрікс/
rm -rf matrix/
rm -rf p004_ai_nexelin/mcp_servers/bridge/
rm -rf p004_ai_nexelin/matrix-bridge/
```

- [ ] **Step 5: Verify Django starts**

```bash
cd p004_ai_nexelin && python manage.py check 2>&1 | head -30
```

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "remove: Matrix/WhatsApp bridge infrastructure"
```

---

## Task 4: Remove Langflow

**Files:**
- Delete: `nextlen/src/pages/LangflowPage.jsx`
- Modify: `nextlen/src/App.jsx` (remove LangflowPage route)
- Modify: `p004_ai_nexelin/MASTER/nexelin_platform/migrations/0006_create_langflow_flag.py` (keep migration but note it's legacy)
- Modify: `p004_ai_nexelin/MASTER/clients/serializers.py` (remove langflow feature flag check)
- Modify: `p004_ai_nexelin/docker-compose.yml` (remove `ai_nexelin_langflow` service)

- [ ] **Step 1: Remove LangflowPage from frontend**

Delete `nextlen/src/pages/LangflowPage.jsx`.

- [ ] **Step 2: Remove Langflow route from App.jsx**

In `nextlen/src/App.jsx`, remove the import and `<Route>` for LangflowPage.

- [ ] **Step 3: Remove Langflow sidebar link**

Search frontend components (likely Sidebar.jsx or similar in `nextlen/src/components/layout/`) for Langflow navigation link and remove it.

- [ ] **Step 4: Remove Langflow Docker service**

In `p004_ai_nexelin/docker-compose.yml`, remove the `ai_nexelin_langflow` service block.

- [ ] **Step 5: Clean langflow feature flag from serializers**

In `p004_ai_nexelin/MASTER/clients/serializers.py`, remove langflow-related feature flag checks.

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "remove: Langflow integration"
```

---

## Task 5: Remove dead documentation and files

**Files to delete:**
- Root MD: `NEXELIN_PLAN.md`, `MIGRATION_PLAN.md`, `API_COMPARISON.md`, `API_ISSUES.md`, `ESCALATION_CODE_SUMMARY.md`, `WEB_WIDGET_INSTRUCTIONS.md`, `VISUAL_EDITOR_ADAPTATION.md`, `API_ENDPOINTS.md`
- Root images: `tools-skills-tab.png`, `whatsapp-card.png`
- Root misc: `dummy`, `.aider.chat.history.md`, `.aider.input.history`, `.aider.tags.cache.v4/`
- Docs: `docs/MATRIX_BRIDGE_EXPLAINED.md`, `docs/MATRIX_HITL_IMPLEMENTATION_DETAILS.md`, `docs/MATRIX_HITL_INTEGRATION_PLAN.md`, `docs/REFACTORING_SUMMARY.md`, `docs/SERVICE_TECHNOLOGY_RECOMMENDATIONS.md`
- Docs plans/specs: `docs/superpowers/specs/` (all except the rebrand spec), `docs/superpowers/plans/` (all files), `docs/plans/`
- Backend docs: `p004_ai_nexelin/docs/API_CREATE_CLIENT.md`, `p004_ai_nexelin/docs/POSTMAN_TEST_CLIENT.md`, `p004_ai_nexelin/docs/ZERO_INTEGRATION_RU.md`, `p004_ai_nexelin/docs/ZERO_REAL_SETUP.md`
- Backend misc: `p004_ai_nexelin/MATRIX_HITL_SETUP.md`, `p004_ai_nexelin/MASTER/docs/whatsapp_webhook_endpoints.md`, `p004_ai_nexelin/MASTER/clients/QR_LOGO_INTEGRATION.md`
- Fix scripts: `p004_ai_nexelin/fix_bootstrap.py`, `p004_ai_nexelin/fix_static.py`, `p004_ai_nexelin/fix_indexes.py`, `p004_ai_nexelin/check_password.py`, `p004_ai_nexelin/check_email_status.py`, `p004_ai_nexelin/MASTER/fix_domain_middleware.py`, `p004_ai_nexelin/clean_migrations.py`, `p004_ai_nexelin/delete_prompts.py`, `p004_ai_nexelin/reduce_dimensions.py`, `p004_ai_nexelin/ensure_pgvector.py`, `p004_ai_nexelin/get-pip.py`
- Backup: `.env-backup-production/` (entire directory)
- `.playwright-mcp/` directory

- [ ] **Step 1: Delete root-level dead files**

```bash
rm -f NEXELIN_PLAN.md MIGRATION_PLAN.md API_COMPARISON.md API_ISSUES.md API_ENDPOINTS.md
rm -f ESCALATION_CODE_SUMMARY.md WEB_WIDGET_INSTRUCTIONS.md VISUAL_EDITOR_ADAPTATION.md
rm -f tools-skills-tab.png whatsapp-card.png dummy
rm -f .aider.chat.history.md .aider.input.history
rm -rf .aider.tags.cache.v4/
rm -rf .playwright-mcp/
```

- [ ] **Step 2: Delete docs/ dead files**

```bash
rm -f docs/MATRIX_BRIDGE_EXPLAINED.md docs/MATRIX_HITL_IMPLEMENTATION_DETAILS.md
rm -f docs/MATRIX_HITL_INTEGRATION_PLAN.md docs/REFACTORING_SUMMARY.md
rm -f docs/SERVICE_TECHNOLOGY_RECOMMENDATIONS.md
rm -rf docs/plans/
```

- [ ] **Step 3: Delete internal specs and plans (keep only rebrand spec)**

```bash
cd docs/superpowers/specs/
# Keep only 2026-04-09-concierge-rebrand-gumroad-design.md
ls | grep -v "2026-04-09-concierge-rebrand" | xargs rm -f
cd ../plans/
rm -f *.md
cd ../../..
```

- [ ] **Step 4: Delete backend dead docs and scripts**

```bash
rm -f p004_ai_nexelin/docs/API_CREATE_CLIENT.md p004_ai_nexelin/docs/POSTMAN_TEST_CLIENT.md
rm -f p004_ai_nexelin/docs/ZERO_INTEGRATION_RU.md p004_ai_nexelin/docs/ZERO_REAL_SETUP.md
rm -f p004_ai_nexelin/MATRIX_HITL_SETUP.md
rm -f p004_ai_nexelin/MASTER/docs/whatsapp_webhook_endpoints.md
rm -f p004_ai_nexelin/MASTER/clients/QR_LOGO_INTEGRATION.md
rm -f p004_ai_nexelin/fix_bootstrap.py p004_ai_nexelin/fix_static.py p004_ai_nexelin/fix_indexes.py
rm -f p004_ai_nexelin/check_password.py p004_ai_nexelin/check_email_status.py
rm -f p004_ai_nexelin/MASTER/fix_domain_middleware.py
rm -f p004_ai_nexelin/clean_migrations.py p004_ai_nexelin/delete_prompts.py
rm -f p004_ai_nexelin/reduce_dimensions.py p004_ai_nexelin/ensure_pgvector.py p004_ai_nexelin/get-pip.py
```

- [ ] **Step 5: Delete production backup secrets**

```bash
rm -rf .env-backup-production/
```

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "remove: dead documentation, scripts, backup configs"
```

---

## Task 6: Rename p004_ai_nexelin → backend

**Files:**
- Rename: `p004_ai_nexelin/` → `backend/`
- Modify: `.github/workflows/dev-deploy.yml` (path references)
- Modify: `.github/workflows/main-tests.yml` (path references)
- Modify: `.gitignore` (if any p004 references)

- [ ] **Step 1: Rename backend directory**

```bash
git mv p004_ai_nexelin backend
```

- [ ] **Step 2: Update GitHub Actions paths**

In `.github/workflows/dev-deploy.yml`, replace all `p004_ai_nexelin/` with `backend/`:
- Line 8, 36: path filter `'p004_ai_nexelin/**'` → `'backend/**'`

In `.github/workflows/main-tests.yml`, replace all `p004_ai_nexelin/` with `backend/`:
- Line 8, 44: path filter `'p004_ai_nexelin/**'` → `'backend/**'`

- [ ] **Step 3: Update any other references to p004_ai_nexelin**

```bash
grep -r "p004_ai_nexelin" --include="*.yml" --include="*.yaml" --include="*.sh" --include="*.md" --include="*.json" -l
```

Fix all found references.

- [ ] **Step 4: Verify Django starts from new path**

```bash
cd backend && python manage.py check 2>&1 | head -20
```

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "rename: p004_ai_nexelin → backend"
```

---

## Task 7: Rename nextlen → frontend

**Files:**
- Rename: `nextlen/` → `frontend/`
- Modify: `.github/workflows/dev-deploy.yml` (path references)
- Modify: `.github/workflows/main-tests.yml` (path references)

- [ ] **Step 1: Rename frontend directory**

```bash
git mv nextlen frontend
```

- [ ] **Step 2: Update GitHub Actions paths**

In `.github/workflows/dev-deploy.yml`, replace `nextlen/` with `frontend/`:
- Line 9, 39: path filter `'nextlen/**'` → `'frontend/**'`

In `.github/workflows/main-tests.yml`:
- Line 9, 47: `'nextlen/**'` → `'frontend/**'`

- [ ] **Step 3: Update any other references to nextlen**

```bash
grep -r "nextlen" --include="*.yml" --include="*.yaml" --include="*.sh" --include="*.md" --include="*.json" --include="*.conf" -l
```

Fix all found references (docker-compose, nginx configs, deployment scripts).

- [ ] **Step 4: Verify frontend builds**

```bash
cd frontend && npm run build 2>&1 | tail -10
```

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "rename: nextlen → frontend"
```

---

## Task 8: Rename nexelin_platform Django app → concierge_platform

**Files:**
- Rename: `backend/MASTER/nexelin_platform/` → `backend/MASTER/concierge_platform/`
- Modify: `backend/MASTER/nexelin_platform/apps.py` (app name)
- Modify: `backend/MASTER/settings.py:113` (INSTALLED_APPS)
- Modify: any files importing from `MASTER.nexelin_platform`

- [ ] **Step 1: Rename directory**

```bash
git mv backend/MASTER/nexelin_platform backend/MASTER/concierge_platform
```

- [ ] **Step 2: Update apps.py**

In `backend/MASTER/concierge_platform/apps.py`, change:
```python
name = 'MASTER.nexelin_platform'
```
to:
```python
name = 'MASTER.concierge_platform'
```

- [ ] **Step 3: Update INSTALLED_APPS**

In `backend/MASTER/settings.py`, change:
```python
"MASTER.nexelin_platform",
```
to:
```python
"MASTER.concierge_platform",
```

- [ ] **Step 4: Update all imports**

```bash
grep -r "nexelin_platform" backend/ --include="*.py" -l
```

Replace `nexelin_platform` with `concierge_platform` in all found files. This includes migrations that reference the app label.

- [ ] **Step 5: Verify Django starts**

```bash
cd backend && python manage.py check 2>&1 | head -20
```

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "rename: nexelin_platform → concierge_platform"
```

---

## Task 9: Rebrand — Nexelin → Concierge in backend

**Files:**
- Modify: `backend/MASTER/settings.py` (domains, CORS, CSRF, Qdrant collection, URLs)
- Modify: `backend/docker-compose.yml` (container names, network, env vars)
- Modify: `backend/MASTER/urls.py` (health check app name)
- Modify: `backend/MASTER/iframe_middleware.py` (domain references)
- Modify: `backend/MASTER/rag/qdrant_sync.py`, `qdrant_search.py` (collection names)
- Modify: `backend/MASTER/EmbeddingModel/admin.py`, `models.py` (mg.nexelin references)
- Modify: `backend/MASTER/api/views.py`, `urls.py` (nexelin references)
- Modify: `backend/MASTER/asgi.py` (fix broken settings module reference)

- [ ] **Step 1: Clean settings.py domains**

In `backend/MASTER/settings.py`:

Replace all hardcoded nexelin.com domains with env vars:
```python
# Before:
ALLOWED_HOSTS = ["api.nexelin.com", "app.nexelin.com", ...]
# After:
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])
```

Same for CSRF_TRUSTED_ORIGINS and CORS_ALLOWED_ORIGINS — move to env vars with `example.com` defaults.

Remove all `bytekraft.net` and `grot.de` hardcoded references.

Replace `QDRANT_COLLECTION = env("QDRANT_COLLECTION", default="nexelin_embeddings")` with `default="concierge_embeddings"`.

Replace `CLIENT_PORTAL_BASE_URL` default from `https://app.nexelin.com` to `https://app.example.com`.

Replace `MG_AI_USAGE_URL` and `MG_PACKAGE_URL` — make them env vars with example.com defaults.

- [ ] **Step 2: Clean docker-compose.yml**

In `backend/docker-compose.yml`:
- Replace all `ai_nexelin_` container name prefixes with `concierge_`
- Replace `nexelin_network` with `concierge_network`
- Remove services: `ai_nexelin_langflow`, `ai_nexelin_postgres_mautrix`, `ai_nexelin_mautrix_whatsapp`, `ai_nexelin_integration_service` (if not already removed in Task 3)
- Update env vars in web service to use new defaults

- [ ] **Step 3: Clean urls.py health check**

In `backend/MASTER/urls.py`, change:
```python
"app": "ai_nexelin"
```
to:
```python
"app": "concierge"
```

- [ ] **Step 4: Fix asgi.py**

In `backend/MASTER/asgi.py`, fix the broken reference:
```python
# Before:
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'admin_panel.settings')
# After:
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'MASTER.settings')
```

- [ ] **Step 5: Clean iframe_middleware.py**

In `backend/MASTER/iframe_middleware.py`, replace hardcoded `mg.nexelin.com` and `app.nexelin.com` with env var lookups.

- [ ] **Step 6: Clean RAG Qdrant references**

In `backend/MASTER/rag/qdrant_sync.py` and `qdrant_search.py`:
- Replace `ai_nexelin_qdrant` host default with `concierge_qdrant`
- Replace `nexelin_embeddings` collection default with `concierge_embeddings`

- [ ] **Step 7: Clean EmbeddingModel and API references**

In `backend/MASTER/EmbeddingModel/admin.py`, `models.py`:
- Replace `sync_from_nexelin` method name with `sync_from_platform`
- Replace `mg.nexelin.com` URLs with env var lookups

In `backend/MASTER/api/views.py`, `urls.py`:
- Replace all `mg.nexelin.com` and `nexelin` references with `concierge` or env vars

- [ ] **Step 8: Grep for remaining nexelin references**

```bash
grep -ri "nexelin" backend/ --include="*.py" -l
```

Fix any remaining references.

- [ ] **Step 9: Commit**

```bash
git add -A && git commit -m "rebrand: Nexelin → Concierge in backend"
```

---

## Task 10: Rebrand — Nexelin → Concierge in frontend

**Files:**
- Modify: `frontend/package.json` (name)
- Modify: `frontend/.env`, `frontend/.env.production` (env vars)
- Modify: `frontend/docker-compose.yml` (network, API URL)
- Modify: `frontend/src/locales/en/translation.json` (+ all 6 other languages)
- Modify: `frontend/src/api/axios.js` (fallback URL)
- Modify: `frontend/src/api/agent.js` (comments)
- Modify: `frontend/src/pages/IntegrationsPage.jsx` (extension URL, bytekraft)
- Modify: `frontend/src/components/` (various — nexelin_ localStorage keys, bridge_auth actions)
- Modify: `frontend/src/modules/supportWidget.js` (domain references)
- Modify: `frontend/src/components/tools/ChromeExtensionSetup.jsx` (extension URL)

- [ ] **Step 1: Update package.json**

In `frontend/package.json`, change:
```json
"name": "nexelin"
```
to:
```json
"name": "concierge-dashboard"
```

- [ ] **Step 2: Update .env files**

In `frontend/.env`:
```
VITE_NEXELIN_EXTENSION_ID=pllaflphfpgpkdnakaamclhjpioicnih
```
→
```
VITE_CONCIERGE_EXTENSION_ID=pllaflphfpgpkdnakaamclhjpioicnih
```

In `frontend/.env.production`:
```
VITE_API_URL=https://api.nexelin.com/api
VITE_NEXELIN_EXTENSION_ID=pllaflphfpgpkdnakaamclhjpioicnih
```
→
```
VITE_API_URL=https://api.example.com/api
VITE_CONCIERGE_EXTENSION_ID=pllaflphfpgpkdnakaamclhjpioicnih
```

- [ ] **Step 3: Update docker-compose.yml**

In `frontend/docker-compose.yml`:
- Replace `nexelin-network` with `concierge-network`
- Replace `https://api.nexelin.com/api` with env var reference

- [ ] **Step 4: Update translation files**

In all 7 locale files (`frontend/src/locales/{en,de,da,nl,it,fr,es}/translation.json`):
- Replace "Nexelin" with "Concierge" in all user-visible strings
- Line 361 (en): `"through Nexelin"` → `"through Concierge"`
- Line 373 (en): `"Enter Credentials in Nexelin"` → `"Enter Credentials in Concierge"`
- Line 765 (en): `"Ask Nexelin support"` → `"Ask Concierge support"`
- Line 847 (en): `"title": "Nexelin"` → `"title": "Concierge"`

- [ ] **Step 5: Update API client files**

In `frontend/src/api/axios.js`:
- Replace `https://api.nexelin.com/api` fallback with `http://localhost:8000/api`
- Remove `mg.nexelin.com` iframe comment

In `frontend/src/api/agent.js`:
- Replace `mg.nexelin.com` comment references

- [ ] **Step 6: Update localStorage keys and action names**

Across frontend components (PromptBook.jsx, LLMProviderCard.jsx, PromptEditor.jsx, RichMessageCard.jsx, FlipToolCard.jsx, ConnectModal.jsx):
- Replace all `nexelin_` localStorage key prefixes with `concierge_`
- Replace `nexelin_bridge_auth` action with `concierge_bridge_auth`
- Replace `nexelin_check_extension` with `concierge_check_extension`

```bash
grep -r "nexelin_" frontend/src/ --include="*.jsx" --include="*.js" -l
```

Update all found files.

- [ ] **Step 7: Update extension URLs and integration references**

In `frontend/src/pages/IntegrationsPage.jsx`:
- Replace `app.nexelin.com` extension download URL
- Remove `ai.bytekraft.net` references

In `frontend/src/components/tools/ChromeExtensionSetup.jsx`:
- Replace extension ZIP URL

In `frontend/src/modules/supportWidget.js`:
- Replace `app.nexelin.com` references

- [ ] **Step 8: Grep for remaining nexelin references**

```bash
grep -ri "nexelin" frontend/src/ --include="*.jsx" --include="*.js" --include="*.json" -l
```

Fix any remaining references.

- [ ] **Step 9: Commit**

```bash
git add -A && git commit -m "rebrand: Nexelin → Concierge in frontend"
```

---

## Task 11: Rebrand Chrome extension

**Files:**
- Modify: `backend/chrome_extension/manifest.json`
- Modify: `backend/chrome_extension/lib/api-client.js`
- Modify: `backend/chrome_extension/contentScript.js`
- Modify: `backend/chrome_extension/background/service-worker.js`
- Modify: `backend/chrome_extension/content/behaviour-tracker.js`
- Modify: `backend/chrome_extension/lib/memory-manager.js`

- [ ] **Step 1: Update manifest.json**

```json
"name": "Concierge Web Agent",
"description": "Concierge Chrome extension: ...",
"matches": ["*://localhost/*"]
```

Remove `*://*.nexelin.com/*` and `*://*.grot.de/*` from matches — make it configurable or localhost-only for development.

- [ ] **Step 2: Update api-client.js**

Replace `DEFAULT_API_BASE_URL = 'https://api.nexelin.com'` with `'http://localhost:8000'`.

- [ ] **Step 3: Update contentScript.js**

Replace `DEFAULT_BACKEND_URL = 'https://api.nexelin.com/api/clients/extension/page/'` with localhost equivalent.

- [ ] **Step 4: Update service-worker.js**

Replace `nexelin_bridge_auth` and `nexelin_check_extension` with `concierge_bridge_auth` and `concierge_check_extension`.

- [ ] **Step 5: Update behaviour-tracker.js and memory-manager.js**

Replace `__nexelin_bt__` namespace with `__concierge_bt__`.
Replace `nexelin_` key prefixes with `concierge_`.

- [ ] **Step 6: Rebuild extension ZIP**

```bash
cd backend/chrome_extension && zip -r ../../frontend/public/static/extensions/concierge-chrome-extension.zip . -x ".*"
rm frontend/public/static/extensions/nexelin-chrome-extension.zip
```

- [ ] **Step 7: Commit**

```bash
git add -A && git commit -m "rebrand: Chrome extension → Concierge Web Agent"
```

---

## Task 12: Add Jeeves as default AI assistant

**Files:**
- Modify: `backend/MASTER/clients/models.py` (default system prompt)
- Modify: `backend/MASTER/api/views.py` (default bot name in bootstrap/provision)
- Modify: `frontend/src/locales/en/translation.json` (default assistant name in UI)

- [ ] **Step 1: Find current default system prompt**

```bash
grep -n "system_prompt\|system prompt\|default.*prompt" backend/MASTER/clients/models.py backend/MASTER/api/views.py
```

- [ ] **Step 2: Set Jeeves as default assistant**

In the Client model or wherever the default system prompt is defined, set:
```python
default_system_prompt = "My name is Jeeves. I am your AI assistant powered by Concierge. I'm here to help you with any questions or tasks. You can rename me and customize my personality in your dashboard settings."
```

- [ ] **Step 3: Update frontend default name**

If there's a hardcoded "AI Assistant" or similar in translation files, update to "Jeeves" as the default display name.

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "feat: add Jeeves as default AI assistant identity"
```

---

## Task 13: Clean remaining grot.de and bytekraft.net references

**Files:**
- Any remaining files with grot.de or bytekraft.net

- [ ] **Step 1: Find all remaining references**

```bash
grep -ri "grot\.de\|bytekraft" . --include="*.py" --include="*.js" --include="*.jsx" --include="*.json" --include="*.yml" --include="*.yaml" --include="*.conf" --include="*.env" -l
```

- [ ] **Step 2: Replace with env vars or example.com**

For each found file, replace hardcoded domains with either:
- Environment variable lookups (for runtime config)
- `example.com` (for documentation/defaults)

- [ ] **Step 3: Commit**

```bash
git add -A && git commit -m "clean: remove grot.de and bytekraft.net references"
```

---

## Task 14: Update .gitignore and clean tracked secrets

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: Review and update .gitignore**

Ensure `.gitignore` includes:
```
.env
.env.*
!.env.example
*.sql
*.pyc
__pycache__/
node_modules/
dist/
staticfiles/
media/
*.log
.aider*
```

- [ ] **Step 2: Remove any tracked .env files from git**

```bash
git rm --cached frontend/.env frontend/.env.production 2>/dev/null
git rm --cached backend/.env 2>/dev/null
```

- [ ] **Step 3: Create .env.example files**

Create `backend/.env.example`:
```env
# Django
SECRET_KEY=change-me-in-production
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database
DATABASE_URL=postgres://concierge:concierge@localhost:5432/concierge

# Redis
REDIS_URL=redis://localhost:6379/0

# OpenAI
OPENAI_API_KEY=sk-your-key-here

# Qdrant
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_COLLECTION=concierge_embeddings

# Platform URLs
CLIENT_PORTAL_BASE_URL=http://localhost:3000
```

Create `frontend/.env.example`:
```env
VITE_API_URL=http://localhost:8000/api
VITE_CONCIERGE_EXTENSION_ID=your-extension-id
```

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "clean: update .gitignore, add .env.example files"
```

---

## Task 15: Write buyer-facing documentation

**Files:**
- Rewrite: `README.md`
- Create: `SETUP.md`
- Keep: `docs/superpowers/specs/2026-04-09-concierge-rebrand-gumroad-design.md` (internal reference)

- [ ] **Step 1: Write new README.md**

```markdown
# Concierge AI Platform

Multi-tenant AI assistant platform with RAG, MCP tools, and a customizable dashboard.

Deploy your own AI assistant — **Jeeves** comes ready out of the box. Rename him, retrain him, make him yours.

## Features

- **RAG Knowledge Base** — Upload documents, Concierge learns from them
- **MCP Tools** — Extensible tool system (email, leads, sales intel, coaching, memory)
- **Multi-tenant** — Branch → Specialization → Client hierarchy
- **Dashboard** — React admin panel with i18n (7 languages)
- **Chrome Extension** — AI assistant embedded in any webpage
- **Web Chat Widget** — Embeddable chat for client websites
- **API-First** — Full REST API with DRF

## Tech Stack

- **Backend:** Django 5, DRF, PostgreSQL + pgvector, Redis, Celery
- **Frontend:** React 18, Vite, Tailwind CSS, i18next
- **AI:** LangChain, OpenAI API, Qdrant
- **Infrastructure:** Docker Compose, Nginx

## Quick Start

See [SETUP.md](SETUP.md) for full installation guide.

## License

[TBD]
```

- [ ] **Step 2: Write SETUP.md**

Write a setup guide covering:
1. Prerequisites (Docker, Node.js, Python)
2. Clone and configure (.env files)
3. Docker Compose up
4. Create first admin user
5. Create first client
6. Access dashboard

- [ ] **Step 3: Clean remaining backend docs**

Review `backend/docs/` — keep CI_CD_SETUP.md and FIX_PGVECTOR.md (useful for buyers). Remove or update the rest.

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "docs: add buyer-facing README and SETUP guide"
```

---

## Task 16: Final verification sweep

- [ ] **Step 1: Grep for all old brand names**

```bash
grep -ri "nexelin\|nextlen\|grot\.de\|bytekraft\|p004" . \
  --include="*.py" --include="*.js" --include="*.jsx" --include="*.json" \
  --include="*.yml" --include="*.yaml" --include="*.conf" --include="*.env" \
  --include="*.md" --include="*.html" --include="*.css" \
  -l | grep -v node_modules | grep -v __pycache__ | grep -v .git/
```

Fix any remaining references.

- [ ] **Step 2: Verify Django starts and basic check passes**

```bash
cd backend && python manage.py check 2>&1
```

- [ ] **Step 3: Verify frontend builds**

```bash
cd frontend && npm run build 2>&1 | tail -20
```

- [ ] **Step 4: Verify Docker Compose config is valid**

```bash
cd backend && docker compose config --quiet 2>&1
```

- [ ] **Step 5: Final commit if any fixes**

```bash
git add -A && git commit -m "clean: final verification sweep"
```
