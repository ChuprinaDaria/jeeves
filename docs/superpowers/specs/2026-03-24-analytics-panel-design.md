# Analytics Panel — Design Spec

**Date:** 2026-03-24
**Branch:** feature/sp1-mcp-core-engine
**Status:** Approved

## Overview

Replace the static Analytics node card with a wide bottom panel below the FlowCanvas. The panel displays three real-time charts (Leads & Conversions, Customer Sentiment, HITL Escalations) powered by Nivo, with a resizable divider between canvas and panel.

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Chart library | Nivo (@nivo/bar, @nivo/line) | Best visual quality out of the box, gradient fills, dark theme |
| Sentiment storage | `sentiment` field on ClientWhatsAppConversation | Minimal migration, sufficient for daily aggregation. Parallel to existing `ai_rating` (which tracks AI response quality, not conversation mood) |
| Panel placement | Below FlowCanvas (not overlay) | Zero event conflict with canvas — sibling DOM subtree |
| Resizable | Drag handle between canvas and panel | User control over split ratio |
| Period selector | One shared selector in panel header | Less UI noise, analytics viewed per single period |
| Approach | Lightweight — ORM aggregation + Redis cache | ~10 files, minimal changes to existing code |
| Timezone | Server timezone (UTC) for TruncDate | B2B clients in PL/DE/Scandinavia — close enough, no per-client tz needed |

## Backend

### Model Change

Add to `ClientWhatsAppConversation`:

```python
SENTIMENT_CHOICES = [
    ('positive', 'Positive'),
    ('neutral', 'Neutral'),
    ('negative', 'Negative'),
]

sentiment = models.CharField(
    max_length=16,
    choices=SENTIMENT_CHOICES,
    default='neutral',
    db_index=True,
)
```

**Note on `ai_rating` vs `sentiment`:** These are separate concerns. `ai_rating` (positive/negative) evaluates the quality of the AI response. `sentiment` (positive/neutral/negative) captures the overall conversation mood. Both fields coexist independently.

Update `_check_realtime_negative_sentiment()` in **both** `views.py` and `views_telegram.py` to persist detected sentiment into this field.

### Migration

One migration adding `sentiment` CharField to `ClientWhatsAppConversation`.

### Celery Task

`backfill_conversation_sentiment` — iterate existing conversations, determine sentiment from summary/last messages via LLM, save to field.

- **LLM:** Use client's configured `llm_provider_model` (same as agent uses)
- **Batch size:** 50 conversations per batch, 1s delay between batches
- **Error handling:** Log error, skip conversation, continue. Failed conversations keep default `neutral`
- **Idempotent:** Skips conversations where `sentiment != 'neutral'` (already processed)
- **Dry run:** Accept `--dry-run` argument to log what would be updated without writing

### API Endpoints

All endpoints authenticated via `X-API-Key` header (existing ClientAPIKeyMiddleware).
All endpoints cached in Redis with TTL 300s (5 min).
All support `?period=7d|30d|90d` query parameter (default `30d`).

**Period validation:** Return HTTP 400 for any value not in `{7d, 30d, 90d}`.

#### GET /api/clients/analytics/leads/

```json
{
  "period": "30d",
  "data": [
    { "date": "2026-03-01", "total": 12, "converted": 3 },
    { "date": "2026-03-02", "total": 8, "converted": 2 }
  ]
}
```

Query:
```python
Lead.objects.filter(
    client=request.client,
    created_at__gte=start_date
).annotate(
    date=TruncDate('created_at')
).values('date').annotate(
    total=Count('id'),
    converted=Count('id', filter=Q(status='converted'))
).order_by('date')
```

#### GET /api/clients/analytics/sentiment/

```json
{
  "period": "30d",
  "data": [
    { "date": "2026-03-01", "positive": 15, "negative": 3, "neutral": 8 },
    { "date": "2026-03-02", "positive": 12, "negative": 5, "neutral": 10 }
  ]
}
```

