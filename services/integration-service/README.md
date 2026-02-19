# Integration Service - Matrix HITL

Модульний мікросервіс для інтеграції Matrix.org з Human-in-the-Loop (HITL) ескалаціями.

## Опис

Цей мікросервіс забезпечує:
- Створення Matrix кімнат для HITL ескалацій
- Синхронізацію повідомлень з Matrix
- Форвардинг відповідей менеджерів назад до оригінальних каналів (Telegram, WhatsApp, Web)

## Архітектура

```
┌─────────────┐
│ Django App  │───POST /api/v1/hitl/escalate───┐
└─────────────┘                                  │
                                                 ▼
┌─────────────┐                          ┌──────────────┐
│   Matrix    │◄──Sync Events────────────│ Integration  │
│   Server    │                          │   Service    │
└─────────────┘                          └──────────────┘
                                                 │
                                                 │ POST /api/v1/integration/forward-message
                                                 ▼
                                         ┌─────────────┐
                                         │ Django App  │
                                         └─────────────┘
```

## Встановлення

### Вимоги

- Go 1.21 або новіше
- Matrix.org акаунт (або self-hosted Synapse)
- Docker (опціонально)

### Локальна розробка

1. Клонуйте репозиторій або скопіюйте папку `services/integration-service`

2. Встановіть залежності:
```bash
cd services/integration-service
go mod download
```

3. Налаштуйте змінні оточення:
```bash
# Production (grot.de)
export MATRIX_HOMESERVER_URL=https://matrix.grot.de
export MATRIX_BOT_USER_ID=@nexelin-bot:grot.de
export MATRIX_BOT_ACCESS_TOKEN=syt_bmV4ZWxpbi1ib3Q_fuwbUhVuxZFcJwDQiBac_4cfwL6
export DJANGO_API_URL=http://localhost:8000
export DJANGO_API_TOKEN=optional_api_token
export PORT=8080
```

4. Запустіть сервіс:
```bash
go run cmd/server/main.go
```

### Docker

1. Створіть `.env` файл:
```bash
# Production (grot.de)
MATRIX_HOMESERVER_URL=https://matrix.grot.de
MATRIX_BOT_USER_ID=@nexelin-bot:grot.de
MATRIX_BOT_ACCESS_TOKEN=syt_bmV4ZWxpbi1ib3Q_fuwbUhVuxZFcJwDQiBac_4cfwL6
DJANGO_API_URL=http://django:8000
DJANGO_API_TOKEN=optional_api_token
```

2. Запустіть через docker-compose:
```bash
docker-compose up -d
```

## Створення Matrix Bot Account

