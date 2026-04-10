# API Documentation для React Frontend

Повна документація всіх API endpoints для інтеграції з React фронтендом.

## Базовий URL

```
http://localhost:8000  (для локальної розробки)
https://api.example.com (для production)
```

## Аутентифікація

### 1. API Key Authentication
Використовується для публічних endpoints (ресторан, RAG chat):
```
Header: X-API-Key: your_api_key_here
```

### 2. JWT Authentication
Використовується для захищених endpoints:
```
Header: Authorization: Bearer <access_token>
```

---

## 📚 1. RAG API (`/api/rag/`)

### 1.1. RAG Query
**POST** `/api/rag/query/`

Отримати відповідь на запит через RAG систему.

**Headers:**
```
X-API-Key: your_api_key
Content-Type: application/json
```

**Body:**
```json
{
  "query": "Ваше питання тут"
}
```

**Response:**
```json
{
  "query": "Ваше питання тут",
  "client": "client_username",
  "specialization": "Restaurant",
  "results": []
}
```

---

### 1.2. Document Upload
**POST** `/api/rag/upload/`

Завантажити документ для RAG системи.

**Headers:**
```
X-API-Key: your_api_key
Content-Type: multipart/form-data
```

**Body (form-data):**
- `file`: File (обов'язково)
- `title`: string (обов'язково)

**Response:**
```json
{
  "message": "Document uploaded successfully",
  "document_id": 123,
  "title": "Document Title",
  "file": "/media/documents/file.pdf",
  "file_type": "pdf",
  "uploaded_at": "2025-01-20T10:30:00Z"
}
```

---

### 1.3. Public RAG Chat
**POST** `/api/rag/chat/`

Публічний чат endpoint з RAG системою.

**Headers:**
```
X-API-Key: your_api_key
Content-Type: application/json
```

**Body:**
```json
{
  "message": "Ваше повідомлення"
}
```

**Response:**
```json
{
  "response": "Відповідь від RAG системи",
  "sources": ["source1", "source2"],
  "num_chunks": 5,
  "total_tokens": 150
}
```

---

### 1.4. Get API Docs
**GET** `/api/rag/docs/`

Отримати документацію API для клієнта.

**Headers:**
```
X-API-Key: your_api_key
```

**Response:**
```json
{
  "client": "client_username",
  "specialization": "Restaurant",
  "branch": "Kyiv",
  "endpoints": {
    "query": {
      "url": "/api/rag/query/",
      "method": "POST",
      "headers": {
        "X-API-Key": "your_api_key",
        "Content-Type": "application/json"
      },
      "body": {
        "query": "Your question here"
      }
    }
  }
}
```

---

### 1.5. Get JWT Token by Client Token
**POST** `/api/rag/auth/token-by-client-token/`

Отримати JWT токени для аутентифікації через client_token.

**Body:**
```json
{
  "client_token": "your_client_token"
}
```

**Response:**
```json
{
  "access": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "client": {
    "id": 123,
    "user": "client_username",
    "company_name": "Company Name",
    "client_type": "restaurant"
  }
}
```

---

### 1.6. Bootstrap Provision
**POST** `/api/rag/bootstrap/<branch_slug>/<specialization_slug>/<client_token>/`

Створити або отримати клієнта через bootstrap.

**Path Parameters:**
- `branch_slug`: string (наприклад, "kyiv")
- `specialization_slug`: string (наприклад, "restaurant")
- `client_token`: string (наприклад, "acme-001")

**Body:**
```json
{
  "company_name": "Company Name",
  "email": "email@example.com"
}
```

**Response:**
```json
{
  "branch": {
    "id": 1,
    "name": "Kyiv",
    "slug": "kyiv"
  },
  "specialization": {
    "id": 10,
    "name": "Restaurant",
    "slug": "restaurant",
    "branch_id": 1
  },
  "client": {
    "id": 100,
    "user_id": 200,
    "username": "client_acme-001",
    "email": "client_acme-001@example.local",
    "specialization_id": 10
  },
  "api_key": {
    "key": "acme-001",
    "name": "bootstrap:acme-001",
    "is_active": true
  }
}
```

---

### 1.7. Provision Link
**POST** `/api/rag/provision-link/`

Створити посилання для provision.

**Body:**
```json
{
  "branch_slug": "kyiv",
  "specialization_slug": "restaurant",
  "client_token": "acme-001"
}
```

**Response:**
```json
{
  "provision_url": "/api/rag/bootstrap/kyiv/restaurant/acme-001/"
}
```

---

### 1.8. Client Features Overview
**GET** `/api/rag/client/features/overview/`

Отримати огляд функцій клієнта.

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response:**
```json
{
  "client_id": 123,
  "features": {
    "menu_chat": true,
    "whatsapp": false,
    "pos_webhook_enabled": true
  }
}
```

---

### 1.9. Embedding Models List
**GET** `/api/rag/embedding-models/`

Отримати список доступних embedding моделей.

**Response:**
```json
[
  {
    "id": 1,
    "model_name": "text-embedding-3-small",
    "dimensions": 1536,
    "is_active": true
  }
]
```

---

### 1.10. Set Client Embedding Model
**POST** `/api/rag/client/embedding-model/`

Встановити embedding модель для клієнта.

**Headers:**
```
Authorization: Bearer <access_token>
```

**Body:**
```json
{
  "model_id": 1
}
```

---

### 1.11. Reindex Client Documents
**POST** `/api/rag/client/reindex/`

Переіндексувати документи клієнта.

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response:**
```json
{
  "message": "Reindexing started",
  "task_id": "task-123"
}
```

---

## 🍽️ 2. Restaurant API (`/api/restaurant/`)

### 2.1. Menu Categories

#### List Categories
**GET** `/api/restaurant/categories/`

**Headers:**
```
X-API-Key: your_api_key
```

**Query Parameters:**
- `search`: string (пошук по назві/опису)
- `ordering`: string (наприклад, "sort_order", "-name")

**Response:**
```json
[
  {
    "id": 1,
    "name": "Закуски",
    "name_translations": {"en": "Appetizers"},
    "description": "Опис категорії",
    "sort_order": 0,
    "is_active": true,
    "icon": "🥗",
    "items_count": 10
  }
]
```

#### Create Category
**POST** `/api/restaurant/categories/`

**Body:**
```json
{
  "name": "Закуски",
  "name_translations": {"en": "Appetizers"},
  "description": "Опис",
  "sort_order": 0,
  "is_active": true,
  "icon": "🥗"
}
```

#### Get Category
**GET** `/api/restaurant/categories/{id}/`

#### Update Category
**PUT/PATCH** `/api/restaurant/categories/{id}/`

#### Delete Category
**DELETE** `/api/restaurant/categories/{id}/`

---

### 2.2. Menus

#### List Menus
**GET** `/api/restaurant/menus/`

**Query Parameters:**
- `search`: string
- `ordering`: string

**Response:**
```json
[
  {
    "id": 1,
    "name": "Основне меню",
    "description_text": "Опис меню",
    "document": null,
    "created_at": "2025-01-20T10:00:00Z",
    "updated_at": "2025-01-20T10:00:00Z"
  }
]
```

#### Create Menu
**POST** `/api/restaurant/menus/`

**Body (form-data):**
- `name`: string
- `description_text`: string
- `document_file`: File (optional)
- `document_title`: string (optional)
- `file_type`: string (optional) - "pdf", "txt", "csv", "json", "docx"

---

### 2.3. Menu Items

#### List Menu Items
**GET** `/api/restaurant/menu-items/`

**Query Parameters:**
- `menu`: integer (filter by menu ID)
- `category`: integer (filter by category ID)
- `dietary`: string (filter by dietary label)
- `available`: boolean (default: true) - filter by availability
- `search`: string
- `ordering`: string

**Response:**
```json
[
  {
    "id": 1,
    "menu_name": "Основне меню",
    "category_name": "Закуски",
    "name": "Цезар салат",
    "description": "Опис страви",
    "display_price": "150.00",
    "discount_price": null,
    "currency": "UAH",
    "image": "/media/restaurant/menu/image.jpg",
    "image_url": "https://example.com/image.jpg",
    "dietary_labels": ["vegetarian"],
    "chef_recommendation": true,
    "is_available": true,
    "spicy_level": 0
  }
]
```

#### Get Menu Item
**GET** `/api/restaurant/menu-items/{id}/`

**Response (повна версія):**
```json
{
  "id": 1,
  "menu": 1,
  "menu_name": "Основне меню",
  "category": 1,
  "category_name": "Закуски",
  "name": "Цезар салат",
  "name_translations": {"en": "Caesar Salad"},
  "description": "Опис страви",
  "description_translations": {"en": "Description"},
  "price": "150.00",
  "discount_price": null,
  "display_price": "150.00",
  "currency": "UAH",
  "image": "/media/restaurant/menu/image.jpg",
  "image_url": "https://example.com/image.jpg",
  "calories": 250,
  "proteins": "15.00",
  "fats": "10.00",
  "carbs": "20.00",
  "allergens": ["eggs", "dairy"],
  "dietary_labels": ["vegetarian"],
  "ingredients": "Список інгредієнтів",
  "cooking_time": 15,
  "spicy_level": 0,
  "wine_pairing": "Біле вино",
  "chef_recommendation": true,
  "popular_item": true,
  "is_available": true,
  "available_from": "10:00:00",
  "available_until": "22:00:00",
  "stock_quantity": null,
  "tags": ["signature"],
  "sort_order": 0
}
```

#### Create Menu Item
**POST** `/api/restaurant/menu-items/`

**Body (form-data):**
- `name`: string
- `description`: string
- `price`: decimal
- `category`: integer (ID)
- `menu`: integer (ID, optional)
- `is_available`: boolean
- ... (інші поля з MenuItemSerializer)

#### Update Menu Item
**PUT/PATCH** `/api/restaurant/menu-items/{id}/`

#### Delete Menu Item
**DELETE** `/api/restaurant/menu-items/{id}/`

#### Search Menu Items
**POST** `/api/restaurant/menu-items/search/`

**Body:**
```json
{
  "query": "салат",
  "language": "uk",
  "category_id": 1,
  "dietary_filters": ["vegetarian"],
  "allergen_exclude": ["nuts"],
  "max_price": 200.00,
  "min_calories": 100,
  "max_calories": 500
}
```

**Response:**
```json
{
  "query": "салат",
  "results": [
    {
      "id": 1,
      "name": "Цезар салат",
      "description": "...",
      "display_price": "150.00",
      "currency": "UAH",
      "dietary_labels": ["vegetarian"],
      "is_available": true
    }
  ],
  "count": 1
}
```

---

### 2.4. Restaurant Tables

#### List Tables
**GET** `/api/restaurant/tables/`

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response:**
```json
[
  {
    "id": 1,
    "table_number": "5",
    "display_name": "Стіл 5",
    "capacity": 4,
    "location": "Main Hall",
    "qr_code": "/media/restaurant/qr_codes/table_5.png",
    "qr_code_url": "https://wa.me/...",
    "is_active": true,
    "is_occupied": false,
    "notes": ""
  }
]
```

#### Create Table
**POST** `/api/restaurant/tables/`

**Body:**
```json
{
  "table_number": "5",
  "display_name": "Стіл 5",
  "capacity": 4,
  "location": "Main Hall",
  "is_active": true
}
```

#### Regenerate QR Code
**POST** `/api/restaurant/tables/{id}/regenerate_qr/`

---

### 2.5. Restaurant Chat
**POST** `/api/restaurant/chat/`

AI офіціант для ресторанів.

**Headers:**
```
X-API-Key: your_api_key
Content-Type: application/json
```

**Body:**
```json
{
  "message": "Що ви рекомендуєте?",
  "session_id": "session-123",
  "table_id": 1,
  "order_id": 1,
  "language": "uk",
  "speak": false,
  "voice": "alloy"
}
```

**Response:**
```json
{
  "response": "Рекомендую наш фірмовий салат Цезар...",
  "session_id": "session-123",
  "suggested_items": [
    {
      "id": 1,
      "name": "Цезар салат",
      "display_price": "150.00",
      "currency": "UAH",
      "is_available": true
    }
  ],
  "context": {
    "table_id": 1,
    "order_id": 1,
    "language": "uk"
  },
  "tts": {
    "mime": "audio/mpeg",
    "audio_base64": "base64_encoded_audio..."
  }
}
```

---

### 2.6. Text-to-Speech (TTS)
**POST** `/api/restaurant/tts/`

**Headers:**
```
X-API-Key: your_api_key
Content-Type: application/json
```

**Body:**
```json
{
  "text": "Привіт, як справи?",
  "voice": "alloy"
}
```

**Response:**
```
Content-Type: audio/mpeg
[Binary audio data]
```

**Voices:** `alloy`, `echo`, `fable`, `onyx`, `nova`, `shimmer`

---

### 2.7. Speech-to-Text (STT)
**POST** `/api/restaurant/stt/`

**Headers:**
```
X-API-Key: your_api_key
Content-Type: multipart/form-data
```

**Body (form-data):**
- `file`: File (audio file)

**Response:**
```json
{
  "text": "Розпізнаний текст"
}
```

---

### 2.8. Public Table Access
**GET** `/restaurant/{client_slug}/table/{token}/`

Публічний доступ до столу через QR код.

**Response:**
```json
{
  "session_id": "generated_session_id",
  "client": {
    "id": 1,
    "name": "Restaurant Name",
    "slug": "restaurant-slug"
  },
  "table": {
    "id": 1,
    "number": "5",
    "display_name": "Стіл 5",
    "capacity": 4
  }
}
```

---

## 👥 3. Clients API (`/api/clients/`)

### 3.1. Client ViewSet (REST)

#### List Clients
**GET** `/api/clients/`

**Headers:**
```
Authorization: Bearer <access_token>
```

#### Get Client
**GET** `/api/clients/{id}/`

#### Create Client
**POST** `/api/clients/`

#### Update Client
**PUT/PATCH** `/api/clients/{id}/`

#### Delete Client
**DELETE** `/api/clients/{id}/`

---

### 3.2. Client Documents

#### List Documents
**GET** `/api/clients/documents/`

#### Upload Document
**POST** `/api/clients/documents/`

**Body (form-data):**
- `file`: File
- `title`: string
- `client`: integer (ID)

---

### 3.3. API Keys

#### List API Keys
**GET** `/api/clients/api-keys/`

#### Create API Key
**POST** `/api/clients/api-keys/`

**Body:**
```json
{
  "name": "API Key Name",
  "client": 1,
  "is_active": true
}
```

#### Delete API Key
**DELETE** `/api/clients/api-keys/{id}/`

---

### 3.4. Client Me
**GET** `/api/clients/me/`

Отримати інформацію про поточного клієнта.

**Headers:**
```
Authorization: Bearer <access_token>
```

---

### 3.5. Client Logo Upload
**POST** `/api/clients/logo/`

**Headers:**
```
Authorization: Bearer <access_token>
Content-Type: multipart/form-data
```

**Body (form-data):**
- `logo`: File

---

### 3.6. Client Stats
**GET** `/api/clients/{client_id}/stats/`

**Response:**
```json
{
  "client_id": 1,
  "total_documents": 10,
  "total_queries": 150,
  "last_activity": "2025-01-20T10:00:00Z"
}
```

---

### 3.7. Create API Key for Client
**POST** `/api/clients/{client_id}/create-api-key/`

---

### 3.8. Generate API Docs
**GET** `/api/clients/api-docs/{client_id}/`

Отримати Markdown документацію API для клієнта.

---

### 3.9. List Clients Extended
**GET** `/api/clients/list-extended/`

Розширений список клієнтів з додатковою інформацією.

---

### 3.10. Regenerate QRs
**POST** `/api/clients/{id}/regenerate-qrs/`

Перегенерувати всі QR коди для клієнта.

---

## 🏢 4. Branches API (`/api/branches/`)

### 4.1. List Branches
**GET** `/api/branches/list/`

**Response:**
```json
[
  {
    "id": 1,
    "name": "Kyiv",
    "slug": "kyiv",
    "description": "Київська філія"
  }
]
```

### 4.2. Create Branch
**POST** `/api/branches/create/`

**Body:**
```json
{
  "name": "Kyiv",
  "slug": "kyiv",
  "description": "Київська філія"
}
```

### 4.3. Get Branch
**GET** `/api/branches/{branch_id}/`

### 4.4. Update Branch
**PUT/PATCH** `/api/branches/{branch_id}/update/`

### 4.5. Delete Branch
**DELETE** `/api/branches/{branch_id}/delete/`

---

## 🎯 5. Specializations API (`/api/specializations/`)

### 5.1. List Specializations
**GET** `/api/specializations/list/`

### 5.2. Create Specialization
**POST** `/api/specializations/create/`

**Body:**
```json
{
  "name": "Restaurant",
  "slug": "restaurant",
  "branch_id": 1,
  "description": "Ресторанна спеціалізація"
}
```

### 5.3. Get Specialization
**GET** `/api/specializations/{spec_id}/`

### 5.4. Update Specialization
**PUT/PATCH** `/api/specializations/{spec_id}/update/`

### 5.5. Delete Specialization
**DELETE** `/api/specializations/{spec_id}/delete/`

---

## 🔧 6. Embedding Models API (`/api/embedding-model/`)

### 6.1. Get Models
**GET** `/api/embedding-model/models/`

### 6.2. Select Model
**POST** `/api/embedding-model/select/`

**Body:**
```json
{
  "model_id": 1,
  "client_id": 1
}
```

### 6.3. Reindex Client Documents
**POST** `/api/embedding-model/reindex/`

---

## 🔐 7. Accounts API (`/api/accounts/`)

### 7.1. Health Check
**GET** `/api/accounts/health/`

### 7.2. Login Redirect
**GET** `/api/accounts/login/`

Перенаправляє на `/admin/login/`

---

## 📊 8. Orders API (`/api/restaurant/`)

### 8.1. List Orders
**GET** `/api/restaurant/orders/`

**Query Parameters:**
- `status`: string (pending, confirmed, preparing, ready, served, paid, cancelled)
- `table`: integer (table ID)
- `date_from`: date
- `date_to`: date

**Response:**
```json
[
  {
    "id": 1,
    "order_number": "ORD20250120120000A1",
    "status": "pending",
    "table": 1,
    "table_number": "5",
    "customer_name": "Іван",
    "customer_phone": "+380671234567",
    "customer_email": "ivan@example.com",
    "customer_language": "uk",
    "subtotal": "300.00",
    "tax_amount": "60.00",
    "discount_amount": "0.00",
    "total_amount": "360.00",
    "special_requests": "",
    "items": [
      {
        "id": 1,
        "menu_item": 1,
        "menu_item_name": "Цезар салат",
        "quantity": 2,
        "unit_price": "150.00",
        "total_price": "300.00",
        "notes": "Без гренок",
        "modifiers": [],
        "is_ready": false
      }
    ],
    "created_at": "2025-01-20T12:00:00Z"
  }
]
```

### 8.2. Create Order
**POST** `/api/restaurant/orders/`

**Headers:**
```
X-API-Key: your_api_key
Content-Type: application/json
```

**Body:**
```json
{
  "table": 1,
  "customer_name": "Іван",
  "customer_phone": "+380671234567",
  "customer_email": "ivan@example.com",
  "customer_language": "uk",
  "special_requests": "Без гренок",
  "items": [
    {
      "menu_item": 1,
      "quantity": 2,
      "notes": "Без гренок",
      "modifiers": ["extra cheese"]
    }
  ]
}
```

### 8.3. Update Order Status
**POST** `/api/restaurant/orders/{id}/update_status/`

**Body:**
```json
{
  "status": "confirmed"
}
```

### 8.4. Add Items to Order
**POST** `/api/restaurant/orders/{id}/add_items/`

**Body:**
```json
{
  "items": [
    {
      "menu_item": 2,
      "quantity": 1,
      "notes": "",
      "modifiers": []
    }
  ]
}
```

---

## 🚨 Error Responses

### 401 Unauthorized
```json
{
  "error": "Unauthorized",
  "detail": "Authentication credentials were not provided."
}
```

### 400 Bad Request
```json
{
  "error": "Validation error",
  "field_name": ["Error message"]
}
```

### 404 Not Found
```json
{
  "error": "Not found",
  "detail": "Object not found"
}
```

### 403 Forbidden
```json
{
  "error": "Forbidden",
  "detail": "You do not have permission to perform this action."
}
```

---

## 📝 Приклади використання в React

### Fetch з API Key
```javascript
const response = await fetch('http://localhost:8000/api/restaurant/chat/', {
  method: 'POST',
  headers: {
    'X-API-Key': 'your_api_key',
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    message: 'Що ви рекомендуєте?',
    session_id: 'session-123',
    language: 'uk'
  })
});

const data = await response.json();
```

### Fetch з JWT Token
```javascript
const response = await fetch('http://localhost:8000/api/clients/me/', {
  method: 'GET',
  headers: {
    'Authorization': `Bearer ${accessToken}`,
    'Content-Type': 'application/json'
  }
});

const data = await response.json();
```

### Upload файлу
```javascript
const formData = new FormData();
formData.append('file', file);
formData.append('title', 'Document Title');

const response = await fetch('http://localhost:8000/api/rag/upload/', {
  method: 'POST',
  headers: {
    'X-API-Key': 'your_api_key'
  },
  body: formData
});
```

---

## 🔗 Корисні посилання

- Health check: `GET /`
- Django Admin: `/admin/`
- Client Portal: `/{branch}/{specialization}/{client_token}/admin/`

---

**Останнє оновлення:** 2025-01-20
