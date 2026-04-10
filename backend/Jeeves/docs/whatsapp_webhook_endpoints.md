# WhatsApp Meta Webhook Endpoints - Полная HTTP документация

## Эндпоинты

1. **Основной**: `/api/whatsapp/meta/webhook/`
2. **Альтернативный**: `/api/clients/whatsapp/meta/webhook/`

Оба эндпоинта используют один и тот же view (`MetaWhatsAppWebhookView`) и работают идентично.

---

## 1. GET запрос - Верификация Webhook (Meta)

Meta отправляет GET запрос для верификации webhook при первоначальной настройке.

### Запрос

```http
GET /api/whatsapp/meta/webhook/?hub.mode=subscribe&hub.verify_token=YOUR_VERIFY_TOKEN&hub.challenge=RANDOM_CHALLENGE_STRING HTTP/1.1
Host: api.example.com
User-Agent: facebookexternalua
Accept: */*
```

**Параметры URL:**
- `hub.mode` - должен быть `"subscribe"`
- `hub.verify_token` - токен верификации (должен совпадать с `Client.meta_verify_token` или глобальным `META_VERIFY_TOKEN`)
- `hub.challenge` - случайная строка, которую Meta ожидает получить в ответе

### Успешный ответ (200 OK)

```http
HTTP/1.1 200 OK
Content-Type: text/html; charset=utf-8
Content-Length: 20

RANDOM_CHALLENGE_STRING
```

**Важно:** Ответ должен содержать **точно** значение `hub.challenge` из запроса.

### Неуспешный ответ (403 Forbidden)

```http
HTTP/1.1 403 Forbidden
Content-Type: text/html; charset=utf-8
```

**Причины отказа:**
- `hub.mode` не равен `"subscribe"`
- `hub.verify_token` не найден в базе данных (нет клиента с таким `meta_verify_token` и `whatsapp_meta_enabled=True`)

---

## 2. POST запрос - Получение сообщений и статусов

Meta отправляет POST запрос при получении сообщений или изменении их статуса.

### Запрос

```http
POST /api/whatsapp/meta/webhook/ HTTP/1.1
Host: api.example.com
Content-Type: application/json
X-Hub-Signature-256: sha256=abc123def456...
User-Agent: facebookexternalua
Content-Length: 1234
```

**Заголовки:**
- `Content-Type: application/json` - обязательно
- `X-Hub-Signature-256` - подпись запроса для верификации (формат: `sha256=<hex_digest>`)
- `User-Agent: facebookexternalua` - стандартный User-Agent от Meta

### Тело запроса - Входящее сообщение

```json
{
  "object": "whatsapp_business_account",
  "entry": [
    {
      "id": "WHATSAPP_BUSINESS_ACCOUNT_ID",
      "changes": [
        {
          "value": {
            "messaging_product": "whatsapp",
            "metadata": {
              "display_phone_number": "15550551234",
              "phone_number_id": "123456789012345"
            },
            "messages": [
              {
                "from": "15551234567",
                "id": "wamid.XXX",
                "timestamp": "1234567890",
                "type": "text",
                "text": {
                  "body": "Привіт! Як справи?"
                }
              }
            ]
          },
          "field": "messages"
        }
      ]
    }
  ]
}
```

### Тело запроса - Статус доставки

```json
{
  "object": "whatsapp_business_account",
  "entry": [
    {
      "id": "WHATSAPP_BUSINESS_ACCOUNT_ID",
      "changes": [
        {
          "value": {
            "messaging_product": "whatsapp",
            "metadata": {
              "display_phone_number": "15550551234",
              "phone_number_id": "123456789012345"
            },
            "statuses": [
              {
                "id": "wamid.XXX",
                "status": "delivered",
                "timestamp": "1234567890",
                "recipient_id": "15551234567"
              }
            ]
          },
          "field": "messages"
        }
      ]
    }
  ]
}
```

**Возможные статусы:**
- `sent` - сообщение отправлено
- `delivered` - сообщение доставлено
- `read` - сообщение прочитано
- `failed` - ошибка отправки

### Успешный ответ (200 OK)

```http
HTTP/1.1 200 OK
Content-Type: text/html; charset=utf-8
Content-Length: 0
```

### Ошибка верификации подписи (403 Forbidden)

```http
HTTP/1.1 403 Forbidden
Content-Type: text/html; charset=utf-8
```

**Причины:**
- Отсутствует заголовок `X-Hub-Signature-256`
- Подпись не совпадает (неверный `meta_app_secret`)

### Внутренняя ошибка (500 Internal Server Error)

```http
HTTP/1.1 500 Internal Server Error
Content-Type: text/html; charset=utf-8
```

---

