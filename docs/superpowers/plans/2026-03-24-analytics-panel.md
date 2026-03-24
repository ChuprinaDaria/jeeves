# Analytics Panel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the static Analytics node card with a resizable bottom panel containing three Nivo charts (Leads, Sentiment, Escalations) powered by real backend data.

**Architecture:** Backend adds `sentiment` field to `ClientWhatsAppConversation` and 3 new analytics views with Redis cache. Frontend adds a `ResizableLayout` wrapper that splits the page between FlowCanvas and a new `AnalyticsPanel` with Nivo charts. Analytics node card and tab are removed.

**Tech Stack:** Django 5, PostgreSQL, Redis, Celery, React 18, Nivo (@nivo/bar, @nivo/line), Tailwind CSS

**Spec:** `docs/superpowers/specs/2026-03-24-analytics-panel-design.md`

---

### Task 1: Add sentiment field to ClientWhatsAppConversation

**Files:**
- Modify: `p004_ai_nexelin/MASTER/clients/models.py:1490` (after ai_rating field)

- [ ] **Step 1: Add sentiment field**

In `p004_ai_nexelin/MASTER/clients/models.py`, add to `ClientWhatsAppConversation` class, after the `ai_rating` field (~line 1490):

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

Add `SENTIMENT_CHOICES` as a class-level constant before the field definition.

- [ ] **Step 2: Create migration**

Run: `cd p004_ai_nexelin && python manage.py makemigrations clients -n add_sentiment_field`
Expected: New migration file created

- [ ] **Step 3: Commit**

```bash
git add p004_ai_nexelin/MASTER/clients/models.py p004_ai_nexelin/MASTER/clients/migrations/
git commit -m "feat(models): add sentiment field to ClientWhatsAppConversation"
```

---

### Task 2: Update _check_realtime_negative_sentiment to persist sentiment

**Files:**
- Modify: `p004_ai_nexelin/MASTER/clients/views.py:2788-2853`
- Modify: `p004_ai_nexelin/MASTER/clients/views_telegram.py:1502-1551`

**Important context:** The method structure is:
```python
def _check_realtime_negative_sentiment(self, conversation, user_message, logger):
    try:
        ...
        is_negative = any(phrase in message_lower for phrase in negative_phrases)

        if is_negative:                               # line 2839
            conversation.ai_rating = 'negative'       # line 2843
            conversation.rating_timestamp = ...       # line 2844
            conversation.save(update_fields=[...])    # line 2845
            ...email alert...                         # lines 2847-2850

    except Exception as e:                            # line 2852
        logger.warning(...)                           # line 2853
```

The `else` must go BEFORE `except`, at the same indentation level as `if is_negative:` (inside `try`).

- [ ] **Step 1: Update views.py — negative branch**

At line 2843, add `conversation.sentiment = 'negative'` and update the save on line 2845 to include `'sentiment'`:

```python
if is_negative:
    logger.info(f"... Real-time NEGATIVE detected ...")

    conversation.ai_rating = 'negative'
    conversation.sentiment = 'negative'
    conversation.rating_timestamp = timezone.now()
    conversation.save(update_fields=['ai_rating', 'sentiment', 'rating_timestamp', 'updated_at'])

    from MASTER.clients.tasks import close_session_and_send_email
    close_session_and_send_email.delay(conversation.id, force_send=True)
    logger.info(f"... Immediate alert email triggered ...")
```

- [ ] **Step 2: Update views.py — positive branch**

Add `else` block AFTER the `if is_negative:` block closes (after line 2850) but BEFORE `except` (line 2852):

```python
            else:
                positive_phrases = [
                    "thank", "thanks", "great", "excellent", "perfect", "love",
                    "amazing", "wonderful", "happy", "satisfied", "good job",
                    "дякую", "чудово", "відмінно", "прекрасно", "задоволен",
                    "danke", "ausgezeichnet", "perfekt", "wunderbar", "zufrieden",
                    "merci", "parfait", "excellent", "magnifique", "satisfait",
                    "gracias", "excelente", "perfecto", "maravilloso", "satisfecho",
                ]
                is_positive = any(phrase in message_lower for phrase in positive_phrases)
                if is_positive and conversation.sentiment != 'positive':
                    conversation.sentiment = 'positive'
                    conversation.save(update_fields=['sentiment'])

        except Exception as e:
            logger.warning(...)
```

Note the indentation: `else` is at the same level as `if is_negative:` (3 levels deep inside the try block — 12 spaces).

- [ ] **Step 3: Update views_telegram.py**

Apply identical changes to `p004_ai_nexelin/MASTER/clients/views_telegram.py` at `_check_realtime_negative_sentiment` (~line 1502). Same structure: add `sentiment = 'negative'` + update `update_fields` in the negative branch, add `else` with positive detection before `except`.

