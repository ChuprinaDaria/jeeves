# Visual Editor — MCP Architecture Adaptation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Evolve the flat node-based visual editor into a rich, categorized MCP architecture visualization with content previews, labeled edges, categorized tabs, and a context panel.

**Architecture:** Extend existing FlowCanvas + CanvasToolNode components with a pluggable rich-card system. Add a backend word-frequency endpoint with Redis caching. Edge labels rendered as SVG text on existing bezier paths. Tab system extended from 4 static tabs to 5 category-based tabs. Context panel as a new overlay component.

**Tech Stack:** React 18, d3-cloud, Django 5, PostgreSQL + pgvector, Redis, Tailwind CSS

**Design System:** Cyberpunk UI dark mode, palette: #020617 (bg) / #0F172A (primary) / #1E293B (secondary) / #22C55E (CTA) / #F8FAFC (text). Typography: Fira Code / Fira Sans.

**Spec:** `VISUAL_EDITOR_ADAPTATION.md`

---

## File Structure

### Backend (new/modified)
- Create: `p004_ai_nexelin/MASTER/tools/word_cloud.py` — word frequency computation logic
- Modify: `p004_ai_nexelin/MASTER/tools/views.py` — add WordCloudView endpoint
- Modify: `p004_ai_nexelin/MASTER/tools/urls.py` — register word-cloud route

### Frontend (new/modified)
- Create: `nextlen/src/components/tools/richcards/KnowledgeBaseCard.jsx` — word cloud rich card
- Create: `nextlen/src/components/tools/richcards/RichCardWrapper.jsx` — pluggable card selector
- Modify: `nextlen/src/components/tools/CanvasToolNode.jsx` — integrate rich card rendering
- Modify: `nextlen/src/components/tools/ConnectionsLayer.jsx` — add edge labels
- Modify: `nextlen/src/components/tools/ToolCatalogStrip.jsx` — new category tabs
- Create: `nextlen/src/components/tools/ContextPanel.jsx` — context view panel
- Modify: `nextlen/src/components/tools/FlowCanvas.jsx` — mount ContextPanel, pass edge labels data
- Modify: `nextlen/src/api/tools.js` — add word-cloud API call
- Modify: `nextlen/src/index.css` — word cloud + context panel animations

---

## Task 1: Backend — Word Frequency Endpoint

**Files:**
- Create: `p004_ai_nexelin/MASTER/tools/word_cloud.py`
- Modify: `p004_ai_nexelin/MASTER/tools/views.py`
- Modify: `p004_ai_nexelin/MASTER/tools/urls.py`

**Context:** `ClientEmbedding.content` stores enhanced chunk text (doc title + chunk). We aggregate word frequencies from all embeddings for a client, filter stop-words (multi-lang: DE, EN, UK, PL, FR, IT), cache in Redis with 1h TTL.

- [ ] **Step 1: Create word_cloud.py with frequency computation**

