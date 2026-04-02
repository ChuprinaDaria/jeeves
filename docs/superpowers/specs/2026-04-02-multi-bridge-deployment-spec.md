# Multi-Bridge Deployment Spec

**Date:** 2026-04-02
**Branch:** `feature/sp1-mcp-core-engine`
**What:** Deploy Meta (Facebook Messenger + Instagram DM) and LinkedIn bridges via mautrix, with Oleg dynamic connection management.

---

## Servers Involved

| Server | IP | User | Purpose | Path |
|--------|-----|------|---------|------|
| **Backend** | 188.34.143.153 | dc | Django API + Docker | `/opt/p004_ai_nexelin/p004_ai_nexelin/` |
| **Matrix** | 195.201.202.162 | dc | Synapse + mautrix bridges | `/opt/matrix/` |
| **Frontend** | 85.13.135.71 | — | React app (FTP deploy) | FTP: w020c360.kasserver.com |

---

## Deploy Order (STRICT — follow this sequence)

### Phase 1: Matrix Server (195.201.202.162)

#### 1.1 Pull new configs

```bash
ssh dc@195.201.202.162
cd /opt/matrix

# Copy new bridge configs and files from the repo
# (assumes repo is cloned or files are transferred)
```

Transfer these files from repo `matrix-stack/` to `/opt/matrix/`:

| Source (repo) | Destination (server) |
|---------------|---------------------|
| `matrix-stack/meta-facebook/config.yaml` | `/opt/matrix/meta-facebook/config.yaml` |
| `matrix-stack/meta-instagram/config.yaml` | `/opt/matrix/meta-instagram/config.yaml` |
| `matrix-stack/linkedin/config.yaml` | `/opt/matrix/linkedin/config.yaml` |
| `matrix-stack/init-mautrix-dbs.sql` | `/opt/matrix/init-mautrix-dbs.sql` |
| `matrix-stack/setup-bridges.sh` | `/opt/matrix/setup-bridges.sh` |
| `matrix-stack/docker-compose.yml` | `/opt/matrix/docker-compose.yml` |
| `matrix-stack/synapse/homeserver.yaml` | `/opt/matrix/synapse/homeserver.yaml` |

#### 1.2 Create databases manually

The `init-mautrix-dbs.sql` only runs on first postgres init. Since postgres-mautrix already exists, create DBs manually:

```bash
# Connect to existing postgres-mautrix container
docker exec -it grot-postgres-mautrix psql -U mautrix -d mautrix_whatsapp

# Inside psql:
CREATE DATABASE mautrix_meta_facebook;
CREATE DATABASE mautrix_meta_instagram;
CREATE DATABASE mautrix_linkedin;
\q
```

#### 1.3 Update config.yaml files with real passwords

Each config.yaml has `${POSTGRES_MAUTRIX_PASSWORD}` placeholder. Replace with actual password:

```bash
# Get the current password
echo $POSTGRES_MAUTRIX_PASSWORD
# OR check existing mautrix-whatsapp config:
grep 'uri:' /opt/matrix/mautrix-whatsapp/config.yaml

# Replace in all new configs
PASS="<actual_password>"
sed -i "s/\${POSTGRES_MAUTRIX_PASSWORD}/$PASS/g" /opt/matrix/meta-facebook/config.yaml
sed -i "s/\${POSTGRES_MAUTRIX_PASSWORD}/$PASS/g" /opt/matrix/meta-instagram/config.yaml
sed -i "s/\${POSTGRES_MAUTRIX_PASSWORD}/$PASS/g" /opt/matrix/linkedin/config.yaml
```

#### 1.4 Start new bridge containers (one at a time)

Each bridge generates a `registration.yaml` on first run:

```bash
cd /opt/matrix

# Start meta-facebook — will generate registration.yaml and stop
docker compose up mautrix-meta-facebook
# Wait for it to generate /opt/matrix/meta-facebook/registration.yaml
# Ctrl+C when you see "registration.yaml generated" or similar

# Start meta-instagram
docker compose up mautrix-meta-instagram
# Wait for registration.yaml generation, Ctrl+C

# Start linkedin
docker compose up mautrix-linkedin
# Wait for registration.yaml generation, Ctrl+C
```

#### 1.5 Copy registration files to Synapse

```bash
chmod +x /opt/matrix/setup-bridges.sh
cd /opt/matrix
./setup-bridges.sh
```

This copies:
- `meta-facebook/registration.yaml` → `synapse/meta-facebook-registration.yaml`
- `meta-instagram/registration.yaml` → `synapse/meta-instagram-registration.yaml`
- `linkedin/registration.yaml` → `synapse/linkedin-registration.yaml`

