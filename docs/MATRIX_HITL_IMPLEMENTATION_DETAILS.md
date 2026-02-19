# Matrix HITL Implementation Details - Nexelin

## Огляд архітектури

Matrix HITL (Human-in-the-Loop) в nexelin дозволяє AI ескалювати складні питання до менеджерів через Matrix кімнати, замість поточного Telegram-only підходу.

---

## 🔄 Потік даних (Flow)

### 1. Виявлення потреби в ескалації

**Файл:** `p004_ai_nexelin/MASTER/rag/response_generator.py`

AI визначає потребу в ескалації через:

1. **Токен `[[ESCALATE_TO_MANAGER]]`** в відповіді LLM:
   ```python
   if '[[ESCALATE_TO_MANAGER]]' in answer:
       requires_escalation = True
       escalation_summary = extract_summary(answer)
   ```

2. **Фрази відмови** (fallback detection):
   ```python
   refusal_phrases = [
       "i don't have that specific information",
       "не маю цієї конкретної інформації",
       # ... інші мови
   ]
   is_refusal = any(phrase in answer_lower for phrase in refusal_phrases)
   ```

3. **Примусова ескалація** через тег `[escalate]` в запиті:
   ```python
   forced_escalation = '[escalate]' in query.lower()
   ```

**Результат:** `RAGResponse` з полями:
- `requires_escalation: bool`
- `escalation_summary: str`

---

### 2. Виклик ескалації з Django

**Файли:**
- `p004_ai_nexelin/MASTER/clients/views_telegram.py` (рядок 1174)
- `p004_ai_nexelin/MASTER/clients/views_meta_whatsapp.py` (рядок 537)
- `p004_ai_nexelin/MASTER/api/views.py` (рядок 485)

**Код:**
```python
# Перевірка чи потрібна ескалація
if rag_response.requires_escalation and getattr(client, 'hitl_enabled', False):
    manager_ids = client.get_manager_telegram_ids()
    if manager_ids:
        # Telegram escalation (старий спосіб)
        notify_manager_of_escalation.delay(
            conversation.id, 
            rag_response.escalation_summary or message_body[:200]
        )
        
        # Matrix escalation (новий спосіб) - якщо увімкнено
        if getattr(client, 'matrix_hitl_enabled', False):
            # Виклик Integration Service API
            escalation_data = {
                "conversation_id": conversation.id,
                "client_id": client.id,
                "client_name": client.company_name,
                "customer_name": customer_name,
                "channel": channel,  # "telegram", "whatsapp", "web"
                "question": query,
                "context": escalation_summary,
                "language": language,
                "manager_user_ids": client.matrix_manager_user_ids or [],
            }
            # POST до Integration Service
            httpx.post(f"{INTEGRATION_SERVICE_URL}/api/v1/hitl/escalate", json=escalation_data)
```

---

### 3. Обробка в Integration Service (Go)

**Файл:** `services/integration-service/internal/api/handlers.go`

**Endpoint:** `POST /api/v1/hitl/escalate`

**Обробка:**
```go
func (h *Handlers) HandleEscalation(c *gin.Context) {
    var req models.EscalationRequest
    // Парсинг JSON запиту
    // Створення Escalation об'єкта
    // Виклик orchestrator.HandleEscalation()
}
```

**Модель запиту:**
```go
type EscalationRequest struct {
    ConversationID int64    `json:"conversation_id"`
    ClientID       int64    `json:"client_id"`
    ClientName     string   `json:"client_name"`
    CustomerName   string   `json:"customer_name"`
    Channel        string   `json:"channel"` // "telegram", "whatsapp", "web"
    Question       string   `json:"question"`
    Context        string   `json:"context"`
    Language       string   `json:"language"`
    ManagerUserIDs []string `json:"manager_user_ids"` // ["@manager1:grot.de"]
}
```

---

### 4. Створення Matrix кімнати

**Файл:** `services/integration-service/internal/hitl/orchestrator.go`

**Метод:** `HandleEscalation()`

**Кроки:**

1. **Створення кімнати:**
   ```go
   roomName := fmt.Sprintf("Escalation: %s - %s", escalation.ClientName, escalation.Channel)
   roomTopic := fmt.Sprintf("Customer question requiring human assistance. Original channel: %s", escalation.Channel)
   
   roomID, err := o.matrixClient.CreateRoom(ctx, roomName, roomTopic, escalation.ManagerUserIDs)
   ```