## Верификация подписи

Система проверяет подпись запроса следующим образом:

1. Извлекает `X-Hub-Signature-256` из заголовков
2. Вычисляет HMAC SHA256 от `request.body` используя `meta_app_secret`
3. Сравнивает вычисленную подпись с полученной

**Приоритет секрета:**
1. `Client.meta_app_secret` (если клиент найден по `phone_number_id`)
2. Глобальный `settings.META_APP_SECRET`

**Формат подписи:**
```
sha256=<hex_digest>
```

Пример:
```
X-Hub-Signature-256: sha256=abc123def456789...
```

---

## Примеры с curl

### Верификация webhook

```bash
curl -X GET "https://api.example.com/api/whatsapp/meta/webhook/?hub.mode=subscribe&hub.verify_token=my_verify_token_123&hub.challenge=challenge_string_456"
```

### Тестовый POST запрос (без подписи - для разработки)

```bash
curl -X POST "https://api.example.com/api/whatsapp/meta/webhook/" \
  -H "Content-Type: application/json" \
  -d '{
    "object": "whatsapp_business_account",
    "entry": [{
      "id": "123",
      "changes": [{
        "value": {
          "messaging_product": "whatsapp",
          "metadata": {
            "phone_number_id": "123456789012345"
          },
          "messages": [{
            "from": "15551234567",
            "id": "wamid.test",
            "timestamp": "1234567890",
            "type": "text",
            "text": {
              "body": "Test message"
            }
          }]
        },
        "field": "messages"
      }]
    }]
  }'
```

---

## Подтверждение маркера (Verify Token) - Подробное объяснение

### Что такое Verify Token?

**Verify Token** (маркер подтверждения) — это секретный токен, который используется для подтверждения, что webhook действительно принадлежит вашему серверу. Это защита от несанкционированных запросов.

### Как это работает?

1. **При настройке webhook в Meta Business Manager:**
   - Вы указываете URL webhook: `https://api.example.com/api/whatsapp/meta/webhook/`
   - Вы указываете Verify Token: например, `my_secret_token_12345`

2. **Meta отправляет GET запрос для проверки:**
   ```
   GET /api/whatsapp/meta/webhook/?hub.mode=subscribe&hub.verify_token=my_secret_token_12345&hub.challenge=random_string
   ```

3. **Ваш сервер проверяет токен:**
   - Ищет клиента в базе данных с `meta_verify_token = "my_secret_token_12345"`
   - Если токен совпадает → возвращает `hub.challenge` (подтверждение)
   - Если токен не совпадает → возвращает 403 Forbidden (отказ)

4. **Meta получает ответ:**
   - Если получил правильный `challenge` → webhook активирован ✅
   - Если получил ошибку → webhook не активирован ❌

### Где взять/настроить Verify Token?

#### Вариант 1: Per-client настройка (рекомендуется)

Каждый клиент может иметь свой уникальный токен:

1. **Через API:**
   ```http
   PATCH /api/clients/whatsapp/meta/config/
   Authorization: Bearer YOUR_API_KEY
   
   {
     "meta_verify_token": "my_unique_token_for_client_123"
   }
   ```

2. **Через Django Admin:**
   - Зайдите в админку → Clients → выберите клиента
   - Найдите поле `Meta verify token`
   - Введите токен (например: `client_abc_xyz_123`)
   - Сохраните

3. **Через базу данных:**
   ```sql
   UPDATE clients_client 
   SET meta_verify_token = 'my_token_123' 
   WHERE id = 1;
   ```

#### Вариант 2: Глобальная настройка

Если не используется per-client конфигурация, можно использовать глобальный токен:

```python
# В settings.py или .env файле
META_VERIFY_TOKEN = "global_verify_token_456"
```

**Приоритет:** Per-client токен имеет приоритет над глобальным.

### Как создать безопасный Verify Token?

Рекомендуется использовать случайную строку длиной 20-40 символов:

**Примеры хороших токенов:**
```
your_verify_token_here
client_1_verify_token_secure_789
whatsapp_meta_verify_xyz456def
```

**Примеры плохих токенов (не используйте):**
```
12345                    # слишком короткий
password                 # легко угадать
token                    # слишком простой
```

**Генерация токена (Python):**
```python
import secrets
token = secrets.token_urlsafe(32)
# Результат: 'abc123xyz456...' (32 байта в base64)
```

**Генерация токена (bash):**
```bash
openssl rand -hex 20
# Результат: 'a1b2c3d4e5f6...' (40 символов)
```

### Где указать Verify Token в Meta Business Manager?

