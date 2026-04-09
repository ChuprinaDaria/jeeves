# Matrix HITL Setup Guide

## Швидкий старт

### 1. Застосуйте міграцію

```bash
cd backend
python manage.py migrate
```

### 2. Налаштуйте змінні оточення

Додайте в `.env` або `docker-compose.yml`:

```bash
MATRIX_HOMESERVER_URL=https://matrix.org
MATRIX_BOT_USER_ID=@nexelin-bot:matrix.org
MATRIX_BOT_ACCESS_TOKEN=your_access_token_here
DJANGO_API_TOKEN=optional_api_token
```

### 3. Запустіть сервіси

```bash
docker-compose up -d
```

Integration Service автоматично підніметься разом з іншими сервісами.

### 4. Налаштуйте клієнта в Django Admin

1. Відкрийте Django Admin → Clients
2. Виберіть клієнта
3. Розгорніть секцію **"Matrix.org HITL (Unified Interface)"**
4. Встановіть галочку **"Matrix hitl enabled"**
5. Додайте Matrix user IDs менеджерів: `["@manager1:matrix.org", "@manager2:matrix.org"]`
   - Кожен менеджер має бути зареєстрований на Matrix homeserver
   - Можна додати кілька менеджерів - всі отримають приглашення в кімнату
6. (Опціонально) Змініть Matrix homeserver URL
7. Збережіть

**💡 Підказка:** В списку клієнтів (list view) ви побачите колонку **"Matrix Managers"** з кількістю налаштованих менеджерів для кожного клієнта.

## Створення Matrix Bot Account

1. Зареєструйтеся на [matrix.org](https://matrix.org) або вашому homeserver
2. Створіть нового користувача для бота (наприклад, `@nexelin-bot:matrix.org`)
3. Отримайте access token:
   - Використайте [Element](https://element.io) або інший Matrix клієнт
   - У налаштуваннях знайдіть "Access Token"
   - Скопіюйте токен

## 📋 Короткая инструкция (Русский)

### Где взять Matrix Access Token:

1. **Зарегистрируйтесь на matrix.org**:
   - Перейдите на https://app.element.io (веб-версия Element)
   - Создайте аккаунт (например, `@nexelin-bot:matrix.org`)

2. **Получите Access Token**:
   - Войдите в Element
   - Нажмите на аватар (левый верхний угол) → **Settings** (Настройки)
   - Перейдите в **Help & About** → **Advanced**
   - Найдите **Access Token** → нажмите **Show** → скопируйте токен
   - Или используйте URL: `https://app.element.io/#/settings/help`

3. **Добавьте токен в docker-compose.yml**:
   ```yaml
   MATRIX_BOT_USER_ID=@nexelin-bot:matrix.org
   MATRIX_BOT_ACCESS_TOKEN=syt_nexelinbot_ваш_токен_тут
   ```

   **⚠️ Важно:** Один Matrix bot account використовується для **всіх клієнтів**. 
   Не потрібно створювати окремий бот для кожного клієнта - бот створює окремі кімнати для кожної ескалації.

   **⚠️ Важно:** Один Matrix bot account використовується для **всіх клієнтів**. 
   Не потрібно створювати окремий бот для кожного клієнта - бот створює окремі кімнати для кожної ескалації.

### Где смотреть комнату менеджера:

1. **После создания эскалации**:
   - Бот автоматически создаст Matrix комнату
   - Менеджеры из списка `matrix_manager_user_ids` получат приглашение

2. **Откройте Element**:
   - Войдите под аккаунтом менеджера (например, `@manager1:matrix.org`)
   - В списке комнат появится новая комната: **"Escalation: [Client Name] - [Channel]"**
   - Откройте комнату и увидите сообщение с деталями эскалации

3. **Ответьте в комнате**:
   - Напишите ответ в Matrix комнате
   - Сообщение автоматически перешлется обратно в оригинальный канал (Telegram/WhatsApp/Web)

### Быстрая проверка:

```bash
# Проверьте логи Integration Service
docker-compose logs integration-service | grep "Matrix room"

# Проверьте создание комнаты
docker-compose logs integration-service | grep "Created Matrix room"
```

## Перевірка роботи

1. Перевірте health endpoint:
```bash
curl http://localhost:8080/health
```

2. Перевірте логи:
```bash
docker-compose logs integration-service
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

## Troubleshooting

### Integration Service не запускається
- Перевірте змінні оточення в docker-compose.yml
- Перевірте чи правильний Matrix access token
- Перевірте логи: `docker-compose logs integration-service`

### Matrix кімната не створюється
- Перевірте чи правильний Matrix user ID та access token
- Перевірте чи homeserver доступний
- Перевірте логи Integration Service

### Повідомлення не форвардяться
- Перевірте чи Django API endpoint доступний
- Перевірте чи правильно налаштований DJANGO_API_URL
- Перевірте логи обох сервісів

## Додаткова документація

- `services/integration-service/README.md` - Документація Integration Service
- `services/integration-service/INTEGRATION_GUIDE.md` - Детальний гайд по інтеграції
- `docs/MATRIX_HITL_INTEGRATION_PLAN.md` - Повний план інтеграції