#### 1.6 Restart all services

```bash
cd /opt/matrix
docker compose down
docker compose up -d
```

#### 1.7 Verify bridges are running

```bash
docker compose ps
# All services should be "Up" including:
# - grot-mautrix-meta-facebook
# - grot-mautrix-meta-instagram
# - grot-mautrix-linkedin

# Check health
curl -sf http://localhost:29319/_matrix/provision/v3/whoami && echo "FB OK"
curl -sf http://localhost:29320/_matrix/provision/v3/whoami && echo "IG OK"
curl -sf http://localhost:29321/_matrix/provision/v3/whoami && echo "LI OK"
```

#### 1.8 Note provisioning secrets

Each bridge generates a provisioning secret in its config.yaml on first run. You'll need these for Django `BridgeConfig`:

```bash
grep 'shared_secret:' /opt/matrix/meta-facebook/config.yaml
grep 'shared_secret:' /opt/matrix/meta-instagram/config.yaml
grep 'shared_secret:' /opt/matrix/linkedin/config.yaml
```

Save these values — they go into Django admin in Phase 2.

---

### Phase 2: Backend Server (188.34.143.153)

#### 2.1 Deploy code

```bash
ssh dc@188.34.143.153
cd /opt/p004_ai_nexelin

# Pull latest
git fetch origin feature/sp1-mcp-core-engine
git checkout feature/sp1-mcp-core-engine
git pull

# Copy tracked code to MASTER/ (production uses untracked MASTER/)
cp -r p004_ai_nexelin/MASTER/* MASTER/
```

#### 2.2 Run migrations

```bash
# Enter the Django container
docker compose exec web bash

# Inside container:
python manage.py migrate clients
python manage.py migrate tools

# Expected output:
# Applying clients.0058_bridge_config_models... OK
# Applying clients.0059_seed_bridge_configs... OK
# Applying clients.0060_encrypt_matrix_access_token... OK
# Applying tools.0016_seed_meta_linkedin_tools... OK
```

#### 2.3 Verify seed data

```bash
# Still inside container:
python manage.py shell -c "
from MASTER.clients.models_bridge import BridgeConfig
for c in BridgeConfig.objects.all():
    print(f'{c.bridge_type}: enabled={c.is_enabled}')
"
# Expected: 3 configs, all enabled=False

python manage.py shell -c "
from MASTER.tools.models import ToolCard
for t in ToolCard.objects.filter(slug__in=['meta-facebook','meta-instagram','linkedin']):
    print(f'{t.slug}: {t.name}')
"
# Expected: meta-facebook, meta-instagram, linkedin
```

#### 2.4 Rebuild and restart Docker

```bash
exit  # exit container
docker compose down
docker compose up -d --build
```

#### 2.5 Configure BridgeConfig via Django Admin

Go to `https://api.nexelin.com/admin/` and edit each `BridgeConfig`:

**Facebook Messenger:**
- `is_enabled`: True
- `provisioning_url`: `http://195.201.202.162:29319` (Matrix server IP)
- `provisioning_secret`: (from Phase 1.8)
- Keep other fields as seeded

**Instagram DM:**
- `is_enabled`: True
- `provisioning_url`: `http://195.201.202.162:29320`
- `provisioning_secret`: (from Phase 1.8)

**LinkedIn Messages:**
- `is_enabled`: True
- `provisioning_url`: `http://195.201.202.162:29321`
- `provisioning_secret`: (from Phase 1.8)

#### 2.6 Ensure env vars

Check that these are in the `.env` file on the backend server:

```bash
# Already should exist:
FIELD_ENCRYPTION_KEY=<fernet_key>

# Must exist for bridge message auth:
INTEGRATION_SERVICE_TOKEN=<same_token_as_in_integration_service>
```

If `INTEGRATION_SERVICE_TOKEN` is missing, generate one:
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Add to `.env` and also set the same value in the Integration Service config on the Matrix server.

---

### Phase 3: Integration Service (195.201.202.162)

#### 3.1 Update Go binary

The Integration Service needs to be rebuilt with the new bridge routing code.

```bash
ssh dc@195.201.202.162
cd /opt/matrix/services/integration-service

# Pull changes
git pull

# Build
go build -o integration-service ./cmd/server/

# Restart
systemctl restart integration-service
# OR if running via docker:
docker compose restart integration-service
```

#### 3.2 Verify universal message endpoint

