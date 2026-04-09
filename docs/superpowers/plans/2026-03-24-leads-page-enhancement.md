# Leads Page Enhancement — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add slide-in detail panel, single delete, CSV export, and fix existing bugs on the Leads page.

**Architecture:** All frontend work in `LeadsPage.jsx` (single file, new components inline). Two small backend fixes (`select_related` + export bypass for `per_page` cap). Translation keys added for new UI elements. No new dependencies.

**Tech Stack:** React 18, Tailwind CSS, lucide-react, Django REST Framework

**Spec:** `docs/superpowers/specs/2026-03-24-leads-page-enhancement-design.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `nextlen/src/pages/LeadsPage.jsx` | Modify | All frontend features |
| `nextlen/src/locales/en/translation.json` | Modify | New translation keys |
| `nextlen/src/locales/de/translation.json` | Modify | German translations |
| `p004_ai_nexelin/MASTER/clients/views_leads.py` | Modify | `select_related` fix + export per_page bypass |

---

### Task 1: Backend fixes — select_related + export per_page bypass

**Files:**
- Modify: `p004_ai_nexelin/MASTER/clients/views_leads.py:38, 64`

- [ ] **Step 1: Add select_related to queryset**

In `LeadListView.get()`, change line 38 from:
```python
leads = Lead.objects.filter(client=client)
```
to:
```python
leads = Lead.objects.filter(client=client).select_related('conversation')
```

- [ ] **Step 2: Raise per_page cap when export=true**

In `LeadListView.get()`, change line 64 from:
```python
per_page = min(int(request.GET.get('per_page', 25)), 100)
```
to:
```python
max_per_page = 10000 if request.GET.get('export') == 'true' else 100
per_page = min(int(request.GET.get('per_page', 25)), max_per_page)
```

- [ ] **Step 3: Commit**

```bash
git add p004_ai_nexelin/MASTER/clients/views_leads.py
git commit -m "fix(leads): add select_related, raise per_page cap for export"
```

---

### Task 2: Frontend bugfixes — pagination, dark theme, email filter

**Files:**
- Modify: `nextlen/src/pages/LeadsPage.jsx:134, 288, 227-232`

- [ ] **Step 1: Fix pagination field name**

In `fetchLeads`, line 134, change:
```js
if (data.count !== undefined) {
  setTotalPages(Math.ceil(data.count / PER_PAGE));
}
```
to:
```js
if (data.total !== undefined) {
  setTotalPages(Math.ceil(data.total / PER_PAGE));
}
```

- [ ] **Step 2: Fix dark theme on thead**

Line 288, change:
```jsx
<tr className="border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-750">
```
to:
```jsx
<tr className="border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50">
```

- [ ] **Step 3: Add Email to source filter**

After line 231 (`<option value="whatsapp">WhatsApp</option>`), add:
```jsx
<option value="email">Email</option>
```

- [ ] **Step 4: Commit**

```bash
git add nextlen/src/pages/LeadsPage.jsx
git commit -m "fix(leads): pagination field, dark theme header, email source filter"
```

---

### Task 3: Translation keys for new features

**Files:**
- Modify: `nextlen/src/locales/en/translation.json` (leads section, ~line 756)
- Modify: `nextlen/src/locales/de/translation.json` (leads section)

- [ ] **Step 1: Add English translation keys**

Add these keys inside the `"leads"` object (after `"viewConversation"`):
```json
"export": "Export CSV",
"exporting": "Exporting...",
"deleteConfirmTitle": "Delete Lead",
"deleteConfirmMessage": "Delete lead {{name}}? This action cannot be undone.",
"deleteConfirm": "Delete",
"deleteCancel": "Cancel",
"detailTitle": "Lead Details",
"contactInfo": "Contact Information",
"aiSummary": "AI Summary",
"noSummary": "No summary yet",
"viewConversationBtn": "View Conversation",
"noConversation": "No conversation linked",
"close": "Close"
```

- [ ] **Step 2: Add German translation keys**

Same keys in German `"leads"` section:
```json
"export": "CSV exportieren",
"exporting": "Exportiere...",
"deleteConfirmTitle": "Lead l\u00f6schen",
"deleteConfirmMessage": "Lead {{name}} l\u00f6schen? Diese Aktion kann nicht r\u00fcckg\u00e4ngig gemacht werden.",
"deleteConfirm": "L\u00f6schen",
"deleteCancel": "Abbrechen",
"detailTitle": "Lead-Details",
"contactInfo": "Kontaktinformationen",
"aiSummary": "KI-Zusammenfassung",
"noSummary": "Noch keine Zusammenfassung",
"viewConversationBtn": "Konversation ansehen",
"noConversation": "Keine Konversation verkn\u00fcpft",
"close": "Schlie\u00dfen"
```

- [ ] **Step 3: Commit**

```bash
git add nextlen/src/locales/en/translation.json nextlen/src/locales/de/translation.json
git commit -m "feat(leads): add translation keys for detail panel, delete, export"
```

---

### Task 4: Delete lead — confirmation dialog + trash icon

**Files:**
- Modify: `nextlen/src/pages/LeadsPage.jsx`

- [ ] **Step 1: Add Trash2 to lucide imports**

Line 4, add `Trash2` to the import:
```js
import { Loader2, Search, ExternalLink, ChevronDown, Globe, MessageCircle, Smartphone, Mail, Users, Trash2 } from 'lucide-react';
```

- [ ] **Step 2: Add DeleteConfirmDialog component**

Add this component after the `SourceBadge` component (after line 103):

```jsx
/* -- Delete confirmation dialog -- */
const DeleteConfirmDialog = ({ lead, onConfirm, onCancel, t }) => (
  <div className="fixed inset-0 z-[60] flex items-center justify-center">
    <div className="absolute inset-0 bg-black/50" onClick={onCancel} />
    <div className="relative bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 shadow-2xl p-6 max-w-sm mx-4">
      <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-2">
        {t('leads.deleteConfirmTitle')}
      </h3>
      <p className="text-sm text-gray-600 dark:text-gray-400 mb-6">
        {t('leads.deleteConfirmMessage', { name: lead.name || `Anonymous #${lead.id}` })}
      </p>
      <div className="flex justify-end gap-3">
        <button
          onClick={onCancel}
          className="px-4 py-2 text-sm font-medium rounded-lg border border-gray-200 dark:border-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors cursor-pointer"
        >
          {t('leads.deleteCancel')}
        </button>
        <button
          onClick={onConfirm}
          className="px-4 py-2 text-sm font-medium rounded-lg bg-red-500 text-white hover:bg-red-600 transition-colors cursor-pointer"
        >
          {t('leads.deleteConfirm')}
        </button>
      </div>
    </div>
  </div>
);
```

- [ ] **Step 3: Add delete state and handler to LeadsPage**

Inside `LeadsPage` component, after `const [updatingId, setUpdatingId] = useState(null);` (line 118), add:

```jsx
const [deletingLead, setDeletingLead] = useState(null);