- [ ] **Step 4: Commit**

```bash
git add p004_ai_nexelin/MASTER/clients/views.py p004_ai_nexelin/MASTER/clients/views_telegram.py
git commit -m "feat(sentiment): persist sentiment in _check_realtime_negative_sentiment"
```

---

### Task 3: Add 3 analytics API views

**Files:**
- Modify: `p004_ai_nexelin/MASTER/clients/views.py` (append views at end, before `ConversationRatingView`)
- Modify: `p004_ai_nexelin/MASTER/clients/urls.py:70` (after Leads section)

- [ ] **Step 1: Add analytics views**

Append these three views to `p004_ai_nexelin/MASTER/clients/views.py`. All imports are inline (following the existing pattern in this file):

```python
class AnalyticsLeadsView(APIView):
    permission_classes = []

    def get(self, request):
        from datetime import timedelta
        from django.db.models import Count
        from django.db.models.functions import TruncDate
        from django.core.cache import cache
        from MASTER.clients.models import Lead

        client = request.client
        period = request.query_params.get('period', '30d')
        if period not in ('7d', '30d', '90d'):
            return Response({'error': 'Invalid period. Use 7d, 30d, or 90d.'}, status=400)

        cache_key = f'analytics:{client.id}:leads:{period}'
        cached = cache.get(cache_key)
        if cached:
            return Response(cached)

        days = int(period.replace('d', ''))
        start_date = timezone.now() - timedelta(days=days)

        data = list(
            Lead.objects.filter(
                client=client,
                created_at__gte=start_date
            ).annotate(
                date=TruncDate('created_at')
            ).values('date').annotate(
                total=Count('id'),
                converted=Count('id', filter=Q(status='converted'))
            ).order_by('date')
        )

        for row in data:
            row['date'] = row['date'].isoformat()

        result = {'period': period, 'data': data}
        cache.set(cache_key, result, 300)
        return Response(result)


class AnalyticsSentimentView(APIView):
    permission_classes = []

    def get(self, request):
        from datetime import timedelta
        from django.db.models import Count
        from django.db.models.functions import TruncDate
        from django.core.cache import cache

        client = request.client
        period = request.query_params.get('period', '30d')
        if period not in ('7d', '30d', '90d'):
            return Response({'error': 'Invalid period. Use 7d, 30d, or 90d.'}, status=400)

        cache_key = f'analytics:{client.id}:sentiment:{period}'
        cached = cache.get(cache_key)
        if cached:
            return Response(cached)

        days = int(period.replace('d', ''))
        start_date = timezone.now() - timedelta(days=days)

        data = list(
            ClientWhatsAppConversation.objects.filter(
                client=client,
                started_at__gte=start_date
            ).annotate(
                date=TruncDate('started_at')
            ).values('date').annotate(
                positive=Count('id', filter=Q(sentiment='positive')),
                negative=Count('id', filter=Q(sentiment='negative')),
                neutral=Count('id', filter=Q(sentiment='neutral'))
            ).order_by('date')
        )

        for row in data:
            row['date'] = row['date'].isoformat()

        result = {'period': period, 'data': data}
        cache.set(cache_key, result, 300)
        return Response(result)


class AnalyticsEscalationsView(APIView):
    permission_classes = []

    def get(self, request):
        from datetime import timedelta
        from django.db.models import Count
        from django.db.models.functions import TruncDate
        from django.core.cache import cache

        client = request.client
        period = request.query_params.get('period', '30d')
        if period not in ('7d', '30d', '90d'):
            return Response({'error': 'Invalid period. Use 7d, 30d, or 90d.'}, status=400)

        cache_key = f'analytics:{client.id}:escalations:{period}'
        cached = cache.get(cache_key)
        if cached:
            return Response(cached)

        days = int(period.replace('d', ''))
        start_date = timezone.now() - timedelta(days=days)

        data = list(
            ClientWhatsAppConversation.objects.filter(
                client=client,
                escalation_started_at__isnull=False,
                escalation_started_at__gte=start_date
            ).annotate(
                date=TruncDate('escalation_started_at')
            ).values('date').annotate(
                total=Count('id'),
                resolved=Count('id', filter=Q(is_waiting_for_manager=False))
            ).order_by('date')
        )

        for row in data:
            row['date'] = row['date'].isoformat()
            row['pending'] = row['total'] - row['resolved']

        result = {'period': period, 'data': data}
        cache.set(cache_key, result, 300)
        return Response(result)
```