2. **Відправка повідомлення про ескалацію:**
   ```go
   message := o.formatEscalationMessage(escalation)
   // HTML форматування з даними:
   // - Customer name
   // - Channel (telegram/whatsapp/web)
   // - Question
   // - Language
   // - Context
   eventID, err := o.matrixClient.SendFormattedMessage(ctx, roomID, message, "org.matrix.custom.html")
   ```

3. **Збереження room_id в Django:**
   ```go
   o.storeEscalationRoom(ctx, conversationID, roomID, "", eventID, true)
   // POST до Django: /api/v1/integration/update-room
   ```

4. **Реєстрація в Bridge:**
   ```go
   o.bridge.RegisterConversation(conversationID, roomID, channel, clientID)
   // Bridge зберігає маппінг: roomID -> conversationID, channel, clientID
   ```

---

### 5. Matrix Client (Go)

**Файл:** `services/integration-service/internal/matrix/client.go`

**Функціональність:**

1. **Створення кімнати:**
   ```go
   func (c *Client) CreateRoom(ctx context.Context, name, topic string, inviteUserIDs []string) (string, error)
   // Використовує gomatrix для створення приватної кімнати
   // Invite всіх manager_user_ids
   ```

2. **Відправка повідомлень:**
   ```go
   func (c *Client) SendFormattedMessage(ctx context.Context, roomID, message, format string) (string, error)
   // Підтримка HTML форматування (org.matrix.custom.html)
   ```

3. **Інвайт користувачів:**
   ```go
   func (c *Client) InviteUser(ctx context.Context, roomID, userID string) error
   ```

---

### 6. Обробка відповідей менеджерів

**Файл:** `services/integration-service/internal/hitl/orchestrator.go`

**Метод:** `handleMatrixEvent()`

**Потік:**

1. **Matrix Sync** отримує події з кімнат
2. **Перевірка чи це escalation кімната:**
   ```go
   conversationID, channel, clientID, found := o.bridge.GetConversationByRoom(roomID)
   if !found {
       return // Не escalation кімната, ігноруємо
   }
   ```

3. **Ігнорування повідомлень від бота:**
   ```go
   if event.Sender == o.matrixClient.GetUserID() {
       return // Ігноруємо власні повідомлення
   }
   ```

4. **Витягнення тексту повідомлення:**
   ```go
   content, ok := event.Content["body"].(string)
   ```

5. **Пересилання в оригінальний канал:**
   ```go
   o.forwardToChannel(ctx, conversationID, channel, content, clientID)
   // POST до Django: /api/v1/integration/forward-message
   ```

---

### 7. Пересилання відповіді в Django

**Endpoint:** `POST /api/v1/integration/forward-message`

**Запит:**
```go
type ForwardMessageRequest struct {
    ConversationID int64  `json:"conversation_id"`
    Message        string `json:"message"`
    Channel        string `json:"channel"` // "telegram", "whatsapp", "web"
}
```

**Django обробка** (потрібно реалізувати):
- Отримує `conversation_id`, `message`, `channel`
- Викликає `process_manager_hitl_response()` task
- Відправляє повідомлення в оригінальний канал (Telegram/WhatsApp/Web)

---

## 📊 Моделі даних

### Django Models

**Client model** (`p004_ai_nexelin/MASTER/clients/models.py`):

```python
class Client(models.Model):
    # HITL налаштування
    hitl_enabled = models.BooleanField(default=False)
    manager_telegram_ids = models.JSONField(default=list)  # [123456789, ...]
    
    # Matrix HITL налаштування
    matrix_hitl_enabled = models.BooleanField(default=False)
    matrix_manager_user_ids = models.JSONField(default=list)  # ["@manager1:grot.de", ...]
    matrix_homeserver_url = models.CharField(max_length=255, default='https://matrix.org')
    matrix_bot_access_token = models.TextField(blank=True)  # Опціонально, може бути глобальний
```

**ClientWhatsAppConversation model**:

```python
class ClientWhatsAppConversation(models.Model):
    # Telegram HITL поля (існуючі)
    is_waiting_for_manager = models.BooleanField(default=False)
    manager_escalation_context = models.TextField(blank=True)
    escalation_started_at = models.DateTimeField(null=True, blank=True)
    escalation_original_query = models.TextField(blank=True)
    escalation_language = models.CharField(max_length=10, blank=True)
    
    # Matrix HITL поля (нові)
    matrix_room_id = models.CharField(max_length=255, blank=True, null=True)  # "!abc123:grot.de"
    matrix_room_alias = models.CharField(max_length=255, blank=True, null=True)  # "#escalation-123:grot.de"
    matrix_escalation_active = models.BooleanField(default=False)
    matrix_last_event_id = models.CharField(max_length=255, blank=True, null=True)
    
    # Методи
    def set_matrix_room(self, room_id: str, room_alias: str = None, event_id: str = None):
        """Зберегти Matrix room інформацію"""
        self.matrix_room_id = room_id
        self.matrix_room_alias = room_alias
        self.matrix_last_event_id = event_id
        self.matrix_escalation_active = True
        self.save(...)
    
    def mark_matrix_escalation_resolved(self):
        """Позначити ескалацію як вирішену"""
        self.matrix_escalation_active = False
        self.save(...)
```

---

### Go Models

**Escalation** (`services/integration-service/pkg/models/escalation.go`):

```go
type Escalation struct {
    ConversationID int64
    ClientID       int64
    ClientName     string
    CustomerName   string
    Channel        string  // "telegram", "whatsapp", "web"
    Question       string
    Context        string
    Language       string
    ManagerUserIDs []string  // ["@manager1:grot.de", "@manager2:grot.de"]
}
```

**Bridge** (`services/integration-service/internal/hitl/bridge.go`):

```go
type ConversationMapping struct {
    ConversationID int64
    RoomID         string  // Matrix room ID
    Channel        string  // "telegram", "whatsapp", "web"
    ClientID       int64
}

// Bridge зберігає маппінг:
// roomID -> ConversationMapping
// conversationID -> roomID
```

---

## 🔌 API Endpoints

### Integration Service (Go)

1. **POST /api/v1/hitl/escalate**
   - Створює Matrix кімнату
   - Відправляє повідомлення про ескалацію
   - Зберігає room_id в Django

2. **GET /health**
   - Health check

3. **GET /api/v1/status**
   - Статус сервісу

### Django API (потрібно реалізувати)

1. **POST /api/v1/integration/update-room**
   - Оновлює `matrix_room_id`, `matrix_escalation_active` в conversation
   - Викликається з Integration Service після створення кімнати

2. **POST /api/v1/integration/forward-message**
   - Отримує повідомлення від менеджера з Matrix
   - Викликає `process_manager_hitl_response()` task
   - Відправляє в оригінальний канал

---

## 🤖 Що потрібно Matrix боту

### 1. Облікові дані

**Production (grot.de):**
- **User ID:** `@nexelin-bot:grot.de`
- **Access Token:** `syt_bmV4ZWxpbi1ib3Q_fuwbUhVuxZFcJwDQiBac_4cfwL6`
- **Homeserver URL:** `https://matrix.grot.de`

**Local Development:**
- **Homeserver URL:** `http://localhost:8008` (для локального Synapse)

### 2. Функціональність

1. **Створення кімнат:**
   - Приватні кімнати для ескалацій
   - Інвайт менеджерів при створенні
   - Назва: `"Escalation: {ClientName} - {Channel}"`
   - Topic: `"Customer question requiring human assistance. Original channel: {channel}"`

2. **Відправка повідомлень:**
   - HTML форматування для красивого відображення
   - Структурована інформація:
     - Customer name
     - Channel (telegram/whatsapp/web)
     - Question
     - Language
     - Context

3. **Синхронізація подій:**
   - Long-polling або WebSocket для отримання нових повідомлень
   - Фільтрація тільки повідомлень з escalation кімнат
   - Ігнорування власних повідомлень

4. **Bridge маппінг:**
   - Зберігання зв'язку: `roomID <-> conversationID`
   - Визначення каналу (telegram/whatsapp/web) для пересилання

5. **Пересилання відповідей:**
   - Витягнення тексту з Matrix event
   - Відправка в Django API для обробки
   - Підтримка різних каналів

### 3. Конфігурація

**Environment variables:**
```bash
# Production (grot.de)
MATRIX_HOMESERVER_URL=https://matrix.grot.de
MATRIX_BOT_USER_ID=@nexelin-bot:grot.de
MATRIX_BOT_ACCESS_TOKEN=syt_bmV4ZWxpbi1ib3Q_fuwbUhVuxZFcJwDQiBac_4cfwL6
DJANGO_API_URL=http://localhost:8000
DJANGO_API_TOKEN=your_django_api_token
PORT=8080
```

**Примітка:** Access Token зберігається в `.env.production` (не комітиться в git)

