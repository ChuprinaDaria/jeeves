# Matrix Stack для grot.de — v3

Полнофункциональная Matrix-система с видеоконференциями, QR-логином и быстрой синхронизацией.

**Особенность этой версии:** NPM находится на отдельном сервере.

---

## Архитектура

```
                    Internet
                        │
                        ▼
                ┌───────────────┐
                │    Router     │
                │  (port forward)│
                └───────┬───────┘
                        │
        ┌───────────────┼───────────────┐
        │               │               │
        ▼               ▼               ▼
  ┌──────────┐   ┌──────────┐   ┌──────────────┐
  │   NPM    │   │  Matrix  │   │Other services│
  │  Server  │   │  Server  │   │              │
  │ :80,:443 │──▶│ :8008... │   │              │
  └──────────┘   └──────────┘   └──────────────┘
       │                │
       └────────────────┘
            LAN (proxy-net не нужен)
```

---

## Компоненты

| Сервис | Контейнер | Порт (LAN) | Поддомен |
|--------|-----------|------------|----------|
| Synapse | grot-synapse | 8008 | matrix.grot.de |
| MAS | grot-mas | 8080 | auth.grot.de |
| Element Web | grot-element | 8081 | chat.grot.de |
| Synapse Admin | grot-synapse-admin | 8082 | admin.grot.de |
| Sliding Sync | grot-sliding-sync | 8009 | sliding.grot.de |
| LiveKit | grot-livekit | 7880 | livekit.grot.de |
| lk-jwt-service | grot-lk-jwt | 8083 | livekit-jwt.grot.de |
| coturn | grot-coturn | 3478/5349 | turn.grot.de |
| well-known | grot-well-known | 8084 | grot.de |

---

## Установка

### Шаг 1: Инициализация

```bash
unzip matrix-stack-grot-v3.zip
cd matrix-stack-grot-v3
chmod +x init.sh
./init.sh
```

Скрипт запросит:
- **External IP** — публичный IP (для DNS и coturn)
- **Internal IP** — локальный IP сервера (для NPM)

**⚠️ СОХРАНИ ВЫВЕДЕННЫЕ ПАРОЛИ!**

---

### Шаг 2: DNS записи (9 штук)

Все записи указывают на **внешний IP роутера**:

```
grot.de              A → EXTERNAL_IP
matrix.grot.de       A → EXTERNAL_IP
chat.grot.de         A → EXTERNAL_IP
auth.grot.de         A → EXTERNAL_IP
admin.grot.de        A → EXTERNAL_IP
livekit.grot.de      A → EXTERNAL_IP
livekit-jwt.grot.de  A → EXTERNAL_IP
sliding.grot.de      A → EXTERNAL_IP
turn.grot.de         A → EXTERNAL_IP
```

---

### Шаг 3: Проброс портов на роутере

Пробросить на **внутренний IP Matrix-сервера**:

| Внешний порт | Протокол | Назначение |
|--------------|----------|------------|
| 3478 | TCP + UDP | coturn STUN/TURN |
| 5349 | TCP + UDP | coturn TLS |
| 49152-49252 | UDP | coturn relay |
| 7881 | TCP | LiveKit |
| 50000-50100 | UDP | LiveKit RTC |

**Примечание:** Порты 80 и 443 должны быть проброшены на NPM-сервер.

---

### Шаг 4: Firewall на Matrix-сервере

```bash
# Разрешить HTTP-трафик от NPM (замени IP)
ufw allow from 192.168.1.10 to any port 8008
ufw allow from 192.168.1.10 to any port 8009
ufw allow from 192.168.1.10 to any port 8080
ufw allow from 192.168.1.10 to any port 8081
ufw allow from 192.168.1.10 to any port 8082
ufw allow from 192.168.1.10 to any port 8083
ufw allow from 192.168.1.10 to any port 8084
ufw allow from 192.168.1.10 to any port 7880

# Разрешить медиа/звонки из интернета
ufw allow 3478/tcp
ufw allow 3478/udp
ufw allow 5349/tcp
ufw allow 5349/udp
ufw allow 49152:49252/udp
ufw allow 7881/tcp
ufw allow 50000:50100/udp
```

---

### Шаг 5: NPM Proxy Hosts (на NPM-сервере)