Note: `ClientWhatsAppConversation` is already imported at line 28 of views.py. `Q` is already imported at line 13. `timezone` is imported inline in other methods — add `from django.utils import timezone` at the top if needed (check first).

- [ ] **Step 2: Add URL routes**

In `p004_ai_nexelin/MASTER/clients/urls.py`, add after the Leads section (after line 70):

```python
    # Analytics
    path('analytics/leads/', views.AnalyticsLeadsView.as_view(), name='analytics-leads'),
    path('analytics/sentiment/', views.AnalyticsSentimentView.as_view(), name='analytics-sentiment'),
    path('analytics/escalations/', views.AnalyticsEscalationsView.as_view(), name='analytics-escalations'),
```

- [ ] **Step 3: Commit**

```bash
git add p004_ai_nexelin/MASTER/clients/views.py p004_ai_nexelin/MASTER/clients/urls.py
git commit -m "feat(analytics): add leads, sentiment, escalations API endpoints with Redis cache"
```

---

### Task 4: Add backfill Celery task

**Files:**
- Modify: `p004_ai_nexelin/MASTER/clients/tasks.py`

**Note:** This uses keyword matching (not LLM) for backfill — intentional decision to avoid API costs and rate limits for initial population. Real-time sentiment is handled by `_check_realtime_negative_sentiment` going forward.

- [ ] **Step 1: Add backfill task**

Append to `p004_ai_nexelin/MASTER/clients/tasks.py`:

```python
@shared_task
def backfill_conversation_sentiment(dry_run=False, batch_size=50):
    from .models import ClientWhatsAppConversation
    import time

    qs = ClientWhatsAppConversation.objects.filter(
        sentiment='neutral'
    ).exclude(messages=[]).order_by('id')

    total = qs.count()
    updated = 0
    skipped = 0
    errors = 0

    logger.info(f"Backfill sentiment: {total} conversations to process (dry_run={dry_run})")

    for batch_start in range(0, total, batch_size):
        batch = list(qs[batch_start:batch_start + batch_size])

        for conv in batch:
            try:
                messages = conv.messages or []
                if not messages:
                    skipped += 1
                    continue

                last_messages = messages[-10:]
                text = ' '.join(
                    m.get('content', '').lower()
                    for m in last_messages
                    if isinstance(m, dict) and m.get('role') == 'user'
                )

                if not text.strip():
                    skipped += 1
                    continue

                negative_indicators = [
                    "don't like", "not happy", "frustrated", "angry", "terrible",
                    "horrible", "worst", "hate", "disappointed", "useless",
                    "не подобається", "незадоволен", "розчарован",
                    "nicht zufrieden", "enttäuscht", "frustriert",
                ]
                positive_indicators = [
                    "thank", "great", "excellent", "perfect", "love", "amazing",
                    "happy", "satisfied", "good job",
                    "дякую", "чудово", "відмінно",
                    "danke", "ausgezeichnet", "perfekt",
                ]

                sentiment = 'neutral'
                if any(p in text for p in negative_indicators):
                    sentiment = 'negative'
                elif any(p in text for p in positive_indicators):
                    sentiment = 'positive'

                if not dry_run:
                    conv.sentiment = sentiment
                    conv.save(update_fields=['sentiment'])

                if sentiment != 'neutral':
                    updated += 1
                else:
                    skipped += 1

            except Exception as e:
                errors += 1
                logger.error(f"Backfill error for conversation {conv.id}: {e}")

        if batch_start + batch_size < total:
            time.sleep(1)

    logger.info(f"Backfill complete: updated={updated}, skipped={skipped}, errors={errors}")
    return {'updated': updated, 'skipped': skipped, 'errors': errors}
```

- [ ] **Step 2: Commit**

```bash
git add p004_ai_nexelin/MASTER/clients/tasks.py
git commit -m "feat(analytics): add backfill_conversation_sentiment Celery task"
```

---

### Task 5: Install Nivo dependencies

**Files:**
- Modify: `nextlen/package.json`

- [ ] **Step 1: Install**

Run: `cd nextlen && npm install @nivo/bar @nivo/line`

- [ ] **Step 2: Commit**

```bash
git add nextlen/package.json nextlen/package-lock.json
git commit -m "deps: add @nivo/bar and @nivo/line for analytics charts"
```

---

### Task 6: Create frontend analytics API module

**Files:**
- Create: `nextlen/src/api/analytics.js`

- [ ] **Step 1: Create API module**

Pattern: follow `nextlen/src/api/tools.js` (import `api` from `./axios`, export named object).

```javascript
import api from './axios';

export const analyticsAPI = {
  getLeads: (period = '30d') => api.get(`/clients/analytics/leads/?period=${period}`),
  getSentiment: (period = '30d') => api.get(`/clients/analytics/sentiment/?period=${period}`),
  getEscalations: (period = '30d') => api.get(`/clients/analytics/escalations/?period=${period}`),
};
```