```python
# p004_ai_nexelin/MASTER/tools/word_cloud.py
import re
from collections import Counter
from django.core.cache import cache

STOP_WORDS = {
    'en': {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
           'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
           'should', 'may', 'might', 'shall', 'can', 'need', 'dare', 'ought',
           'used', 'to', 'of', 'in', 'for', 'on', 'with', 'at', 'by', 'from',
           'as', 'into', 'through', 'during', 'before', 'after', 'above', 'below',
           'between', 'out', 'off', 'over', 'under', 'again', 'further', 'then',
           'once', 'here', 'there', 'when', 'where', 'why', 'how', 'all', 'each',
           'every', 'both', 'few', 'more', 'most', 'other', 'some', 'such', 'no',
           'nor', 'not', 'only', 'own', 'same', 'so', 'than', 'too', 'very',
           'just', 'because', 'but', 'and', 'or', 'if', 'while', 'this', 'that',
           'these', 'those', 'it', 'its', 'i', 'me', 'my', 'we', 'our', 'you',
           'your', 'he', 'him', 'his', 'she', 'her', 'they', 'them', 'their',
           'what', 'which', 'who', 'whom'},
    'de': {'der', 'die', 'das', 'ein', 'eine', 'und', 'ist', 'in', 'von', 'zu',
           'den', 'mit', 'auf', 'fur', 'an', 'als', 'auch', 'es', 'ich', 'nicht',
           'sich', 'dem', 'dass', 'er', 'sie', 'wir', 'sind', 'hat', 'aus',
           'bei', 'wird', 'nach', 'wie', 'aber', 'noch', 'da', 'nur', 'wenn',
           'sein', 'ihre', 'oder', 'war', 'uber', 'so', 'zum', 'im', 'haben',
           'einer', 'mir', 'um', 'des', 'bis', 'vor', 'zur', 'worden'},
    'uk': {'i', 'в', 'на', 'з', 'що', 'не', 'до', 'та', 'як', 'за', 'у',
           'це', 'але', 'для', 'вiд', 'по', 'про', 'яка', 'який', 'яке',
           'бути', 'було', 'були', 'його', 'їх', 'так', 'цей', 'ця', 'тi'},
    'pl': {'i', 'w', 'na', 'z', 'do', 'nie', 'co', 'to', 'jak', 'ale',
           'za', 'od', 'po', 'ze', 'si', 'jest', 'czy', 'tak', 'go', 'ich',
           'te', 'ten', 'ta', 'przez', 'przy', 'dla'},
    'fr': {'le', 'la', 'les', 'de', 'du', 'des', 'un', 'une', 'et', 'en',
           'est', 'que', 'qui', 'dans', 'pour', 'pas', 'au', 'sur', 'ce',
           'il', 'ne', 'se', 'par', 'avec', 'sont', 'son', 'sa', 'ses'},
    'it': {'il', 'lo', 'la', 'le', 'di', 'del', 'dei', 'un', 'una', 'e',
           'in', 'che', 'per', 'non', 'con', 'da', 'su', 'al', 'sono'},
}

ALL_STOP_WORDS = set()
for words in STOP_WORDS.values():
    ALL_STOP_WORDS |= words

CACHE_KEY_PREFIX = 'word_cloud'
CACHE_TTL = 3600

WORD_RE = re.compile(r'[a-zA-Zа-яА-ЯіІїЇєЄґҐąćęłńóśźżÄÖÜäöüß]+', re.UNICODE)
MIN_WORD_LEN = 3
MAX_WORDS = 80


def compute_word_frequencies(client_id):
    cache_key = f'{CACHE_KEY_PREFIX}:{client_id}'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    from MASTER.clients.models import ClientEmbedding
    contents = ClientEmbedding.objects.filter(
        client_id=client_id
    ).values_list('content', flat=True)

    counter = Counter()
    for text in contents.iterator(chunk_size=500):
        words = WORD_RE.findall(text.lower())
        counter.update(
            w for w in words
            if len(w) >= MIN_WORD_LEN and w not in ALL_STOP_WORDS
        )

    result = [
        {'text': word, 'value': count}
        for word, count in counter.most_common(MAX_WORDS)
    ]

    cache.set(cache_key, result, CACHE_TTL)
    return result
```

- [ ] **Step 2: Add WordCloudView to tools/views.py**

Add at the end of `p004_ai_nexelin/MASTER/tools/views.py`:

```python
from MASTER.tools.word_cloud import compute_word_frequencies

class WordCloudView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        client = get_client_from_request(request)
        if not client:
            return Response({'error': 'Client not found'}, status=401)
        words = compute_word_frequencies(client.id)
        return Response({'words': words})
```

- [ ] **Step 3: Register URL in tools/urls.py**

Add to urlpatterns:
```python
path('word-cloud/', views.WordCloudView.as_view(), name='tool-word-cloud'),
```

- [ ] **Step 4: Add frontend API call**

Add to `nextlen/src/api/tools.js`:
```javascript
getWordCloud: () => api.get('/tools/word-cloud/'),
```

- [ ] **Step 5: Test endpoint manually**

```bash
curl -H "Authorization: Bearer <token>" http://localhost:8000/api/tools/word-cloud/
```
Expected: `{"words": [{"text": "...", "value": N}, ...]}`

- [ ] **Step 6: Commit**

