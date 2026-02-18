# Структура проєкту

```
services/integration-service/
├── cmd/
│   └── server/
│       └── main.go              # Точка входу, ініціалізація сервісу
├── internal/
│   ├── api/
│   │   ├── handlers.go          # HTTP handlers для API endpoints
│   │   └── routes.go            # Налаштування маршрутів
│   ├── hitl/
│   │   ├── bridge.go            # Міст між Matrix rooms та conversations
│   │   └── orchestrator.go     # Оркестрація HITL flow
│   └── matrix/
│       ├── client.go            # Matrix API клієнт
│       └── sync.go              # Синхронізація Matrix events
├── pkg/
│   └── models/
│       └── escalation.go       # Data models
├── Dockerfile                   # Docker образ
├── docker-compose.yml           # Docker Compose конфігурація
├── go.mod                       # Go модуль
├── Makefile                     # Команди для розробки
├── README.md                    # Основна документація
├── INTEGRATION_GUIDE.md         # Гайд по інтеграції з Django
├── config.example.env           # Приклад конфігурації
└── PROJECT_STRUCTURE.md         # Цей файл
```

## Компоненти

### cmd/server/main.go
Головний файл, який:
- Завантажує конфігурацію з environment variables
- Створює Matrix клієнт
- Ініціалізує HITL orchestrator
- Запускає HTTP сервер
- Обробляє graceful shutdown

### internal/matrix/
**client.go**: Обгортка над gomatrix клієнтом
- Створення Matrix кімнат
- Відправка повідомлень
- Запрошення користувачів

**sync.go**: Синхронізація з Matrix сервером
- Long polling для отримання events
- Фільтрація message events
- Thread-safe event channel

### internal/hitl/
**orchestrator.go**: Головна логіка HITL
- Обробка escalation requests
- Створення Matrix кімнат
- Форвардинг повідомлень менеджерів
- Інтеграція з Django API

**bridge.go**: Міст між Matrix та conversations
- Зберігання маппінгу room_id <-> conversation_id
- Thread-safe операції
- Швидкий lookup

### internal/api/
**handlers.go**: HTTP handlers
- POST /api/v1/hitl/escalate - створення ескалації
- GET /health - health check
- GET /api/v1/status - статус сервісу

**routes.go**: Налаштування маршрутів Gin

### pkg/models/
**escalation.go**: Data models
- EscalationRequest - вхідний запит
- Escalation - внутрішня модель
- ConversationInfo - інформація про conversation
- ForwardMessageRequest - запит на форвардинг

## Потік даних

1. **Escalation Request** (Django → Integration Service)
   ```
   Django RAG Service → POST /api/v1/hitl/escalate → Orchestrator
   ```

2. **Room Creation** (Integration Service → Matrix)
   ```
   Orchestrator → Matrix Client → Matrix Server
   ```

3. **Event Sync** (Matrix → Integration Service)
   ```
   Matrix Server → Sync Handler → Event Channel → Orchestrator
   ```

4. **Message Forwarding** (Integration Service → Django)
   ```
   Orchestrator → POST /api/v1/integration/forward-message → Django
   ```

## Залежності

- `github.com/gin-gonic/gin` - HTTP framework
- `github.com/matrix-org/gomatrix` - Matrix client library

## Модульність

Сервіс повністю модульний:
- Не залежить від Django коду
- Може бути використаний в інших проєктах
- Використовує стандартні HTTP API для інтеграції
- Легко тестується окремо

## Розширення

Для додавання нових каналів:
1. Додайте новий case в `forwardToChannel()` в orchestrator.go
2. Реалізуйте форвардинг в Django endpoint
3. Оновіть models якщо потрібно

Для додавання нових Matrix features:
1. Розширте `matrix.Client` з новими методами
2. Використайте в orchestrator за потреби

