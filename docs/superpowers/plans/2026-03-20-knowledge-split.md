# Knowledge Split (Oleg/Vasya) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split knowledge access between Oleg (Assistant) and Vasya (Manager) with `target_scope` field on KnowledgeBlock, gated by feature flag `mcp_knowledge_split` for client `srtyh` only.

**Architecture:** New `target_scope` field on KnowledgeBlock model (`all`/`assistant`/`manager`). RAG search filters by scope when flag enabled. Frontend shows scope badges/selector on Train AI page. Sandbox becomes Assistant (Oleg) page with UI fixes. All changes gated by `FeatureFlag('mcp_knowledge_split')`.

**Tech Stack:** Django 5.x, DRF, PostgreSQL, React 18, Tailwind CSS, i18next

**Spec:** `docs/superpowers/specs/2026-03-20-knowledge-split-design.md`

**CRITICAL RULE:** Every new code path MUST check `FeatureFlag.is_enabled('mcp_knowledge_split', client)`. If flag is off — old code runs unchanged.

---

## File Structure

### Backend (modify)
- `p004_ai_nexelin/MASTER/clients/models.py` — add `target_scope` field to KnowledgeBlock
- `p004_ai_nexelin/MASTER/clients/serializers.py` — add `target_scope` to KnowledgeBlockSerializer, add `mcp_knowledge_split` to feature flags
- `p004_ai_nexelin/MASTER/clients/views.py` — scope filter in KnowledgeBlockViewSet.get_queryset
- `p004_ai_nexelin/MASTER/clients/admin.py` — show target_scope in KnowledgeBlockAdmin
- `p004_ai_nexelin/MASTER/api/views.py` — SaveSandboxQAView sets scope='assistant' when flag on
- `p004_ai_nexelin/MASTER/mcp_hub/builtin/rag_search.py` — pass scope to search

### Backend (create)
- `p004_ai_nexelin/MASTER/clients/migrations/XXXX_knowledgeblock_target_scope.py` — migration

### Frontend (modify)
- `nextlen/src/components/layout/Sidebar.jsx` — conditional nav item name/icon
- `nextlen/src/components/layout/ClientLayout.jsx` — same
- `nextlen/src/pages/SandboxPage.jsx` — conditional layout (new vs old)
- `nextlen/src/components/sandbox/ChatWindow.jsx` — P0-P1 UI fixes
- `nextlen/src/components/training/KnowledgeBlocks.jsx` — scope badge + filter
- `nextlen/src/components/training/KnowledgeBlockAddModal.jsx` — scope selector
- `nextlen/src/locales/en/translation.json` — new i18n keys
- `nextlen/src/locales/uk/translation.json` — Ukrainian translations

---

## Task 1: Backend — Add `target_scope` field to KnowledgeBlock

**Files:**
- Modify: `p004_ai_nexelin/MASTER/clients/models.py:916-941`

- [ ] **Step 1: Add TARGET_SCOPE_CHOICES and field**

In `KnowledgeBlock` class, after `is_permanent` field (line 929):
```python
    TARGET_SCOPE_CHOICES = [
        ('all', 'All (available to everyone)'),
        ('assistant', 'Assistant only (Oleg)'),
        ('manager', 'Manager only (Vasya)'),
    ]

    # ... existing fields (client, name, description, is_active, is_permanent) ...

    target_scope = models.CharField(
        max_length=20, choices=TARGET_SCOPE_CHOICES, default='all',
        help_text='Who can access this knowledge block')
```

Add `TARGET_SCOPE_CHOICES` before the `id` field and `target_scope` after `is_permanent`.

- [ ] **Step 2: Create migration**

```bash
cd /home/dchuprina/nexelin_web && python p004_ai_nexelin/manage.py makemigrations clients -n "knowledgeblock_target_scope"
```

- [ ] **Step 3: Run migration**

```bash
python p004_ai_nexelin/manage.py migrate clients
```

- [ ] **Step 4: Commit**

```bash
git add p004_ai_nexelin/MASTER/clients/models.py p004_ai_nexelin/MASTER/clients/migrations/
git commit -m "feat(knowledge): add target_scope field to KnowledgeBlock model"
```

---