Query:
```python
ClientWhatsAppConversation.objects.filter(
    client=request.client,
    started_at__gte=start_date
).annotate(
    date=TruncDate('started_at')
).values('date').annotate(
    positive=Count('id', filter=Q(sentiment='positive')),
    negative=Count('id', filter=Q(sentiment='negative')),
    neutral=Count('id', filter=Q(sentiment='neutral'))
).order_by('date')
```

#### GET /api/clients/analytics/escalations/

```json
{
  "period": "30d",
  "data": [
    { "date": "2026-03-01", "total": 5, "resolved": 4, "pending": 1 },
    { "date": "2026-03-02", "total": 3, "resolved": 1, "pending": 2 }
  ]
}
```

Query:
```python
qs = ClientWhatsAppConversation.objects.filter(
    client=request.client,
    escalation_started_at__isnull=False,
    escalation_started_at__gte=start_date
).annotate(
    date=TruncDate('escalation_started_at')
).values('date').annotate(
    total=Count('id'),
    resolved=Count('id', filter=Q(is_waiting_for_manager=False))
).order_by('date')

# Compute pending on backend
for row in qs:
    row['pending'] = row['total'] - row['resolved']
```

### Redis Caching

Cache key pattern: `analytics:{client_id}:{metric}:{period}`
TTL: 300 seconds.
Invalidation: not needed (TTL-based expiry is sufficient for 5-min freshness).

## Frontend

### Component Architecture

```
ToolsPage.jsx (modified)
└── ResizableLayout.jsx (new)
    ├── FlowCanvas.jsx (unchanged, dynamic height)
    ├── DragHandle (6px, cursor: row-resize)
    └── AnalyticsPanel.jsx (new)
        ├── Header: title + period toggle (7d/30d/90d) + collapse chevron
        └── grid grid-cols-3 gap-4
            ├── LeadsChart.jsx (new)
            ├── SentimentChart.jsx (new)
            └── EscalationsChart.jsx (new)
```

### ResizableLayout

- Flex column container
- State: `splitRatio` (default 0.65 — 65% canvas, 35% panel)
- DragHandle: `onPointerDown` → pointer capture → `onPointerMove` recalculate ratio → `onPointerUp` release
- Constraints: min canvas 300px, min panel 180px
- On restore from localStorage: clamp ratio to respect min constraints at current viewport height
- Persist ratio to `localStorage('flow-analytics-split')`
- Double-click on handle collapses/expands panel

### AnalyticsPanel

- Background: `bg-gray-900/95`, `border-t border-gray-700/50`
- Header row: title "Real-time Monitoring & Analytics" (left), period toggle group (center), collapse chevron (right)
- Period toggle: three buttons (7d / 30d / 90d), pill-style, shared state
- Charts grid: `grid grid-cols-3 gap-4 p-4`
- Each chart has its own title and mini legend

### Chart Specifications

#### LeadsChart (Nivo ResponsiveBar)

- Type: Grouped bar
- Series: `total` (teal `#14b8a6` gradient fill), `converted` (green `#10b981` gradient fill)
- Gradient: top-to-bottom, opacity 1 → 0.4
- Axes: X = dates (formatted), Y = count
- Mini legend: teal dot "Leads", green dot "Converted"

#### SentimentChart (Nivo ResponsiveLine)

- Type: Multi-line with area fill
- Lines: positive (`#10b981`), negative (`#ef4444`), neutral (`#f59e0b`)
- Area fill: gradient opacity 0.3 → 0
- Curve: `monotoneX`
- Point markers on hover
- Mini legend: three colored dots with labels

#### EscalationsChart (Nivo ResponsiveBar)

- Type: Stacked bar
- Series: `resolved` (emerald `#10b981`), `pending` (slate `#64748b`) — both values from API
- Mini legend: "Resolved", "Pending"

#### Shared Chart Config

