# Matrix infra for Jeeves

Self-hosted **Synapse** + mautrix **WhatsApp**, **Telegram**, **Meta** (Instagram DM + FB Messenger) bridges.
Drives the `mcp_matrix` MCP server in `backend/mcp_servers/matrix/`.

## Layout

```
infra/matrix/
├── docker-compose.yml          # Synapse + Postgres + 3 bridges
├── .env.example                # copy to .env, fill secrets
├── synapse/                    # homeserver.yaml lives here after first run
└── bridges/
    ├── mautrix-whatsapp/       # config.yaml + registration.yaml
    ├── mautrix-telegram/
    └── mautrix-meta/
```

## First-time setup (on 128.140.65.237)

1. `cp .env.example .env` and pick a strong `SYNAPSE_DB_PASSWORD`.
2. Generate Synapse config:
   ```bash
   docker compose run --rm synapse generate
   ```
   This writes `synapse/homeserver.yaml`. Edit it:
   - set `database` block to Postgres (see snippet below);
   - add `app_service_config_files:` with paths to each bridge's `registration.yaml`;
   - disable federation if this is a closed homeserver.
3. Start the stack: `docker compose up -d synapse-db synapse`.
4. Register the Jeeves service-account bot:
   ```bash
   docker compose exec synapse register_new_matrix_user \
     -u jeeves-bot -p <STRONG_PWD> -a -c /data/homeserver.yaml http://localhost:8008
   ```
   Log in once with that account to get the access token. Drop the token into
   `backend/.env` as `MATRIX_BOT_TOKEN`. Also set `MATRIX_HOMESERVER_URL` and
   `MATRIX_BOT_USER_ID` there.
5. Configure bridges (see `bridges/*/config.yaml.example`), generate registrations,
   reference them in Synapse, then `docker compose up -d` the bridges.

## Postgres snippet for `synapse/homeserver.yaml`

```yaml
database:
  name: psycopg2
  args:
    user: synapse
    password: <SYNAPSE_DB_PASSWORD>
    database: synapse
    host: synapse-db
    cp_min: 5
    cp_max: 10
```

## Nginx reverse-proxy

The system nginx on the host should proxy `https://matrix.<domain>/` to
`127.0.0.1:8008` (Synapse CS API).

## Bridge login UX

Clients pair their messengers from inside Element (or any Matrix client) by
DM'ing the relevant bridge bot:

| Bridge      | Bot                         | Login command                                   |
|-------------|-----------------------------|-------------------------------------------------|
| WhatsApp    | `@whatsappbot:matrix.<dom>` | `login` → scan QR with phone (multidevice)      |
| Telegram    | `@telegrambot:matrix.<dom>` | `login` → enter phone + code (userbot mode)     |
| Meta IG/FB  | `@metabot:matrix.<dom>`     | `login instagram` / `login facebook` → cookies  |

The Jeeves frontend `ConnectModal` shows these instructions per locale.
