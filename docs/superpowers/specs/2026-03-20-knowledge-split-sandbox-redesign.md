# Knowledge Split (Oleg/Vasya) + Sandbox → MCP Assistant Page — Design Spec

## 1. Knowledge Split Architecture

### Concept

- **Oleg (Assistant)** — має доступ до ВСІХ знань, включаючи знання Васі
- **Vasya (Manager)** — має доступ ТІЛЬКИ до своїх знань (B2C, бізнес-релевантні)
- Все що завантажено через поточний Train AI / Knowledge Blocks — автоматично належить Олегу
- Для Васі — окремий розділ Train AI де можна додавати B2C-специфічні знання

### Backend: KnowledgeBlock changes

Поточна модель `KnowledgeBlock` в `MASTER/clients/models.py`:
```python
class KnowledgeBlock:
    client, name, is_active, is_permanent
```

Додати поле `target_scope`:
```python
class KnowledgeBlock(models.Model):
    TARGET_SCOPE_CHOICES = [
        ('all', 'All (available to everyone)'),       # Oleg sees it, Vasya sees it
        ('assistant', 'Assistant only (Oleg)'),         # Only Oleg
        ('manager', 'Manager only (Vasya)'),            # Only Vasya, but Oleg also sees it
    ]

    target_scope = models.CharField(
        max_length=20, choices=TARGET_SCOPE_CHOICES, default='all',
        help_text='Who can access this knowledge block')
```

**Access rules:**
- `target_scope='all'` → Oleg YES, Vasya YES
- `target_scope='assistant'` → Oleg YES, Vasya NO
- `target_scope='manager'` → Oleg YES, Vasya YES (Oleg has superset)

So effectively: **Oleg always sees everything. Vasya sees only `all` + `manager`.**

### Backend: RAG search filtering

In `mcp_hub/builtin/rag_search.py` (or wherever RAG query happens), filter by scope:

```python
def search_knowledge(client, query, requesting_agent='assistant'):
    blocks = KnowledgeBlock.objects.filter(client=client, is_active=True)

    if requesting_agent == 'manager':
        # Vasya: only 'all' and 'manager' scoped blocks
        blocks = blocks.filter(target_scope__in=['all', 'manager'])
    # else: assistant gets everything (no filter needed)

    # ... proceed with vector search on filtered blocks' documents
```

### Backend: API changes

`GET /api/clients/knowledge-blocks/` — add `target_scope` to response and accept filter:
```
GET /api/clients/knowledge-blocks/?scope=manager  → only manager+all blocks
GET /api/clients/knowledge-blocks/?scope=assistant → all blocks
GET /api/clients/knowledge-blocks/ → all blocks (default)
```

`POST /api/clients/knowledge-blocks/` — accept `target_scope` field (default: 'all')

### Frontend: Train AI page

Current Train AI page shows all knowledge blocks in one list. Split into two sections or tabs:

**Option A (tabs):**
- Tab "All Knowledge" (Oleg's view) — shows everything, scope badge on each block
- Tab "Manager Knowledge" (Vasya's view) — shows only manager+all scoped blocks

**Option B (section headers):**
- Section "General Knowledge" (scope=all) — available to both
- Section "Assistant Only" (scope=assistant) — Oleg exclusive
- Section "Manager (B2C)" (scope=manager) — Vasya's B2C knowledge

When creating new knowledge block, show scope selector dropdown.

---

## 2. Sandbox → MCP Assistant Page (Oleg's Page)

### Concept

Sandbox becomes Oleg's dedicated page — MCP Assistant interface for internal testing and interaction with the AI assistant. Client-facing chat stays on Dashboard.

### Navigation changes

```
Sidebar:
  Dashboard
  Train AI        → knowledge management (both Oleg + Vasya)
  Assistant (Oleg) → renamed from Sandbox, MCP assistant chat
  Tools
  Activity
  Leads
  Prompt Book
  Settings
```

Remove "Also in Train AI" subtitle from nav.

### Page layout (redesigned)

Full-height chat interface, no grid split:

```
┌─────────────────────────────────────────┐
│ [Oleg] MCP Assistant          [Clear] │  ← header with name + clear button
├─────────────────────────────────────────┤
│                                         │
│  AI: Hello, I'm Oleg, your assistant   │  ← chat area, full width
│                                         │
│  You: What do you know about pricing?  │
│                                         │
│  AI: Based on the knowledge base...    │
│      [▶ Play] [💾 Save to KB]          │
│                                         │
│  ··· (typing indicator)                │
│                                         │
├─────────────────────────────────────────┤
│ [🎤] [📎] [  Type your message...  ] [→]│  ← input area
└─────────────────────────────────────────┘
```

Photo Upload Test merges into the chat — image upload button in input area sends image to assistant.

### UI/UX fixes from review (P0-P2)

**P0 — Critical:**
1. Remove magenta debug borders from cards
2. Add background to AI message bubbles: `bg-gray-100 dark:bg-gray-700/50 rounded-lg p-3 max-w-[80%]`
3. Replace `<input type="text">` with `<textarea>` auto-resize (min 44px, max 120px), Enter=send, Shift+Enter=newline
4. Add confirmation dialog on Clear History

**P1 — Important:**
5. Responsive chat height: `h-[calc(100vh-280px)] min-h-[400px] max-h-[800px]`
6. Tooltips on all icon-only buttons (Clear=title, Mic=title, Upload=title, Play=title, Save=title, Send=title)
7. Disable send button when textarea empty (`opacity-50 cursor-not-allowed`)
8. Dismissible info banner (X button, localStorage persist `sandbox-banner-dismissed`)
9. Dark theme scrollbar styling (6px, gray-600 thumb, transparent track)

**P2 — Nice to have:**
10. Upload zone: "Drag & drop an image here" + supported formats text + hover/active states
11. Typing indicator (3 animated dots in AI bubble position)
12. Timestamps: relative "Today 09:42", date dividers for different days, text-xs text-gray-500
13. Image preview after upload in chat

### Implementation order

1. Rename Sandbox → Assistant (Oleg) in sidebar nav
2. P0 fixes (debug borders, AI bubbles, textarea, confirm)
3. P1 fixes (responsive height, tooltips, disable send, banner, scrollbar)
4. Merge Photo Upload into chat input area
5. P2 fixes

---

## 3. Integration: Knowledge + Canvas + Scopes

### How it all connects

```
Train AI page:
  ├── General Knowledge (scope=all)     → both Oleg and Vasya
  ├── Assistant Knowledge (scope=assistant) → Oleg only
  └── Manager Knowledge (scope=manager)  → Vasya + Oleg

Tools Canvas:
  ├── rag-search → assistant (Oleg)     scope: {knowledge: "all"}
  ├── rag-search → manager (Vasya)      scope: {knowledge: "manager_only"}
  └── email → assistant (Oleg)          scope: {can_read: true, can_send: true}
  └── email → manager (Vasya)           scope: {can_send: true, send_scope: "b2c"}

MCP Agent Orchestrator:
  When Oleg processes a query:
    → rag_search(scope='assistant') → searches ALL knowledge blocks
  When Vasya processes a query:
    → rag_search(scope='manager') → searches only 'all' + 'manager' blocks
```

### ToolConnection.scope drives RAG filtering

When `rag-search` is connected to manager with `scope: {knowledge: "manager_only"}`, the MCP executor passes this scope to the builtin RAG handler, which filters KnowledgeBlocks accordingly.

---

## 4. Summary of all changes needed

### Backend
- [ ] Add `target_scope` field to KnowledgeBlock model + migration
- [ ] Add `scope` field to ToolConnection model (from multi-connection spec)
- [ ] Update `scope_schema` on ToolCard for rag-search
- [ ] Filter knowledge blocks by scope in RAG search handler
- [ ] Add scope filter to knowledge blocks API
- [ ] Update knowledge blocks serializer to include target_scope

### Frontend — Train AI page
- [ ] Add scope selector when creating knowledge blocks
- [ ] Show scope badge on each knowledge block
- [ ] Tab or section split: General / Assistant / Manager knowledge

### Frontend — Sandbox → Assistant (Oleg) page
- [ ] Rename in sidebar navigation
- [ ] P0 fixes: debug borders, AI bubbles bg, textarea, confirm clear
- [ ] P1 fixes: responsive height, tooltips, disable send, banner dismiss, scrollbar
- [ ] Merge Photo Upload into chat input
- [ ] P2 fixes: upload zone, typing indicator, timestamps

### Frontend — Tools Canvas
- [ ] Multi-connection support (from multi-connection spec)
- [ ] Scope display on edge popover/tooltip

---

## 5. Questions for next session (Opus must ask Dasha)

1. Knowledge blocks scope defaults: should existing blocks be `all` or `assistant`?
2. Can Vasya create his own knowledge blocks from his chat? Or only admin adds them?
3. Train AI page: tabs or sections for scope separation?
4. Should scope be editable inline (click on badge) or through edit modal?
5. Specific scope definitions per tool (see multi-connection spec TODO)
6. Sandbox rename: "Assistant (Oleg)" or just "Assistant" or "AI Assistant"?
7. Should the Assistant page show tool usage indicators (which tools were called during response)?