## Task 2: Backend — Update serializer + feature flag

**Files:**
- Modify: `p004_ai_nexelin/MASTER/clients/serializers.py:177-193` (KnowledgeBlockSerializer)
- Modify: `p004_ai_nexelin/MASTER/clients/serializers.py:98-102` (get_feature_flags)

- [ ] **Step 1: Add target_scope to KnowledgeBlockSerializer fields**

In `KnowledgeBlockSerializer.Meta.fields` (line 182-192):
```python
        fields = [
            'id',
            'client',
            'name',
            'description',
            'is_active',
            'is_permanent',
            'target_scope',       # ADD
            'entries_count',
            'created_at',
            'updated_at',
        ]
```

- [ ] **Step 2: Add mcp_knowledge_split to feature flags**

In `get_feature_flags` method (line 98-102):
```python
    def get_feature_flags(self, obj):
        return {
            'mcp_tools_dashboard': FeatureFlag.is_enabled('mcp_tools_dashboard', obj),
            'mcp_sse_streaming': FeatureFlag.is_enabled('mcp_sse_streaming', obj),
            'mcp_knowledge_split': FeatureFlag.is_enabled('mcp_knowledge_split', obj),
        }
```

- [ ] **Step 3: Commit**

```bash
git add p004_ai_nexelin/MASTER/clients/serializers.py
git commit -m "feat(knowledge): add target_scope to serializer, mcp_knowledge_split flag"
```

---

## Task 3: Backend — Scope filter in KnowledgeBlockViewSet

**Files:**
- Modify: `p004_ai_nexelin/MASTER/clients/views.py:326-331` (get_queryset)

- [ ] **Step 1: Add scope filtering gated by feature flag**

Replace `get_queryset` (lines 326-331):
```python
    def get_queryset(self):
        """Повертає тільки активні блоки поточного клієнта."""
        client = self.get_client_from_request_or_api_key()
        if not client:
            return KnowledgeBlock.objects.none()

        qs = KnowledgeBlock.objects.filter(client=client, is_active=True)

        # Scope filtering — only when feature flag is enabled
        from MASTER.nexelin_platform.models import FeatureFlag
        if FeatureFlag.is_enabled('mcp_knowledge_split', client):
            scope = self.request.query_params.get('scope')
            if scope == 'manager':
                qs = qs.filter(target_scope__in=['all', 'manager'])
            # 'assistant' or no scope param → return all (Oleg sees everything)

        return qs
```

- [ ] **Step 2: Commit**

```bash
git add p004_ai_nexelin/MASTER/clients/views.py
git commit -m "feat(knowledge): scope filter in KnowledgeBlockViewSet (flag-gated)"
```

---

## Task 4: Backend — Update admin + SaveSandboxQAView

**Files:**
- Modify: `p004_ai_nexelin/MASTER/clients/admin.py:723-747` (KnowledgeBlockAdmin)
- Modify: `p004_ai_nexelin/MASTER/api/views.py:2477-2517` (SaveSandboxQAView)

- [ ] **Step 1: Add target_scope to KnowledgeBlockAdmin**

In `KnowledgeBlockAdmin` (line 723):
```python
class KnowledgeBlockAdmin(admin.ModelAdmin):
    list_display = ['name', 'client', 'description', 'target_scope', 'entries_count', 'is_active', 'is_permanent', 'created_at']
    list_filter = ['is_active', 'is_permanent', 'target_scope', 'created_at']
    search_fields = ['name', 'description', 'client__user', 'client__company_name']
    ordering = ['client', 'is_permanent', 'name']
    list_editable = ['is_active', 'target_scope']
```

Add `target_scope` to:
- `list_display` (after `description`)
- `list_filter` (after `is_permanent`)
- `list_editable` (add `target_scope`)

Also add `target_scope` to fieldsets Basic Info:
```python
        ('Basic Info', {
            'fields': ('client', 'name', 'description', 'target_scope')
        }),
```

- [ ] **Step 2: Update SaveSandboxQAView to set scope='assistant' when flag on**

