# Jeeves — Self-Hosted AI Assistant Platform

> Your own AI butler. Doesn't judge. Doesn't sleep. Occasionally hallucinates — but so does your best employee.

Multi-tenant AI concierge with RAG knowledge base, MCP tools, 5 messaging channels, and a full admin dashboard. Built on Django 5 + React 19. Fully open source, self-hosted, no license keys, no paywalls.

### Status

**Work in progress.** The project is functional but not finished. Bugs exist, some features are rough around the edges, and the documentation may lie to you. If something breaks — congratulations, you found a feature request. PRs, issues, and constructive complaints are very welcome.

---

## What It Does

Jeeves is a white-label AI assistant platform. Deploy it on your server, connect a knowledge base, plug in messaging channels (WhatsApp, Telegram, Email, Web Widget, Voice), and get an AI concierge that answers questions from your docs, captures leads, and escalates to humans when needed.

**Target audience:** agencies, service businesses, SaaS operators who need a customizable AI assistant without building one from scratch.

---

## Table of Contents

- [Features](#features)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Quick Start](#quick-start)
- [Dual-Agent Architecture](#dual-agent-architecture)
- [MCP Tool Servers](#mcp-tool-servers)
- [RAG Knowledge Base](#rag-knowledge-base)
- [Messaging Channels](#messaging-channels)
- [Admin Dashboard](#admin-dashboard)
- [API Reference](#api-reference)
- [Background Tasks](#background-tasks)
- [Security](#security)
- [Environment Variables](#environment-variables)
- [CI/CD](#cicd)
- [Contributing](#contributing)

---

## Features

### Core

- **RAG Knowledge Base** — upload documents (PDF, DOCX, TXT, CSV, JSON, images), automatic chunking + embedding + vector search
- **Dual-Agent System** — Assistant (full-power sandbox) + Consultant (customer-facing, lead-optimized)
- **9 MCP Tool Servers** — RAG search, email, leads, escalation, memory, coaching, sales intel, Excel generation, sequential thinking
- **5 Messaging Channels** — WhatsApp (Meta API + bridge), Telegram bot, Email (SMTP/IMAP), Web Widget (iframe), Voice/Telephony
- **HITL Escalation** — route unanswered questions to live managers via Telegram, with timeout and auto-close
- **Lead Capture** — automatic contact extraction, interest scoring (1-5), LLM-powered qualification
- **Multi-Tenant Hierarchy** — Branch > Specialization > Client, each with isolated documents and embeddings
- **Admin Dashboard** — full platform management with 37+ pages across owner admin and client portal

### Additional

- **Multi-Language UI** — 8 languages: English, German, French, Spanish, Italian, Dutch, Danish, Ukrainian
- **Automatic Language Detection** — AI responds in the customer's language
- **Chrome Extension** — embed assistant in any webpage, semantic search over page content, sales intelligence scraping
- **Web Chat Widget** — embeddable iframe chat for client websites, configurable appearance (light/dark), custom CSS
- **QR Code Generation** — dynamic QR codes per client for WhatsApp/Telegram linking
- **Conversation Analytics** — top questions, sentiment detection, recent activity, statistics
- **Conversation Ratings** — 1-5 star rating with automatic follow-up email on negative reviews
- **Conversation Notes** — manual notes per conversation for manager reference
- **Word Cloud** — trending terms from conversations
- **Image Analysis** — upload images to chat for vision-powered analysis
- **Custom Prompts** — per-client system prompt customization with prompt library and voting
- **Knowledge Blocks** — organize documents into logical groups
- **Web Parsing** — scrape URLs and ingest content into knowledge base
- **Daily Digest** — automated email summary of last 24h conversations (17:00 Europe/Kyiv)
- **Feature Flags** — per-client feature rollout (off / selected / all) with caching
- **Auto-Reply Rules** — per-channel auto-reply configuration (WhatsApp, Telegram, Email)
- **API Documentation** — auto-generated per client
- **News Feed** — in-app news/updates
- **Usage Tracking** — per-operation token + cost tracking, synced to external platform
- **Pixel Dashboard** — pixel event tracking status

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Django 5, Django REST Framework, Python 3.12 |
| Frontend | React 19, Vite 7, Tailwind CSS 3 |
| Database | PostgreSQL 16 + pgvector |
| Vector Search | Qdrant (primary), pgvector (fallback) |
| Queue | Celery + Redis |
| AI / LLM | OpenAI, Anthropic (Claude), Ollama (local), Kimi (Moonshot) |
| Embeddings | OpenAI, Cohere, Hugging Face, Ollama (local) |
| MCP | FastMCP 2.0 (stdio transport) |
| Infrastructure | Docker Compose, Nginx, Gunicorn |
| Auth | JWT (SimpleJWT), API Key, Client Token |
| Encryption | Fernet (EncryptedJSONField for credentials) |
| i18n | i18next (frontend), per-agent language config (backend) |
| CI/CD | GitHub Actions |

---

## Project Structure

```
.
├── backend/
│   ├── Jeeves/                      # Django project root
│   │   ├── accounts/                # Users (4 roles: admin, owner, manager, client), JWT auth
│   │   ├── agents/                  # AgentConfig, AgentSession, AgentLog, MCP orchestrator
│   │   ├── api/                     # Client-facing REST endpoints, bootstrap provisioning
│   │   ├── branches/                # Org hierarchy Level 1 + documents + embeddings
│   │   ├── specializations/         # Org hierarchy Level 2 + documents + embeddings
│   │   ├── clients/                 # Tenants, channels (WA/TG/Email/Widget), HITL, leads, QR codes
│   │   ├── concierge_platform/      # PlatformDefaults, FeatureFlag, SystemMessage
│   │   ├── EmbeddingModel/          # AI model registry (EmbeddingModel, LLMProvider, ModelPair)
│   │   ├── mcp_hub/                 # MCP server management + SSE streaming + tool execution
│   │   ├── processing/              # Document parsing, chunking, embedding, UsageStats, Celery tasks
│   │   ├── rag/                     # RAG engine: vector search, context builder, LLM client
│   │   └── tools/                   # ToolCard catalog, ToolConnection, EdgeMiddleware, InstalledMCPServer
│   ├── mcp_servers/                 # 9 standalone FastMCP servers (stdio)
│   │   ├── rag/                     # Semantic search over knowledge base
│   │   ├── escalation/              # HITL escalation to live managers
│   │   ├── email/                   # Send/read/search emails (SMTP/IMAP)
│   │   ├── leads/                   # Lead capture + qualification
│   │   ├── memory/                  # Persistent conversational memory (Qdrant + Cohere)
│   │   ├── coaching/                # AI coaching + gap analysis
│   │   ├── sales_intel/             # Website scraping + tech stack detection
│   │   ├── xlsx/                    # Excel generation with formulas (LibreOffice)
│   │   └── common/                  # Shared Django ORM bootstrap
│   ├── chrome_extension/            # Browser extension source (content + background scripts)
│   ├── docker-compose.yml
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── pages/                   # 37+ pages (owner admin + client portal + setup wizard)
│   │   ├── components/              # UI components (layout, forms, chat, integrations, tools)
│   │   ├── api/                     # Axios clients (auth, owner, client, agent, tools, embedding)
│   │   ├── context/                 # AuthContext, ThemeContext, BootstrapContext
│   │   ├── locales/                 # 8 language translation files (en/de/fr/es/it/nl/da/uk)
│   │   └── modules/                 # Experimental modules (pixel dashboard)
│   ├── docker-compose.yml
│   └── Dockerfile
├── docs/                            # Development plans + specs
├── CLAUDE.md                        # Instructions for Claude Code
├── SETUP.md                         # Full installation guide
└── .github/workflows/               # CI/CD (pytest + eslint + build)
```

---

## Quick Start

See [SETUP.md](SETUP.md) for the full installation guide.

```bash
# 1. Clone and configure
git clone https://github.com/ChuprinaDaria/jeeves.git
cd jeeves
make setup                # copies .env.example files
# Edit backend/.env — set SECRET_KEY, FIELD_ENCRYPTION_KEY, OPENAI_API_KEY

# 2. Start all services
make up                   # docker compose up -d
make migrate              # run database migrations
make superuser            # create admin account

# 3. Open dashboard
# http://localhost:3000
```

Or manually:

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
cd backend && docker compose up -d
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser
cd ../frontend && docker compose up -d
```

### Docker Services

| Service | Port | Description |
|---------|------|-------------|
| `postgres` | 5433 | PostgreSQL 16 + pgvector |
| `redis` | 6380 | Cache + Celery broker |
| `web` | 8000 | Django API (Gunicorn) |
| `celery_worker` | — | Async task processing |
| `celery_beat` | — | Scheduled tasks (digest, escalation timeouts, session cleanup) |
| `qdrant` | 6333 | Vector search (optional, enabled via `USE_QDRANT`) |
| `nginx` | 80 | Reverse proxy + static files |

---

## Dual-Agent Architecture

Jeeves runs two agent personas with different capabilities:

### Assistant (Sandbox)

Full-power agent for business owners. Available in the dashboard Sandbox.

- Access to all MCP tools (RAG, email, leads, memory, coaching, sales intel, xlsx)
- Business operations focus
- Full conversation context

### Consultant / Concierge (Messengers)

Customer-facing agent optimized for lead capture. Runs on WhatsApp, Telegram, Web Widget.

- Limited tool scope (RAG, escalation, leads, memory)
- Passive/Warm/Hot lead engagement strategies
- Natural lead qualification without being pushy
- Automatic escalation to human managers

### Orchestrator Flow

```
User message → Build system prompt + history
             → LLM call with available MCP tools (OpenAI function schema)
             → If tool call returned: execute via MCP → feed result back → repeat
             → If final text: return response
             → Log everything to AgentLog
             → Max 10 iterations (prevents infinite loops)
```

Auto-injected parameters (hidden from LLM): `client_id`, `session_id`, `user_id`.

### AgentConfig (per-client)

Each client gets an `AgentConfig` with customizable settings:

- `language` — conversation language
- `temperature` — creativity (0-1)
- `max_tokens` — response length limit
- `system_prompt` — custom prompt (falls back to `PlatformDefaults`)
- LLM provider + embedding model selection

---

## MCP Tool Servers

9 FastMCP servers running as stdio subprocesses. Each bootstraps Django ORM through `mcp_servers.common.django_setup`.

| Server | Scope | Tools | Description |
|--------|-------|-------|-------------|
| `rag` | assistant, manager | `search_knowledge_base` | Semantic search over the knowledge base (Qdrant or pgvector) |
| `escalation` | assistant, manager | `escalate_to_manager`, `check_escalation_status` | Route unanswered questions to live managers via Telegram |
| `email` | assistant | `send_email`, `read_emails`, `search_emails`, `analyze_emails` | Send/read/search emails via client SMTP/IMAP |
| `leads` | manager, leads | `capture_lead`, `qualify_lead`, `update_lead` | Lead capture, qualification, interest scoring |
| `memory` | assistant, manager | `save_memory`, `search_memory`, `clear_memory` | Persistent conversational memory (Qdrant + Cohere embeddings) |
| `coaching` | assistant | `analyze_gaps`, `generate_coaching_plan` | AI coaching, gap analysis, skill development |
| `sales_intel` | assistant | `scrape_website`, `detect_tech_stack`, `research_company` | Website scraping and company research |
| `xlsx` | assistant | `generate_xlsx`, `add_worksheet`, `add_formula` | Excel generation with formulas (uses LibreOffice for recalc) |
| `sequential-thinking` | assistant | `think` | Chain-of-thought reasoning (npm: `@modelcontextprotocol/server-sequential-thinking`) |

**Scopes** control which tools are available to which agent:
- `assistant` — full tools in Sandbox
- `manager` — limited tools for customer-facing Consultant
- `leads` — lead-specific tools only

Configured in `settings.py` under `MCP_SERVERS` and `MCP_TOOL_SCOPES`.

---

## RAG Knowledge Base

### Document Processing Pipeline

1. **Upload** — PDF, DOCX, TXT, CSV, JSON, JPG, PNG, GIF, WEBP
2. **Parsing** — pdfplumber (PDF), python-docx (DOCX), standard parsers (CSV/JSON), Vision API (images)
3. **Chunking** — recursive token-based splitter (default 512 tokens, 128 overlap), metadata preserved
4. **Embedding** — via configurable provider (OpenAI, Cohere, Hugging Face, Ollama)
5. **Storage** — Qdrant (primary) or pgvector (fallback)
6. **Indexing** — Celery tasks with rate limiting (10/min)

### Multi-Level Search

Documents are organized in a three-level hierarchy with weighted search:

| Level | Weight | Description |
|-------|--------|-------------|
| Client | 0.8 | Client-specific documents (highest priority) |
| Specialization | 0.5 | Domain-specific shared docs |
| Branch | 0.3 | Regional shared docs |

- Similarity threshold: 0.1 (configurable)
- Max results: 5 per level
- Context window: max 2000 tokens (fits 4096 token limit with prompt + response)
- Optional Cohere reranking for better relevance

### Vector Search Backends

**Qdrant** (primary, `USE_QDRANT=true`):
- Collection: `jeeves_embeddings`
- Metadata filtering by client_id, level, etc.
- Payload storage, snapshot backup

**pgvector** (fallback):
- Cosine distance similarity
- IVFFlat or HNSW indexing

### Knowledge Organization

- **Knowledge Blocks** — group documents into logical collections
- **Web Parsing** — scrape URLs and ingest content automatically
- **Reindexing** — full reindex or incremental (new docs only)

---

## Messaging Channels

### WhatsApp (Meta Business API)

- **Webhook**: `POST /api/whatsapp/meta/webhook/`
- **Security**: X-Hub-Signature-256 (HMAC-SHA256) verification
- Message handling (text + media), conversation tracking
- QR code linking to clients, auto-reply rules
- Sentiment detection with negative rating escalation
- Lead capture, RAG-powered responses, HITL escalation
- Zero-touch configuration (`ClientZeroConfig`)
- Legacy Twilio bridge support

### Telegram

- **Webhook**: `POST /api/clients/telegram/webhook/`
- **Security**: X-Telegram-Bot-Api-Secret-Token verification
- `/start` command (welcome + QR linking), `/start2` (custom linking)
- Callback queries (inline button handling)
- Manager replies via forwarding
- Conversation history, sentiment analysis, lead capture

### Email (SMTP/IMAP)

- Send emails via client SMTP (encrypted credentials)
- Read + search emails via IMAP
- Analyze email sentiment/intent via LLM
- Daily digest (automated at 17:00 Europe/Kyiv, or manual trigger)
- Negative rating follow-up emails

### Web Widget

- **Script**: `/widget/chat.js` (inject into any page)
- **Iframe**: `/widget/chat` (embedded chat)
- Configurable domain restriction, light/dark mode, custom CSS
- Conversation history (localStorage), image upload + analysis
- Lead capture, RAG-powered responses

### Voice / Telephony

- Voice configuration per client
- Multiple voice providers + voice selection
- HITL escalation for complex calls
- Endpoints: `/api/clients/telephony/*`

---

## Admin Dashboard

### Owner Portal (`/owner/*`)

Platform-wide administration. Protected by `BootstrapGate` (checks setup completion).

| Page | What it does |
|------|-------------|
| Dashboard | Platform statistics, overview |
| Clients | CRUD clients, stats per client, API key generation |
| Branches | Manage org hierarchy Level 1 |
| Specializations | Manage org hierarchy Level 2 |
| AI Providers > LLM | Configure LLM providers (OpenAI, Anthropic, Ollama, Kimi) + test connections |
| AI Providers > Embeddings | Configure embedding models (OpenAI, Cohere, HF, Ollama) + test connections |
| AI Providers > Pairs | Assign LLM + embedding model pairs |
| Tools | Tool catalog management, discovery, URL import |
| MCP Servers | MCP server configuration |
| Feature Flags | Per-client feature toggles (off / selected / all) |
| System Messages | Multi-language system prompts (default, assistant, consultant) |
| Settings | Platform defaults (temperature, max_tokens, language, etc.) |
| Setup Wizard | First-time setup: owner account creation |

### Client Portal (`/l/:tag/*`)

Per-client management. Authenticated via `X-Client-Token` header.

| Page | What it does |
|------|-------------|
| Dashboard | Stats, top questions, recent activity, web conversations |
| History | Conversation browser with date/channel filter, search, sentiment |
| Tools | Connected tools, flow canvas visual editor, edge middleware |
| Integrations | WhatsApp QR, Telegram token, Email SMTP config, Widget config |
| Leads | Lead list, detail view, scoring, qualification status |
| Training | Prompt library, create/edit prompts, vote on suggestions |
| Sandbox | Test RAG queries, upload files, image analysis, live chat |
| Settings | Language, theme, profile, logo upload |

---

## API Reference

Full documentation: [`backend/docs/API_DOCUMENTATION.md`](backend/docs/API_DOCUMENTATION.md)

### Authentication Modes

| Mode | Header | Used by |
|------|--------|---------|
| JWT Bearer | `Authorization: Bearer <token>` | Owner/Admin dashboard |
| Client Token | `X-Client-Token: <tag>` | Client portal, web widget |
| API Key | `X-API-Key: <key>` | External API clients, webhooks |

### Key Endpoints

#### Auth
- `POST /api/accounts/register/` — register user
- `POST /api/accounts/login/` — JWT login
- `POST /api/accounts/refresh/` — refresh JWT
- `GET /api/accounts/me/` — current user profile

#### RAG & Chat
- `POST /api/rag/query/` — query knowledge base
- `POST /api/rag/chat/` — RAG chat (supports image analysis)
- `POST /api/mcp/chat/` — MCP chat (SSE streaming, full agent orchestration)
- `POST /api/rag/upload/` — upload document

#### Client Management
- `GET /api/clients/conversations/` — list conversations
- `GET /api/clients/conversations/statistics/` — aggregated stats
- `GET /api/clients/top-questions/` — most asked questions
- `GET /api/clients/leads/` — list captured leads
- `GET /api/clients/documents/` — list documents
- `GET /api/clients/knowledge-blocks/` — list knowledge blocks
- `POST /api/clients/reports/daily-digest/send/` — trigger daily digest

#### Owner Admin
- `GET /api/owner/dashboard/stats/` — platform statistics
- `CRUD /api/owner/clients/` — manage clients
- `CRUD /api/owner/branches/` — manage branches
- `CRUD /api/owner/specializations/` — manage specializations
- `CRUD /api/owner/ai-providers/llm/` — manage LLM providers
- `CRUD /api/owner/ai-providers/embeddings/` — manage embedding models
- `CRUD /api/owner/ai-providers/pairs/` — manage model pairs
- `CRUD /api/owner/tools/` — manage tool catalog
- `CRUD /api/owner/feature-flags/` — manage feature flags
- `CRUD /api/owner/system-messages/` — manage system messages
- `GET|PUT /api/owner/settings/defaults/` — platform defaults

#### Channel Config
- `GET|POST|PATCH /api/clients/whatsapp/meta/config/` — WhatsApp Meta config
- `GET|POST|PATCH /api/clients/telegram/config/` — Telegram config
- `GET|POST /api/clients/email-smtp/config/` — Email SMTP config
- `GET|POST|PATCH /api/clients/web-widget/config/` — Web Widget config
- `GET|POST /api/clients/hitl/config/` — HITL escalation config
- `CRUD /api/clients/telephony/` — voice/telephony config
- `GET|PUT /api/clients/channel-auto-reply/<channel>/` — auto-reply rules

#### Tools
- `GET /api/tools/catalog/` — tool catalog
- `POST /api/tools/<slug>/connect/` — connect tool
- `POST /api/tools/<slug>/disconnect/` — disconnect tool
- `GET /api/tools/my/` — connected tools
- `CRUD /api/tools/flow/connections/` — flow canvas connections
- `CRUD /api/tools/flow/edges/<conn_id>/middleware/` — edge middleware

#### Setup
- `POST /api/setup/owner/` — create first owner account
- `POST /api/setup/complete/` — mark setup complete

200+ total endpoints. See [`backend/docs/API_DOCUMENTATION.md`](backend/docs/API_DOCUMENTATION.md) for the complete list.

---

## Background Tasks

### Periodic (Celery Beat)

| Task | Schedule | Description |
|------|----------|-------------|
| `check_inactive_chat_sessions` | Every 60 seconds | Detect + clean up idle conversations |
| `send_daily_digest` | Daily at 17:00 (Europe/Kyiv) | Email summary of last 24h to client contacts |
| `check_escalation_timeouts` | Every 5 minutes | Auto-close expired HITL escalations |

### Document Processing (Celery Worker)

| Task | Description |
|------|-------------|
| `process_client_document` | Parse + chunk + embed client document |
| `process_branch_document` | Parse + chunk + embed branch document |
| `process_specialization_document` | Parse + chunk + embed specialization document |

Rate limited: 10 tasks/minute per model type. Cost tracked in `UsageStats`.

---

## Security

### Authentication

- **JWT** — access (24h) + refresh (7d) tokens with rotation
- **API Key** — per-client `ClientAPIKey` model, `X-API-Key` header
- **Client Token** — tag-based auth for portal + widget

### Role-Based Access Control

4 roles with view-level permission checks:

| Role | Access |
|------|--------|
| `ADMIN` | Full platform access |
| `OWNER` | Platform admin dashboard, all clients |
| `MANAGER` | HITL escalation, assigned clients |
| `CLIENT` | Own portal only |

### Webhook Security

- **WhatsApp Meta**: X-Hub-Signature-256 (HMAC-SHA256 with `META_APP_SECRET`)
- **Telegram**: X-Telegram-Bot-Api-Secret-Token header
- **Bootstrap**: X-Bootstrap-Signature (HMAC-SHA256, 5-minute validity)

### Data Protection

- **EncryptedJSONField** — Fernet encryption for tool credentials, API configs, SMTP passwords
- **Field encryption key** — `FIELD_ENCRYPTION_KEY` env var (base64-encoded Fernet key)
- `.env` files never committed to git

---

## Environment Variables

### Required

| Variable | Description |
|----------|------------|
| `SECRET_KEY` | Django secret key (generate: `python -c "import secrets; print(secrets.token_urlsafe(50))"`) |
| `FIELD_ENCRYPTION_KEY` | Fernet key for credential encryption (generate: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`) |
| `OPENAI_API_KEY` | OpenAI API key (or configure another LLM provider) |

### Database

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_NAME` | `admin_db` | PostgreSQL database name |
| `DB_USER` | `admin_user` | Database user |
| `DB_PASS` | — | Database password |
| `DB_HOST` | `postgres` | Database host |
| `DB_PORT` | `5432` | Database port |

### AI Providers

| Variable | Description |
|----------|------------|
| `ANTHROPIC_API_KEY` | Anthropic Claude API |
| `COHERE_API_KEY` | Cohere embeddings + reranking |
| `HUGGINGFACE_API_KEY` | Hugging Face models |
| `KIMI_API_KEY` | Kimi (Moonshot) API |

### Vector Search

| Variable | Default | Description |
|----------|---------|-------------|
| `USE_QDRANT` | `True` | Enable Qdrant vector search |
| `QDRANT_HOST` | `qdrant` | Qdrant hostname |
| `QDRANT_COLLECTION` | `jeeves_embeddings` | Qdrant collection name |
| `QDRANT_PORT` | `6333` | Qdrant port |

### Security

| Variable | Description |
|----------|------------|
| `FIELD_ENCRYPTION_KEY` | Base64 Fernet key for credential encryption |
| `BOOTSTRAP_SECRET` | HMAC secret for bootstrap webhook verification |

### Messaging

| Variable | Description |
|----------|------------|
| `META_WABA_ID` | WhatsApp Business Account ID |
| `META_APP_ID` | Meta app ID |
| `META_APP_SECRET` | Meta app secret (webhook signature verification) |
| `META_ACCESS_TOKEN` | Meta access token |
| `TWILIO_ACCOUNT_SID` | Twilio SID (legacy WhatsApp) |
| `TWILIO_AUTH_TOKEN` | Twilio auth token |

### Infrastructure

| Variable | Default | Description |
|----------|---------|-------------|
| `CELERY_BROKER_URL` | `redis://redis:6379/0` | Celery broker |
| `CELERY_RESULT_BACKEND` | `redis://redis:6379/0` | Celery results |
| `CORS_ALLOWED_ORIGINS` | — | Frontend origins (comma-separated) |
| `CSRF_TRUSTED_ORIGINS` | — | Trusted origins for CSRF |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1,web,nginx` | Django allowed hosts |
| `DEBUG` | `True` | Debug mode (set `False` in production) |

---

## CI/CD

GitHub Actions (`.github/workflows/main-tests.yml`):

- **Backend**: pytest with PostgreSQL (pgvector) + Redis services
- **Frontend**: ESLint + production build
- Runs on push/PR to `main`

### Production Checklist

- [ ] Set `DEBUG=False`
- [ ] Generate fresh `SECRET_KEY`
- [ ] Configure `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `CORS_ALLOWED_ORIGINS`
- [ ] Set up HTTPS (Nginx + Let's Encrypt or Caddy)
- [ ] Enable automated PostgreSQL backups
- [ ] Generate `FIELD_ENCRYPTION_KEY`
- [ ] Rotate all API keys

---

## LLM Providers

### Supported

| Provider | Type | Default Model |
|----------|------|---------------|
| OpenAI | `openai` | gpt-4o-mini |
| Anthropic | `anthropic` | Claude family |
| Ollama (main) | `ollama_main` | qwen2.5:7b |
| Ollama (light) | `ollama_light` | qwen2.5:1.5b |
| Kimi (Moonshot) | `kimi` | Advanced reasoning |

### Configuration Priority

1. `client.llm_provider_model` (FK to LLMProvider) — preferred
2. `client.llm_provider` + `client.llm_model_name` — legacy
3. `LLM_CONFIG` default — fallback

### Embedding Models

| Provider | Models |
|----------|--------|
| OpenAI | text-embedding-3-small, text-embedding-3-large |
| Ollama | bge-m3, nomic-embed-text |
| Hugging Face | Via transformers |
| Cohere | embed-multilingual-v3.0 (reranking support) |

---

## Contributing

Jeeves is free forever and actively developed. Pull requests, bug reports, and feature ideas are welcome.

- **[CONTRIBUTING.md](CONTRIBUTING.md)** — how to set up, code style, PR process
- **[SETUP.md](SETUP.md)** — local development setup
- **[SECURITY.md](SECURITY.md)** — reporting vulnerabilities
- **[Code of Conduct](CODE_OF_CONDUCT.md)** — community standards

Found a bug? [Open an issue.](https://github.com/ChuprinaDaria/jeeves/issues)

---

## License

Elastic License 2.0 — See [LICENSE](LICENSE) for full terms.

**In short:**
- **Free forever** — use, deploy, modify for yourself or your organization
- **Don't sell it** — you may not provide Jeeves as a hosted/managed service to third parties
- **Keep the branding** — the "Jeeves" name and attribution footer must remain intact

Jeeves — by Daria Chuprina & open-source community. Forever free.