- [ ] **Step 2: Commit**

```bash
git add nextlen/src/api/analytics.js
git commit -m "feat(frontend): add analytics API module"
```

---

### Task 7: Create shared chart theme and useAnalyticsData hook

**Files:**
- Create: `nextlen/src/components/analytics/chartTheme.js`
- Create: `nextlen/src/components/analytics/useAnalyticsData.js`

- [ ] **Step 1: Create shared chart theme**

```javascript
const chartTheme = {
  axis: {
    ticks: { text: { fill: '#9ca3af', fontSize: 10 } },
    legend: { text: { fill: '#9ca3af' } },
  },
  grid: { line: { stroke: '#374151', strokeWidth: 1 } },
  tooltip: {
    container: {
      background: '#1f2937',
      color: '#f3f4f6',
      borderRadius: '8px',
      border: '1px solid #4b5563',
      fontSize: '12px',
    },
  },
  crosshair: { line: { stroke: '#6b7280', strokeWidth: 1 } },
};

export default chartTheme;
```

- [ ] **Step 2: Create useAnalyticsData hook**

```javascript
import { useState, useEffect, useCallback } from 'react';
import { analyticsAPI } from '../../api/analytics';

const useAnalyticsData = (period) => {
  const [leads, setLeads] = useState(null);
  const [sentiment, setSentiment] = useState(null);
  const [escalations, setEscalations] = useState(null);
  const [loading, setLoading] = useState(true);
  const [errors, setErrors] = useState({ leads: null, sentiment: null, escalations: null });

  const fetchAll = useCallback(async () => {
    setLoading(true);
    const results = await Promise.allSettled([
      analyticsAPI.getLeads(period),
      analyticsAPI.getSentiment(period),
      analyticsAPI.getEscalations(period),
    ]);

    const newErrors = { leads: null, sentiment: null, escalations: null };

    if (results[0].status === 'fulfilled') {
      setLeads(results[0].value.data.data);
    } else {
      newErrors.leads = true;
    }

    if (results[1].status === 'fulfilled') {
      setSentiment(results[1].value.data.data);
    } else {
      newErrors.sentiment = true;
    }

    if (results[2].status === 'fulfilled') {
      setEscalations(results[2].value.data.data);
    } else {
      newErrors.escalations = true;
    }

    setErrors(newErrors);
    setLoading(false);
  }, [period]);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  return { leads, sentiment, escalations, loading, errors, refetch: fetchAll };
};

export default useAnalyticsData;
```

- [ ] **Step 3: Commit**

```bash
git add nextlen/src/components/analytics/chartTheme.js nextlen/src/components/analytics/useAnalyticsData.js
git commit -m "feat(frontend): add shared chart theme and useAnalyticsData hook"
```

---

### Task 8: Create LeadsChart component

**Files:**
- Create: `nextlen/src/components/analytics/LeadsChart.jsx`

- [ ] **Step 1: Create component**

```jsx
import { ResponsiveBar } from '@nivo/bar';
import chartTheme from './chartTheme';

const LeadsChart = ({ data, error, onRetry }) => {
  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-gray-400 gap-2">
        <span className="text-xs">Failed to load</span>
        <button onClick={onRetry} className="text-xs text-primary-400 hover:text-primary-300">Retry</button>
      </div>
    );
  }

  if (!data || data.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-gray-500 text-xs">No data yet</div>
    );
  }

  const chartData = data.map((d) => ({
    date: d.date.slice(5),
    total: d.total,
    converted: d.converted,
  }));

  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center justify-between mb-1 px-1">
        <span className="text-xs font-medium text-gray-300">Leads & Conversions</span>
        <div className="flex items-center gap-3 text-[10px] text-gray-400">
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-teal-400" /> Leads
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-emerald-500" /> Converted
          </span>
        </div>
      </div>
      <div className="flex-1">
        <ResponsiveBar
          data={chartData}
          keys={['total', 'converted']}
          indexBy="date"
          groupMode="grouped"
          margin={{ top: 10, right: 10, bottom: 24, left: 32 }}
          padding={0.3}
          colors={['#2dd4bf', '#10b981']}
          borderRadius={3}
          enableLabel={false}
          enableGridX={false}
          enableGridY={true}
          axisBottom={{ tickSize: 0, tickPadding: 6 }}
          axisLeft={{ tickSize: 0, tickPadding: 6, tickValues: 4 }}
          theme={chartTheme}
          animate={true}
          motionConfig="gentle"
          defs={[
            {
              id: 'gradientTeal',
              type: 'linearGradient',
              colors: [
                { offset: 0, color: '#2dd4bf', opacity: 1 },
                { offset: 100, color: '#2dd4bf', opacity: 0.4 },
              ],
            },
            {
              id: 'gradientGreen',
              type: 'linearGradient',
              colors: [
                { offset: 0, color: '#10b981', opacity: 1 },
                { offset: 100, color: '#10b981', opacity: 0.4 },
              ],
            },
          ]}
          fill={[
            { match: { id: 'total' }, id: 'gradientTeal' },
            { match: { id: 'converted' }, id: 'gradientGreen' },
          ]}
        />
      </div>
    </div>
  );
};

export default LeadsChart;
```