- `animate={true}`, `motionConfig="gentle"`
- Theme: dark — axis ticks `#9ca3af`, grid lines `#374151` (horizontal only)
- Tooltip: bg `#1f2937`, rounded, `border border-gray-600`
- Margins: `{ top: 20, right: 20, bottom: 30, left: 40 }`
- Responsive containers adapt to parent size

### Loading & Error States

- **Loading:** Skeleton pulse bars (3 gray rectangles per chart area) matching chart dimensions
- **Error (per chart):** Inline message "Failed to load" with retry button, other charts remain functional
- **Empty data:** Centered "No data yet" message per chart with muted icon

### Event Isolation

- AnalyticsPanel is a sibling of FlowCanvas in DOM — not inside it
- Sibling DOM subtree guarantees zero event conflict with canvas
- No `pointer-events` hacks needed — Nivo tooltips and interactions work naturally within the panel
- Canvas drag, edge drawing, node selection, and skill middleware are completely unaffected

### Data Fetching

New API module `nextlen/src/api/analytics.js`:

```javascript
getLeads(period)       → GET /api/clients/analytics/leads/?period={period}
getSentiment(period)   → GET /api/clients/analytics/sentiment/?period={period}
getEscalations(period) → GET /api/clients/analytics/escalations/?period={period}
```

Custom hook `useAnalyticsData(period)` — fetches all three in parallel, returns `{ leads, sentiment, escalations, loading, error }`. Refetches on period change.

### Removals

- Delete `AnalyticsCard.jsx`
- Remove `analytics` mapping from `RichCardWrapper.jsx`
- Remove `analytics` tab from `ToolCatalogStrip.jsx` TABS array
- Remove `analytics` from `SLUG_TO_GROUP` mapping

Analytics ToolCard stays in backend catalog — it just no longer renders as a node on canvas.

## File Changes Summary

### New Files

| File | Purpose |
|------|---------|
| `nextlen/src/components/analytics/AnalyticsPanel.jsx` | Panel container |
| `nextlen/src/components/analytics/LeadsChart.jsx` | Leads bar chart |
| `nextlen/src/components/analytics/SentimentChart.jsx` | Sentiment line chart |
| `nextlen/src/components/analytics/EscalationsChart.jsx` | Escalations bar chart |
| `nextlen/src/components/analytics/useAnalyticsData.js` | Data fetching hook |
| `nextlen/src/components/layout/ResizableLayout.jsx` | Resizable split panel |
| `nextlen/src/api/analytics.js` | API module |

### Modified Files

| File | Change |
|------|--------|
| `nextlen/src/pages/ToolsPage.jsx` | Wrap in ResizableLayout, add AnalyticsPanel |
| `nextlen/src/components/tools/RichCardWrapper.jsx` | Remove analytics mapping |
| `nextlen/src/components/tools/ToolCatalogStrip.jsx` | Remove analytics tab and group |
| `p004_ai_nexelin/MASTER/clients/models.py` | Add sentiment field |
| `p004_ai_nexelin/MASTER/clients/views.py` | Add 3 analytics views + update _check_realtime_negative_sentiment |
| `p004_ai_nexelin/MASTER/clients/views_telegram.py` | Update _check_realtime_negative_sentiment |
| `p004_ai_nexelin/MASTER/clients/urls.py` | Add 3 routes |
| `p004_ai_nexelin/MASTER/clients/tasks.py` | Add backfill task |

### Deleted Files

| File | Reason |
|------|--------|
| `nextlen/src/components/tools/AnalyticsCard.jsx` | Replaced by AnalyticsPanel |

### npm Dependencies

```
@nivo/bar @nivo/line
```

(`@nivo/core` is a transitive dependency of both, no need to install separately)

## What We Do NOT Touch

- FlowCanvas.jsx layout engine
- ConnectionsLayer.jsx edge rendering
- CoreNode.jsx
- EdgeSkillBadge.jsx skill middleware on edges
- KnowledgeBaseCard.jsx (d3-cloud)
- CrmCard.jsx
- Any existing API endpoints
- ToolCard backend model
- `ai_rating` field (separate concern from `sentiment`)