### 4. Залежності

**Go packages:**
- `github.com/matrix-org/gomatrix` - Matrix client library
- `github.com/gin-gonic/gin` - HTTP router
- Standard Go packages для HTTP, JSON, sync

---

## 📝 Приклад повного потоку

### Сценарій: Користувач запитує щось, що потребує ескалації

1. **Користувач (Telegram):** "Яка ціна на столик на 20 осіб?"

2. **AI (ResponseGenerator):** 
   - Генерує відповідь з `[[ESCALATE_TO_MANAGER]]`
   - `requires_escalation = True`
   - `escalation_summary = "Питання про ціну столика на 20 осіб"`

3. **Django (views_telegram.py):**
   - Перевіряє `client.matrix_hitl_enabled == True`
   - Отримує `client.matrix_manager_user_ids = ["@manager1:grot.de", "@manager2:grot.de"]`
   - POST до Integration Service:
     ```json
     {
       "conversation_id": 123,
       "client_id": 5,
       "client_name": "Restaurant ABC",
       "customer_name": "John Doe",
       "channel": "telegram",
       "question": "Яка ціна на столик на 20 осіб?",
       "context": "Питання про ціну столика на 20 осіб",
       "language": "uk",
       "manager_user_ids": ["@manager1:grot.de", "@manager2:grot.de"]
     }
     ```

4. **Integration Service (orchestrator.go):**
   - Створює Matrix кімнату: `!abc123:grot.de`
   - Інвайтить менеджерів
   - Відправляє HTML повідомлення:
     ```html
     <h2>🆘 ESCALATION NEEDED</h2>
     <p><strong>Customer:</strong> John Doe<br/>
     <strong>Channel:</strong> telegram<br/>
     <strong>Question:</strong> Яка ціна на столик на 20 осіб?<br/>
     <strong>Language:</strong> uk</p>
     <p><em>Please respond in this room...</em></p>
     ```
   - Зберігає room_id в Django через API
   - Реєструє в Bridge: `!abc123:grot.de -> conversation_id=123, channel=telegram`

5. **Менеджер (Matrix клієнт):**
   - Бачить нову кімнату в списку
   - Відкриває кімнату
   - Бачить повідомлення про ескалацію
   - Відповідає: "Столик на 20 осіб коштує 500€"

6. **Integration Service (sync):**
   - Отримує подію з Matrix
   - Перевіряє: це escalation кімната? Так
   - Витягує текст: "Столик на 20 осіб коштує 500€"
   - POST до Django: `/api/v1/integration/forward-message`

7. **Django:**
   - Отримує повідомлення
   - Викликає `process_manager_hitl_response()` task
   - AI перефразовує відповідь (опціонально)
   - Відправляє в Telegram користувачу
   - Позначає ескалацію як вирішену

8. **Користувач (Telegram):**
   - Отримує відповідь: "Столик на 20 осіб коштує 500€"

---

## 🔧 Налаштування бота

### Реєстрація бота в Matrix

1. Створити обліковий запис: `@nexelin-bot:grot.de`
2. Отримати Access Token через:
   - Matrix Client API (`/login`)
   - Або через `gen_token.py` скрипт

### Конфігурація в Django Admin

1. Увімкнути Matrix HITL для клієнта:
   - `Client.matrix_hitl_enabled = True`
   - `Client.matrix_homeserver_url = "https://matrix.grot.de"`
   - `Client.matrix_manager_user_ids = ["@manager1:grot.de", "@manager2:grot.de"]`

2. Налаштувати Integration Service:
   - Environment variables з Matrix credentials
   - Django API URL та токен

---

## 📌 Важливі моменти

1. **Bridge маппінг** - критично важливий для зв'язку Matrix кімнат з conversations
2. **Синхронізація** - потрібен постійний sync з Matrix для отримання повідомлень
3. **Канали** - бот повинен знати, в який канал пересилати (telegram/whatsapp/web)
4. **HTML форматування** - для красивого відображення в Matrix клієнтах
5. **Обробка помилок** - fallback на Telegram escalation, якщо Matrix недоступний

---

## 🚀 Наступні кроки для реалізації

1. ✅ Matrix server налаштований (Synapse)
2. ✅ Integration Service структура готова
3. ⏳ Реєстрація бота в Matrix
4. ⏳ Реалізація Django API endpoints (`/update-room`, `/forward-message`)
5. ⏳ Тестування повного потоку
6. ⏳ Міграція з Telegram-only на Matrix

