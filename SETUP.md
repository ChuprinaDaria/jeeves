# Jeeves — Setup Guide

This guide walks through installing Concierge locally via Docker Compose.

## Prerequisites

- **Docker** 24+ and **Docker Compose** v2
- **Node.js** 20+ (only needed if you want to run the frontend outside Docker)
- **Python** 3.12+ (only needed if you want to run the backend outside Docker)
- An **OpenAI API key** (or Anthropic / Cohere — at least one LLM provider)

## 1. Clone the repository

```bash
git clone <your-repo-url> concierge
cd concierge
```

## Quick start (recommended)

```bash
make setup     # copies .env.example files
# Edit backend/.env — add your API keys and FIELD_ENCRYPTION_KEY
make up        # starts all services
make migrate   # runs database migrations
make superuser # creates your admin account
```

For all available commands, see the [Makefile](Makefile).

## 2. Configure environment

### Backend

```bash
cp backend/.env.example backend/.env
```

Edit `backend/.env` and set at minimum:

```env
SECRET_KEY=<generate-a-random-string>
OPENAI_API_KEY=sk-...
```

Generate a Django `SECRET_KEY`:

```bash
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

### Frontend

```bash
cp frontend/.env.example frontend/.env
```

The defaults point the dashboard at `http://localhost:8000/api` — no change needed for local development.

## 3. Start the services

```bash
cd backend
docker compose up -d
```

This brings up:

- **postgres** (with pgvector) on port `5433`
- **redis** on port `6380`
- **web** (Django + Gunicorn) on port `8000`
- **celery_worker** and **celery_beat** for background tasks
- **qdrant** for vector search

Wait for migrations to finish:

```bash
docker compose logs -f web
# look for "Listening at: http://0.0.0.0:8000"
```

Then start the frontend:

```bash
cd ../frontend
docker compose up -d
```

The dashboard will be served on `http://localhost:3000`.

## 4. Create the first admin user

```bash
cd ../backend
docker compose exec web python manage.py createsuperuser
```

## 5. Log in and create your first client

1. Open `http://localhost:3000`
2. Log in with the superuser credentials
3. Navigate to **Clients** → **New client**
4. Fill in the required fields; leave `custom_system_prompt` empty to use the default (Jeeves)
5. Upload a few documents to the knowledge base
6. Open the **Sandbox** to chat with your new assistant

## 6. (Optional) Install the Chrome extension

The extension ZIP is served at:

```
http://localhost:3000/static/extensions/concierge-chrome-extension.zip
```

To load it as an unpacked extension:

1. Download and unzip
2. Open `chrome://extensions`
3. Toggle **Developer mode**
4. Click **Load unpacked** and select the extracted folder

## Troubleshooting

**`pgvector` extension not available**
The `postgres` service uses the `pgvector/pgvector:pg16` image which has the extension preinstalled. If you swap images, run `CREATE EXTENSION vector;` manually in the database.

**Qdrant connection errors**
Verify `QDRANT_HOST` in `backend/.env` matches the service name in `docker-compose.yml` (default: `qdrant`).

**CORS errors in the dashboard**
Add your frontend origin to `CORS_ALLOWED_ORIGINS` in `backend/.env`, then restart the `web` service.

**Celery tasks not running**
Check that `celery_worker` and `celery_beat` are up: `docker compose ps`. Logs: `docker compose logs celery_worker`.

## Production checklist

Before deploying to production:

- [ ] Set `DEBUG=False`
- [ ] Generate a fresh `SECRET_KEY`
- [ ] Configure `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `CORS_ALLOWED_ORIGINS`
- [ ] Set up HTTPS (Caddy or Nginx + Let's Encrypt)
- [ ] Enable automated PostgreSQL backups
- [ ] Review Celery beat schedule for your use case
- [ ] Rotate any third-party API keys that were committed during development

## For contributors

See [CONTRIBUTING.md](CONTRIBUTING.md) for code style, testing, and PR guidelines.