const handleDeleteLead = async (leadId) => {
  try {
    await api.delete(`/clients/leads/${leadId}/`);
    setLeads((prev) => prev.filter((lead) => lead.id !== leadId));
  } catch (err) {
    console.error('Failed to delete lead:', err);
  } finally {
    setDeletingLead(null);
  }
};
```

- [ ] **Step 4: Add trash icon to Actions column**

In the table row Actions cell (around line 359), replace the entire `<td>` for Actions with:

```jsx
<td className="px-4 py-3">
  <div className="flex items-center gap-2">
    {lead.conversation_id ? (
      <button
        onClick={(e) => { e.stopPropagation(); handleViewConversation(lead.conversation_id); }}
        title={t('leads.viewConversation')}
        aria-label={t('leads.viewConversation')}
        className="text-primary-500 hover:text-primary-700 dark:hover:text-primary-300 transition-colors cursor-pointer"
      >
        <ExternalLink size={16} />
      </button>
    ) : (
      <span className="text-gray-300 dark:text-gray-600" title="No conversation linked">
        <ExternalLink size={16} />
      </span>
    )}
    <button
      onClick={(e) => { e.stopPropagation(); setDeletingLead(lead); }}
      title="Delete lead"
      aria-label="Delete lead"
      className="text-gray-400 hover:text-red-500 dark:hover:text-red-400 transition-colors cursor-pointer"
    >
      <Trash2 size={16} />
    </button>
  </div>