```bash
git add p004_ai_nexelin/MASTER/tools/word_cloud.py p004_ai_nexelin/MASTER/tools/views.py p004_ai_nexelin/MASTER/tools/urls.py nextlen/src/api/tools.js
git commit -m "feat(tools): add word-cloud frequency endpoint with Redis cache"
```

---

## Task 2: Knowledge Base Rich Card with Word Cloud

**Files:**
- Create: `nextlen/src/components/tools/richcards/KnowledgeBaseCard.jsx`
- Create: `nextlen/src/components/tools/richcards/RichCardWrapper.jsx`
- Modify: `nextlen/src/components/tools/CanvasToolNode.jsx`
- Modify: `nextlen/src/index.css`

**Context:** `CanvasToolNode` currently renders a flat card (icon + name + tagline + status). For `rag-search` slug, we replace the tagline area with a d3-cloud word cloud visualization. Card size expands from 160px to 220px width for rich cards.

**Dependencies:** `npm install d3-cloud` (d3-cloud has zero deps beyond d3-dispatch)

- [ ] **Step 1: Install d3-cloud**

```bash
cd nextlen && npm install d3-cloud
```

- [ ] **Step 2: Create KnowledgeBaseCard.jsx**

```jsx
// nextlen/src/components/tools/richcards/KnowledgeBaseCard.jsx
import { useEffect, useRef, useState } from 'react';
import cloud from 'd3-cloud';
import { toolsAPI } from '../../../api/tools';

const COLORS = ['#22C55E', '#a29bfe', '#fbbf24', '#00d9a3', '#8b5cf6', '#f472b6', '#38bdf8'];

const KnowledgeBaseCard = ({ clientId }) => {
  const svgRef = useRef(null);
  const [words, setWords] = useState([]);

  useEffect(() => {
    toolsAPI.getWordCloud()
      .then(res => setWords(res.data?.words || []))
      .catch(() => {});
  }, [clientId]);

  useEffect(() => {
    if (!words.length || !svgRef.current) return;

    const w = 180, h = 90;
    const maxVal = Math.max(...words.map(d => d.value));

    const layout = cloud()
      .size([w, h])
      .words(words.map(d => ({ text: d.text, size: 8 + (d.value / maxVal) * 14 })))
      .padding(1)
      .rotate(() => (Math.random() > 0.7 ? 90 : 0))
      .fontSize(d => d.size)
      .on('end', draw);

    layout.start();

    function draw(computed) {
      const svg = svgRef.current;
      while (svg.firstChild) svg.removeChild(svg.firstChild);
      const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
      g.setAttribute('transform', `translate(${w / 2},${h / 2})`);

      computed.forEach((d, i) => {
        const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        text.setAttribute('text-anchor', 'middle');
        text.setAttribute('transform', `translate(${d.x},${d.y}) rotate(${d.rotate})`);
        text.setAttribute('font-size', `${d.size}px`);
        text.setAttribute('font-family', "'Fira Code', monospace");
        text.setAttribute('fill', COLORS[i % COLORS.length]);
        text.setAttribute('opacity', '0.85');
        text.textContent = d.text;
        g.appendChild(text);
      });

      svg.appendChild(g);
    }
  }, [words]);

  if (!words.length) {
    return (
      <div className="w-full h-[90px] flex items-center justify-center">
        <div className="text-[9px] text-gray-500">No documents yet</div>
      </div>
    );
  }

  return (
    <svg
      ref={svgRef}
      className="w-full word-cloud-fade-in"
      viewBox="0 0 180 90"
      style={{ height: 90 }}
    />
  );
};

export default KnowledgeBaseCard;
```

- [ ] **Step 3: Create RichCardWrapper.jsx**

```jsx
// nextlen/src/components/tools/richcards/RichCardWrapper.jsx
import { lazy, Suspense } from 'react';

const KnowledgeBaseCard = lazy(() => import('./KnowledgeBaseCard'));

const RICH_CARDS = {
  'rag-search': KnowledgeBaseCard,
};

const RichCardWrapper = ({ slug, clientId }) => {
  const CardComponent = RICH_CARDS[slug];
  if (!CardComponent) return null;

  return (
    <Suspense fallback={<div className="h-[90px] animate-pulse bg-gray-100 dark:bg-gray-700 rounded-lg" />}>
      <CardComponent clientId={clientId} />
    </Suspense>
  );
};

export default RichCardWrapper;
export const hasRichCard = (slug) => slug in RICH_CARDS;
```

