# Knowledge Split (Oleg/Vasya) + Sandbox → Assistant Page — Design Spec

## 1. Концепція

- **Oleg (Assistant)** — бачить ВСІ знання (all + assistant + manager)
- **Vasya (Manager)** — бачить тільки `all` + `manager`
- Юзер кидає файли/текст Олегу в Sandbox, каже "запам'ятай" → з'являється KnowledgeBlock з `scope='assistant'` на Train AI
- Train AI — сторінка для завантаження знань (для обох) та тестування Васі
- Sandbox → сторінка Олега (Assistant), повний редизайн

## 2. Backend: KnowledgeBlock.target_scope

### Модель

```python
# MASTER/clients/models.py — KnowledgeBlock (line ~916)
class KnowledgeBlock(models.Model):
    TARGET_SCOPE_CHOICES = [
        ('all', 'All (available to everyone)'),
        ('assistant', 'Assistant only (Oleg)'),
        ('manager', 'Manager only (Vasya)'),
    ]

    # ... existing fields ...
    target_scope = models.CharField(
        max_length=20, choices=TARGET_SCOPE_CHOICES, default='all',
        help_text='Who can access this knowledge block')
```

### Міграція

- Додати `target_scope` з `default='all'`
- Існуючі блоки автоматично отримують `all` — обидва бачать

### Access rules

| target_scope | Oleg бачить? | Vasya бачить? |
|---|---|---|
| `all` | ✅ | ✅ |
| `assistant` | ✅ | ❌ |
| `manager` | ✅ | ✅ |

Олег завжди бачить все. Вася бачить тільки `all` + `manager`.

## 3. Backend: RAG search фільтрація

### `mcp_hub/builtin/rag_search.py`

`rag_search()` отримує параметр `requesting_agent` (або бере з `connection.target`):

```python
async def rag_search(connection, tool_name, query, **kwargs):
    requesting_agent = connection.target  # 'assistant' or 'manager'
    # ... pass to _search_sync ...

def _search_sync(client, query, agent_config, defaults, requesting_agent='assistant'):
    # ... existing search logic ...
    # Before search, filter knowledge blocks by scope:
    # if requesting_agent == 'manager':
    #     exclude client documents with target_scope='assistant'
```

RAG pipeline шукає в `ClientEmbedding` / `ClientDocument`. Потрібно додати фільтрацію по `target_scope` knowledge block'у документа.

### `rag/vector_search.py` — VectorSearchService.search()

Зараз шукає по всіх embeddings клієнта без фільтра scope. Додати `scope_filter` параметр:

```python
def search(self, query_vector, branch, specialization, client,
           embedding_model, scope_filter=None):
    # ... existing code ...
    # When building Qdrant filter for client-level search:
    # if scope_filter == 'manager':
    #     add filter: document.knowledge_block.target_scope IN ['all', 'manager']
```

**Варіант реалізації:** фільтрувати на рівні Qdrant (якщо scope зберігається в payload metadata) або пост-фільтром після пошуку (простіше, менш ефективно).

**Рекомендація:** додати `target_scope` в payload метадату при індексації embedding — тоді Qdrant фільтрує сам.

## 4. Backend: API зміни

### KnowledgeBlockSerializer

```python
class KnowledgeBlockSerializer(serializers.ModelSerializer):
    entries_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = KnowledgeBlock
        fields = [
            'id', 'client', 'name', 'description',
            'is_active', 'is_permanent', 'target_scope',  # ADD
            'entries_count', 'created_at', 'updated_at',
        ]
        read_only_fields = ['client', 'is_permanent', 'entries_count', 'created_at', 'updated_at']
```

### KnowledgeBlockViewSet.get_queryset

Додати фільтр `?scope=manager`:

```python
def get_queryset(self):
    client = self.get_client_from_request_or_api_key()
    if not client:
        return KnowledgeBlock.objects.none()
    qs = KnowledgeBlock.objects.filter(client=client, is_active=True)

    scope = self.request.query_params.get('scope')
    if scope == 'manager':
        qs = qs.filter(target_scope__in=['all', 'manager'])
    # 'assistant' or no filter → return all (Oleg sees everything)
    return qs
```

### POST створення — приймає `target_scope`

`KnowledgeBlockViewSet.create()` — target_scope вже є в serializer fields, буде прийматися автоматично. Default = `all`.

### "Save to KB" з Sandbox чату

Поточна кнопка BookmarkPlus в `ChatWindow.jsx` зберігає Q&A пару. При збереженні з Sandbox (сторінка Олега) — передавати `target_scope: 'assistant'`.

Потрібен backend endpoint або модифікація існуючого, щоб приймати scope при збереженні з чату.

## 5. Backend: Індексація embeddings з scope metadata

При створенні/оновленні ClientDocument embedding — додавати `target_scope` в Qdrant payload:

```python
# При індексації в Qdrant:
payload = {
    'client_id': client.id,
    'document_id': doc.id,
    'knowledge_block_id': block.id,
    'target_scope': block.target_scope,  # ADD
    # ... existing payload fields
}
```

При зміні `target_scope` на KnowledgeBlock — оновити payload всіх його embeddings в Qdrant.

## 6. Frontend: Train AI page

### Scope badge

На кожному KnowledgeBlock в списку — badge:
- `all` → без badge (дефолт, не акцентуємо)
- `assistant` → badge "Oleg" (indigo)
- `manager` → badge "Vasya" (purple)

### Scope selector при створенні

В `KnowledgeBlockAddModal` — dropdown/radio для `target_scope`:
- All (дефолт) — "Доступно обом"
- Assistant (Oleg) — "Тільки для Олега"
- Manager (Vasya) — "Тільки для Васі"

### Фільтр по scope

В `KnowledgeBlocks.jsx` — додати фільтр аналогічно існуючому `filterStatus`:
- All scopes (дефолт)
- Oleg only
- Vasya only
- Shared (all)

## 7. Frontend: Sandbox → Assistant (Oleg) Page

### Sidebar зміни

```js
// Sidebar.jsx line 77
// BEFORE:
{ to: '/sandbox', icon: FlaskConical, label: t('nav.sandbox'), badge: t('nav.sandboxBadge') || 'Also in Train AI' },

// AFTER:
{ to: '/sandbox', icon: Bot, label: t('nav.assistant') || 'Assistant', badge: null },
```

Іконка: `Bot` з lucide-react замість `FlaskConical`.

### SandboxPage layout redesign

Прибрати grid layout. Full-height chat без Photo Upload card (merge upload в chat input).

```
┌─────────────────────────────────────────┐
│ [Oleg] Assistant              [Clear]   │  ← header
├─────────────────────────────────────────┤
│                                         │
│  AI: Привіт, я Олег, ваш асистент     │  ← chat area, full width
│                                         │
│  You: Запам'ятай цю інформацію...      │
│                                         │
│  AI: Записав у базу знань!             │
│      [▶ Play] [💾 Save to KB]          │
│                                         │
├─────────────────────────────────────────┤
│ [🎤] [📎] [  Type your message...  ] [→]│  ← input, image upload merged
└─────────────────────────────────────────┘
```

### P0 фікси (критичні)

1. **Видалити magenta debug borders** — пошук fuchsia/magenta border/outline стилів
2. **AI message bubbles — фон:** `bg-gray-100 dark:bg-gray-700/50 rounded-lg p-3 max-w-[80%]`
3. **Textarea замість input:** auto-resize (min 44px, max 120px), Enter=send, Shift+Enter=newline
4. **Confirmation на Clear History:** `window.confirm()` перед очищенням

### P1 фікси (важливі)

5. **Responsive chat height:** `h-[calc(100vh-280px)] min-h-[400px] max-h-[800px]`
6. **Tooltips** на всі icon-only кнопки (title attribute)
7. **Disable send button** коли textarea порожній
8. **Dismissible info banner:** X кнопка, localStorage persist
9. **Dark theme scrollbar:** 6px, gray-600 thumb

### P2 фікси (бажані)

10. Upload zone: "Drag & drop" + підтримувані формати
11. Typing indicator (3 dots animation)
12. Timestamps: "Today 09:42", date dividers
13. Image preview після upload

### "Save to KB" з scope=assistant

Кнопка BookmarkPlus в ChatWindow — при збереженні додавати `target_scope: 'assistant'`, бо це знання Олега.

## 8. i18n ключі

```json
{
  "nav.assistant": "Assistant",
  "sandbox.title": "AI Assistant (Oleg)",
  "training.scopeAll": "Shared",
  "training.scopeAssistant": "Oleg only",
  "training.scopeManager": "Vasya only",
  "training.scopeFilter": "Scope",
  "training.scopeBadgeAssistant": "Oleg",
  "training.scopeBadgeManager": "Vasya"
}
```

## 9. Що НЕ змінюється

- Train AI page layout — залишається як є, тільки додаються scope badges/фільтр
- Dashboard chat — без змін
- EdgeMiddleware — без змін
- ToolConnection — без змін (scopes для tools — окрема задача)

## 10. Міграційний план

1. Backend: додати `target_scope` поле + міграція (non-breaking, default='all')
2. Backend: оновити serializer + viewset фільтрацію
3. Backend: додати scope metadata в Qdrant при індексації
4. Backend: фільтрація RAG search по scope
5. Frontend: scope badge + фільтр на Train AI
6. Frontend: scope selector в KnowledgeBlockAddModal
7. Frontend: Sandbox → Assistant редизайн + P0 фікси
8. Frontend: P1 фікси
9. Frontend: "Save to KB" з scope=assistant
10. Frontend: P2 фікси (якщо залишиться час)
