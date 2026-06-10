# Matrix MCP — setup spec

End-to-end checklist to bring Jeeves's **Matrix-first messaging** online: a
self-hosted Synapse homeserver + mautrix bridges (WhatsApp, Telegram, IG DM,
FB Messenger), the `mcp_matrix` MCP server, per-client `ToolConnection`s, and
agent wiring.

Treat this as the single source of truth for "what does it take to enable
Matrix on a fresh deployment." If something is missing here, fix this doc.

---

## 0. Architecture in one paragraph

`Jeeves Agent → mcp_matrix (stdio FastMCP) → matrix-nio → Synapse CS API → mautrix bridges → IG DM / FB Messenger / WhatsApp / Telegram`.
Each Jeeves `Client` gets one **Matrix puppet** (`@client-<id>:<domain>`) and
one **`ToolConnection(slug='matrix')`** holding `{homeserver_url, user_id,
access_token}` (`EncryptedJSONField`). All DMs of that client across bridged
networks land in Matrix rooms which the agent reads/writes via MCP. **No
direct Meta Graph / Telegram Bot API calls.** Feed posting and analytics are
out of scope here (separate decision, currently skipped).

---

## 1. Prerequisites

- Docker + Docker Compose v2.
- Free ports: `8008/tcp` (Synapse CS API, bound to `127.0.0.1` only).
- For each bridge, account credentials on the target network (see §3).
- Backend stack already running: `cd backend && docker compose up -d`.
- DNS / hostname:
  - **Local dev:** `matrix.localhost` (already configured).
  - **Prod:** real subdomain (e.g. `matrix.example.com`) with TLS via system
    nginx + Certbot. Federation stays disabled — the homeserver is closed.

---

## 2. Synapse bring-up (one-time)

All under `infra/matrix/`. Run from there.

1. **Secrets:** `cp .env.example .env` and fill `MATRIX_DOMAIN` +
   `SYNAPSE_DB_PASSWORD` (use `python3 -c 'import secrets; print(secrets.token_urlsafe(24))'`).

2. **Generate config (first run only):**
   ```bash
   mkdir -p synapse
   docker compose --env-file .env run --rm synapse generate
   ```
   Creates `synapse/homeserver.yaml`, signing key, log config. Files are owned
   by uid `991:991` — to edit, use `docker run --rm -v "$(pwd)/synapse:/data" --user 0 alpine chown -R "$(id -u):$(id -g)" /data`.

3. **Patch `synapse/homeserver.yaml`:**
   - Switch `database` to Postgres:
     ```yaml
     database:
       name: psycopg2
       args:
         user: synapse
         password: "<SYNAPSE_DB_PASSWORD>"
         database: synapse
         host: synapse-db
         cp_min: 5
         cp_max: 10
     ```
   - Bind to `0.0.0.0` inside Docker (port `8008` is mapped to host
     `127.0.0.1` by compose):
     ```yaml
     listeners:
       - port: 8008
         bind_addresses: ['0.0.0.0']
         resources: [{names: [client], compress: false}]
         tls: false
         type: http
         x_forwarded: true
     ```
   - Close the door:
     ```yaml
     federation_domain_whitelist: []
     allow_public_rooms_over_federation: false
     enable_registration: false
     suppress_key_server_warning: true
     ```
   - Add bridge AS files later (see §3).
   - **Hand ownership back to Synapse uid:** `docker run --rm -v "$(pwd)/synapse:/data" --user 0 alpine sh -c "chown -R 991:991 /data && chmod 640 /data/*.signing.key"`.

4. **Start it:** `docker compose --env-file .env up -d synapse-db synapse`.
   Verify: `curl http://127.0.0.1:8008/_matrix/client/versions`.

5. **Register the Jeeves service-account bot:**
   ```bash
   BOT_PWD=$(python3 -c 'import secrets; print(secrets.token_urlsafe(20))')
   echo "BOT_PASSWORD=$BOT_PWD" > .bot-secret
   docker compose exec -T synapse register_new_matrix_user \
     -u jeeves-bot -p "$BOT_PWD" -a -c /data/homeserver.yaml http://localhost:8008
   ```