- [ ] **Step 2: Commit**

```bash
git add nextlen/src/components/analytics/LeadsChart.jsx
git commit -m "feat(frontend): add LeadsChart Nivo component"
```

---

### Task 9: Create SentimentChart component

**Files:**
- Create: `nextlen/src/components/analytics/SentimentChart.jsx`

- [ ] **Step 1: Create component**

```jsx
import { ResponsiveLine } from '@nivo/line';
import chartTheme from './chartTheme';

const SentimentChart = ({ data, error, onRetry }) => {
  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-gray-400 gap-2">
        <span className="text-xs">Failed to load</span>
        <button onClick={onRetry} className="text-xs text-primary-400 hover:text-primary-300">Retry</button>
      </div>
    );
  }

  if (!data || data.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-gray-500 text-xs">No data yet</div>
    );
  }

  const lineData = [
    {
      id: 'Positive',
      color: '#10b981',
      data: data.map((d) => ({ x: d.date.slice(5), y: d.positive })),
    },
    {
      id: 'Negative',
      color: '#ef4444',
      data: data.map((d) => ({ x: d.date.slice(5), y: d.negative })),
    },
    {
      id: 'Neutral',
      color: '#f59e0b',
      data: data.map((d) => ({ x: d.date.slice(5), y: d.neutral })),
    },
  ];

  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center justify-between mb-1 px-1">
        <span className="text-xs font-medium text-gray-300">Customer Sentiment</span>
        <div className="flex items-center gap-3 text-[10px] text-gray-400">
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-emerald-500" /> Positive
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-red-500" /> Negative
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-amber-500" /> Neutral
          </span>
        </div>
      </div>
      <div className="flex-1">
        <ResponsiveLine
          data={lineData}
          colors={['#10b981', '#ef4444', '#f59e0b']}
          margin={{ top: 10, right: 10, bottom: 24, left: 32 }}
          xScale={{ type: 'point' }}
          yScale={{ type: 'linear', min: 0, stacked: false }}
          curve="monotoneX"
          enableArea={true}
          areaOpacity={0.15}
          enablePoints={false}
          useMesh={true}
          enableGridX={false}
          enableGridY={true}
          axisBottom={{ tickSize: 0, tickPadding: 6 }}
          axisLeft={{ tickSize: 0, tickPadding: 6, tickValues: 4 }}
          theme={chartTheme}
          animate={true}
          motionConfig="gentle"
          enableSlices="x"
        />
      </div>
    </div>
  );
};

export default SentimentChart;
```

- [ ] **Step 2: Commit**

```bash
git add nextlen/src/components/analytics/SentimentChart.jsx
git commit -m "feat(frontend): add SentimentChart Nivo component"
```

---

### Task 10: Create EscalationsChart component

**Files:**
- Create: `nextlen/src/components/analytics/EscalationsChart.jsx`

- [ ] **Step 1: Create component**

