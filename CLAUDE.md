# CLAUDE.md

Instructions for Claude Code working on the Jeeves repository.

## Product

**Jeeves** — multi-tenant AI assistant platform with RAG, MCP tools, messaging integrations, and admin dashboard. Open source (Elastic License 2.0), self-hosted. The AI character is named "Jeeves" (double 'e').

## Commands

### Backend (from `backend/`)

```bash
# Docker (primary)
docker compose up -d
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser
docker compose logs -f web

# Tests (from backend/Jeeves/)
pytest -v
pytest -v -k test_name
pytest Jeeves/concierge_platform/tests/ -v
pytest --cov=Jeeves

# Linting (from backend/)
black --check .
isort --check-only .
flake8
mypy .
```

### Frontend (from `frontend/`)

```bash
npm ci
npm run dev          # Dev server :5173
npm run build        # Production build
npm run lint         # ESLint
```

### Full stack

```bash
cd backend && docker compose up -d      # Backend on :8000
cd frontend && docker compose up -d     # Frontend on :3000
```

### Matrix (optional — for `mcp_matrix`)

```bash
cd infra/matrix
cp .env.example .env                              # fill MATRIX_DOMAIN + SYNAPSE_DB_PASSWORD
mkdir -p synapse
docker compose --env-file .env run --rm synapse generate
# … patch synapse/homeserver.yaml (Postgres, listeners, federation off) — see docs/matrix-setup.md
docker compose --env-file .env up -d synapse-db synapse
docker compose exec -T synapse register_new_matrix_user \
  -u jeeves-bot -p <STRONG_PWD> -a -c /data/homeserver.yaml http://localhost:8008
# capture access_token via POST /_matrix/client/v3/login, drop into backend/.env as MATRIX_BOT_TOKEN
```

Bridges (WhatsApp / Telegram / Meta) live in the same compose but require per-bridge credentials and Synapse `app_service_config_files:` wiring — see `docs/matrix-setup.md` §3.

## Architecture

### Monorepo layout

- `backend/` — Django 5 + DRF. Inner working directory: `backend/Jeeves/` (contains `manage.py`)
- `frontend/` — React 19 + Vite + Tailwind
- `backend/mcp_servers/` — 8 standalone FastMCP servers (stdio transport)
- `backend/chrome_extension/` — Browser extension source

### Django apps (all under `backend/Jeeves/`)

| App | Purpose |
|-----|---------|
| `accounts` | User model (4 roles: ADMIN, OWNER, MANAGER, CLIENT), JWT auth |
| `agents` | AgentConfig per client, AgentSession, AgentLog, MCP orchestrator |
| `api` | Client-facing REST endpoints, bootstrap |
| `branches` | Org hierarchy Level 1 — documents + embeddings |
| `specializations` | Org hierarchy Level 2 — documents + embeddings |
| `clients` | **Largest app.** Tenants, channels (WhatsApp/Telegram/Email/Widget), HITL, leads, QR codes |
| `concierge_platform` | PlatformDefaults (singleton), FeatureFlag, SystemMessage |
| `content_planner` | ContentPlan / ContentPost / ContentIdea — editorial calendar fed by `mcp_content_planner` |
| `EmbeddingModel` | EmbeddingModel, LLMProvider, ModelPair — AI model registry |
| `mcp_hub` | MCP server management + tool execution |
| `processing` | Document parsing, chunking, embedding, UsageStats |
| `rag` | RAG engine: vector search (Qdrant/pgvector), context builder, LLM client |
| `tools` | ToolCard catalog, ToolConnection per client, InstalledMCPServer |

### Data hierarchy

Branch > Specialization > Client. Each level has isolated documents + embeddings. Search weights: Client (0.8) > Specialization (0.5) > Branch (0.3).

### Agent architecture

Dual-agent system: Assistant (sandbox, full power) + Consultant (messengers, lead-optimized). Scope-based tool filtering. AgentConfig falls back to PlatformDefaults for unset fields.

### MCP servers (`backend/mcp_servers/`)

FastMCP servers communicating via stdio. Each bootstraps Django ORM through `mcp_servers.common.django_setup`:

| Server | Function |
|--------|----------|
| `rag` | Semantic search over knowledge base |
| `escalation` | HITL escalation to live managers |
| `email` | Send/read/search emails via client SMTP/IMAP |
| `leads` | Lead capture + qualification |
| `memory` | Persistent conversational memory (Qdrant + Cohere) |
| `coaching` | AI coaching, gap analysis |
| `sales_intel` | Website scraping, tech stack detection |
| `xlsx` | Excel generation with formulas (LibreOffice) |
| `matrix` | Cross-platform DM via Synapse + mautrix bridges (IG/FB/WA/TG). Replaces direct Meta Graph / Telegram Bot API |
| `hardware` | Remote workstation control via SSH + Wake-on-LAN (ported from sloth/pi-remote). Disabled by default — requires `config.yaml` |
| `google_workspace` | Google Calendar / Sheets / Business Reviews via OAuth |
| `content_planner` | Editorial CRUD over `content_planner.ContentPlan` / `ContentPost` / `ContentIdea`. Publishes through `mcp_matrix` |

Configured in `settings.py` under `MCP_SERVERS`. Tool scopes in `MCP_TOOL_SCOPES`.

### Matrix infrastructure (`infra/matrix/`)

Optional self-hosted Synapse + mautrix bridges stack that powers `mcp_matrix`. Full setup spec: [`docs/matrix-setup.md`](docs/matrix-setup.md).

- `docker compose --env-file .env up -d synapse-db synapse` (from `infra/matrix/`).
- Backend `web` joins the external Docker network `matrix_matrix`; `mcp_matrix` reaches Synapse at `http://synapse:8008`.
- `backend/.env` must define `MATRIX_HOMESERVER_URL`, `MATRIX_BOT_USER_ID`, `MATRIX_BOT_TOKEN` (service-account `@jeeves-bot:<domain>`).
- Per-client OAuth-style credentials live in `tools.ToolConnection.credentials` (slug=`matrix`, `EncryptedJSONField`): `{homeserver_url, user_id, access_token}`.
- Bridges (`mautrix-whatsapp`, `mautrix-telegram`, `mautrix-meta`) ship in compose but stay down until per-bridge `config.yaml` + AS registration are generated. None are live yet.

### Frontend architecture

**Router zones** (React Router v7):
- `/owner/*` — Platform admin (protected by `BootstrapGate`)
- `/l/:tag/*` — Client portal (tag-based auth via `X-Client-Token`)
- `/client` — Public B2C web chat
- Legacy routes at root for backward compatibility

**Context providers** (nesting): `AuthProvider` > `ThemeProvider` > `BrowserRouter` > `BootstrapProvider`

**API layer** (`src/api/`): Modular Axios clients — `authAPI`, `clientAPI`, `ownerAPI`, `toolsAPI`, `agentAPI`. Interceptors handle JWT refresh + dual auth (Bearer vs X-Client-Token).

**i18n:** 8 languages (en, de, fr, es, it, nl, da, uk) via i18next. Translations in `src/locales/{lang}/translation.json`.

## Key Conventions

- **Python:** Black (120 chars), isort (black profile), flake8 (120 chars, complexity 10). Config in `pyproject.toml` and `.flake8`
- **Python target:** 3.12. Settings module: `Jeeves.settings`
- **Imports:** Always use `Jeeves` prefix — `from Jeeves.app_name.models import ...`
- **Tests:** pytest + pytest-django. Config in `pyproject.toml`. Test root: `backend/Jeeves/`. Conftest provides auto-generated Fernet key for EncryptedJSONField
- **Frontend:** JSX (no TypeScript). ESLint with react-hooks + react-refresh plugins
- **Env files:** `backend/.env` and `frontend/.env` — never committed. Examples at `.env.example`
- **Docker ports:** Postgres 5433, Redis 6380, Backend 8000, Frontend 3000 (Docker) / 5173 (Vite dev)
- **Celery:** App in `Jeeves.celery`, autodiscover tasks. Beat schedule in `settings.py`
- **Sensitive fields:** Use `EncryptedJSONField` for credentials (tool connections, API configs)
- **License:** Elastic License 2.0 — free use, no reselling as hosted service, branding footer must stay

## CI/CD

GitHub Actions (`.github/workflows/main-tests.yml`): runs on push/PR to `main`. Backend needs Postgres (pgvector) + Redis services. Frontend runs lint + build.
