# Jeeves — Self-Hosted AI Assistant Platform

Deploy your own AI assistant. Jeeves comes ready out of the box — rename him, retrain him, make him yours.

Multi-tenant AI assistant SaaS with RAG knowledge base, MCP tools, messaging integrations, and a full admin dashboard. Built on Django + React. Sold on [Gumroad](https://gumroad.com) for self-hosting.

---

## What It Does

Jeeves is a white-label AI concierge platform. You deploy it on your own server, connect your knowledge base, plug in messaging channels, and get an AI assistant that answers questions, captures leads, and escalates to humans when needed.

**Target audience:** agencies, service businesses, SaaS operators who need a customizable AI assistant without building from scratch.

---

## Features

### RAG Knowledge Base
- Upload documents (PDF, DOCX, TXT, images)
- Automatic chunking, embedding, and vector search
- Three-level hierarchy: Branch > Specialization > Client — each with isolated documents
- Qdrant (primary) or PostgreSQL pgvector (fallback) for vector storage
- Supports OpenAI, Cohere, Huggingface, and local Ollama embeddings

### Dual-Agent Architecture
- **Assistant** — full-power agent for business owners (Sandbox)
- **Consultant/Concierge** — customer-facing agent optimized for lead capture (Messengers)
- Scope-based tool filtering per agent role
- Fallback to legacy RAG pipeline if MCP fails

### MCP Tool Integration
8 built-in FastMCP servers (stdio transport):

| Server | What it does |
|--------|-------------|
| `rag` | Semantic search over the knowledge base |
| `escalation` | Route unanswered questions to live managers (HITL) |
| `email` | Send, read, search emails via client SMTP/IMAP |
| `leads` | Capture contact info + interest scoring from conversations |
| `memory` | Persistent conversational memory (Qdrant + Cohere) |
| `coaching` | AI coaching and gap analysis |
| `sales_intel` | Website scraping and tech stack detection |
| `xlsx` | Excel generation with formulas (LibreOffice) |

Dynamic tool discovery at runtime. OpenAI function-calling interface.

### Messaging Channels
- **WhatsApp** — Meta official API + mautrix bridge
- **Telegram** — bot with auto-reply and escalation
- **Email** — SMTP/IMAP per client
- **Web Widget** — embeddable iframe chat
- **Web Chat** — B2C white-label portal

### Human-in-the-Loop (HITL)
- Automatic escalation to live managers for unresolved questions
- Telegram notifications for escalated messages
- Manager dashboard with conversation routing

### Lead Capture
- Automatic contact info extraction from conversations
- Interest scoring (1-5) via LLM analysis
- Lead qualification and management dashboard

### Admin Dashboard
- Full CRUD: clients, branches, specializations
- AI provider management (LLM + embedding model pairs)
- MCP server configuration
- Feature flag rollout (off / selected clients / all)
- Multi-language system messages
- License management (Gumroad)

### Multi-Language Support
8 UI languages: English, German, French, Spanish, Italian, Dutch, Danish, Ukrainian.
Automatic customer language detection in chat. Per-client notification language.

### Chrome Extension
- Embed assistant in any webpage
- Semantic search over page content
- Sales intelligence scraping

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Django 5, DRF, Python 3.12 |
| Frontend | React 19, Vite, Tailwind CSS |
| Database | PostgreSQL 16 + pgvector |
| Vector Search | Qdrant (primary), pgvector (fallback) |
| Queue | Celery + Redis |
| AI | LangChain, OpenAI API, Cohere, Anthropic, Ollama |
| MCP | FastMCP 2.0 (stdio transport) |
| Infrastructure | Docker Compose, Nginx, Gunicorn |

---

## Project Structure

```
.
├── backend/
│   ├── Jeeves/                  # Django project
│   │   ├── accounts/            # Users (4 roles: admin, owner, manager, client)
│   │   ├── agents/              # Agent config, sessions, logs, MCP orchestrator
│   │   ├── api/                 # Client-facing REST endpoints
│   │   ├── branches/            # Org hierarchy Level 1 + documents
│   │   ├── specializations/     # Org hierarchy Level 2 + documents
│   │   ├── clients/             # Tenants, channels, HITL, leads, QR codes
│   │   ├── concierge_platform/  # Platform defaults, feature flags, license
│   │   ├── EmbeddingModel/      # AI model registry (LLM + embedding pairs)
│   │   ├── mcp_hub/             # MCP server management + tool execution
│   │   ├── processing/          # Document parsing, chunking, embeddings
│   │   ├── rag/                 # RAG engine: vector search, context, LLM client
│   │   └── tools/               # Tool catalog + per-client connections
│   ├── mcp_servers/             # 8 standalone FastMCP servers
│   ├── chrome_extension/        # Browser extension source
│   ├── docker-compose.yml
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── pages/               # 37 pages (owner admin + client portal)
│   │   ├── components/          # UI components
│   │   ├── api/                 # Axios clients (auth, owner, client, agent, tools)
│   │   ├── context/             # Auth, Theme, Bootstrap providers
│   │   └── locales/             # 8 language translation files
│   ├── docker-compose.yml
│   └── Dockerfile
└── docs/
```

---

## Quick Start

See [SETUP.md](SETUP.md) for the full installation guide.

```bash
# 1. Clone and configure
git clone https://github.com/ChuprinaDaria/jeeves.git
cd jeeves
cp backend/.env.example backend/.env
# Edit backend/.env — set at minimum: SECRET_KEY, OPENAI_API_KEY

# 2. Start backend
cd backend && docker compose up -d

# 3. Run migrations + create admin
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser

# 4. Start frontend
cd ../frontend && docker compose up -d

# 5. Open dashboard
# http://localhost:3000
```

### Docker services

| Service | Port | Description |
|---------|------|-------------|
| `postgres` | 5433 | PostgreSQL 16 + pgvector |
| `redis` | 6380 | Cache + Celery broker |
| `web` | 8000 | Django API (Gunicorn) |
| `celery_worker` | — | Async task processing |
| `celery_beat` | — | Scheduled tasks |
| `qdrant` | 6333 | Vector search |
| `nginx` | 80 | Reverse proxy + static files |

---

## Licensing

Jeeves uses [Gumroad](https://gumroad.com) for license distribution. When you purchase the product, you get a license key that activates your instance during the setup wizard.

### How licensing works

1. Purchase on Gumroad — you get a license key
2. During first-time setup wizard, enter the key
3. Jeeves verifies it against Gumroad API
4. If verification fails (network issue), a 7-day grace period activates
5. Re-verify anytime at `/api/owner/license/reverify/`

### Removing the Gumroad license module

This project is open source. If you want to remove the Gumroad license validation entirely:

**1. Remove the license check from settings:**

In `backend/Jeeves/settings.py`, delete or comment out:

```python
# Line ~468-477
GUMROAD_PRODUCT_ID = os.environ.get("GUMROAD_PRODUCT_ID", "")

if not DEBUG and not GUMROAD_PRODUCT_ID:
    raise ImproperlyConfigured(
        "GUMROAD_PRODUCT_ID environment variable is required in production"
    )
```

**2. Remove license-related views:**

In `backend/Jeeves/concierge_platform/views_setup.py`, remove `SetupLicenseView` and any license verification logic from the setup wizard.

In `backend/Jeeves/concierge_platform/views_owner.py`, remove the `/api/owner/license/reverify/` endpoint.

**3. Remove the Gumroad client:**

Delete `backend/Jeeves/concierge_platform/gumroad_client.py`.

**4. Clean up the PlatformLicense model:**

In `backend/Jeeves/concierge_platform/models.py`, remove the `PlatformLicense` model and create a migration:

```bash
cd backend/Jeeves
python manage.py makemigrations concierge_platform
python manage.py migrate
```

**5. Remove frontend license checks:**

In `frontend/src/context/BootstrapContext.jsx`, remove the license status check from the bootstrap gate logic. The setup wizard steps related to license entry can be removed from the setup pages.

**6. Remove env variable:**

Remove `GUMROAD_PRODUCT_ID` from `backend/.env` and `backend/.env.example`.

After these changes, the platform will run without any license validation.

---

## Environment Variables

### Required

| Variable | Description |
|----------|------------|
| `SECRET_KEY` | Django secret key |
| `OPENAI_API_KEY` | OpenAI API key (or another LLM provider) |
| `GUMROAD_PRODUCT_ID` | Gumroad product ID (remove if self-hosting without license) |

### Optional

| Variable | Description |
|----------|------------|
| `ANTHROPIC_API_KEY` | Anthropic Claude API |
| `COHERE_API_KEY` | Cohere embeddings + reranking |
| `HUGGINGFACE_API_KEY` | Huggingface models |
| `USE_QDRANT` | Enable Qdrant vector search (default: True) |
| `QDRANT_HOST` | Qdrant hostname (default: qdrant) |
| `FIELD_ENCRYPTION_KEY` | Fernet key for credential encryption |
| `META_WABA_ID` | WhatsApp Business Account ID |
| `META_APP_ID` | Meta app ID |
| `META_ACCESS_TOKEN` | Meta access token |
| `TWILIO_ACCOUNT_SID` | Twilio SID (legacy WhatsApp) |
| `TWILIO_AUTH_TOKEN` | Twilio auth token |

---

## API Authentication

Two modes:

- **Owner/Admin** — JWT Bearer token (`Authorization: Bearer <token>`)
- **Client portal** — Client tag token (`X-Client-Token: <tag>`)

API documentation: `backend/docs/API_DOCUMENTATION.md`

---

## Background Tasks (Celery)

| Task | Schedule |
|------|----------|
| Check inactive chat sessions | Every 60 seconds |
| Send daily digest | Daily at 17:00 (Europe/Kyiv) |
| Check escalation timeouts | Every 5 minutes |

---

## CI/CD

GitHub Actions (`.github/workflows/main-tests.yml`):
- Backend: pytest with PostgreSQL (pgvector) + Redis
- Frontend: ESLint + production build
- Runs on push/PR to `main`

---

## Contributing

Pull requests welcome. See the project structure above and [CLAUDE.md](CLAUDE.md) for development conventions.

---

## License

See [LICENSE](LICENSE) for terms.