```jsx
import { ResponsiveBar } from '@nivo/bar';
import chartTheme from './chartTheme';

const EscalationsChart = ({ data, error, onRetry }) => {
  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-gray-400 gap-2">
        <span className="text-xs">Failed to load</span>
        <button onClick={onRetry} className="text-xs text-primary-400 hover:text-primary-300">Retry</button>
      </div>
    );
  }

  if (!data || data.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-gray-500 text-xs">No data yet</div>
    );
  }

  const chartData = data.map((d) => ({
    date: d.date.slice(5),
    resolved: d.resolved,
    pending: d.pending,
  }));

  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center justify-between mb-1 px-1">
        <span className="text-xs font-medium text-gray-300">HITL Escalations</span>
        <div className="flex items-center gap-3 text-[10px] text-gray-400">
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-emerald-500" /> Resolved
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-slate-400" /> Pending
          </span>
        </div>
      </div>
      <div className="flex-1">
        <ResponsiveBar
          data={chartData}
          keys={['resolved', 'pending']}
          indexBy="date"
          groupMode="stacked"
          margin={{ top: 10, right: 10, bottom: 24, left: 32 }}
          padding={0.3}
          colors={['#10b981', '#64748b']}
          borderRadius={3}
          enableLabel={false}
          enableGridX={false}
          enableGridY={true}
          axisBottom={{ tickSize: 0, tickPadding: 6 }}
          axisLeft={{ tickSize: 0, tickPadding: 6, tickValues: 4 }}
          theme={chartTheme}
          animate={true}
          motionConfig="gentle"
          defs={[
            {
              id: 'gradientEmerald',
              type: 'linearGradient',
              colors: [
                { offset: 0, color: '#10b981', opacity: 1 },
                { offset: 100, color: '#10b981', opacity: 0.4 },
              ],
            },
            {
              id: 'gradientSlate',
              type: 'linearGradient',
              colors: [
                { offset: 0, color: '#64748b', opacity: 1 },
                { offset: 100, color: '#64748b', opacity: 0.4 },
              ],
            },
          ]}
          fill={[
            { match: { id: 'resolved' }, id: 'gradientEmerald' },
            { match: { id: 'pending' }, id: 'gradientSlate' },
          ]}
        />
      </div>
    </div>
  );
};

export default EscalationsChart;
```

- [ ] **Step 2: Commit**

```bash
git add nextlen/src/components/analytics/EscalationsChart.jsx
git commit -m "feat(frontend): add EscalationsChart Nivo component"
```

---

### Task 11: Create AnalyticsPanel component

**Files:**
- Create: `nextlen/src/components/analytics/AnalyticsPanel.jsx`

- [ ] **Step 1: Create component**

```jsx
import { useState, useMemo } from 'react';
import { ChevronDown, BarChart3 } from 'lucide-react';
import useAnalyticsData from './useAnalyticsData';
import LeadsChart from './LeadsChart';
import SentimentChart from './SentimentChart';
import EscalationsChart from './EscalationsChart';

const PERIODS = ['7d', '30d', '90d'];

const SkeletonChart = () => {
  const heights = useMemo(
    () => Array.from({ length: 7 }, () => 30 + Math.random() * 50),
    []
  );
  return (
    <div className="flex items-end gap-1 h-full p-4">
      {heights.map((h, i) => (
        <div
          key={i}
          className="flex-1 bg-gray-700/50 rounded animate-pulse"
          style={{ height: `${h}%` }}
        />
      ))}
    </div>
  );
};

const AnalyticsPanel = ({ collapsed, onToggleCollapse }) => {
  const [period, setPeriod] = useState('30d');
  const { leads, sentiment, escalations, loading, errors, refetch } = useAnalyticsData(period);

  if (collapsed) return null;

  return (
    <div className="bg-gray-900/95 border-t border-gray-700/50 flex flex-col h-full overflow-hidden">
      <div className="flex items-center justify-between px-4 py-2 flex-shrink-0">
        <div className="flex items-center gap-2">
          <BarChart3 className="w-4 h-4 text-primary-400" />
          <span className="text-sm font-medium text-gray-200">Real-time Monitoring & Analytics</span>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex bg-gray-800 rounded-lg p-0.5">
            {PERIODS.map((p) => (
              <button
                key={p}
                onClick={() => setPeriod(p)}
                className={`px-2.5 py-1 text-xs rounded-md transition-colors ${
                  period === p
                    ? 'bg-primary-600 text-white'
                    : 'text-gray-400 hover:text-gray-200'
                }`}
              >
                {p}
              </button>
            ))}
          </div>
          <button onClick={onToggleCollapse} className="text-gray-400 hover:text-gray-200">
            <ChevronDown className="w-4 h-4" />
          </button>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-4 px-4 pb-4 flex-1 min-h-0">
        <div className="bg-gray-800/50 rounded-lg p-3">
          {loading ? <SkeletonChart /> : <LeadsChart data={leads} error={errors.leads} onRetry={refetch} />}
        </div>
        <div className="bg-gray-800/50 rounded-lg p-3">
          {loading ? <SkeletonChart /> : <SentimentChart data={sentiment} error={errors.sentiment} onRetry={refetch} />}
        </div>
        <div className="bg-gray-800/50 rounded-lg p-3">
          {loading ? <SkeletonChart /> : <EscalationsChart data={escalations} error={errors.escalations} onRetry={refetch} />}
        </div>
      </div>
    </div>
  );
};

export default AnalyticsPanel;
```

- [ ] **Step 2: Commit**

```bash
git add nextlen/src/components/analytics/AnalyticsPanel.jsx
git commit -m "feat(frontend): add AnalyticsPanel container with period selector and skeleton loading"
```

---

### Task 12: Create ResizableLayout component