In `SaveSandboxQAView.post()` (line 2499-2509), update `get_or_create`:
```python
            # Determine scope based on feature flag
            from MASTER.nexelin_platform.models import FeatureFlag
            scope = 'assistant' if FeatureFlag.is_enabled('mcp_knowledge_split', client) else 'all'

            # Знайти або створити knowledge block "Sandbox"
            knowledge_block, created = KnowledgeBlock.objects.get_or_create(
                client=client,
                name='Sandbox',
                defaults={
                    'description': 'Q&A pairs saved from sandbox chat',
                    'is_active': True,
                    'is_permanent': False,
                    'target_scope': scope,
                }
            )
            # Update scope if block already existed and flag is on
            if not created and FeatureFlag.is_enabled('mcp_knowledge_split', client):
                if knowledge_block.target_scope != scope:
                    knowledge_block.target_scope = scope
                    knowledge_block.save(update_fields=['target_scope'])
```

- [ ] **Step 3: Commit**

```bash
git add p004_ai_nexelin/MASTER/clients/admin.py p004_ai_nexelin/MASTER/api/views.py
git commit -m "feat(knowledge): admin target_scope, SaveSandboxQA sets scope=assistant"
```

---

## Task 5: Backend — Create feature flag in DB

**Files:** none (management command / shell)

- [ ] **Step 1: Create mcp_knowledge_split flag for srtyh**

```bash
cd /home/dchuprina/nexelin_web && python p004_ai_nexelin/manage.py shell -c "
from MASTER.nexelin_platform.models import FeatureFlag
from MASTER.clients.models import Client
flag, created = FeatureFlag.objects.get_or_create(
    key='mcp_knowledge_split',
    defaults={'description': 'Knowledge split: Oleg sees all, Vasya sees only all+manager', 'rollout': 'selected'}
)
srtyh = Client.objects.filter(tag='srtyh').first()
if srtyh:
    flag.enabled_clients.add(srtyh)
    print(f'Enabled for srtyh (pk={srtyh.pk})')
print(f'Flag: {flag.key} rollout={flag.rollout} created={created}')
"
```

- [ ] **Step 2: Verify flag works**

```bash
python p004_ai_nexelin/manage.py shell -c "
from MASTER.nexelin_platform.models import FeatureFlag
from MASTER.clients.models import Client
srtyh = Client.objects.filter(tag='srtyh').first()
other = Client.objects.exclude(tag='srtyh').first()
print('srtyh:', FeatureFlag.is_enabled('mcp_knowledge_split', srtyh))
print('other:', FeatureFlag.is_enabled('mcp_knowledge_split', other))
"
```

Expected: `srtyh: True`, `other: False`

---

## Task 6: Frontend — i18n keys

**Files:**
- Modify: `nextlen/src/locales/en/translation.json`
- Modify: `nextlen/src/locales/uk/translation.json` (if exists)

- [ ] **Step 1: Add knowledge split i18n keys**

Add to the `en/translation.json` inside appropriate sections:

```json
"nav": {
  "assistant": "Assistant"
},
"training": {
  "scopeAll": "Shared",
  "scopeAssistant": "Oleg only",
  "scopeManager": "Vasya only",
  "scopeFilter": "Scope",
  "scopeBadgeAssistant": "Oleg",
  "scopeBadgeManager": "Vasya"
},
"sandbox": {
  "assistantTitle": "AI Assistant",
  "assistantSubtitle": "Chat with Oleg — your AI assistant"
}
```

