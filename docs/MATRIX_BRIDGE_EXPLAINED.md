
# Matrix Bridge - Пояснення та Підключення

## Що таке Matrix Bridge?

**Matrix Bridge** - це внутрішня структура даних в Integration Service (Go), яка зберігає зв'язок між Matrix кімнатами та Django conversations. Це НЕ окремий сервіс, а частина Integration Service.

## Навіщо потрібен Bridge?

Коли менеджер відповідає в Matrix кімнаті, Integration Service повинен знати:
- Яка Django conversation відповідає цій Matrix кімнаті?
- В який канал пересилати відповідь? (telegram/whatsapp/web)
- Який client_id використовувати?

Bridge зберігає цей маппінг в пам'яті.

---

## Як працює Bridge?

### Структура даних

```go
type Bridge struct {
    mu         sync.RWMutex          // Захист від race conditions
    roomToConv map[string]*ConversationMapping  // roomID -> conversation info
    convToRoom map[int64]string      // conversationID -> roomID
}

type ConversationMapping struct {
    ConversationID int64   // Django conversation ID
    RoomID         string  // Matrix room ID (!abc123:grot.de)
    Channel        string  // "telegram", "whatsapp", "web"
    ClientID       int64   // Django client ID
}
```

### Два напрямки маппінгу:

1. **roomID → conversation** (коли отримуємо повідомлення з Matrix)
2. **conversationID → roomID** (коли потрібно знайти Matrix кімнату)

---

## Як Bridge використовується?

### 1. Реєстрація (коли створюється ескалація)

**Файл:** `services/integration-service/internal/hitl/orchestrator.go`

```go
// Після створення Matrix кімнати
func (o *Orchestrator) HandleEscalation(...) {
    // 1. Створюємо Matrix кімнату
    roomID, err := o.matrixClient.CreateRoom(...)
    
    // 2. Реєструємо в Bridge
    o.bridge.RegisterConversation(
        escalation.ConversationID,  // 123
        roomID,                      // "!abc123:grot.de"
        escalation.Channel,          // "telegram"
        escalation.ClientID,         // 5
    )
}
```

**Що відбувається:**
- Bridge зберігає: `"!abc123:grot.de" -> {conversationID: 123, channel: "telegram", clientID: 5}`
- І навпаки: `123 -> "!abc123:grot.de"`

### 2. Обробка повідомлень (коли менеджер відповідає)

**Файл:** `services/integration-service/internal/hitl/orchestrator.go`

```go
func (o *Orchestrator) handleMatrixEvent(ctx context.Context, event *gomatrix.Event) {
    roomID := event.RoomID  // "!abc123:grot.de"
    
    // Шукаємо conversation через Bridge
    conversationID, channel, clientID, found := o.bridge.GetConversationByRoom(roomID)
    
    if !found {
        return // Не escalation кімната, ігноруємо
    }
    
    // Тепер знаємо:
    // - conversationID = 123
    // - channel = "telegram"
    // - clientID = 5
    
    // Пересилаємо в Django
    o.forwardToChannel(ctx, conversationID, channel, message, clientID)
}
```

---

## Як підключитися до Bridge?

### Bridge - це НЕ окремий сервіс!

Bridge працює **всередині Integration Service**. Він створюється автоматично при старті сервісу.

### Створення Bridge

**Файл:** `services/integration-service/internal/hitl/orchestrator.go`

```go
func NewOrchestrator(...) *Orchestrator {
    syncHandler := matrix.NewSyncHandler(matrixClient)
    bridge := NewBridge()  // ← Створюється тут
    
    return &Orchestrator{
        matrixClient:   matrixClient,
        syncHandler:    syncHandler,
        bridge:         bridge,  // ← Зберігається в orchestrator
        ...
    }
}
```

### Доступ до Bridge

Bridge доступний тільки через Orchestrator:

```go
// В orchestrator.go
o.bridge.RegisterConversation(...)      // Реєстрація
o.bridge.GetConversationByRoom(...)     // Пошук по roomID
o.bridge.GetRoomByConversation(...)     // Пошук по conversationID
```

**Ззовні Integration Service Bridge недоступний** - це внутрішня реалізація.

---

## Життєвий цикл Bridge

### 1. Створення ескалації

```
Django → Integration Service API
  POST /api/v1/hitl/escalate
  {
    "conversation_id": 123,
    "channel": "telegram",
    ...
  }
```

```
Integration Service:
  1. Створює Matrix кімнату: "!abc123:grot.de"
  2. Реєструє в Bridge:
     bridge.RegisterConversation(123, "!abc123:grot.de", "telegram", 5)
  3. Зберігає room_id в Django через API
```

### 2. Менеджер відповідає в Matrix

```
Matrix Server → Integration Service (sync)
  Event: message in room "!abc123:grot.de"
```

```
Integration Service:
  1. Отримує event з Matrix
  2. Шукає в Bridge:
     conversationID, channel, clientID, found := bridge.GetConversationByRoom("!abc123:grot.de")
     // Знаходить: 123, "telegram", 5
  3. Пересилає в Django:
     POST /api/v1/integration/forward-message
     {
       "conversation_id": 123,
       "message": "Відповідь менеджера",
       "channel": "telegram"
     }
```

### 3. Ескалація вирішена (опціонально)

```
Bridge може видалити маппінг:
  bridge.UnregisterConversation(123)
```

**Але зазвичай маппінг залишається** - на випадок подальших повідомлень.