**Files:**
- Create: `nextlen/src/components/layout/ResizableLayout.jsx`

- [ ] **Step 1: Create component**

```jsx
import { useState, useRef, useCallback, useEffect } from 'react';
import { ChevronUp } from 'lucide-react';

const LS_KEY = 'flow-analytics-split';
const DEFAULT_RATIO = 0.65;
const MIN_TOP = 300;
const MIN_BOTTOM = 180;

const ResizableLayout = ({ top, bottom }) => {
  const containerRef = useRef(null);
  const [ratio, setRatio] = useState(() => {
    const saved = localStorage.getItem(LS_KEY);
    return saved ? parseFloat(saved) : DEFAULT_RATIO;
  });
  const [collapsed, setCollapsed] = useState(false);
  const [isDragging, setIsDragging] = useState(false);

  const clampRatio = useCallback((r) => {
    const el = containerRef.current;
    if (!el) return r;
    const h = el.offsetHeight;
    if (h === 0) return r;
    const minTopRatio = MIN_TOP / h;
    const maxTopRatio = (h - MIN_BOTTOM) / h;
    return Math.max(minTopRatio, Math.min(maxTopRatio, r));
  }, []);

  useEffect(() => {
    setRatio((prev) => clampRatio(prev));
  }, [clampRatio]);

  const handlePointerDown = useCallback((e) => {
    e.preventDefault();
    setIsDragging(true);
    const el = containerRef.current;
    if (!el) return;

    const onMove = (ev) => {
      const rect = el.getBoundingClientRect();
      const newRatio = (ev.clientY - rect.top) / rect.height;
      setRatio(clampRatio(newRatio));
    };

    const onUp = () => {
      setIsDragging(false);
      document.removeEventListener('pointermove', onMove);
      document.removeEventListener('pointerup', onUp);
      setRatio((r) => {
        localStorage.setItem(LS_KEY, String(r));
        return r;
      });
    };

    document.addEventListener('pointermove', onMove);
    document.addEventListener('pointerup', onUp);
  }, [clampRatio]);

  const topStyle = collapsed ? { flex: 1 } : { height: `${ratio * 100}%` };

  return (
    <div
      ref={containerRef}
      className="flex flex-col h-full"
      style={{ cursor: isDragging ? 'row-resize' : undefined }}
    >
      <div className="overflow-hidden" style={topStyle}>
        {top}
      </div>

      <div
        className={`flex-shrink-0 flex items-center justify-center group ${
          isDragging ? 'bg-primary-600/30' : 'hover:bg-gray-700/50'
        } transition-colors`}
        style={{ height: '6px', cursor: 'row-resize' }}
        onPointerDown={handlePointerDown}
        onDoubleClick={() => setCollapsed((c) => !c)}
      >
        <div className={`w-12 h-1 rounded-full ${
          isDragging ? 'bg-primary-400' : 'bg-gray-600 group-hover:bg-gray-400'
        } transition-colors`} />
      </div>

      {collapsed ? (
        <button
          onClick={() => setCollapsed(false)}
          className="flex items-center justify-center gap-1 py-1 text-xs text-gray-400 hover:text-gray-200 bg-gray-900/95 border-t border-gray-700/50"
        >
          <ChevronUp className="w-3 h-3" /> Analytics
        </button>
      ) : (
        <div className="overflow-hidden" style={{ height: `${(1 - ratio) * 100}%` }}>
          {typeof bottom === 'function'
            ? bottom({ collapsed, onToggleCollapse: () => setCollapsed(true) })
            : bottom}
        </div>
      )}
    </div>
  );
};

export default ResizableLayout;
```

- [ ] **Step 2: Commit**

```bash
git add nextlen/src/components/layout/ResizableLayout.jsx
git commit -m "feat(frontend): add ResizableLayout with drag handle and collapse"
```

---

### Task 13: Integrate into ToolsPage

**Files:**
- Modify: `nextlen/src/pages/ToolsPage.jsx:1-267`

- [ ] **Step 1: Add imports**

At the top of `nextlen/src/pages/ToolsPage.jsx` (after existing imports, ~line 10), add:

```javascript
import ResizableLayout from '../components/layout/ResizableLayout';
import AnalyticsPanel from '../components/analytics/AnalyticsPanel';
```

- [ ] **Step 2: Update layout**

In the return block (line ~197), change:

**Before:**
```jsx
<div className="space-y-6 max-w-full overflow-x-hidden">
  {/* Header */}
  <div className="flex items-center justify-between">...</div>
  {/* ToolCatalogStrip */}
  {error ? (...) : (<ToolCatalogStrip ... />)}
  {/* FlowCanvas */}
  <FlowCanvas ... />
  {/* Popover + Toast */}
</div>
```

