# Інтеграційний гайд для Django

Цей документ описує як інтегрувати Integration Service з існуючим Django проєктом.

## Крок 1: Додайте поля до моделей (опціонально)

Якщо хочете зберігати Matrix room ID в базі даних, додайте міграцію:

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
            field=models.CharField(
                max_length=255,
                blank=True,
                null=True,
                help_text="Matrix room ID for HITL escalation"
            ),
        ),
        migrations.AddField(
            model_name='clientwhatsappconversation',
            name='matrix_room_alias',
            field=models.CharField(
                max_length=255,
                blank=True,
                null=True,
                help_text="Matrix room alias"
            ),
        ),
        migrations.AddField(
            model_name='clientwhatsappconversation',
            name='matrix_escalation_active',
            field=models.BooleanField(
                default=False,
                help_text="Whether there's an active escalation in Matrix room"
            ),
        ),
        migrations.AddField(
            model_name='clientwhatsappconversation',
            name='matrix_last_event_id',
            field=models.CharField(
                max_length=255,
                blank=True,
                null=True,
                help_text="Last processed Matrix event ID"
            ),
        ),
        migrations.AddField(
            model_name='client',
            name='matrix_hitl_enabled',
            field=models.BooleanField(
                default=False,
                help_text="Enable Matrix.org for HITL escalations"
            ),
        ),
        migrations.AddField(
            model_name='client',
            name='matrix_manager_user_ids',
            field=models.JSONField(
                default=list,
                blank=True,
                help_text="List of Matrix user IDs for managers"
            ),
        ),
        migrations.AddField(
            model_name='client',
            name='matrix_homeserver_url',
            field=models.CharField(
                max_length=255,
                default='https://matrix.org',
                blank=True,
                help_text="Matrix homeserver URL"
            ),
        ),
    ]
```

## Крок 2: Додайте API endpoints в Django

Створіть новий файл або додайте до існуючого:

```python
# MASTER/api/integration_views.py

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
from MASTER.clients.models import ClientWhatsAppConversation
import logging

logger = logging.getLogger(__name__)

