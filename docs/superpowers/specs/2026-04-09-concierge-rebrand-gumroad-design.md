# Concierge AI Platform — Ребрендинг та підготовка до продажу на Gumroad

**Дата:** 2026-04-09
**Статус:** Approved

## Мета

Перетворити внутрішній проєкт AI Nexelin на продукт для продажу на Gumroad під назвою **Concierge AI Platform**. Вичистити клієнтські дані, мертвий код, зайву документацію. Стандартизувати структуру.

## Брендинг

| Контекст | Було | Стає |
|----------|------|------|
| Продукт (зовні) | Nexelin / AI Nexelin | **Concierge AI Platform** |
| Дефолтний AI бот (всередині) | — | **Jeeves** |
| Бекенд директорія | `p004_ai_nexelin/` | `backend/` |
| Фронтенд директорія | `nextlen/` | `frontend/` |
| Django project module | `MASTER` | залишається |
| Docker network | `nexelin_network` | `concierge_network` |
| package.json name | `nexelin` | `concierge-dashboard` |
| Домени (grot.de, bytekraft.net) | hardcoded | env vars, приклади → `example.com` |
| Chrome extension | nexelin references | **Concierge** |
| Gumroad акаунт | — | `dariachuprina` |

## Що видаляємо

### Модулі та сервіси
- `MASTER/restaurant/` — весь модуль (моделі, views, serializers, admin, міграції 001–006)
- `MASTER/client_portal/` — ресторанна React адмінка (Tables, Menu, Orders, Chat)
- `services/integration-service/` — Go-based Matrix/WhatsApp bridge
- `matrix-stack/`, `матрікс/`, `matrix/` — весь Matrix стек
- `mcp_servers/bridge/` — bridge MCP agent
- `zero-docker/`, `zero-mock/` — Zero Docker варіанти
- `LangflowPage.jsx` + langflow-related код у фронтенді
- `dummy/`, `scrapping/` — тестові/скрапінг директорії

### Файли
- `NEXELIN_PLAN.md`, `MIGRATION_PLAN.md`, `API_COMPARISON.md`, `API_ISSUES.md`
- `ESCALATION_CODE_SUMMARY.md`, `WEB_WIDGET_INSTRUCTIONS.md`, `VISUAL_EDITOR_ADAPTATION.md`
- `MATRIX_HITL_SETUP.md`, всі `MATRIX_*.md` в `docs/`
- `.aider.chat.history.md`, `.aider.tags.cache.*`
- `tools-skills-tab.png`, `whatsapp-card.png`
- `backup_20251118_122058.sql`
- `fix_*.py`, `check_*.py`, `clean_migrations.py`, `delete_prompts.py`, `reduce_dimensions.py`
- `docker-compose_fix.yml`, `docker-compose.zero.yml`
- Бекенд docs що стосуються клієнтів: `API_CREATE_CLIENT.md`, `POSTMAN_TEST_CLIENT.md`
- `.env-backup-production/` — production секрети
- `docs/superpowers/specs/` — внутрішні дизайн-доки (крім цього файлу)
- `docs/superpowers/plans/` — внутрішні плани

### З коду
- Celery tasks для WhatsApp bridge polling (`poll_whatsapp_bridge_messages`, `check_whatsapp_bridge_status`)
- WhatsApp-specific код у `clients/` моделях (bridge fields)
- Matrix-related middleware та URL routes
- Restaurant URL routes в `urls.py`
- Langflow URL routes та imports

## Що залишається

### Core
- **Django backend** (DRF, PostgreSQL+pgvector, Redis, Celery)
- **React frontend** (Vite, Tailwind, i18next — 7 мов)
- **MCP Hub** + executor
- **Chrome Extension** (ребренд)

### MCP Servers
- `rag/` — RAG пошук по базі знань
- `email/` — email agent
- `leads/` — lead capture
- `sales_intel/` — sales intelligence
- `coaching/` — coaching agent
- `memory/` — conversation memory
- `xlsx/` — Excel processing
- `escalation/` — HITL escalation (без Matrix, generic)

### Django Apps (залишаються)
- `accounts` — юзери та ролі
- `branches` — галузі та документи
- `specializations` — спеціалізації
- `clients` — клієнти, API ключі
- `api` — core RAG, bootstrap, provision
- `processing` — парсинг, чанкінг, embeddings
- `rag` — RAG pipeline
- `EmbeddingModel` — embedding моделі
- `tools` — MCP tools management
- `agents` — agent orchestration
- `mcp_hub` — MCP executor
- `nexelin_platform` → перейменувати на `concierge_platform`

### Фронтенд сторінки (залишаються)
- Dashboard, Settings, Training, Sandbox
- Integrations (без Langflow), Tools
- Leads, History, Pricing
- WebChat, Login/Register
- Setup Instructions

## Етапи виконання

### Етап 1 — Вичистка мертвого коду
Видалити все що в секції "Що видаляємо". Кожна група — окремий коміт. Перевірити що Django стартує після кожного видалення.

### Етап 2 — Структурне перейменування
1. `p004_ai_nexelin/` → `backend/`
2. `nextlen/` → `frontend/`
3. Оновити всі імпорти, docker-compose, Dockerfile paths, CI/CD конфіги
4. `nexelin_platform` app → `concierge_platform`
5. Перевірити що все запускається

### Етап 3 — Брендинг у коді
1. Nexelin/nexelin/NEXELIN → Concierge/concierge у всіх файлах
2. Дефолтний system prompt: "My name is Jeeves, I'm your AI assistant"
3. grot.de, bytekraft.net → замінити на env vars з дефолтом `example.com`
4. Chrome extension manifest — name, description
5. Локалізація (7 мов) — назва продукту
6. Docker: network name, service names, image tags

### Етап 4 — Документація для покупця
1. Новий `README.md` — опис продукту, features, screenshots placeholder
2. `SETUP.md` — як розгорнути (Docker)
3. `.env.example` — всі потрібні змінні з коментарями
4. `LICENSE` — вибрати ліцензію
5. Почистити `requirements.txt` від невикористаних залежностей

## Що НЕ входить
- UI/UX редизайн (окремо, коли буде готовий макет)
- HubSpot MCP інтеграція (окрема задача)
- Нові фічі
- Тести (якщо зламаються при видаленні — фіксимо, але нових не пишемо)
