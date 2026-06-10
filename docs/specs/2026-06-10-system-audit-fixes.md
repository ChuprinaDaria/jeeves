# System Audit Fixes — Spec & Plan

**Date:** 2026-06-10
**Branch:** `claude/jolly-edison-7h9367`
**Status:** Phase 1 implemented in this PR; Phases 2-4 are the roadmap.

A full system audit (backend, frontend, security, infrastructure) surfaced ~80 issues.
This spec records all of them, prioritized by impact, and defines what is fixed now vs. later.

---

## Phase 1 — Critical fixes (THIS PR)

> **Note:** file/line references below reflect the pre-fix state of the codebase
> at audit time (2026-06-10); they will drift as the code evolves.

### 1.1 Insecure configuration defaults (CRITICAL)
- `backend/Jeeves/settings.py:17` — `SECRET_KEY` defaulted to `"dev-secret"`.
- `backend/Jeeves/settings.py:124` — `DB_PASS` defaulted to `"admin_pass"`.
- `backend/docker-compose.yml` — `DEBUG` defaulted to `1` (DEBUG=True in prod), `SECRET_KEY`/`DB_PASS` insecure defaults.

**Fix:** settings now fail fast with `ImproperlyConfigured` when running with
`DEBUG=False` and an unset/placeholder `SECRET_KEY` or `DB_PASS`. Dev defaults still
work when `DEBUG=True`. docker-compose `DEBUG` default flipped to `0`.

### 1.2 `ALLOWED_HOSTS = '*'` (CRITICAL — Host header injection)
- `settings.py:389` — `ALLOWED_HOSTS.append('*')` unconditionally.

**Fix:** wildcard is appended only when `DEBUG=True`. Production must list domains via
`ALLOWED_HOSTS` env (supports `.domain.com` suffix patterns for white-label subdomains).

### 1.3 `SameSite=None` on session/CSRF cookies (CRITICAL — CSRF exposure)
- `settings.py:60,64` — both cookies were `SameSite=None` platform-wide, combined with
  `CORS_ALLOW_CREDENTIALS=True`.

**Fix:** default is now `Lax`, overridable via `COOKIE_SAMESITE` env for deployments
that genuinely need iframe session cookies (the chat widget itself authenticates via
`X-Client-Token` header, not cookies, so it is unaffected).

### 1.4 SQL interpolation in pgvector tuning (CRITICAL)
- `rag/vector_search.py:265,269` — config values f-string-interpolated into `SET` statements.

**Fix:** values are coerced to `int()` before interpolation (`SET` does not accept
bind parameters in PostgreSQL, so integer coercion is the correct guard).

### 1.5 SSRF in sales_intel MCP server (CRITICAL)
- `mcp_servers/sales_intel/server.py:59-98` — `website_extract` fetched arbitrary URLs
  (could reach `localhost`, `redis:6379`, cloud metadata `169.254.169.254`).

**Fix:** URL validation added — only `http/https` schemes, hostname resolved and checked
against private/loopback/link-local/reserved ranges before fetching. Same check applied
to `detect_techstack` domains.

### 1.6 Meta WhatsApp webhook signature optional (CRITICAL)
- `clients/views_meta_whatsapp.py:154-157` — signature verified only *if the attacker
  sent one*; omitting `X-Hub-Signature-256` bypassed verification entirely.

**Fix:** when an app secret is configured (per-client or global), a missing or invalid
signature is rejected with 403. When no secret is configured anywhere, the request is
still processed but a loud warning is logged (backward compatibility for unconfigured
installs).

### 1.7 No timeout on MCP tool calls (HIGH)
- `mcp_hub/executor.py` — a hung MCP server hung the whole agent request forever.

**Fix:** all transports (stdio/SSE/streamable HTTP/builtin) wrapped in
`asyncio.wait_for` with `MCP_TOOL_TIMEOUT` setting (default 60s).

### 1.8 Race conditions on counters and bootstrap (HIGH)
- `clients/views.py` `PromptViewSet.vote` — read-modify-write on `likes_count`/`dislikes_count`.
- `api/views.py` bootstrap — multi-model `get_or_create` chain without a transaction.

**Fix:** vote counters now use `F()` expressions; bootstrap wrapped in `transaction.atomic()`.

### 1.9 Unbounded in-process cache (HIGH — memory leak)
- `api/views.py` — `_email_intent_cache` class dict with no TTL/size limit, per gunicorn worker.

**Fix:** replaced with Django cache (`django.core.cache`) with 1h TTL.

### 1.10 CI ignores test failures (CRITICAL — process)
- `.github/workflows/main-tests.yml:127` — `pytest ... || true`; `:181` — `npm run lint || true`.

**Fix:** `|| true` removed so CI actually fails on broken tests/lint.

### 1.11 docker-compose hardening (HIGH)
- No healthcheck for `celery_worker`/`celery_beat`; they waited only for `web` *started*,
  not *healthy*.

**Fix:** healthchecks added (`celery inspect ping`), `depends_on: web` upgraded to
`service_healthy`.