@api_view(['POST'])
@permission_classes([AllowAny])  # Або використайте ваш authentication
def update_matrix_room(request):
    """
    Оновлює Matrix room ID для conversation.
    Викликається Integration Service після створення Matrix кімнати.
    """
    try:
        conversation_id = request.data.get('conversation_id')
        matrix_room_id = request.data.get('matrix_room_id')
        matrix_room_alias = request.data.get('matrix_room_alias', '')
        matrix_event_id = request.data.get('matrix_event_id', '')
        matrix_escalation_active = request.data.get('matrix_escalation_active', True)
        
        if not conversation_id or not matrix_room_id:
            return Response(
                {'error': 'conversation_id and matrix_room_id are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        conversation = ClientWhatsAppConversation.objects.get(id=conversation_id)
        conversation.matrix_room_id = matrix_room_id
        if matrix_room_alias:
            conversation.matrix_room_alias = matrix_room_alias
        if matrix_event_id:
            conversation.matrix_last_event_id = matrix_event_id
        conversation.matrix_escalation_active = matrix_escalation_active
        conversation.save(update_fields=[
            'matrix_room_id',
            'matrix_room_alias',
            'matrix_last_event_id',
            'matrix_escalation_active'
        ])
        
        logger.info(f"Updated Matrix room for conversation {conversation_id}: {matrix_room_id}")
        return Response({'status': 'ok'})
        
    except ClientWhatsAppConversation.DoesNotExist:
        return Response(
            {'error': 'Conversation not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Error updating Matrix room: {e}", exc_info=True)
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([AllowAny])  # Або використайте ваш authentication
def forward_message(request):
    """
    Форвардить повідомлення менеджера до оригінального каналу.
    Викликається Integration Service коли менеджер відповідає в Matrix кімнаті.
    """
    try:
        conversation_id = request.data.get('conversation_id')
        message = request.data.get('message')
        channel = request.data.get('channel')
        
        if not all([conversation_id, message, channel]):
            return Response(
                {'error': 'conversation_id, message, and channel are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        conversation = ClientWhatsAppConversation.objects.select_related('client').get(
            id=conversation_id
        )
        client = conversation.client
        
        # Відправте повідомлення залежно від каналу
        if channel == 'telegram' and conversation.telegram_chat_id:
            from MASTER.clients.tasks import send_telegram_message
            send_telegram_message.delay(
                client.telegram_bot_token,
                int(conversation.telegram_chat_id),
                message
            )
            logger.info(f"Forwarded message to Telegram for conversation {conversation_id}")
            
        elif channel == 'whatsapp' and conversation.customer_phone:
            # Відправте через WhatsApp API (Meta або Twilio)
            # Приклад для Meta WhatsApp:
            # from MASTER.clients.views_meta_whatsapp import send_meta_whatsapp_message
            # send_meta_whatsapp_message(client, conversation.customer_phone, message)
            logger.info(f"Forwarded message to WhatsApp for conversation {conversation_id}")
            
        elif channel in ('web', 'web_widget', 'iframe'):
            # Додайте повідомлення до conversation.messages
            if not conversation.messages:
                conversation.messages = []
            
            from django.utils import timezone
            conversation.messages.append({
                'role': 'assistant',
                'content': message,
                'timestamp': timezone.now().isoformat(),
                'metadata': {'hitl_response': True, 'source': 'matrix'}
            })
            conversation.save(update_fields=['messages'])
            logger.info(f"Added message to web conversation {conversation_id}")
        
        # Оновіть стан ескалації
        conversation.is_waiting_for_manager = False
        conversation.matrix_escalation_active = False
        conversation.save(update_fields=['is_waiting_for_manager', 'matrix_escalation_active'])
        
        return Response({'status': 'ok'})
        
    except ClientWhatsAppConversation.DoesNotExist:
        return Response(
            {'error': 'Conversation not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Error forwarding message: {e}", exc_info=True)
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
```

## Крок 3: Додайте URL routes

```python
# MASTER/urls.py

from django.urls import path
from MASTER.api.integration_views import update_matrix_room, forward_message

urlpatterns = [
    # ... existing patterns
    path('api/v1/integration/update-room', update_matrix_room, name='update_matrix_room'),
    path('api/v1/integration/forward-message', forward_message, name='forward_message'),
]
```

## Крок 4: Оновіть RAG response generator

Додайте виклик Integration Service в місці де обробляється ескалація:

```python
# MASTER/rag/response_generator.py

# В методі _generate_complete, після виявлення requires_escalation:

if requires_escalation and getattr(client, 'matrix_hitl_enabled', False):
    # Перевірте чи є Matrix manager IDs
    matrix_manager_ids = getattr(client, 'matrix_manager_user_ids', [])
    if matrix_manager_ids:
        # Викликайте Integration Service
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
            "manager_user_ids": matrix_manager_ids,
        }
        
        try:
            integration_service_url = getattr(
                settings,
                'INTEGRATION_SERVICE_URL',
                'http://localhost:8080'
            )
            
            # Використайте async або sync HTTP клієнт
            async def call_integration_service():
                async with httpx.AsyncClient() as client_http:
                    response = await client_http.post(
                        f"{integration_service_url}/api/v1/hitl/escalate",
                        json=escalation_data,
                        timeout=5.0
                    )
                    if response.status_code == 200:
                        logger.info(
                            f"Matrix escalation created for conversation {conversation.id}"
                        )
                    else:
                        logger.warning(
                            f"Failed to create Matrix escalation: {response.status_code}"
                        )
            
            # Запустіть async функцію
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            loop.run_until_complete(call_integration_service())
            
        except Exception as e:
            logger.error(f"Failed to create Matrix escalation: {e}", exc_info=True)
            # Fallback до Telegram HITL якщо потрібно
```

## Крок 5: Додайте налаштування в settings.py

```python
# MASTER/settings.py

# Integration Service Configuration
INTEGRATION_SERVICE_URL = os.getenv('INTEGRATION_SERVICE_URL', 'http://localhost:8080')
INTEGRATION_SERVICE_TIMEOUT = int(os.getenv('INTEGRATION_SERVICE_TIMEOUT', '5'))
```

## Крок 6: Налаштуйте клієнта в Django Admin

1. Відкрийте Django Admin
2. Перейдіть до Client
3. Увімкніть `matrix_hitl_enabled`
4. Додайте Matrix user IDs менеджерів: `["@manager1:matrix.org", "@manager2:matrix.org"]`
5. (Опціонально) Встановіть `matrix_homeserver_url` якщо використовуєте інший homeserver

## Тестування

1. Запустіть Integration Service:
```bash
cd services/integration-service
docker-compose up -d
```

2. Перевірте health endpoint:
```bash
curl http://localhost:8080/health
```

3. Створіть тестову ескалацію через Django або напряму:
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

4. Перевірте Matrix кімнату - ви повинні отримати запрошення

5. Відправте повідомлення в Matrix кімнаті - воно має бути форварднуте до оригінального каналу

## Troubleshooting

### Integration Service не запускається
- Перевірте змінні оточення
- Перевірте Matrix access token
- Перевірте логи: `docker-compose logs integration-service`

### Matrix кімната не створюється
- Перевірте чи правильний Matrix user ID та access token
- Перевірте чи homeserver доступний
- Перевірте логи Integration Service

### Повідомлення не форвардяться
- Перевірте чи Django API endpoint доступний
- Перевірте чи правильно налаштований DJANGO_API_URL
- Перевірте логи обох сервісів

## Production Deployment

1. Використовуйте HTTPS для всіх API calls
2. Додайте authentication для Django API endpoints
3. Налаштуйте monitoring та alerting
4. Використовуйте secrets manager для токенів
5. Налаштуйте rate limiting
6. Додайте retry logic для HTTP calls