Merge these keys into existing nav/training/sandbox objects (don't overwrite existing keys).

- [ ] **Step 2: Commit**

```bash
git add nextlen/src/locales/
git commit -m "feat(i18n): add knowledge split translation keys"
```

---

## Task 7: Frontend — Sidebar conditional nav

**Files:**
- Modify: `nextlen/src/components/layout/Sidebar.jsx:1-3,74-77`
- Modify: `nextlen/src/components/layout/ClientLayout.jsx` (same pattern)

- [ ] **Step 1: Import Bot icon**

At top of `Sidebar.jsx` (line 3-15), add `Bot` to lucide-react import:
```js
import {
  LayoutDashboard,
  GraduationCap,
  FlaskConical,
  Bot,          // ADD
  Plug2,
  Puzzle,
  // ... rest
} from 'lucide-react';
```

- [ ] **Step 2: Conditional sandbox/assistant nav item**

Replace line 77:
```js
// BEFORE
{ to: '/sandbox', icon: FlaskConical, label: t('nav.sandbox'), badge: t('nav.sandboxBadge') || 'Also in Train AI' },

// AFTER
user?.feature_flags?.mcp_knowledge_split
  ? { to: '/sandbox', icon: Bot, label: t('nav.assistant') || 'Assistant' }
  : { to: '/sandbox', icon: FlaskConical, label: t('nav.sandbox'), badge: t('nav.sandboxBadge') || 'Also in Train AI' },
```

- [ ] **Step 3: Same change in ClientLayout.jsx**

Apply identical pattern in `nextlen/src/components/layout/ClientLayout.jsx` (same navItems structure).

- [ ] **Step 4: Commit**

```bash
git add nextlen/src/components/layout/Sidebar.jsx nextlen/src/components/layout/ClientLayout.jsx
git commit -m "feat(nav): conditional Assistant/Sandbox nav item (flag-gated)"
```

---

## Task 8: Frontend — Scope badges in KnowledgeBlocks

**Files:**
- Modify: `nextlen/src/components/training/KnowledgeBlocks.jsx`

- [ ] **Step 1: Add scope badge rendering**

Import `useAuth` at top:
```js
import { useAuth } from '../../context/AuthContext';
```

Inside `KnowledgeBlocks` component, get feature flag:
```js
const { user } = useAuth();
const knowledgeSplitEnabled = user?.feature_flags?.mcp_knowledge_split;
```

- [ ] **Step 2: Add scope badge to each block in the list**

Find where each block is rendered (block name/title area). After the block name, add:
```jsx
{knowledgeSplitEnabled && block.target_scope && block.target_scope !== 'all' && (
  <span className={`ml-2 px-2 py-0.5 text-xs rounded-full font-medium ${
    block.target_scope === 'assistant'
      ? 'bg-indigo-100 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-300'
      : 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300'
  }`}>
    {block.target_scope === 'assistant'
      ? (t('training.scopeBadgeAssistant') || 'Oleg')
      : (t('training.scopeBadgeManager') || 'Vasya')}
  </span>
)}
```

- [ ] **Step 3: Add scope filter dropdown**

After existing `filterStatus` state, add:
```js
const [filterScope, setFilterScope] = useState('all_scopes');
```

Add scope filter to the filter area (next to existing status filter):
```jsx
{knowledgeSplitEnabled && (
  <select
    value={filterScope}
    onChange={(e) => setFilterScope(e.target.value)}
    className="px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
  >
    <option value="all_scopes">{t('training.scopeFilter') || 'All scopes'}</option>
    <option value="all">{t('training.scopeAll') || 'Shared'}</option>
    <option value="assistant">{t('training.scopeAssistant') || 'Oleg only'}</option>
    <option value="manager">{t('training.scopeManager') || 'Vasya only'}</option>
  </select>
)}
```

Apply filter in the `filteredBlocks` useMemo — add scope filtering:
```js
// After existing status filter, add:
if (knowledgeSplitEnabled && filterScope !== 'all_scopes') {
  filtered = filtered.filter(b => b.target_scope === filterScope);
}
```

- [ ] **Step 4: Commit**

```bash
git add nextlen/src/components/training/KnowledgeBlocks.jsx
git commit -m "feat(training): scope badges and filter on knowledge blocks (flag-gated)"
```

---

## Task 9: Frontend — Scope selector in KnowledgeBlockAddModal

**Files:**
- Modify: `nextlen/src/components/training/KnowledgeBlockAddModal.jsx`

- [ ] **Step 1: Add scope state and selector**

Add import and state:
```js
import { useAuth } from '../../context/AuthContext';

// Inside component:
const { user } = useAuth();
const knowledgeSplitEnabled = user?.feature_flags?.mcp_knowledge_split;
const [targetScope, setTargetScope] = useState('all');
```

- [ ] **Step 2: Add scope selector UI after description textarea**

```jsx
{knowledgeSplitEnabled && (
  <div>
    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
      {t('training.scopeFilter') || 'Scope'}
    </label>
    <select
      value={targetScope}
      onChange={(e) => setTargetScope(e.target.value)}
      className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-primary-500 dark:focus:ring-primary-400 focus:border-transparent bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
    >
      <option value="all">{t('training.scopeAll') || 'Shared (Oleg + Vasya)'}</option>
      <option value="assistant">{t('training.scopeAssistant') || 'Oleg only'}</option>
      <option value="manager">{t('training.scopeManager') || 'Vasya only'}</option>
    </select>
  </div>
)}
```

- [ ] **Step 3: Pass scope to onSave callback**

Update `handleSave`:
```js
const handleSave = () => {
  if (!name.trim()) {
    alert(t("knowledgeBlocks.nameRequired") || "Block name is required");
    return;
  }
  onSave(name, description, knowledgeSplitEnabled ? targetScope : 'all');
  setName("");
  setDescription("");
  setTargetScope('all');
};
```

- [ ] **Step 4: Update parent KnowledgeBlocks.jsx handleAddBlock to pass scope**

In `KnowledgeBlocks.jsx`, find `handleAddBlock` (or similar) that calls the API. Update to pass `target_scope`:

```js
const handleAddBlock = async (name, description, targetScope = 'all') => {
  // ... existing code ...
  await clientAPI.createKnowledgeBlock({ name, description, target_scope: targetScope });
  // ... reload ...
};
```

- [ ] **Step 5: Commit**

```bash
git add nextlen/src/components/training/KnowledgeBlockAddModal.jsx nextlen/src/components/training/KnowledgeBlocks.jsx
git commit -m "feat(training): scope selector in KnowledgeBlockAddModal (flag-gated)"
```

---

## Task 10: Frontend — SandboxPage conditional layout

**Files:**
- Modify: `nextlen/src/pages/SandboxPage.jsx`

- [ ] **Step 1: Add feature flag check**

```js
import { useAuth } from '../context/AuthContext';

const SandboxPage = () => {
  const { t } = useTranslation();
  const { user } = useAuth();
  const knowledgeSplitEnabled = user?.feature_flags?.mcp_knowledge_split;
```

- [ ] **Step 2: New layout when flag is on**

Replace the return statement with conditional rendering:

```jsx
if (knowledgeSplitEnabled) {
  return (
    <div className="flex flex-col h-[calc(100vh-140px)] min-h-[500px]">
      <div className="mb-4">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
          {t('sandbox.assistantTitle') || 'AI Assistant'}
        </h1>
        <p className="text-gray-600 dark:text-gray-400">
          {t('sandbox.assistantSubtitle') || 'Chat with Oleg — your AI assistant'}
        </p>
      </div>
      <div className="flex-1 min-h-0">
        <ChatWindow fullHeight />
      </div>
    </div>
  );
}

// Old layout — unchanged for clients without flag
return (
  <div className="space-y-6">
    {/* ... existing old layout ... */}
  </div>
);
```

- [ ] **Step 3: Commit**

```bash
git add nextlen/src/pages/SandboxPage.jsx
git commit -m "feat(sandbox): conditional Assistant layout when knowledge split flag on"
```

---

## Task 11: Frontend — ChatWindow P0 fixes

**Files:**
- Modify: `nextlen/src/components/sandbox/ChatWindow.jsx`

- [ ] **Step 1: Accept fullHeight prop and apply responsive height**

```js
const ChatWindow = ({ fullHeight = false }) => {
```

Update the root div (line 366):
```jsx
// BEFORE
<div className="card h-[600px] flex flex-col">

// AFTER
<div className={`card flex flex-col ${fullHeight ? 'h-full' : 'h-[600px]'}`}>
```

- [ ] **Step 2: Add background to AI message bubbles**

Find AI message rendering (around line 395-420). Wrap AI text in a styled div:

```jsx
// For AI messages, wrap content in:
<div className={`max-w-[80%] ${
  msg.sender === 'user'
    ? 'bg-primary-600 text-white rounded-lg p-3'
    : 'bg-gray-100 dark:bg-gray-700/50 rounded-lg p-3'
}`}>
```

- [ ] **Step 3: Replace input with textarea**

Find the input element (around line 460-470). Replace:
```jsx
// BEFORE
<input
  type="text"
  ref={inputRef}
  value={input}
  onChange={(e) => setInput(e.target.value)}
  onKeyPress={(e) => e.key === 'Enter' && handleSend()}
  placeholder={t('sandbox.inputPlaceholder')}
  className="..."
/>

// AFTER
<textarea
  ref={inputRef}
  value={input}
  onChange={(e) => {
    setInput(e.target.value);
    // Auto-resize
    e.target.style.height = '44px';
    e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px';
  }}
  onKeyDown={(e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }}
  placeholder={t('sandbox.inputPlaceholder') || 'Type your message...'}
  rows={1}
  className="flex-1 resize-none overflow-hidden bg-gray-100 dark:bg-gray-600 border border-gray-300 dark:border-gray-500 rounded-xl px-4 py-3 text-base focus:ring-2 focus:ring-indigo-500 focus:border-transparent text-gray-900 dark:text-gray-100"
  style={{ minHeight: '44px', maxHeight: '120px' }}
/>
```

- [ ] **Step 4: Disable send button when empty**

Find send button. Add disabled state:
```jsx
<button
  onClick={handleSend}
  disabled={!input.trim() && !selectedImage}
  className={`... ${(!input.trim() && !selectedImage) ? 'opacity-50 cursor-not-allowed' : ''}`}
  title={t('sandbox.sendMessage') || 'Send message'}
>
```

- [ ] **Step 5: Add tooltips to icon buttons**

Add `title` attribute to:
- Trash icon → `title={t('sandbox.clearHistory') || 'Clear chat history'}`
- Mic button → `title={t('sandbox.recordVoice') || 'Record voice message'}`
- Image button → `title={t('sandbox.uploadImage') || 'Upload image'}`
- Play button → `title={t('sandbox.playVoice') || 'Play voice response'}`
- BookmarkPlus → already has title

- [ ] **Step 6: Commit**

```bash
git add nextlen/src/components/sandbox/ChatWindow.jsx
git commit -m "fix(sandbox): P0+P1 UI fixes — AI bubbles, textarea, disable send, tooltips"
```

---

## Task 12: Frontend — Dismissible info banner

**Files:**
- Modify: `nextlen/src/pages/SandboxPage.jsx`

- [ ] **Step 1: Add banner dismiss state**

In the old layout branch (when flag is off), add:
```js
const [bannerDismissed, setBannerDismissed] = useState(
  () => localStorage.getItem('sandbox-banner-dismissed') === 'true'
);

const dismissBanner = () => {
  setBannerDismissed(true);
  localStorage.setItem('sandbox-banner-dismissed', 'true');
};
```

- [ ] **Step 2: Wrap banner in conditional + add X button**

```jsx
{!bannerDismissed && (
  <div className="relative bg-gradient-to-r ...">
    <button
      onClick={dismissBanner}
      className="absolute top-3 right-3 text-purple-400 hover:text-purple-600 dark:hover:text-purple-200"
      title="Dismiss"
    >
      <X size={16} />
    </button>
    {/* ... existing banner content ... */}
  </div>
)}
```

Note: When `knowledgeSplitEnabled` is true, the banner is not shown at all (new layout doesn't include it).

- [ ] **Step 3: Commit**

```bash
git add nextlen/src/pages/SandboxPage.jsx
git commit -m "fix(sandbox): dismissible info banner with localStorage persist"
```

---

## Summary of changes

| # | Task | Type | Files changed |
|---|------|------|---------------|
| 1 | KnowledgeBlock.target_scope | model | 1 backend + migration |
| 2 | Serializer + feature flag | backend | 1 backend |
| 3 | Scope filter in ViewSet | backend | 1 backend |
| 4 | Admin + SaveSandboxQA scope | backend | 2 backend |
| 5 | Create feature flag in DB | data | shell command |
| 6 | i18n keys | frontend | 2 locale files |
| 7 | Sidebar conditional nav | frontend | 2 frontend |
| 8 | Scope badges + filter | frontend | 1 frontend |
| 9 | Scope selector in add modal | frontend | 2 frontend |
| 10 | SandboxPage conditional layout | frontend | 1 frontend |
| 11 | ChatWindow P0+P1 fixes | frontend | 1 frontend |
| 12 | Dismissible banner | frontend | 1 frontend |