### 1.12 Frontend resilience (HIGH)
- No `ErrorBoundary` anywhere — any render error blanks the whole app.
- All 30+ pages imported eagerly in `App.jsx` — single huge bundle.
- `TrainingPage.jsx` polling effect keyed on `files` (re-creates interval on every
  fetch, risk of tight loop); `WebChatPage.jsx` polling keyed on `conversationDbId`
  (interval churn).

**Fix:** `ErrorBoundary` component added and wraps the router; routes converted to
`React.lazy` + `Suspense`; polling effects fixed to use refs/stable deps.

### 1.13 Iframe middleware origin bypass (HIGH)
- `Jeeves/iframe_middleware.py:39-44` — substring check (`host in referer`) was
  bypassable via `http://evil.com/?x=http://localhost:3000`, letting an attacker
  origin into `Content-Security-Policy: frame-ancestors`.

**Fix:** exact origin comparison after parsing scheme://netloc.

### 1.14 Broken CI job gating (CRITICAL — process)
- `.github/workflows/main-tests.yml` — the `check-changes` job (dorny/paths-filter
  with `fetch-depth: 2`) evaluated to `false` on merge commits, so backend/frontend
  test jobs were **skipped on every push to main** while the workflow reported green.
- The backend job env was also broken: it exported `DATABASE_URL` (which
  `settings.py` never reads) instead of `DB_*` vars, and never set the required
  `FIELD_ENCRYPTION_KEY` — so the job could not have passed even if it had run.

**Fix:** per-job gating removed (workflow-level `paths:` already gates), correct
`DB_*`/`FIELD_ENCRYPTION_KEY` env wired in, `|| true` removed from pytest and ESLint,
all pre-existing ESLint errors fixed so lint can be blocking.

---

## Phase 2 — High priority (next PRs, not in this one)

1. **MCP transport migration (biggest scalability win).** stdio spawns a full Python
   process + `django.setup()` per tool call (~300-500MB, seconds of latency). Migrate
   the 8 first-party servers to streamable HTTP (one long-lived process each, behind
   compose services), or inline them as builtin handlers. `executor.py` already
   supports both transports.
2. **Encrypt messenger credentials at rest.** `clients/models.py` —
   `meta_app_secret`, `meta_access_token`, `telegram_bot_token`, `email_smtp_password`
   are plaintext. Introduce encrypted fields + data migration.
3. **Move blocking I/O out of the request cycle.** Telegram sends
   (`views_telegram.py`), Ollama/LLM calls with 60s timeouts — move to Celery or
   async views; raise gunicorn workers (currently 3×2 threads).
4. **DRF default permission flip.** `AllowAny` default (`settings.py:140-144`) means a
   single forgotten `get_client_from_request()` exposes data. Flip to
   `IsAuthenticated` default and explicitly whitelist public endpoints. Needs a full
   endpoint inventory + tests first.
5. **Test coverage.** `clients`, `rag`, `processing`, `branches`, `specializations`
   have zero tests. Priority: tenant isolation (IDOR), chat flow, document pipeline,
   webhook auth.
6. **Observability.** Sentry, Flower, JSON logging, request-ID middleware,
   django-prometheus.
7. **SSRF hardening against DNS rebinding.** The sales_intel check validates the
   resolved IP at check time, but the downstream fetcher (external
   open_sales_stack package) re-resolves at connect time. Full fix requires
   pinning vetted IPs at socket-connect in the fetcher, or container egress
   rules blocking private ranges.
8. **Meta webhook fail-closed per tenant.** Signature header is now mandatory
   and verified when a secret is known; clients without a configured
   `meta_app_secret` still cannot be verified. Enforce secret configuration for
   enabled WhatsApp clients (or refuse to enable the channel without one).

## Phase 3 — Medium priority

- Celery: `acks_late`, exponential backoff retries, task routing to dedicated queues
  (documents/email/periodic), `CELERY_WORKER_CONCURRENCY` default = CPU count.
- N+1 / pagination: `select_related` on `ClientViewSet`, pagination on all list
  endpoints, aggregate instead of repeated `.count()`.
- Refactor god files: `clients/views.py` (3997 lines), `clients/tasks.py` (3352),
  `api/views.py` (2807) → split by domain; extract `ClientAuthMixin`.
- Deduplicate Document/Embedding models across `clients`/`branches`/`specializations`
  via abstract base models; generic document-processing task.
- File upload validation via magic bytes; random storage names.
- Prompt injection hardening: separate user content from `[LEAD_DATA]` instruction
  markers in `rag/llm_client.py`.
- Lock dependency versions (pip-compile / lock file) + `pip-audit` in CI.
- Dockerfile: non-root user; resource limits in compose.

## Phase 4 — Lower priority

- i18n completion (uk has 8/24 sections; da/es/fr/it/nl missing 4 each) + lazy-load locales.
- Frontend: migrate data fetching to react-query; extract shared form/edit-page
  components; remove legacy duplicate routes; React.memo on large tables.
- JWT storage migration from localStorage to HttpOnly cookies (needs backend support).
- HNSW indexes for pgvector; embedding query cache; LLM provider fallback chain.
- API versioning (`/api/v1/`).

---

## Verification for Phase 1

- `pytest` (backend suite) passes.
- `npm run lint` and `npm run build` pass.
- Manual review: settings keep working in DEBUG mode without env vars (dev UX
  unchanged); production without proper secrets now fails fast with clear messages.