6. **Capture the access token (login the bot once):**
   ```bash
   curl -s -X POST http://127.0.0.1:8008/_matrix/client/v3/login \
     -H "Content-Type: application/json" \
     -d "{\"type\":\"m.login.password\",
          \"identifier\":{\"type\":\"m.id.user\",\"user\":\"jeeves-bot\"},
          \"password\":\"$BOT_PWD\"}"
   ```
   Pull `user_id` + `access_token` out of the JSON response.

7. **Wire backend to Synapse — `backend/.env`:**
   ```env
   MATRIX_HOMESERVER_URL=http://synapse:8008
   MATRIX_BOT_USER_ID=@jeeves-bot:<MATRIX_DOMAIN>
   MATRIX_BOT_TOKEN=syt_...
   ```

8. **Cross-network access (Docker):** the backend `web` container must join
   the matrix bridge network. `backend/docker-compose.yml` declares
   `matrix_matrix` as an external network and attaches `web` to it. After
   editing, `docker compose up -d web` to recreate.

9. **Smoke test:**
   ```bash
   docker compose exec -T web python -c "
   import asyncio, os
   os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Jeeves.settings')
   import django; django.setup()
   from mcp_servers.matrix import tools
   asyncio.run(tools.send_message(None, '<ROOM_ID>', 'hi'))
   "
   ```

---

## 3. Bridges (per-network, opt-in)

Each bridge follows the same pattern:

1. Generate its registration file via `docker compose run --rm <bridge> -g -c /data/config.yaml -r /data/registration.yaml`.
2. Mount the registration into Synapse and reference it under
   `app_service_config_files:` in `homeserver.yaml`, then restart Synapse.
3. `docker compose up -d <bridge>`.
4. Client logs in by DM-ing the bridge bot from any Matrix client (Element).

### 3.1 Telegram (`mautrix-telegram`) — easiest

**You need:** an `api_id` + `api_hash` from <https://my.telegram.org/apps>.

1. Edit `infra/matrix/bridges/mautrix-telegram/config.yaml.example` →
   `config.yaml`. Replace `REPLACE_ME` values, set `homeserver.domain` to
   your `MATRIX_DOMAIN`, set `as_token` + `hs_token` to fresh random
   `token_urlsafe(32)` strings.
2. Generate registration, then restart Synapse with it referenced.
3. Login flow (per client):
   - In Element, DM `@telegrambot:<domain>`.
   - Send `login`, enter phone number, then the SMS code (userbot mode).
   - Bridge starts mirroring all DMs into Matrix rooms named after Telegram
     contacts.

### 3.2 WhatsApp (`mautrix-whatsapp`)

**You need:** a phone running WhatsApp (multidevice, for QR pairing).

1. Same config-edit / registration / restart cycle as 3.1.
2. Login: DM `@whatsappbot:<domain>` → `login` → scan QR with phone's
   WhatsApp **Linked devices** screen.

### 3.3 Meta (`mautrix-meta` — IG DM + FB Messenger)

**You need:** a real IG/FB user account and either cookies or login
credentials. **Page access tokens do NOT work** — this is a user-account
bridge, not a Page bridge.

1. Decide bridge mode in `config.yaml`: `instagram` / `facebook` /
   `messenger`. Multi-mode requires running multiple instances.
2. Same registration / restart cycle.
3. Login: DM `@metabot:<domain>` → `login instagram` (or `facebook`).
   Bridge will walk you through cookie/password entry.

### 3.4 Bridge is unstable

`mautrix-meta` reverse-engineers Instagram's MQTT — expect periodic breakage.
Keep `mautrix-meta` version pinned to a known-good tag (not `:latest`) in
prod. Have a manual-fallback runbook (manager replies in IG mobile app).