1. Зареєструйтеся на [matrix.org](https://matrix.org) або вашому homeserver
2. Створіть нового користувача для бота (наприклад, `@nexelin-bot:matrix.org`)
3. Отримайте access token:
   - Використайте [Element](https://element.io) або інший Matrix клієнт
   - У налаштуваннях знайдіть "Access Token"
   - Скопіюйте токен

## API Endpoints

### POST /api/v1/hitl/escalate

Створює Matrix кімнату для ескалації.

**Request Body:**
```json
{
  "conversation_id": 123,
  "client_id": 1,
  "client_name": "Example Client",
  "customer_name": "John Doe",
  "channel": "telegram",
  "question": "How do I reset my password?",
  "context": "Customer asked about password reset",
  "language": "en",
  "manager_user_ids": ["@manager1:matrix.org", "@manager2:matrix.org"]
}
```

**Response:**
```json
{
  "status": "escalation_created",
  "message": "Matrix room created and managers notified"
}
```

### GET /health

Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "service": "integration-service"
}
```

### GET /api/v1/status

Service status endpoint.

**Response:**
```json
{
  "status": "running",
  "service": "integration-service",
  "version": "1.0.0"
}
```

## Інтеграція з Django

### 1. Додайте API endpoint в Django для оновлення Matrix room ID

```python
# MASTER/api/views.py або MASTER/clients/views.py

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from MASTER.clients.models import ClientWhatsAppConversation

@api_view(['POST'])
@permission_classes([AllowAny])  # Або використайте ваш authentication
def update_matrix_room(request):
    """Оновлює Matrix room ID для conversation"""
    conversation_id = request.data.get('conversation_id')
    matrix_room_id = request.data.get('matrix_room_id')
    matrix_room_alias = request.data.get('matrix_room_alias', '')
    matrix_event_id = request.data.get('matrix_event_id', '')
    matrix_escalation_active = request.data.get('matrix_escalation_active', True)
    
    try:
        conversation = ClientWhatsAppConversation.objects.get(id=conversation_id)
        conversation.matrix_room_id = matrix_room_id
        conversation.matrix_room_alias = matrix_room_alias
        conversation.matrix_last_event_id = matrix_event_id
        conversation.matrix_escalation_active = matrix_escalation_active
        conversation.save()
        return Response({'status': 'ok'})
    except ClientWhatsAppConversation.DoesNotExist:
        return Response({'error': 'Conversation not found'}, status=404)
```

### 2. Додайте API endpoint для форвардингу повідомлень

```python
@api_view(['POST'])
@permission_classes([AllowAny])
def forward_message(request):
    """Форвардить повідомлення менеджера до оригінального каналу"""
    conversation_id = request.data.get('conversation_id')
    message = request.data.get('message')
    channel = request.data.get('channel')
    
    try:
        conversation = ClientWhatsAppConversation.objects.get(id=conversation_id)
        client = conversation.client
        
        if channel == 'telegram' and conversation.telegram_chat_id:
            # Відправте через Telegram Bot API
            from MASTER.clients.tasks import send_telegram_message
            send_telegram_message.delay(
                client.telegram_bot_token,
                int(conversation.telegram_chat_id),
                message
            )
        elif channel == 'whatsapp':
            # Відправте через WhatsApp API
            # (ваша реалізація)
            pass
        elif channel == 'web':
            # Додайте повідомлення до conversation.messages
            conversation.add_message('assistant', message)
            conversation.save()
        
        return Response({'status': 'ok'})
    except ClientWhatsAppConversation.DoesNotExist:
        return Response({'error': 'Conversation not found'}, status=404)
```

### 3. Додайте URL routes

```python
# MASTER/urls.py

urlpatterns = [
    # ... existing patterns
    path('api/v1/integration/update-room', update_matrix_room, name='update_matrix_room'),
    path('api/v1/integration/forward-message', forward_message, name='forward_message'),
]
```

### 4. Викликайте Integration Service з RAG response generator

```python
# MASTER/rag/response_generator.py

if requires_escalation and getattr(client, 'matrix_hitl_enabled', False):
    import httpx
    import asyncio
    
    escalation_data = {
        "conversation_id": conversation.id if conversation else None,
        "client_id": client.id,
        "client_name": client.company_name,
        "customer_name": customer_name or "Customer",
        "channel": channel,  # "telegram", "whatsapp", "web"
        "question": query,
        "context": escalation_summary or "",
        "language": language or "en",
        "manager_user_ids": client.matrix_manager_user_ids or [],
    }
    
    try:
        integration_service_url = getattr(settings, 'INTEGRATION_SERVICE_URL', 'http://localhost:8080')
        async with httpx.AsyncClient() as client_http:
            response = await client_http.post(
                f"{integration_service_url}/api/v1/hitl/escalate",
                json=escalation_data,
                timeout=5.0
            )
            if response.status_code == 200:
                logger.info(f"Matrix escalation created for conversation {conversation.id}")
    except Exception as e:
        logger.error(f"Failed to create Matrix escalation: {e}")
```

## Міграція бази даних Django (опціонально)

Якщо потрібно зберігати Matrix room ID в базі даних:

```python
# MASTER/clients/migrations/XXXX_add_matrix_fields.py

from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('clients', 'XXXX_previous_migration'),
    ]

    operations = [
        migrations.AddField(
            model_name='clientwhatsappconversation',
            name='matrix_room_id',
            field=models.CharField(max_length=255, blank=True, null=True),
        ),
        migrations.AddField(
            model_name='clientwhatsappconversation',
            name='matrix_room_alias',
            field=models.CharField(max_length=255, blank=True, null=True),
        ),
        migrations.AddField(
            model_name='clientwhatsappconversation',
            name='matrix_escalation_active',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='clientwhatsappconversation',
            name='matrix_last_event_id',
            field=models.CharField(max_length=255, blank=True, null=True),
        ),
        migrations.AddField(
            model_name='client',
            name='matrix_hitl_enabled',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='client',
            name='matrix_manager_user_ids',
            field=models.JSONField(default=list, blank=True),
        ),
    ]
```

## Тестування

### Тестовий запит

```bash
curl -X POST http://localhost:8080/api/v1/hitl/escalate \
  -H "Content-Type: application/json" \
  -d '{
    "conversation_id": 123,
    "client_id": 1,
    "client_name": "Test Client",
    "customer_name": "Test Customer",
    "channel": "telegram",
    "question": "Test question",
    "context": "Test context",
    "language": "en",
    "manager_user_ids": ["@your_matrix_user:matrix.org"]
  }'
```

## Моніторинг

Сервіс логує всі важливі події:
- Створення Matrix кімнат
- Отримання повідомлень від менеджерів
- Форвардинг повідомлень
- Помилки

Перевіряйте логи для моніторингу:
```bash
docker-compose logs -f integration-service
```

## Безпека

1. **Access Tokens**: Зберігайте Matrix access tokens в безпечному місці (secrets manager, environment variables)
2. **API Authentication**: Додайте authentication для Django API endpoints
3. **HTTPS**: Використовуйте HTTPS в production
4. **Rate Limiting**: Matrix API має rate limits - додайте retry logic

## Ліцензія

MIT