1. Зайдите в [Meta Business Manager](https://business.facebook.com/)
2. Выберите ваше приложение → WhatsApp → Configuration
3. В разделе **Webhook** нажмите **Edit**
4. В поле **Verify Token** введите ваш токен (например: `my_secret_token_12345`)
5. В поле **Callback URL** введите: `https://api.example.com/api/whatsapp/meta/webhook/`
6. Нажмите **Verify and Save**

### Важные моменты

⚠️ **Безопасность:**
- Храните токен в секрете (не коммитьте в git)
- Используйте разные токены для разных клиентов
- Регулярно меняйте токены

⚠️ **Требования:**
- Токен должен быть уникальным для каждого клиента (если используется per-client конфигурация)
- Клиент должен иметь `whatsapp_meta_enabled=True` для работы верификации
- Токен может содержать буквы, цифры, дефисы и подчеркивания

⚠️ **Ограничения:**
- Максимальная длина: 128 символов (ограничение модели)
- Минимальная длина: рекомендуется не менее 16 символов

### Пример полного процесса настройки

1. **Создайте токен:**
   ```bash
   openssl rand -hex 20
   # Результат: a1b2c3d4e5f6789012345678901234567890ab
   ```

2. **Сохраните токен в базе данных:**
   ```python
   client = Client.objects.get(id=1)
   client.meta_verify_token = "a1b2c3d4e5f6789012345678901234567890ab"
   client.whatsapp_meta_enabled = True
   client.save()
   ```

3. **Укажите токен в Meta Business Manager:**
   - Verify Token: `a1b2c3d4e5f6789012345678901234567890ab`
   - Callback URL: `https://api.example.com/api/whatsapp/meta/webhook/`

4. **Meta автоматически отправит GET запрос:**
   ```
   GET /api/whatsapp/meta/webhook/?hub.mode=subscribe&hub.verify_token=a1b2c3d4e5f6789012345678901234567890ab&hub.challenge=xyz789
   ```

5. **Ваш сервер вернет challenge:**
   ```
   HTTP/1.1 200 OK
   xyz789
   ```

6. **Webhook активирован! ✅**

---

## Настройка в Meta Business Manager

1. **Callback URL**: `https://api.example.com/api/whatsapp/meta/webhook/`
   или `https://api.example.com/api/clients/whatsapp/meta/webhook/`

2. **Verify Token**: Значение из `Client.meta_verify_token` (для per-client настройки)
   или глобальный `META_VERIFY_TOKEN` из settings
   
   **Как узнать токен клиента:**
   - Через API: `GET /api/clients/whatsapp/meta/config/` (требует авторизацию)
   - Через Django Admin: Clients → выберите клиента → поле "Meta verify token"
   - Через базу данных: `SELECT meta_verify_token FROM clients_client WHERE id = X;`

3. **Подписи**: Включите проверку подписи и укажите `meta_app_secret` в настройках клиента

---

## Отладка проблем с верификацией

### Ошибка: "Проверка URL обратного вызова или маркера подтверждения не пройдена"

Если вы получаете эту ошибку при настройке webhook в Meta Business Manager, проверьте следующее:

#### 1. Проверьте, что токен сохранен в базе данных

**Через Django Admin:**
1. Зайдите в Django Admin → Clients
2. Выберите нужного клиента
3. Проверьте поле **"Meta verify token"** - должно быть: `your_verify_token_here`
4. Проверьте поле **"Whatsapp meta enabled"** - должно быть включено (✅)

**Через базу данных:**
```sql
SELECT id, company_name, meta_verify_token, whatsapp_meta_enabled 
FROM clients_client 
WHERE meta_verify_token = 'your_verify_token_here';
```

**Через API:**
```bash
curl -X GET "https://api.example.com/api/clients/whatsapp/meta/config/" \
  -H "Authorization: Bearer YOUR_API_KEY"
```

#### 2. Проверьте логи сервера

После попытки верификации в Meta, проверьте логи Django:

```bash
# Если используете Docker
docker-compose logs -f web | grep "Meta WhatsApp webhook"

# Или напрямую в логах Django
tail -f /path/to/logs/django.log | grep "Meta WhatsApp"
```

**Ожидаемые логи при успешной верификации:**
```
INFO: Meta WhatsApp webhook verification request: mode=subscribe, token_length=32, challenge_length=20
INFO: Meta WhatsApp webhook verified successfully for client: 1 (Company Name)
```

**Логи при ошибке:**
```
WARNING: Meta WhatsApp webhook verification failed:
  - Received token: your_ver...... (length: 32)
  - Clients with this token: 0
  - Clients with enabled WhatsApp: 1
  - Global token set: False
```

#### 3. Проверьте точное совпадение токена

⚠️ **Важно:** Токен должен совпадать **точно**, включая регистр и все символы!

**Проверьте:**
- Нет ли лишних пробелов в начале или конце
- Правильный ли регистр букв
- Нет ли опечаток

**Пример правильного токена:**
```
your_verify_token_here
```

**Примеры неправильных токенов:**
```
your_verify_token_here   # лишний пробел в конце
Nexelin_webhook_2024_abc123xyz   # неправильный регистр
your_verify_token_here_    # не хватает символа
```

#### 4. Проверьте, что `whatsapp_meta_enabled=True`

Токен не будет работать, если у клиента не включен WhatsApp Meta:

```sql
-- Проверка
SELECT id, company_name, whatsapp_meta_enabled, meta_verify_token 
FROM clients_client 
WHERE id = YOUR_CLIENT_ID;

-- Включение (если нужно)
UPDATE clients_client 
SET whatsapp_meta_enabled = TRUE 
WHERE id = YOUR_CLIENT_ID;
```

#### 5. Проверьте URL обратного вызова

Убедитесь, что URL точно совпадает:
- ✅ Правильно: `https://api.example.com/api/whatsapp/meta/webhook/`
- ❌ Неправильно: `https://api.example.com/api/whatsapp/meta/webhook` (без слеша в конце)
- ❌ Неправильно: `http://api.example.com/api/whatsapp/meta/webhook/` (http вместо https)

#### 6. Тестовая верификация через curl

Проверьте верификацию вручную:

```bash
curl -X GET "https://api.example.com/api/whatsapp/meta/webhook/?hub.mode=subscribe&hub.verify_token=your_verify_token_here&hub.challenge=test123" \
  -v
```

**Ожидаемый ответ:**
```http
HTTP/1.1 200 OK
Content-Type: text/html; charset=utf-8

test123
```

**Если получаете 403:**
- Проверьте токен в базе данных
- Проверьте логи сервера для деталей

#### 7. Использование глобального токена (fallback)

Если per-client токен не работает, можно использовать глобальный:

**В settings.py или .env:**
```python
META_VERIFY_TOKEN = "your_verify_token_here"
```

**В Meta Business Manager:**
- Verify Token: `your_verify_token_here` (тот же, что в settings)

#### 8. Частые проблемы и решения

| Проблема | Решение |
|----------|---------|
| Токен не найден | Проверьте, что токен сохранен в БД и `whatsapp_meta_enabled=True` |
| 403 Forbidden | Проверьте точное совпадение токена (регистр, пробелы) |
| URL не доступен | Проверьте, что сервер доступен и URL правильный |
| Таймаут | Проверьте firewall и настройки сети |
| Неправильный challenge | Проверьте, что сервер возвращает точно значение `hub.challenge` |

#### 9. Пошаговая инструкция для исправления

1. **Откройте Django Admin:**
   ```
   https://api.example.com/admin/clients/client/
   ```

2. **Найдите клиента** и откройте его

3. **В разделе "WhatsApp (Meta)":**
   - ✅ Включите **"Whatsapp meta enabled"**
   - Введите токен в поле **"Meta verify token"**: `your_verify_token_here`
   - Сохраните

4. **Проверьте в базе данных:**
   ```sql
   SELECT meta_verify_token, whatsapp_meta_enabled 
   FROM clients_client 
   WHERE id = YOUR_CLIENT_ID;
   ```

5. **Попробуйте верификацию в Meta Business Manager снова**

6. **Проверьте логи** для детальной информации об ошибке

---

## Обработка сообщений

Система обрабатывает:
- ✅ Текстовые сообщения (`type: "text"`)
- ✅ Интерактивные сообщения (`type: "interactive"`) - кнопки и меню
- ✅ Команды START2 для QR-кодов
- ⏭️ Статусы доставки (пропускаются, но логируются)

**Не поддерживается:**
- Медиа файлы (изображения, видео, аудио)
- Документы
- Локации
- Контакты

---

## Логирование

Все запросы логируются:
- Успешная верификация: `INFO: Meta WhatsApp webhook verified successfully`
- Получение сообщения: `INFO: Meta WhatsApp Webhook POST: {...}`
- Ошибки: `ERROR: Error processing Meta webhook: ...`

---

## Безопасность

1. **CSRF отключен** - используется `@method_decorator(csrf_exempt)`
2. **Проверка подписи** - обязательна для POST запросов
3. **Per-client токены** - каждый клиент может иметь свой `meta_verify_token`
4. **Per-client секреты** - каждый клиент может иметь свой `meta_app_secret`

---

## Альтернативный эндпоинт

Эндпоинт `/api/clients/whatsapp/meta/webhook/` работает **идентично** основному.

Используйте любой из них в зависимости от вашей конфигурации URL.