</td>
```

- [ ] **Step 5: Render DeleteConfirmDialog**

Inside the return JSX, just before the closing `</div>` of the main wrapper (before line 407), add:

```jsx
{deletingLead && (
  <DeleteConfirmDialog
    lead={deletingLead}
    onConfirm={() => handleDeleteLead(deletingLead.id)}
    onCancel={() => setDeletingLead(null)}
    t={t}
  />
)}
```

- [ ] **Step 6: Commit**

```bash
git add nextlen/src/pages/LeadsPage.jsx
git commit -m "feat(leads): add single lead delete with confirmation dialog"
```

---

### Task 5: CSV export

**Files:**
- Modify: `nextlen/src/pages/LeadsPage.jsx`

- [ ] **Step 1: Add Download icon to imports**

Line 4, add `Download` to lucide imports:
```js
import { Loader2, Search, ExternalLink, ChevronDown, Globe, MessageCircle, Smartphone, Mail, Users, Trash2, Download } from 'lucide-react';
```

- [ ] **Step 2: Add CSV helper and export state**

Inside `LeadsPage`, after the `handleDeleteLead` function, add:

```jsx
const [exporting, setExporting] = useState(false);

const INTEREST_LABELS = ['Cold', 'Cool', 'Warm', 'Hot', 'Fire'];

const escapeCsvField = (val) => {
  const str = String(val ?? '');
  if (str.includes(',') || str.includes('"') || str.includes('\n')) {
    return `"${str.replace(/"/g, '""')}"`;
  }
  return str;
};

