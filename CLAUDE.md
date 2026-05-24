# CLAUDE.md

Instructions for Claude Code working on the Jeeves repository.

## Product

**Jeeves** — multi-tenant AI assistant SaaS platform with RAG, MCP tools, messaging integrations, and admin dashboard. Self-hosted, sold on Gumroad. The AI character is named "Jeeves" (double 'e').

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
| `concierge_platform` | PlatformDefaults (singleton), FeatureFlag, SystemMessage, PlatformLicense (Gumroad) |
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

9 FastMCP servers communicating via stdio. Each bootstraps Django ORM through `mcp_servers.common.django_setup`:

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

Configured in `settings.py` under `MCP_SERVERS`. Tool scopes in `MCP_TOOL_SCOPES`.

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
- **Gumroad:** License validation via `concierge_platform/gumroad_client.py`. Product ID from `GUMROAD_PRODUCT_ID` env var. Grace period: 7 days on network failure

## CI/CD

GitHub Actions (`.github/workflows/main-tests.yml`): runs on push/PR to `main`. Backend needs Postgres (pgvector) + Redis services. Frontend runs lint + build.
