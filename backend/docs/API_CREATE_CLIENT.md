# API: Створення клієнта

## Endpoint
```
POST /api/clients/
```
(правильний URL після виправлення конфігурації роутера)

## Опис
Створює нового клієнта в системі. API ключ генерується автоматично через `secrets.token_urlsafe(32)`.

## Авторизація

API публічний - авторизація не потрібна для створення клієнта.

## Тіло запиту (JSON)

### Приклад запиту:
```json
{
  "user": "Іван Петренко",
  "branch": 2,
  "specialization": 3,
  "company_name": "Моя Компанія",
  "tag": "my-company-tag",
  "description": "Опис компанії для клієнта",
  "client_type": "restaurant",
  "features": {
    "menu_chat": true,
    "allergens": true,
    "calories": true
  },
  "custom_system_prompt": "Ви AI-асистент для ресторану",
  "is_active": true
}
```

### Обов'язкові поля:
- `user` (string, max 255) - **Ім'я користувача** (наприклад: "Іван Петренко")
- `tag` (string, max 255) - Унікальний тег клієнта
- `description` (text) - Опис клієнта

### Опціональні поля:
- `branch` (integer, nullable) - ID філії (null=True)
- `specialization` (integer, nullable) - ID спеціалізації (null=True)
- `company_name` (string, max 200) - Назва компанії
- `client_type` (string) - Тип клієнта:
  - `generic` (за замовчуванням)
  - `restaurant`
  - `hotel`
  - `medical`
  - `retail`
- `features` (JSON object) - Конфігурація функцій
- `custom_system_prompt` (text) - Кастомний системний промпт для AI
- `is_active` (boolean, default=true) - Активний статус
- `logo` (file, через multipart/form-data) - Логотип

### Автоматично генеруються:
- `api_key` (string, max 64) - API ключ через `secrets.token_urlsafe(32)`
- `created_at` (datetime) - Дата створення
- `updated_at` (datetime) - Дата оновлення
- `created_by` (integer, nullable) - ID користувача, який створив

## Відповідь

### Успіх (201 Created):
```json
{
  "id": 1,
  "user": "Іван Петренко",
  "branch": 2,
  "branch_name": "Філія 1",
  "specialization": 3,
  "specialization_name": "Ресторан",
  "company_name": "Моя Компанія",
  "tag": "my-company-tag",
  "description": "Опис компанії для клієнта",
  "api_key": "abc123xyz456...",
  "logo": null,
  "logo_url": null,
  "is_active": true,
  "client_type": "restaurant",
  "features": {
    "menu_chat": true,
    "allergens": true,
    "calories": true
  },
  "custom_system_prompt": "Ви AI-асистент для ресторану",
  "created_by": 1,
  "created_at": "2025-12-26T12:00:00Z",
  "updated_at": "2025-12-26T12:00:00Z"
}
```

### Помилка (400 Bad Request):
```json
{
  "user": ["This field is required."],
  "tag": ["This field is required."],
  "description": ["This field is required."]
}
```

### Помилка (403 Forbidden):
```json
{
  "error": "Permission denied"
}
```

## Приклади використання

### cURL:
```bash
curl -X POST https://api.nexelin.com/api/clients/ \
  -H "Content-Type: application/json" \
  -d '{
    "user": "Іван Петренко",
    "tag": "my-company",
    "description": "Моя компанія опис"
  }'
```

### JavaScript (fetch):
```javascript
const response = await fetch('https://api.nexelin.com/api/clients/', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    user: 1,
    branch: 2,
    specialization: 3,
    company_name: "Моя Компанія",
    tag: "my-company",
    description: "Опис компанії для клієнта",
    client_type: "restaurant",
    features: {
      menu_chat: true,
      allergens: true,
      calories: true
    },
    is_active: true
  })
});

const data = await response.json();
console.log(data);
```

### Python (requests):
```python
import requests

url = "https://api.nexelin.com/api/clients/"
headers = {
    "Content-Type": "application/json"
}
data = {
    "user": "Іван Петренко",
    "branch": 2,
    "specialization": 3,
    "company_name": "Моя Компанія",
    "tag": "my-company",
    "description": "Опис компанії для клієнта",
    "client_type": "restaurant",
    "features": {
        "menu_chat": True,
        "allergens": True,
        "calories": True
    },
    "is_active": True
}

response = requests.post(url, headers=headers, json=data)
print(response.json())
```

### React/TypeScript:
```typescript
interface CreateClientRequest {
  user: string;
  branch?: number | null;
  specialization?: number | null;
  company_name?: string;
  tag: string;
  description: string;
  client_type?: 'generic' | 'restaurant' | 'hotel' | 'medical' | 'retail';
  features?: Record<string, any>;
  custom_system_prompt?: string;
  is_active?: boolean;
}

const createClient = async (data: CreateClientRequest) => {
  const response = await fetch('https://api.nexelin.com/api/clients/', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(data)
  });
  
  if (!response.ok) {
    throw new Error('Failed to create client');
  }
  
  return response.json();
};
```

## Примітки

1. **API ключ** генерується автоматично при створенні клієнта через `secrets.token_urlsafe(32)` і не може бути змінений через API
2. **user** - це текст з ім'ям (наприклад: "Іван Петренко")
3. **Branch** і **Specialization** є опціональними полями і можуть бути `null`
4. `api_key` додається автоматично і не потрібно надсилати його в запиті
5. При видаленні Branch або Specialization, клієнт не видаляється, а поля стають `null` (SET_NULL)