const handleExportCsv = async () => {
  setExporting(true);
  try {
    const params = { per_page: 10000, export: 'true' };
    if (search) params.search = search;
    if (statusFilter) params.status = statusFilter;
    if (sourceFilter) params.source = sourceFilter;

    const response = await api.get('/clients/leads/', { params });
    const allLeads = response.data.results || response.data;

    const headers = ['Name', 'Email', 'Phone', 'Source', 'Interest', 'Status', 'Date', 'AI Summary'];
    const rows = allLeads.map((lead) => [
      lead.name || '',
      lead.email || '',
      lead.phone || '',
      lead.source || '',
      INTEREST_LABELS[Math.max(0, Math.min(4, (lead.interest_score || 1) - 1))],
      lead.status || 'new',
      lead.created_at ? new Date(lead.created_at).toLocaleDateString() : '',
      lead.request_summary || '',
    ]);

    const csv = [headers, ...rows].map((row) => row.map(escapeCsvField).join(',')).join('\n');
    const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `leads-export-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  } catch (err) {
    console.error('Failed to export leads:', err);
  } finally {
    setExporting(false);
  }
};
```

- [ ] **Step 3: Add Export button to filters bar**

In the filters `<div>` (line 193), after the source filter `</select>` (after line 232), add:

```jsx
<button
  onClick={handleExportCsv}
  disabled={leads.length === 0 || exporting}
  className="inline-flex items-center gap-2 px-3 py-2 text-sm font-medium border border-gray-200 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 disabled:opacity-40 transition-colors cursor-pointer"
>
  {exporting ? <Loader2 size={16} className="animate-spin" /> : <Download size={16} />}
  {exporting ? t('leads.exporting') : t('leads.export')}
</button>
```

- [ ] **Step 4: Commit**

```bash
git add nextlen/src/pages/LeadsPage.jsx
git commit -m "feat(leads): add CSV export with all filtered leads"
```

---

### Task 6: Slide-in detail panel

**Files:**
- Modify: `nextlen/src/pages/LeadsPage.jsx`

- [ ] **Step 1: Add X icon to imports**

Line 4, add `X` to lucide imports:
```js
import { Loader2, Search, ExternalLink, ChevronDown, Globe, MessageCircle, Smartphone, Mail, Users, Trash2, Download, X } from 'lucide-react';
```

- [ ] **Step 2: Add slide-in keyframes to index.css**

Find `nextlen/src/index.css` and add this keyframe (at the end of the file or near other `@keyframes`):

```css
@keyframes slideInRight {
  from { transform: translateX(100%); }
  to { transform: translateX(0); }
}
```

- [ ] **Step 3: Add LeadDetailPanel component**

Add after `DeleteConfirmDialog` component:

```jsx
/* -- Slide-in detail panel -- */
const LeadDetailPanel = ({ lead, onClose, onStatusChange, updatingId, onViewConversation, formatDate, t }) => {
  useEffect(() => {
    const handler = (e) => {
      if (e.key === 'Escape') {
        // Don't close panel if a dropdown or dialog is open (they handle Escape themselves)
        if (document.querySelector('[data-dropdown-open="true"]')) return;
        onClose();
      }
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-black/30" onClick={onClose} />
      <div
        className="relative w-full max-w-md bg-white dark:bg-gray-800 border-l border-gray-200 dark:border-gray-700 shadow-2xl overflow-y-auto"
        style={{ animation: 'slideInRight 0.2s ease-out' }}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100 truncate">
            {lead.name || <span className="text-gray-400 italic">Anonymous #{lead.id}</span>}
          </h2>
          <button
            onClick={onClose}
            aria-label={t('leads.close')}
            className="p-1 rounded-lg text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors cursor-pointer"
          >
            <X size={20} />
          </button>
        </div>

        <div className="px-6 py-5 space-y-6">
          {/* Contact Info */}
          <div>
            <h3 className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-3">
              {t('leads.contactInfo')}
            </h3>
            <div className="space-y-2">
              <div className="flex items-center justify-between text-sm">
                <span className="text-gray-500 dark:text-gray-400">{t('leads.email')}</span>
                <span className="text-gray-900 dark:text-gray-100">{lead.email || '\u2014'}</span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-gray-500 dark:text-gray-400">{t('leads.phone')}</span>
                <span className="text-gray-900 dark:text-gray-100">{lead.phone || '\u2014'}</span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-gray-500 dark:text-gray-400">{t('leads.source')}</span>
                <SourceBadge source={lead.source} />
              </div>
            </div>
          </div>

          {/* Status & Interest */}
          <div className="flex items-center gap-4">
            <div>
              <h3 className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-2">
                {t('leads.status')}
              </h3>
              <StatusDropdown
                status={lead.status || 'new'}
                onStatusChange={(newStatus) => onStatusChange(lead.id, newStatus)}
                loading={updatingId === lead.id}
              />
            </div>
            <div>
              <h3 className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-2">
                {t('leads.interest')}
              </h3>
              <HeatIndicator score={lead.interest_score || 0} />
            </div>
          </div>

          {/* AI Summary */}
          <div>
            <h3 className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-2">
              {t('leads.aiSummary')}
            </h3>
            {lead.request_summary ? (
              <p className="text-sm text-gray-700 dark:text-gray-300 leading-relaxed bg-gray-50 dark:bg-gray-900/50 rounded-lg p-3">
                {lead.request_summary}
              </p>
            ) : (
              <p className="text-sm text-gray-400 dark:text-gray-500 italic">
                {t('leads.noSummary')}
              </p>
            )}
          </div>

          {/* Date */}
          <div className="flex items-center justify-between text-sm">
            <span className="text-gray-500 dark:text-gray-400">{t('leads.date')}</span>
            <span className="text-gray-900 dark:text-gray-100">{formatDate(lead.created_at)}</span>
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-gray-200 dark:border-gray-700">
          <button
            onClick={() => lead.conversation_id && onViewConversation(lead.conversation_id)}
            disabled={!lead.conversation_id}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-medium rounded-lg bg-primary-500 text-white hover:bg-primary-600 disabled:opacity-40 disabled:cursor-not-allowed transition-colors cursor-pointer"
          >
            <ExternalLink size={16} />
            {t('leads.viewConversationBtn')}
          </button>
          {!lead.conversation_id && (
            <p className="text-xs text-gray-400 dark:text-gray-500 text-center mt-2">
              {t('leads.noConversation')}
            </p>
          )}
        </div>
      </div>
    </div>
  );
};
```

- [ ] **Step 4: Add selected lead state**

Inside `LeadsPage`, after `const [deletingLead, setDeletingLead] = useState(null);`, add:

```jsx
const [selectedLead, setSelectedLead] = useState(null);
```

- [ ] **Step 5: Patch handleDeleteLead to close panel**

In `handleDeleteLead`, after `setLeads((prev) => prev.filter(...));`, add:
```jsx
    setSelectedLead((prev) => prev && prev.id === leadId ? null : prev);
```

- [ ] **Step 6: Make table rows clickable**

On each `<tr>` in the table body (line 315), add `onClick` and cursor:

```jsx
<tr
  key={lead.id}
  onClick={() => setSelectedLead(lead)}
  className="border-b border-gray-100 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors cursor-pointer"
>
```

- [ ] **Step 7: Add data-dropdown-open attribute to StatusDropdown**

In the `StatusDropdown` component, on the outer `<div>` (the one with `ref={ref}`), add the data attribute:

```jsx
<div className="relative" ref={ref} data-dropdown-open={open}>
```

This allows `LeadDetailPanel`'s Escape handler to detect if a dropdown is open before closing the panel.

- [ ] **Step 8: Stop propagation on StatusDropdown click**

Wrap the StatusDropdown `<td>` (line 345) to prevent row click:

```jsx
<td className="px-4 py-3" onClick={(e) => e.stopPropagation()}>
```

- [ ] **Step 9: Render LeadDetailPanel**

In the return JSX, after the `DeleteConfirmDialog` render, add:

```jsx
{selectedLead && (
  <LeadDetailPanel
    lead={selectedLead}
    onClose={() => setSelectedLead(null)}
    onStatusChange={(id, newStatus) => {
      handleStatusChange(id, newStatus);
      setSelectedLead((prev) => prev && prev.id === id ? { ...prev, status: newStatus } : prev);
    }}
    updatingId={updatingId}
    onViewConversation={handleViewConversation}
    formatDate={formatDate}
    t={t}
  />
)}
```

- [ ] **Step 10: Commit**

```bash
git add nextlen/src/pages/LeadsPage.jsx nextlen/src/index.css
git commit -m "feat(leads): add slide-in detail panel with AI summary"
```

---

### Task 7: Final verification

- [ ] **Step 1: Run frontend dev server and verify**

```bash
cd nextlen && npm run dev
```

Check manually:
- Pagination works (shows correct page count)
- Dark theme header has proper background
- Email appears in source filter
- Click row → slide-in panel opens with contact info, AI summary, status, interest
- Escape / click outside / X closes panel
- StatusDropdown in table doesn't open panel
- Trash icon visible, click shows confirmation, confirm deletes lead
- Export CSV button fetches all leads, downloads file with correct content
- CSV opens correctly in Excel (no encoding issues with BOM)

- [ ] **Step 2: Final commit if any adjustments needed**

```bash
git add -A
git commit -m "fix(leads): polish after manual testing"
```