**After:**
```jsx
<div className="flex flex-col max-w-full overflow-x-hidden h-[calc(100vh-4rem)]">
  {/* Header */}
  <div className="flex items-center justify-between flex-shrink-0 pb-2">...</div>

  {/* ToolCatalogStrip */}
  <div className="flex-shrink-0">
    {error ? (...) : (<ToolCatalogStrip ... />)}
  </div>

  {/* Canvas + Analytics */}
  <div className="flex-1 min-h-0 mt-2">
    <ResizableLayout
      top={
        <FlowCanvas
          tools={tools}
          onToolClick={handleCanvasToolClick}
          highlightedTool={highlightedTool}
          onToolDrop={handleToolDrop}
          onDisconnect={handleDisconnect}
          onConnect={handleConnect}
          onMiddlewareRemove={handleMiddlewareRemove}
          onMiddlewareAttach={handleMiddlewareAttach}
        />
      }
      bottom={({ collapsed, onToggleCollapse }) => (
        <AnalyticsPanel collapsed={collapsed} onToggleCollapse={onToggleCollapse} />
      )}
    />
  </div>

  {/* Popover */}
  {popover && (<ToolPopover ... />)}

  {/* Toast */}
  <FlowToast ... />
</div>
```

Key changes:
- Outer div: `space-y-6` → `flex flex-col h-[calc(100vh-4rem)]`
- Header and strip wrapped with `flex-shrink-0`
- Canvas + Analytics in `flex-1 min-h-0` with `ResizableLayout`
- Popover and Toast stay outside (portals/absolute)

- [ ] **Step 3: Commit**

```bash
git add nextlen/src/pages/ToolsPage.jsx
git commit -m "feat(frontend): integrate ResizableLayout and AnalyticsPanel into ToolsPage"
```

---

### Task 14: Remove Analytics node card and tab

**Files:**
- Delete: `nextlen/src/components/tools/richcards/AnalyticsCard.jsx`
- Modify: `nextlen/src/components/tools/richcards/RichCardWrapper.jsx:5,10`
- Modify: `nextlen/src/components/tools/ToolCatalogStrip.jsx:25,36,256`

- [ ] **Step 1: Clean RichCardWrapper**

In `nextlen/src/components/tools/richcards/RichCardWrapper.jsx`:
- Remove line 5: `const AnalyticsCard = lazy(() => import('./AnalyticsCard'));`
- Remove line 10: `'analytics': AnalyticsCard,`

- [ ] **Step 2: Clean ToolCatalogStrip**

In `nextlen/src/components/tools/ToolCatalogStrip.jsx`:
- Remove line 25: `'analytics': 'analytics',`
- Remove line 36: `{ id: 'analytics', labelKey: 'tools.flow.tabAnalytics' },`
- Remove `|| group === 'analytics'` from line 256: `if (group === 'data' || group === 'logic' || group === 'analytics')` → `if (group === 'data' || group === 'logic')`

- [ ] **Step 3: Delete AnalyticsCard**

Delete `nextlen/src/components/tools/richcards/AnalyticsCard.jsx`

- [ ] **Step 4: Commit**

```bash
git rm nextlen/src/components/tools/richcards/AnalyticsCard.jsx
git add nextlen/src/components/tools/richcards/RichCardWrapper.jsx nextlen/src/components/tools/ToolCatalogStrip.jsx
git commit -m "refactor: remove Analytics node card, tab, and group from catalog strip"
```

---

### Task 15: Apply migration and verify

- [ ] **Step 1: Apply migration**

Run: `cd p004_ai_nexelin && python manage.py migrate`
Expected: Migration applied successfully

- [ ] **Step 2: Verify frontend builds**

Run: `cd nextlen && npm run build`
Expected: Build succeeds without errors

- [ ] **Step 3: Manual verification checklist**

Verify in browser:
- [ ] Analytics panel appears below the canvas with dark background
- [ ] Drag handle resizes canvas/panel ratio
- [ ] Double-click on handle collapses/expands panel
- [ ] Collapsed state shows "Analytics" button to expand
- [ ] Period selector switches between 7d/30d/90d and refetches data
- [ ] Charts render with data (or show "No data yet" for empty data)
- [ ] Loading shows skeleton pulse bars
- [ ] Error state shows "Failed to load" with retry button per chart
- [ ] Canvas: nodes can be dragged
- [ ] Canvas: edges can be drawn and selected
- [ ] Canvas: skill middleware on edges still responds
- [ ] Canvas: zoom and pan work
- [ ] Analytics tab is gone from catalog strip
- [ ] Analytics node card is gone from canvas
- [ ] Split ratio persists after page reload