Все хосты с **SSL** (Let's Encrypt)!

| Домен | Forward Hostname | Port | WebSocket |
|-------|------------------|------|-----------|
| grot.de | 192.168.x.x | 8084 | — |
| matrix.grot.de | 192.168.x.x | 8008 | — |
| chat.grot.de | 192.168.x.x | 8081 | — |
| auth.grot.de | 192.168.x.x | 8080 | — |
| admin.grot.de | 192.168.x.x | 8082 | — |
| livekit.grot.de | 192.168.x.x | 7880 | ✅ ВКЛ |
| livekit-jwt.grot.de | 192.168.x.x | 8083 | — |
| sliding.grot.de | 192.168.x.x | 8009 | — |

**Замени 192.168.x.x на внутренний IP Matrix-сервера!**

**Для matrix.grot.de** → Advanced → Custom Nginx Configuration:
```nginx
client_max_body_size 100M;
```

---

### Шаг 6: Первый запуск

```bash
docker compose up -d
```

Проверка логов:
```bash
docker compose logs -f synapse
```

**⚠️ Если ошибка "Permission denied: signing.key":**
```bash
sudo chown -R 991:991 synapse/
docker compose restart synapse
```

---

### Шаг 7: Создание администратора

```bash
docker exec -it grot-synapse register_new_matrix_user \
  -u admin -p ТВОЙ_ПАРОЛЬ -a \
  -c /data/homeserver.yaml http://localhost:8008
```

---

### Шаг 8: Проверка

1. Открой https://chat.grot.de
2. Войди под admin
3. Проверь видеозвонок

---

## Включение MAS (QR-логин)

После успешной работы базовой системы.

### 8.1: Установи syn2mas

```bash
sudo apt install nodejs npm
npm install -g @vector-im/syn2mas
```

### 8.2: Временно открой порты PostgreSQL

В `docker-compose.yml` добавь:

```yaml
  postgres-synapse:
    ...
    ports:
      - "5432:5432"

  postgres-mas:
    ...
    ports:
      - "5433:5432"
```

```bash
docker compose up -d postgres-synapse postgres-mas
```

### 8.3: Временно измени конфиги

**synapse/homeserver.yaml:**
```yaml
database:
  ...
    host: localhost
```

**mas/config.yaml:**
```yaml
database:
  uri: "postgres://mas:ПАРОЛЬ@localhost:5433/mas"
```

### 8.4: Останови Synapse

```bash
docker compose stop synapse
```

### 8.5: Миграция

```bash
# Тест
syn2mas --command migrate \
  --synapseConfigFile synapse/homeserver.yaml \
  --masConfigFile mas/config.yaml \
  --dryRun

# Реальная миграция
syn2mas --command migrate \
  --synapseConfigFile synapse/homeserver.yaml \
  --masConfigFile mas/config.yaml
```

### 8.6: Верни настройки

**synapse/homeserver.yaml:**
```yaml
host: postgres-synapse
```

**mas/config.yaml:**
```yaml
uri: "postgres://mas:ПАРОЛЬ@postgres-mas:5432/mas"
```

**docker-compose.yml** — убери `ports` у баз.

### 8.7: Включи MAS в Synapse

```bash
nano synapse/homeserver.yaml
```

Раскомментируй (⚠️ БЕЗ пробелов в начале!):

```yaml
matrix_authentication_service:
  enabled: true
  endpoint: "http://mas:8080"
  secret: "..."

experimental_features:
  msc4108_enabled: true
```

### 8.8: Запусти

```bash
docker compose up -d
```

---

## Альтернативная миграция (через Docker)

Если syn2mas не видит базы:

```bash
docker run --rm -it \
  --network grot-internal \
  -v $(pwd)/synapse:/synapse:ro \
  -v $(pwd)/mas:/mas:ro \
  node:20 bash -c "
    npm install -g @vector-im/syn2mas && 
    syn2mas --command migrate \
      --synapseConfigFile /synapse/homeserver.yaml \
      --masConfigFile /mas/config.yaml \
      --dryRun
  "
```

При этом способе НЕ нужно менять host на localhost.

---

## Создание пользователей

**До MAS:**
```bash
docker exec -it grot-synapse register_new_matrix_user \
  -u username -p password \
  -c /data/homeserver.yaml http://localhost:8008
```

**После MAS:**
```bash
docker exec -it grot-mas mas-cli manage register-user
```

---

## Synapse Admin

1. Открой https://admin.grot.de
2. **Homeserver URL:** `https://matrix.grot.de`
3. Логин/пароль админа

Если не работает с MAS:
```bash
docker exec -it grot-mas mas-cli manage issue-compatibility-token admin
```

Используй полученный токен для входа.

---

## Полезные команды

```bash
# Статус
docker compose ps

# Логи
docker compose logs -f synapse
docker compose logs -f mas

# Перезапуск
docker compose restart synapse

# Обновление
docker compose pull
docker compose up -d
```

---

## Troubleshooting

### Synapse не стартует

```bash
docker compose logs synapse --tail 50
sudo chown -R 991:991 synapse/
```

### NPM не видит сервисы

1. Проверь firewall: `ufw status`
2. Проверь порты: `ss -tlnp | grep 8008`
3. Проверь связь с NPM: `curl http://MATRIX_IP:8008/_matrix/client/versions`

### Видеозвонки не работают

1. Проверь проброс портов на роутере
2. Проверь firewall
3. Проверь логи: `docker compose logs livekit coturn`

---

## Бэкап

```bash
docker compose down

tar -czvf grot-backup-$(date +%Y%m%d).tar.gz \
  data/ synapse/ mas/ element/ livekit/ coturn/ well-known/ .env

docker compose up -d
```

---

## Структура файлов

```
matrix-stack-grot-v3/
├── docker-compose.yml
├── .env
├── init.sh
├── INSTALL.md
├── synapse/
│   ├── homeserver.yaml
│   └── grot.de.log.config
├── mas/
│   └── config.yaml
├── element/
│   └── config.json
├── livekit/
│   └── livekit.yaml
├── coturn/
│   └── turnserver.conf
├── well-known/
│   ├── nginx.conf
│   └── files/.well-known/matrix/
└── data/
    ├── postgres-synapse/
    ├── postgres-mas/
    └── postgres-sliding/
```

---

## Сводка портов

### Для NPM (внутренняя сеть)

| Порт | Сервис |
|------|--------|
| 8008 | Synapse |
| 8009 | Sliding Sync |
| 8080 | MAS |
| 8081 | Element |
| 8082 | Synapse Admin |
| 8083 | lk-jwt |
| 8084 | well-known |
| 7880 | LiveKit (HTTP) |

### Для роутера (внешний доступ)

| Порт | Протокол | Сервис |
|------|----------|--------|
| 3478 | TCP+UDP | coturn |
| 5349 | TCP+UDP | coturn TLS |
| 49152-49252 | UDP | coturn relay |
| 7881 | TCP | LiveKit |
| 50000-50100 | UDP | LiveKit RTC |

