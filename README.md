# Concierge AI Platform

Multi-tenant AI assistant platform with RAG, MCP tools, and a customizable dashboard.

Deploy your own AI assistant — **Jeeves** comes ready out of the box. Rename him, retrain him, make him yours.

## Features

- **RAG Knowledge Base** — upload documents, Concierge learns from them
- **MCP Tools** — extensible tool system (email, leads, sales intel, coaching, memory, xlsx, escalation)
- **Multi-tenant** — Branch → Specialization → Client hierarchy
- **Dashboard** — React admin panel with i18n (7 languages: en, de, da, nl, it, fr, es)
- **Chrome Extension** — AI assistant embedded in any webpage
- **Web Chat Widget** — embeddable chat for client websites
- **API-First** — full REST API built on Django REST Framework

## Tech Stack

- **Backend:** Django 5, DRF, PostgreSQL + pgvector, Redis, Celery
- **Frontend:** React 18, Vite, Tailwind CSS, i18next
- **AI:** LangChain, OpenAI API, Qdrant, Cohere (optional)
- **Infrastructure:** Docker Compose, Nginx

## Project Structure

```
.
├── backend/              Django + DRF + MCP servers
│   ├── Jeeves/           Django project (settings, urls, apps)
│   ├── mcp_servers/      Standalone MCP tool servers
│   ├── chrome_extension/ Browser extension source
│   └── docker-compose.yml
├── frontend/             React dashboard
│   ├── src/
│   └── docker-compose.yml
└── docs/                 Project documentation
```

## Quick Start

See [SETUP.md](SETUP.md) for the full installation guide.

```bash
# 1. Clone and configure
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
# edit both files — at minimum set OPENAI_API_KEY

# 2. Start services
cd backend && docker compose up -d
cd ../frontend && docker compose up -d

# 3. Create the first admin user
docker compose -f backend/docker-compose.yml exec web python manage.py migrate
docker compose -f backend/docker-compose.yml exec web python manage.py createsuperuser

# 4. Open the dashboard
open http://localhost:3000
```

## License

See [LICENSE](LICENSE) for terms.