- [ ] **Step 4: Integrate into CanvasToolNode.jsx**

Modify `CanvasToolNode.jsx`:
- Import `RichCardWrapper, { hasRichCard }` from `./richcards/RichCardWrapper`
- After the tagline block (line 79), add:
```jsx
{hasRichCard(tool.slug) && isConnected && (
  <RichCardWrapper slug={tool.slug} />
)}
```
- Change card width from `w-[160px]` to dynamic: `${hasRichCard(tool.slug) && isConnected ? 'w-[220px]' : 'w-[160px]'}`

- [ ] **Step 5: Add CSS animation for word cloud**

Add to `nextlen/src/index.css`:
```css
@keyframes word-cloud-fade-in {
  from { opacity: 0; filter: blur(4px); }
  to { opacity: 1; filter: blur(0); }
}
.word-cloud-fade-in {
  animation: word-cloud-fade-in 0.6s ease-out both;
}
```

- [ ] **Step 6: Update TOOL_W in FlowCanvas.jsx for rich cards**

In `FlowCanvas.jsx`, the layout uses `TOOL_W = 160`. For tools with rich cards, adjust positioning. Modify `buildInitialPositions` to check rich card width:

```javascript
const getToolWidth = (slug) => hasRichCard(slug) ? 220 : TOOL_W;
```

Import `{ hasRichCard }` from `./richcards/RichCardWrapper` in FlowCanvas.jsx and use `getToolWidth(tool.slug)` in position calculations where `TOOL_W` is referenced for specific tools.

- [ ] **Step 7: Commit**

```bash
git add nextlen/src/components/tools/richcards/ nextlen/src/components/tools/CanvasToolNode.jsx nextlen/src/components/tools/FlowCanvas.jsx nextlen/src/index.css
git commit -m "feat(tools): add Knowledge Base word cloud rich card with d3-cloud"
```

---

## Task 3: Edge Labels

**Files:**
- Modify: `nextlen/src/components/tools/ConnectionsLayer.jsx`
- Modify: `nextlen/src/components/tools/FlowCanvas.jsx`

**Context:** Each connection already has `target` and `toolSlug`. We map (toolSlug, target) pairs to action labels. Labels rendered as SVG `<text>` at 40% of the bezier path, rotated to follow the curve direction.

- [ ] **Step 1: Define edge label mapping**

Add at the top of `ConnectionsLayer.jsx`:

```javascript
const EDGE_LABELS = {
  'rag-search': { assistant: 'Fetch semantic query', manager: 'Fetch semantic profile' },
  'email-smtp': { assistant: 'Send email', manager: 'Send email' },
  'telegram': { assistant: 'Send message', manager: 'Escalation' },
  'whatsapp-bridge': { assistant: 'Send message', manager: 'Escalation' },
  'web-widget': { assistant: 'Send message', manager: 'Escalation' },
  'instagram': { assistant: 'Send message', manager: 'Escalation' },
  'hitl-matrix': { assistant: 'Escalation', manager: 'Live handoff' },
  'crm': { assistant: 'Query CRM data', manager: 'Query CRM data' },
  'analytics': { assistant: 'Fetch analytics', manager: 'Fetch analytics' },
  'xlsx-processor': { assistant: 'Process spreadsheet' },
  'translation': { assistant: 'Translate text' },
  'leads': { leads: 'Capture lead' },
  'sales-intel': { leads: 'Enrich lead data' },
  'coaching': { assistant: 'Apply coaching rules' },
  'email': { assistant: 'Fetch email context' },
  '__escalation': { escalation: 'Escalation' },
};
```

- [ ] **Step 2: Add path IDs for textPath references**

The main line `<path>` needs an `id` for `<textPath>` to reference. Add `id={`edge-path-${conn.id}`}` to the main line path element (the one with `className="flow-line-animated"`).

- [ ] **Step 3: Render labels on edges**

Inside the `connections.map()` in ConnectionsLayer, after the animated particles block (before closing `</g>`), add:

```jsx
{(() => {
  const label = conn.toolSlug === '__escalation'
    ? 'Escalation'
    : EDGE_LABELS[conn.toolSlug]?.[conn.target];
  if (!label) return null;
  return (
    <text
      fill="#94a3b8"
      fontSize="9"
      fontFamily="'Fira Sans', sans-serif"
      fontWeight="500"
      textAnchor="middle"
      dy="-8"
      opacity={isHighlighted ? 0.9 : 0}
      style={{ transition: 'opacity 0.3s', pointerEvents: 'none' }}
    >
      <textPath href={`#edge-path-${conn.id}`} startOffset="40%">
        {label}
      </textPath>
    </text>
  );
})()}
```

- [ ] **Step 4: Pass toolSlug in escalation connection**

In `FlowCanvas.jsx`, the escalation connection object (assistant -> manager) needs `toolSlug: '__escalation'` so the label mapping works. Find where escalation connections are built and ensure this field is set.

- [ ] **Step 5: Commit**

```bash
git add nextlen/src/components/tools/ConnectionsLayer.jsx nextlen/src/components/tools/FlowCanvas.jsx
git commit -m "feat(tools): add action labels on edges with textPath rendering"
```

---

## Task 4: Categorized Tab System

**Files:**
- Modify: `nextlen/src/components/tools/ToolCatalogStrip.jsx`

**Context:** Replace current 4 tabs (All/Servers/Skills/Tools) with 6 category tabs (All/Data Sources/Business Logic/Automation & Skills/Communication/Analytics). Update `SLUG_TO_GROUP` mapping accordingly.

- [ ] **Step 1: Update TABS and SLUG_TO_GROUP**

Replace the constants at the top of `ToolCatalogStrip.jsx`:

```javascript
const SLUG_TO_GROUP = {
  'rag-search':      'data',
  'email':           'data',
  'crm':             'data',
  'sales-intel':     'data',
  'coaching':        'logic',
  'hitl-matrix':     'logic',
  'translation':     'skills',
  'xlsx-processor':  'skills',
  'leads':           'skills',
  'telegram':        'comm',
  'web-widget':      'comm',
  'whatsapp-bridge': 'comm',
  'instagram':       'comm',
  'email-smtp':      'comm',
  'calendar':        'comm',
  'analytics':       'analytics',
};

const TABS = [
  { id: 'all',       labelKey: 'tools.flow.tabAll' },
  { id: 'data',      labelKey: 'tools.flow.tabData' },
  { id: 'logic',     labelKey: 'tools.flow.tabLogic' },
  { id: 'skills',    labelKey: 'tools.flow.tabSkills' },
  { id: 'comm',      labelKey: 'tools.flow.tabComm' },
  { id: 'analytics', labelKey: 'tools.flow.tabAnalytics' },
];
```

- [ ] **Step 2: Update rendering logic**

The current rendering uses `group === 'servers'` and `group === 'skills'` to decide ServerChip vs SkillChip. Update:
- `'data'` and `'logic'` -> render as `ServerChip` (larger cards)
- `'skills'` -> render as `SkillChip` (circles)
- `'comm'` and `'analytics'` -> render as `FlipToolCard` (with auth flow)

Update the SERVER_COLORS map to include new slugs if missing.

- [ ] **Step 3: Add i18n keys**

Add translation keys for new tab labels. Fallback defaults:
- `tools.flow.tabData` -> "Data Sources"
- `tools.flow.tabLogic` -> "Business Logic"
- `tools.flow.tabComm` -> "Communication"
- `tools.flow.tabAnalytics` -> "Analytics"

- [ ] **Step 4: Commit**

```bash
git add nextlen/src/components/tools/ToolCatalogStrip.jsx
git commit -m "feat(tools): categorized tab system — Data Sources, Business Logic, Skills, Comm, Analytics"
```

---

## Task 5: Context View Panel

**Files:**
- Create: `nextlen/src/components/tools/ContextPanel.jsx`
- Modify: `nextlen/src/components/tools/FlowCanvas.jsx`
- Modify: `nextlen/src/index.css`

**Context:** A collapsible side panel (top-right overlay) showing merged context: which data sources are connected, active permissions, recent query info. Data comes from existing `tools` prop (connected tools with targets) — no new API needed for v1.

- [ ] **Step 1: Create ContextPanel.jsx**

```jsx
// nextlen/src/components/tools/ContextPanel.jsx
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ChevronRight, Database, Shield, MessageSquare, Layers } from 'lucide-react';
import ToolIcon from './ToolIcon';

