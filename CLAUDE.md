# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Product

**Concierge AI Platform (Jeeves)** — multi-tenant AI assistant SaaS with RAG, MCP tools, and a customizable dashboard. Sold on Gumroad for self-hosting. The AI character is named "Jeeves" (with double 'e').

## Commands

### Backend (run from `backend/`)

```bash
# Docker (primary way to run)
docker compose up -d                    # Start all services (postgres, redis, web, celery, nginx)
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser
docker compose logs -f web              # Watch backend logs

# Tests (inside container or locally with services running)
cd Jeeves && pytest -v                  # All backend tests
cd Jeeves && pytest -v -k test_name     # Single test by name
cd Jeeves && pytest Jeeves/concierge_platform/tests/ -v  # Tests for one app
cd Jeeves && pytest --cov=Jeeves        # With coverage

# Linting (from backend/)
black --check .
isort --check-only .
flake8
mypy .
```

### Frontend (run from `frontend/`)

```bash
npm ci                     # Install deps (use ci, not install)
npm run dev                # Dev server on :5173
npm run build              # Production build
npm run build:prod         # Production build (explicit mode)
npm run lint               # ESLint
```

### Full stack via Docker

```bash
cd backend && docker compose up -d      # Backend services on :8000
cd frontend && docker compose up -d     # Frontend on :3000 (requires backend network)
```

## Architecture

### Monorepo Layout

- `backend/` — Django 5 + DRF project. Working directory for `manage.py` is `backend/Jeeves/` (the inner Jeeves dir also contains `manage.py`).
- `frontend/` — React 19 + Vite + Tailwind dashboard.
- `backend/mcp_servers/` — Standalone FastMCP tool servers (stdio transport).
- `backend/chrome_extension/` — Browser extension source.
- `docs/` — Superpowers scratch (gitignored).

### Backend: Django Project Structure

The Django project is `Jeeves` (capital J). Settings module: `Jeeves.settings`. All apps are under `backend/Jeeves/`:

| App | Purpose |
|---|---|
| `accounts` | User model (4 roles: ADMIN, OWNER, MANAGER, CLIENT), JWT auth |
| `agents` | AgentConfig per client, AgentSession, AgentLog, orchestrator, MCP dispatch |
| `api` | Large views.py with client-facing REST endpoints, bootstrap |
| `branches` | Organizational branches with documents + embeddings |
| `specializations` | Domain specializations under branches with documents + embeddings |
| `clients` | **Largest app.** Client tenants, documents, WhatsApp/Telegram/email channels, HITL escalation, leads, QR codes, web widget |
| `concierge_platform` | PlatformDefaults (singleton), FeatureFlag, SystemMessage, PlatformLicense (Gumroad) |
| `EmbeddingModel` | EmbeddingModel, LLMProvider, ModelPair — AI model registry |
| `mcp_hub` | MCP server management + tool execution layer |
| `processing` | Document parsing, chunking, embedding generation, UsageStats |
| `rag` | RAG engine: context builder, LLM client, Qdrant/pgvector search |
| `tools` | ToolCard catalog, ToolConnection per client, InstalledMCPServer, installer |

**Data hierarchy:** Branch > Specialization > Client. Each level has its own documents and embeddings.

**Agent architecture:** Dual-agent (Assistant + Manager). Scope-based tool filtering. AgentConfig falls back to PlatformDefaults for unset values.

### MCP Servers (`backend/mcp_servers/`)

9 FastMCP servers communicating via stdio. Each bootstraps Django ORM through `mcp_servers.common.django_setup`:

- `rag` — semantic search over knowledge base (Qdrant or pgvector)
- `escalation` — HITL escalation to live managers
- `email` — send/read/search emails via client SMTP/IMAP
- `leads` — lead capture and qualification from conversations
- `memory` — persistent conversational memory (Qdrant + Cohere embeddings)
- `coaching` — AI coaching: gap analysis, knowledge updates
- `sales_intel` — website scraping, tech stack detection
- `xlsx` — Excel generation with formulas (uses LibreOffice for recalc)
- `common/` — shared Django bootstrap

Configured in `settings.py` under `MCP_SERVERS` dict. Tool scopes defined in `MCP_TOOL_SCOPES`.

### Frontend Architecture

**Router zones** (React Router v7):
- `/owner/*` — Platform admin (protected by `BootstrapGate`)
- `/l/:tag/*` — Client portal (tag-based auth via `X-Client-Token`)
- `/client` — Public B2C web chat
- Legacy routes at root (`/dashboard`, `/sandbox`, etc.)

**Context providers** (nesting order): `AuthProvider` > `ThemeProvider` > `BrowserRouter` > `BootstrapProvider`

**API layer** (`src/api/`): Modular Axios clients — `authAPI`, `clientAPI`, `ownerAPI`, `toolsAPI`, `agentAPI`. Interceptors handle JWT refresh and dual auth modes (Bearer token vs X-Client-Token).

**i18n:** 8 languages (en, de, fr, es, it, nl, da, uk) via i18next. Translations in `src/locales/{lang}/translation.json`.

## Key Conventions

- **Python formatting:** Black (120 chars), isort (black profile), flake8 (120 chars, complexity 10). Config in `pyproject.toml` and `.flake8`.
- **Python target:** 3.12. Django settings module: `Jeeves.settings`.
- **Imports:** `from Jeeves.app_name.models import ...` — the `Jeeves` prefix is always required.
- **Tests:** pytest + pytest-django. Config in `pyproject.toml`. Test root: `backend/Jeeves/`. Conftest provides auto-generated Fernet key for EncryptedJSONField.
- **Frontend:** JSX (no TypeScript). ESLint with react-hooks + react-refresh plugins. Unused vars pattern: `^[A-Z_]`.
- **Env files:** `backend/.env` and `frontend/.env` (never committed). Examples at `.env.example`.
- **Docker ports:** Postgres 5433, Redis 6380, Backend 8000, Frontend 3000 (Docker) / 5173 (Vite dev).
- **Celery:** App in `Jeeves.celery`, autodiscover tasks. Beat schedule in settings.py.
- **Sensitive fields:** Use `EncryptedJSONField` for credentials (tool connections, API configs).

## CI/CD

GitHub Actions (`.github/workflows/main-tests.yml`): runs on push/PR to `main`. Backend tests need Postgres (pgvector) + Redis services. Frontend job runs lint + production build.