---

## Важливі особливості

### 1. Bridge зберігається в пам'яті

- При перезапуску Integration Service Bridge втрачається
- Але room_id зберігається в Django БД
- При наступній ескалації Bridge реєструється знову

### 2. Thread-safe

Bridge використовує `sync.RWMutex` для захисту від race conditions:
- Кілька goroutines можуть читати одночасно
- Запис блокує всі операції

### 3. Bridge не синхронізується з Django

- Bridge - це швидкий кеш в пам'яті
- Django БД - це джерело правди
- Якщо Bridge втрачений, можна відновити з Django БД (по matrix_room_id)

---

## Як використовувати Bridge ззовні?

### Ви НЕ можете підключитися до Bridge напряму!

Bridge - це внутрішня реалізація. Але ви можете:

### 1. Використовувати через Integration Service API

```bash
# Створити ескалацію (Bridge реєструється автоматично)
POST http://integration-service:8080/api/v1/hitl/escalate
{
  "conversation_id": 123,
  "channel": "telegram",
  ...
}
```

### 2. Перевірити через Django БД

```python
# В Django
from MASTER.clients.models import ClientWhatsAppConversation

conv = ClientWhatsAppConversation.objects.get(id=123)
if conv.matrix_room_id:
    print(f"Matrix room: {conv.matrix_room_id}")
    print(f"Active: {conv.matrix_escalation_active}")
```

### 3. Відправити повідомлення в Matrix кімнату

Якщо знаєте `matrix_room_id` з Django, можете відправити повідомлення через Matrix API напряму (але краще через Integration Service).

---

## Приклад повного потоку з Bridge

### Крок 1: Ескалація створюється

```
Django (views_telegram.py):
  send_matrix_escalation(conversation, client, "telegram", ...)
  ↓
  POST http://integration-service:8080/api/v1/hitl/escalate
```

```
Integration Service (orchestrator.go):
  1. Створює Matrix кімнату: "!abc123:grot.de"
  2. Bridge.RegisterConversation(123, "!abc123:grot.de", "telegram", 5)
     ↓
     Bridge тепер містить:
     roomToConv["!abc123:grot.de"] = {conversationID: 123, channel: "telegram", clientID: 5}
     convToRoom[123] = "!abc123:grot.de"
  3. Зберігає в Django: conv.matrix_room_id = "!abc123:grot.de"
```

### Крок 2: Менеджер відповідає

```
Matrix Server:
  Менеджер пише в кімнаті "!abc123:grot.de": "Відповідь"
  ↓
  Matrix Sync → Integration Service
```

```
Integration Service (orchestrator.go):
  1. Отримує event з roomID = "!abc123:grot.de"
  2. Bridge.GetConversationByRoom("!abc123:grot.de")
     ↓
     Повертає: (123, "telegram", 5, true)
  3. Знає, що потрібно переслати в conversation 123, channel telegram
  4. POST Django: /api/v1/integration/forward-message
     {
       "conversation_id": 123,
       "message": "Відповідь",
       "channel": "telegram"
     }
```

### Крок 3: Django обробляє

```
Django (api/views.py):
  integration_forward_message()
  ↓
  process_manager_hitl_response.delay(123, "Відповідь", None)
  ↓
  Відправляє в Telegram користувачу
```

---

## Як перевірити, що Bridge працює?

### 1. Перевірити логи Integration Service

```bash
docker logs integration-service | grep "Bridge\|RegisterConversation\|GetConversationByRoom"
```

### 2. Перевірити Django БД

```python
# В Django shell
from MASTER.clients.models import ClientWhatsAppConversation

# Знайти conversation з Matrix escalation
conv = ClientWhatsAppConversation.objects.filter(
    matrix_escalation_active=True
).first()

if conv:
    print(f"Conversation {conv.id}:")
    print(f"  Matrix room: {conv.matrix_room_id}")
    print(f"  Channel: {conv.context_metadata.get('platform')}")
```

### 3. Перевірити Matrix кімнату

Увійдіть в Matrix клієнт (Element) як менеджер і перевірте:
- Чи є кімната з назвою "Escalation: ..."
- Чи є повідомлення про ескалацію

---

## Troubleshooting

### Bridge не знаходить conversation

**Проблема:** `GetConversationByRoom()` повертає `found = false`

**Причини:**
1. Integration Service перезапустився (Bridge втрачений)
2. Conversation не був зареєстрований
3. Неправильний roomID

**Рішення:**
- Перевірити Django БД: чи є `matrix_room_id`?
- Перезапустити ескалацію (створити нову)
- Перевірити логи Integration Service

### Bridge знаходить, але channel неправильний

**Проблема:** Повідомлення пересилається не в той канал

**Рішення:**
- Перевірити, який channel передається при реєстрації
- Перевірити `conversation.context_metadata['platform']` в Django

---

## Підсумок

**Matrix Bridge:**
- ✅ Внутрішня структура в Integration Service
- ✅ Зберігає маппінг: Matrix Room ↔ Django Conversation
- ✅ Створюється автоматично при старті
- ✅ Використовується для пересилання повідомлень
- ❌ НЕ окремий сервіс
- ❌ НЕ має HTTP API
- ❌ НЕ зберігається в БД (тільки в пам'яті)

**Як підключитися:**
- Через Integration Service API (`/api/v1/hitl/escalate`)
- Через Django БД (перевірка `matrix_room_id`)
- Bridge працює автоматично, коли Integration Service запущений