const ContextPanel = ({ tools }) => {
  const { t } = useTranslation();
  const [collapsed, setCollapsed] = useState(true);

  const connected = tools.filter(tool => {
    if (tool.connections) return tool.connections.some(c => c.status === 'connected' && c.enabled);
    return tool.connection?.status === 'connected' && tool.connection?.enabled;
  });

  const dataSources = connected.filter(t => ['rag-search', 'email', 'crm', 'sales-intel'].includes(t.slug));
  const channels = connected.filter(t => ['telegram', 'web-widget', 'whatsapp-bridge', 'instagram', 'email-smtp'].includes(t.slug));
  const skills = connected.filter(t => ['translation', 'xlsx-processor'].includes(t.slug));

  if (collapsed) {
    return (
      <button
        onClick={() => setCollapsed(false)}
        className="absolute top-3 right-3 z-20 px-2.5 py-2 rounded-xl
          bg-gray-900/80 dark:bg-gray-800/90 backdrop-blur-sm border border-gray-700/50
          text-gray-400 hover:text-gray-200 transition-all cursor-pointer
          hover:bg-gray-800/90 shadow-lg"
        title="Merged Context"
      >
        <Layers className="w-4 h-4" />
      </button>
    );
  }

  return (
    <div className="absolute top-3 right-3 z-20 w-[260px] context-panel-enter
      bg-gray-900/90 dark:bg-gray-800/95 backdrop-blur-md rounded-2xl border border-gray-700/50
      shadow-2xl overflow-hidden">

      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-700/50">
        <span className="text-xs font-semibold text-gray-300 uppercase tracking-wider">Merged Context</span>
        <button
          onClick={() => setCollapsed(true)}
          className="text-gray-500 hover:text-gray-300 transition-colors cursor-pointer"
        >
          <ChevronRight className="w-4 h-4" />
        </button>
      </div>

      <div className="p-3 space-y-3 max-h-[400px] overflow-y-auto scrollbar-hide">
        {dataSources.length > 0 && (
          <Section icon={Database} title="Data Sources" items={dataSources} />
        )}
        {channels.length > 0 && (
          <Section icon={MessageSquare} title="Channels" items={channels} />
        )}
        {skills.length > 0 && (
          <Section icon={Shield} title="Active Skills" items={skills} />
        )}
        {connected.length === 0 && (
          <div className="text-center py-4 text-xs text-gray-500">
            No tools connected
          </div>
        )}
      </div>

      <div className="px-4 py-2 border-t border-gray-700/50">
        <div className="text-[9px] text-gray-500 font-mono">
          {connected.length} sources active
        </div>
      </div>
    </div>
  );
};

const Section = ({ icon: Icon, title, items }) => (
  <div>
    <div className="flex items-center gap-1.5 mb-1.5">
      <Icon className="w-3 h-3 text-gray-500" />
      <span className="text-[10px] font-semibold text-gray-400 uppercase tracking-wide">{title}</span>
    </div>
    <div className="space-y-1">
      {items.map(tool => (
        <div key={tool.slug} className="flex items-center gap-2 px-2 py-1 rounded-lg bg-gray-800/50">
          <ToolIcon name={tool.icon} className="w-3.5 h-3.5 text-gray-400" />
          <span className="text-[11px] text-gray-300 truncate">{tool.name}</span>
          <span className="ml-auto w-1.5 h-1.5 rounded-full bg-green-500 shrink-0" />
        </div>
      ))}
    </div>
  </div>
);

