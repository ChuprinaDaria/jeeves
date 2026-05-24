# CI/CD Pipeline Setup

## Overview

This project has a full CI/CD pipeline with automated testing and deployment:

- **Main branch**: Runs tests with code coverage
- **Dev branch**: Automatic backend and frontend deployment

## Trigger Logic

The pipeline automatically detects what changed:

- If changes are **only in frontend** (`frontend/**`) — only frontend is deployed
- If changes are **only in backend** (`backend/**`) — only backend is deployed
- If changes are **in both** — both frontend and backend are deployed

## GitHub Secrets Configuration

Go to **Settings → Secrets and variables → Actions** and add:

### Backend Deployment Secrets

```bash
VPS_HOST=your.server.ip.or.domain
VPS_USER=deploy
VPS_SSH_PRIVATE_KEY=-----BEGIN OPENSSH PRIVATE KEY-----
...
-----END OPENSSH PRIVATE KEY-----
VPS_DOCKER_COMPOSE_PATH=/path/to/docker-compose.yml
```

### Frontend Deployment Secrets

```bash
FTP_HOST=your.ftp.host
FTP_USER=your_ftp_user
FTP_PASSWORD=your_ftp_password
FTP_DIR=/
VITE_API_URL=https://your-api-domain.com/api
```

## Workflow Structure

### Main Branch (`main-tests.yml`)

**Triggers:**
- Push to `main`
- Pull Request to `main`

**Jobs:**
1. **check-changes** — Detects what changed
2. **backend-tests** — Runs only if changes in `backend/**`
   - Tests with coverage
   - Coverage reports (XML, HTML)
3. **frontend-tests** — Runs only if changes in `frontend/**`
   - ESLint check
   - Production build

### Dev Branch (`dev-deploy.yml`)

**Triggers:**
- Push to `dev`

**Jobs:**
1. **check-changes** — Detects what changed
2. **deploy-backend** — Runs only if changes in `backend/**`
   - Safe deployment (preserves database volumes)
   - Health checks
   - Detailed logging
3. **deploy-frontend** — Runs only if changes in `frontend/**`
   - Production build
   - FTP deployment
   - Health check

## Backend Deployment Safety

The `deploy-backend-safe.sh` script **does NOT delete**:
- Database volumes (`postgres_data`)
- Static files volume (`static_volume`)
- Media files volume (`media_volume`)

It only:
- Rebuilds containers
- Runs migrations (safely)
- Collects static files

## Health Checks

### Backend Health Check

Verifies:
1. Docker container status
2. Database connection
3. Redis connection
4. API endpoint response
5. Error log inspection

### Frontend Health Check

Verifies:
1. Website accessibility

## Logging

All deployments have detailed logging:
- Timestamp for each operation
- Color-formatted output
- Logs saved on server
- GitHub Actions Summary

## Local Testing

### Testing Deployment Scripts

```bash
# Backend
cd backend
bash scripts/deploy-backend-safe.sh \
  --host your-server \
  --user deploy \
  --compose-path /path/to/docker-compose.yml

# Frontend
cd frontend
bash scripts/deploy-ftp-safe.sh \
  --host your-ftp-host \
  --user your-ftp-user \
  --pass your-password \
  --dir /
```

### Health Check

```bash
cd backend
bash scripts/health-check.sh \
  --host your-server \
  --user deploy \
  --url http://your-server:8000
```

## Usage Examples

### Frontend-only changes

```bash
git add frontend/src/pages/WebChatPage.jsx
git commit -m "Update chat page"
git push origin dev
```

**Result:** Only `deploy-frontend` job runs

### Backend-only changes

```bash
git add backend/Jeeves/clients/views.py
git commit -m "Update client views"
git push origin dev
```

**Result:** Only `deploy-backend` job runs

### Changes in both

```bash
git add frontend/ backend/
git commit -m "Update both frontend and backend"
git push origin dev
```

**Result:** Both jobs run in parallel

## Important

1. **Database volumes** are always preserved — data is never lost
2. **Secrets** must be configured in GitHub before the first deployment
3. **SSH key** must have passwordless access to the server
4. **FTP credentials** are stored in GitHub Secrets (never in code)

## Troubleshooting

### Backend deployment doesn't start

1. Check if there are changes in `backend/**`
2. Check the SSH key in secrets
3. Check server access permissions

### Frontend deployment doesn't start

1. Check if there are changes in `frontend/**`
2. Check FTP credentials in secrets
3. Check if `lftp` is installed on the runner

### Health check fails

1. Check container logs: `docker-compose logs`
2. Check port accessibility
3. Check database connection