```bash
# Test that the new endpoint responds (should return 403 without token)
curl -X POST http://localhost:PORT/api/v1/clients/bridges/message/ \
  -H "Content-Type: application/json" \
  -d '{"client_id": 1, "bridge_type": "meta-instagram"}'
# Expected: 403 Forbidden
```

---

### Phase 4: Frontend (85.13.135.71)

#### 4.1 Add env vars

In `nextlen/.env.production` (or wherever frontend env is):

```
VITE_NEXELIN_EXTENSION_ID=<chrome_extension_id>
```

This is the Chrome extension ID from the Chrome Web Store (or from `chrome://extensions` in developer mode).

#### 4.2 Build and deploy

```bash
cd nextlen
npm run build:prod
# Deploy via FTP
./deploy-ftp.sh
```

---

### Phase 5: Chrome Extension

#### 5.1 Update extension

The extension needs to be rebuilt and published with new permissions (cookies, externally_connectable).

```bash
cd p004_ai_nexelin/chrome_extension
# Zip for Chrome Web Store upload or load unpacked in dev mode
```

New manifest changes:
- Added `"cookies"` permission
- Added `"externally_connectable"` for localhost, nexelin.com, grot.de
- Version bumped to 0.3.0

**IMPORTANT:** Users must update/reinstall the extension to get cookie extraction. Without the updated extension, Meta/LinkedIn bridge auth won't work.

---

## Verification Checklist

After all phases complete:

- [ ] `docker compose ps` on Matrix server shows all 4 bridges running (whatsapp, meta-facebook, meta-instagram, linkedin)
- [ ] Health checks pass: `curl -sf http://195.201.202.162:29319/_matrix/provision/v3/whoami`
- [ ] Django admin shows 3 `BridgeConfig` entries with `is_enabled=True`
- [ ] Django admin shows 3 new `ToolCard` entries (meta-facebook, meta-instagram, linkedin)
- [ ] Frontend loads, Tools page shows new bridge cards in catalog
- [ ] Oleg chat responds to "підключи інстаграм" with bridge_start_connection tool call
- [ ] Chrome extension v0.3.0 installed with cookies permission

## Rollback Plan

If something breaks:

**Backend:**
```bash
# Revert to previous commit
git checkout HEAD~20  # or specific SHA before bridge commits
cp -r p004_ai_nexelin/MASTER/* MASTER/
docker compose up -d --build
# Migrations are additive — no need to reverse
```

**Matrix server:**
```bash
# Stop new bridges, leave WhatsApp running
docker compose stop mautrix-meta-facebook mautrix-meta-instagram mautrix-linkedin
# Remove registration files from Synapse
rm /opt/matrix/synapse/meta-facebook-registration.yaml
rm /opt/matrix/synapse/meta-instagram-registration.yaml
rm /opt/matrix/synapse/linkedin-registration.yaml
# Restore original homeserver.yaml (remove 3 new registration lines)
# Restart Synapse
docker compose restart synapse
```

**Frontend:**
```bash
# Redeploy previous build
git checkout main -- nextlen/
cd nextlen && npm run build:prod && ./deploy-ftp.sh
```

---

## New Files Summary

| File | Server | Description |
|------|--------|-------------|
| `MASTER/clients/models_bridge.py` | Backend | BridgeConfig + ClientBridgeConnection models |
| `MASTER/clients/services/bridge_service.py` | Backend | Universal bridge service |
| `MASTER/clients/views_bridge.py` | Backend | Bridge API endpoints |
| `MASTER/clients/urls_bridge.py` | Backend | URL routing |
| `MASTER/mcp_hub/builtin/bridge_tools.py` | Backend | 5 MCP tools for Oleg |
| `MASTER/clients/migrations/0058-0060` | Backend | DB migrations |
| `MASTER/tools/migrations/0016` | Backend | ToolCard seed |
| `MASTER/nexelin_platform/fields.py` | Backend | EncryptedTextField added |
| `meta-facebook/config.yaml` | Matrix | mautrix-meta config (FB) |
| `meta-instagram/config.yaml` | Matrix | mautrix-meta config (IG) |
| `linkedin/config.yaml` | Matrix | mautrix-linkedin config |
| `init-mautrix-dbs.sql` | Matrix | Extra DB creation |
| `setup-bridges.sh` | Matrix | Registration file copier |
| `chrome_extension/content/cookie-extractor.js` | Extension | Cookie extraction module |
| `nextlen/src/components/sandbox/chat/RichMessageCard.jsx` | Frontend | Rich message cards |