export default ContextPanel;
```

- [ ] **Step 2: Mount in FlowCanvas.jsx**

Import `ContextPanel` and add inside the canvas container div (absolute positioned):

```jsx
<ContextPanel tools={tools} />
```

Place it inside the outer container `ref={containerRef}` but outside the transform wrapper, so it stays fixed in screen space.

- [ ] **Step 3: Add CSS animation**

Add to `nextlen/src/index.css`:
```css
@keyframes context-panel-enter {
  from { opacity: 0; transform: translateX(20px); }
  to { opacity: 1; transform: translateX(0); }
}
.context-panel-enter {
  animation: context-panel-enter 0.3s ease-out both;
}
```

- [ ] **Step 4: Commit**

```bash
git add nextlen/src/components/tools/ContextPanel.jsx nextlen/src/components/tools/FlowCanvas.jsx nextlen/src/index.css
git commit -m "feat(tools): add collapsible Context View panel with merged context summary"
```

---

## Task 6: Remaining Rich Cards (Stubs)

**Files:**
- Create: `nextlen/src/components/tools/richcards/CrmCard.jsx`
- Create: `nextlen/src/components/tools/richcards/AnalyticsCard.jsx`
- Modify: `nextlen/src/components/tools/richcards/RichCardWrapper.jsx`

**Context:** Add stub rich cards for CRM (contact preview) and Analytics (sparkline). These are visual placeholders that show the card structure and will be connected to real data later.

- [ ] **Step 1: Create CrmCard.jsx**

A simple card showing a placeholder contact preview.

```jsx
// nextlen/src/components/tools/richcards/CrmCard.jsx
import { User, Building2, Clock } from 'lucide-react';

const CrmCard = () => (
  <div className="space-y-1.5 py-1">
    <div className="flex items-center gap-1.5">
      <User className="w-3 h-3 text-pink-400" />
      <span className="text-[10px] text-gray-300 font-medium">Latest Contact</span>
    </div>
    <div className="px-2 py-1.5 rounded-lg bg-gray-800/60 space-y-1">
      <div className="text-[10px] text-gray-400 flex items-center gap-1">
        <Building2 className="w-2.5 h-2.5" />
        <span>Awaiting CRM data...</span>
      </div>
      <div className="text-[9px] text-gray-500 flex items-center gap-1">
        <Clock className="w-2.5 h-2.5" />
        <span>Connect CRM to see contacts</span>
      </div>
    </div>
  </div>
);

export default CrmCard;
```

- [ ] **Step 2: Create AnalyticsCard.jsx**

A mini bar chart placeholder using CSS.

```jsx
// nextlen/src/components/tools/richcards/AnalyticsCard.jsx
import { BarChart3 } from 'lucide-react';

const AnalyticsCard = () => {
  const bars = [30, 55, 40, 70, 50, 85, 65];
  return (
    <div className="space-y-1.5 py-1">
      <div className="flex items-center gap-1.5">
        <BarChart3 className="w-3 h-3 text-blue-400" />
        <span className="text-[10px] text-gray-300 font-medium">Activity</span>
      </div>
      <div className="flex items-end gap-[3px] h-[40px] px-1">
        {bars.map((h, i) => (
          <div
            key={i}
            className="flex-1 rounded-sm bg-blue-500/30 transition-all hover:bg-blue-500/60"
            style={{ height: `${h}%` }}
          />
        ))}
      </div>
    </div>
  );
};

export default AnalyticsCard;
```

- [ ] **Step 3: Register in RichCardWrapper.jsx**

Add lazy imports and register in `RICH_CARDS`:

```javascript
const CrmCard = lazy(() => import('./CrmCard'));
const AnalyticsCard = lazy(() => import('./AnalyticsCard'));

const RICH_CARDS = {
  'rag-search': KnowledgeBaseCard,
  'crm': CrmCard,
  'analytics': AnalyticsCard,
};
```

- [ ] **Step 4: Commit**

```bash
git add nextlen/src/components/tools/richcards/
git commit -m "feat(tools): add CRM and Analytics rich card stubs"
```

---

## Execution Order & Dependencies

```
Task 1 (Backend word cloud) ──┐
                               ├──> Task 2 (KB Rich Card) ──> Task 6 (More Rich Cards)
Task 3 (Edge Labels) ─────────┤
Task 4 (Categorized Tabs) ────┤
Task 5 (Context Panel) ───────┘
```

- Tasks 1, 3, 4, 5 are independent — can run in parallel
- Task 2 depends on Task 1 (needs the API endpoint)
- Task 6 depends on Task 2 (uses RichCardWrapper pattern)
