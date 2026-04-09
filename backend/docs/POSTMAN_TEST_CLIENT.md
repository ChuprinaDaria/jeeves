# Тестування API створення клієнта в Postman

## 📋 Крок 1: Налаштування Postman

### Створіть новий Request:
1. Method: **POST**
2. URL: `https://api.nexelin.com/api/clients/`

## 📝 Крок 2: Додайте Headers

### Вкладка "Headers":
```
Content-Type: application/json
```

## 💾 Крок 3: Додайте Body

### Вкладка "Body":
- Виберіть: **raw**
- Формат: **JSON**

### Мінімальний приклад (обов'язкові поля):
```json
{
  "user": "Іван Петренко",
  "tag": "my-company",
  "description": "Опис моєї компанії"
}
```

### Повний приклад з усіма полями:
```json
{
  "user": "Іван Петренко",
  "branch": 1,
  "specialization": 1,
  "company_name": "Моя Ресторанна Компанія",
  "tag": "my-restaurant",
  "description": "Ресторан пропонує італійську кухню з сучасним підходом",
  "client_type": "restaurant",
  "features": {
    "menu_chat": true,
    "allergens": true,
    "calories": true,
    "table_ordering": true,
    "multilingual": true
  },
  "custom_system_prompt": "Ви AI-асистент для італійського ресторану. Допоможіть клієнтам з меню.",
  "is_active": true
}
```

## ✅ Очікувана відповідь (201 Created):

```json
{
  "id": 1,
  "user": "Іван Петренко",
  "branch": 1,
  "branch_name": "Ресторани",
  "specialization": 1,
  "specialization_name": "Італійська кухня",
  "company_name": "Моя Ресторанна Компанія",
  "tag": "my-restaurant",
  "description": "Ресторан пропонує італійську кухню з сучасним підходом",
  "api_key": "abc123xyz456def789...",
  "logo": null,
  "logo_url": null,
  "is_active": true,
  "client_type": "restaurant",
  "features": {
    "menu_chat": true,
    "allergens": true,
    "calories": true,
    "table_ordering": true,
    "multilingual": true
  },
  "custom_system_prompt": "Ви AI-асистент для італійського ресторану. Допоможіть клієнтам з меню.",
  "created_by": 1,
  "created_at": "2025-12-26T12:00:00Z",
  "updated_at": "2025-12-26T12:00:00Z"
}
```

## ❌ Можливі помилки:

### 400 Bad Request - Не всі обов'язкові поля:
```json
{
  "tag": ["This field is required."],
  "description": ["This field is required."]
}
```

### 403 Forbidden - Немає прав:
```json
{
  "detail": "You do not have permission to perform this action."
}
```

### 401 Unauthorized - Невірний токен:
```json
{
  "detail": "Authentication credentials were not provided."
}
```

## 🌐 Для фронтенду (React/TypeScript/JavaScript)

Якщо ви створюєте клієнта з фронтенду `https://mg.nexelin.com/star/package-types`:

```javascript
const createClient = await fetch('https://api.nexelin.com/api/clients/', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    user: 1,
    tag: 'my-company',
    description: 'Моя компанія'
  })
});

const clientData = await createClient.json();
console.log(clientData);
```

## 🎯 Швидкий експорт для Postman

Скопіюйте цей JSON в Postman → Import → Raw text:

```json
{
  "info": {
    "name": "Create Client",
    "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
  },
  "item": [
    {
      "name": "Create Client",
      "request": {
        "method": "POST",
        "header": [
          {
            "key": "Content-Type",
            "value": "application/json"
          }
        ],
        "body": {
          "mode": "raw",
          "raw": "{\n  \"user\": 1,\n  \"branch\": 1,\n  \"specialization\": 1,\n  \"company_name\": \"Моя Компанія\",\n  \"tag\": \"my-company\",\n  \"description\": \"Опис компанії\",\n  \"client_type\": \"restaurant\",\n  \"features\": {\n    \"menu_chat\": true\n  },\n  \"is_active\": true\n}"
        },
        "url": {
          "raw": "{{base_url}}/api/clients/",
          "host": ["{{base_url}}"],
          "path": ["api", "clients", ""]
        }
      }
    }
  ]
}
```

## 📚 Примітки:

1. **API ключ** (`api_key`) генерується автоматично, не потрібно надсилати
2. **Branch** і **Specialization** опціональні (можна не надсилати або `null`)
3. **created_by** встановлюється автоматично з токену
4. **User ID** має бути валідним ID користувача з role='client'

## 🧪 Інші корисні запити для тестування:

### Отримати всіх клієнтів:
```
GET /api/clients/clients/
```

### Отримати одного клієнта:
```
GET /api/clients/clients/1/
```

### Оновити клієнта:
```
PATCH /api/clients/clients/1/
Body: {"company_name": "Нова назва"}
```

### Видалити клієнта:
```
DELETE /api/clients/clients/1/
```

### Отримати статистику клієнта:
```
GET /api/clients/1/stats/
```