---

## 4. Per-client wiring

For each Jeeves `Client` that should appear over Matrix:

1. **Create a Matrix puppet user.** Admin registers
   `@client-<id>:<domain>` either via the admin API (`/_synapse/admin/v2/users`)
   or via `register_new_matrix_user`. Capture its access token.
2. **Seed `ToolConnection(slug='matrix')`** for that client. Done from the
   client portal `/l/<tag>/` → MCP catalog → Matrix → Connect. Paste
   `homeserver_url`, `user_id`, `access_token` (frontend stores them
   encrypted via `EncryptedJSONField`).
3. **Bridge login** — same as §3 for each enabled bridge.
4. **Verify** by calling `matrix_list_rooms(client_id=<id>)` from the MCP —
   one room per bridged contact should appear.

The MCP also supports a `client_id=None` service-account fallback (uses
`MATRIX_BOT_*`) for system-level things like HITL room creation.

---

## 5. Agent flow

Two integration points in `Jeeves.agents`:

1. **Inbound:** the agent subscribes to a Matrix room (per client) and calls
   `matrix_read_room_history` / `matrix_mark_read` when new events arrive.
   For long-poll, run a Celery task or a long-lived `nio.AsyncClient.sync`
   listener — TBD; current MCP tools are one-shot.
2. **Outbound:** instead of channel-specific publishing (`send_telegram`,
   etc.), the agent calls `matrix_send_message(client_id, room_id, body)`.
   The bridge forwards into the source network.

**HITL escalation:** `matrix_invite_user(client_id, room_id, manager_mxid)`
pulls a live manager into the conversation. The bridge mirrors any of the
manager's replies back into the source DM transparently.

---

## 6. Security & ops notes

- **Secrets that must never land in git:** `infra/matrix/.env`,
  `infra/matrix/.bot-secret`, `infra/matrix/synapse/` (the generated
  `homeserver.yaml` contains the signing/registration shared secret + Postgres
  password), per-client access tokens in `ToolConnection.credentials` (already
  encrypted by Fernet). `.gitignore` already excludes these paths.
- **Backups:** the Synapse Postgres volume (`synapse_db`) carries all rooms +
  encryption state. Add it to your `pg_dump` cron alongside the Jeeves DB.
- **Ports:** Synapse is bound to `127.0.0.1:8008` — never `0.0.0.0`. Federation
  is off so port `8448` stays closed.
- **Token rotation:** if `MATRIX_BOT_TOKEN` leaks, log the bot out via
  `/_matrix/client/v3/logout` and re-issue. Same for client puppet tokens.
- **`matrix-nio`:** installed via `requirements.txt`. The `[e2e]` extra (E2EE
  rooms) requires `libolm` at build time — currently NOT enabled. Bridges
  expose **decrypted** content into Matrix rooms anyway, so E2EE only matters
  for direct manager-agent chats. Add `[e2e]` when that ships.

---

## 7. Known gaps / TODO

- **Long-poll inbound listener.** Current MCP tools are pull-style. To react
  to bridged messages in real time we need either a Celery worker running
  `client.sync_forever()` or a small webhook gateway. Plan: implement as
  `Jeeves.agents.matrix_listener` Celery task.
- **i18n keys** for the Matrix `ConnectModal` instructions live only as
  English fallbacks (`tools.matrix.howto_title` etc.). Add real translations
  to all 8 locale files.
- **Bridge registrations not generated yet.** §3 is dry-runnable but no
  bridge has actually been brought up. Decide first which bridge a real
  client needs and run §3.1/3.2/3.3 then.
- **mautrix-meta** is fragile — pin to a tag and document the manual
  fallback before depending on it in prod.
- **No per-client puppet provisioning script** yet (§4 step 1 is manual).
  Add a Django management command `provision_matrix_puppet --client <id>`.
- **Frontend ConnectModal** lacks UI for picking which bridges to enable
  per client. Today the user copies access tokens manually.
