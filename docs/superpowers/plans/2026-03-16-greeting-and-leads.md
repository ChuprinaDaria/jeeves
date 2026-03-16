# Greeting Message + Leads Module Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a universal greeting message setting and a full Leads module with LLM-powered data extraction across all messenger channels.

**Architecture:** Two independent features sharing the same Client model. Greeting is a simple TextField shown on first contact in all channels. Leads is a new model + API + frontend page with LLM extraction via tagged JSON blocks in responses, parsed post-generation.

**Tech Stack:** Django 5.x, DRF, React 18, Tailwind CSS, Celery, PostgreSQL

---

## Chunk 1: Greeting Message

### Task 1: Backend — greeting_message field on Client model

**Files:**
- Modify: `p004_ai_nexelin/MASTER/clients/models.py` (near line 190, after `telegram_welcome_message`)
- Create: `p004_ai_nexelin/MASTER/clients/migrations/0048_client_greeting_message.py` (auto-generated)

- [ ] **Step 1: Add greeting_message field to Client model**

In `models.py`, after `telegram_welcome_message` (line ~193), add:

```python
greeting_message = models.TextField(
    blank=True,
    default='',
    help_text="Universal greeting message shown to customers on first contact in all channels (web, Telegram, WhatsApp). Displayed exactly as written."
)
```

- [ ] **Step 2: Generate migration**

Run: `cd /home/dchuprina/nexelin_web && python p004_ai_nexelin/manage.py makemigrations clients -n client_greeting_message`

- [ ] **Step 3: Apply migration**

Run: `cd /home/dchuprina/nexelin_web && python p004_ai_nexelin/manage.py migrate clients`

- [ ] **Step 4: Commit**

```bash
git add p004_ai_nexelin/MASTER/clients/models.py p004_ai_nexelin/MASTER/clients/migrations/0048_client_greeting_message.py
git commit -m "feat: add greeting_message field to Client model"
```

### Task 2: Backend — expose greeting_message in API

**Files:**
- Modify: `p004_ai_nexelin/MASTER/clients/serializers.py:27-69` (add to ClientSerializer fields)
- Modify: `p004_ai_nexelin/MASTER/clients/views.py:1299-1343` (add to ClientEmailSMTPConfigView GET/PATCH)
- Modify: `p004_ai_nexelin/MASTER/clients/admin.py:74-77` (add to Basic Info fieldset)

- [ ] **Step 1: Add greeting_message to ClientSerializer**

In `serializers.py`, add `'greeting_message'` to the `fields` list in `ClientSerializer.Meta` (after `'custom_system_prompt'`, around line 44):

```python
'greeting_message',
```

- [ ] **Step 2: Add greeting_message to ClientEmailSMTPConfigView**

In `views.py`, `ClientEmailSMTPConfigView.get()` (line ~1299), add to the `data` dict:

```python
'greeting_message': getattr(client, 'greeting_message', ''),
```

In `_update()` method (line ~1331), add `'greeting_message'` to the `updatable` set:

```python
'greeting_message',
```

- [ ] **Step 3: Add greeting_message to admin fieldset**

In `admin.py`, add `'greeting_message'` to the `'Basic Info'` fieldset `fields` tuple (line ~76):

```python
('Basic Info', {
    'fields': ('user', 'tag', 'webchat_domain', 'description', 'specialization', 'company_name', 'is_active', 'client_type', 'greeting_message')
}),
```

- [ ] **Step 4: Commit**

```bash
git add p004_ai_nexelin/MASTER/clients/serializers.py p004_ai_nexelin/MASTER/clients/views.py p004_ai_nexelin/MASTER/clients/admin.py
git commit -m "feat: expose greeting_message in API, serializer, and admin"
```

### Task 3: Frontend — greeting_message in SettingsPage

**Files:**
- Modify: `nextlen/src/pages/SettingsPage.jsx`
- Modify: `nextlen/src/locales/en/translation.json` (and other locale files)

- [ ] **Step 1: Add state and load/save logic in SettingsPage.jsx**

Add state variable after `notificationLanguage` state (line ~23):

```jsx
const [greetingMessage, setGreetingMessage] = useState('');
```

In `loadReportSettings()` (line ~74), add after setting `notificationLanguage`:

```jsx
setGreetingMessage(res.data?.greeting_message || '');
```

In `saveReportSettings()` (line ~217), add `greeting_message` to the PATCH payload:

```jsx
await api.patch('/clients/email-smtp/config/', {
  email_report_enabled: reportEnabled,
  email_report_recipients: reportRecipients,
  notification_language: notificationLanguage,
  greeting_message: greetingMessage,
});
```

- [ ] **Step 2: Add Greeting Message UI section**

Insert a new card section **before** the Report Settings Section (before line ~361). Place it after the Logo Upload section:

```jsx
{/* Greeting Message Section */}
<div className="max-w-2xl">
  <div className="card">
    <div className="mb-6">
      <h3 className="text-xl font-semibold mb-2 text-gray-900 dark:text-gray-100">
        {t('settings.greetingTitle') || 'Greeting Message'}
      </h3>
      <p className="text-sm text-gray-600 dark:text-gray-400 leading-relaxed">
        {t('settings.greetingDescription') || 'This message is shown to customers when they first open the chat or contact you via Telegram/WhatsApp. It will be displayed exactly as written.'}
      </p>
    </div>
    <div className="space-y-4">
      <textarea
        value={greetingMessage}
        onChange={(e) => setGreetingMessage(e.target.value)}
        placeholder={t('settings.greetingPlaceholder') || 'Hello! How can I help you today?'}
        className="input w-full h-24 resize-y"
        maxLength={500}
      />
      <div className="flex items-center justify-between">
        <span className="text-xs text-gray-500 dark:text-gray-400">
          {greetingMessage.length}/500
        </span>
        <button
          onClick={saveReportSettings}
          disabled={reportSaving}
          className="btn-primary flex items-center justify-center gap-2"
        >
          {reportSaving ? (
            <>
              <Loader2 className="animate-spin" size={18} />
              {t('common.loading') || 'Saving...'}
            </>
          ) : (
            t('common.save') || 'Save'
          )}
        </button>
      </div>
    </div>
  </div>
</div>
```

- [ ] **Step 3: Add translations**

In `nextlen/src/locales/en/translation.json`, add to the `"settings"` object:

```json
"greetingTitle": "Greeting Message",
"greetingDescription": "This message is shown to customers when they first open the chat or contact you via Telegram/WhatsApp. It will be displayed exactly as written.",
"greetingPlaceholder": "Hello! How can I help you today?"
```

Add corresponding translations to other locale files (de, fr, es, it, nl, da).

- [ ] **Step 4: Commit**

```bash
git add nextlen/src/pages/SettingsPage.jsx nextlen/src/locales/*/translation.json
git commit -m "feat: add Greeting Message section to Settings page"
```

### Task 4: Greeting in Web Chat

**Files:**
- Modify: `nextlen/src/pages/WebChatPage.jsx` (line ~74-90, in `applyBranding`)

- [ ] **Step 1: Show greeting as first message in WebChatPage**

In `WebChatPage.jsx`, in the `applyBranding` function (around line 74), after loading client data and before `initializeConversation()` call, add greeting message display:

```jsx
const applyBranding = async () => {
  try {
    const { data } = await clientAPI.getMe();
    updateBrandingFromClient(data, { context: 'webchat' });
    if (data.logo_url || data.logo) {
      setClientLogo(data.logo_url || data.logo);
    }
    if (data.company_name || data.user) {
      setClientName(data.company_name || data.user);
    }
    // Show greeting message as first assistant message
    if (data.greeting_message) {
      setMessages([{
        id: 'greeting',
        role: 'assistant',
        content: data.greeting_message,
        timestamp: new Date().toISOString(),
      }]);
    }
  } catch (e) {
    document.title = 'AI Chat Assistant';
  }
};
```

- [ ] **Step 2: Commit**

```bash
git add nextlen/src/pages/WebChatPage.jsx
git commit -m "feat: show greeting message in web chat on first open"
```

### Task 5: Greeting in Telegram

**Files:**
- Modify: `p004_ai_nexelin/MASTER/clients/views_telegram.py` (line ~1385-1402, `_generate_welcome_message`)

- [ ] **Step 1: Update _generate_welcome_message to use greeting_message**

In `views_telegram.py`, modify `_generate_welcome_message` method (line ~1385). Change priority to check `greeting_message` first (universal), then `telegram_welcome_message` (Telegram-specific), then fallback:

```python
def _generate_welcome_message(self, client, first_name):
    """
    Генерує привітальне повідомлення для Telegram бота.

    Пріоритет:
    1. Універсальне привітання з greeting_message (якщо налаштовано)
    2. Telegram-specific повідомлення з telegram_welcome_message (якщо налаштовано)
    3. Fallback: базове привітання з назвою компанії
    """
    try:
        # 1. Перевіряємо універсальне привітання
        universal_greeting = getattr(client, 'greeting_message', '') or ''
        if universal_greeting.strip():
            greeting_text = universal_greeting.strip()
            if '{name}' in greeting_text:
                greeting_text = greeting_text.replace('{name}', first_name or '')
            greeting_text = ' '.join(greeting_text.split())
            logger.info(f"Using universal greeting_message for client: {client.company_name}")
            return greeting_text

        # 2. Перевіряємо чи є кастомне привітання для Telegram
        custom_message = getattr(client, 'telegram_welcome_message', '') or ''
        if custom_message.strip():
            welcome_text = custom_message.strip()
            if '{name}' in welcome_text:
                welcome_text = welcome_text.replace('{name}', first_name or '')
            welcome_text = ' '.join(welcome_text.split())
            logger.info(f"Using telegram_welcome_message for client: {client.company_name}")
            return welcome_text
```

(Keep the existing fallback logic after this.)

- [ ] **Step 2: Commit**

```bash
git add p004_ai_nexelin/MASTER/clients/views_telegram.py
git commit -m "feat: use universal greeting_message in Telegram welcome"
```

### Task 6: Greeting in WhatsApp (Meta API)

**Files:**
- Modify: `p004_ai_nexelin/MASTER/clients/views_meta_whatsapp.py` (where new conversations are created)

- [ ] **Step 1: Find the new conversation creation in WhatsApp webhook and add greeting**

In `views_meta_whatsapp.py`, find where a new conversation is created for a first-time WhatsApp contact. After creating the conversation, if `client.greeting_message` is set, send it as the first response before the LLM-generated response. This should be done by prepending the greeting to the conversation messages:

```python
# After creating new conversation for first-time WhatsApp contact:
greeting = getattr(client, 'greeting_message', '') or ''
if greeting.strip() and created:  # Only on first contact
    # Send greeting via WhatsApp API
    self._send_whatsapp_message(client, sender_phone, greeting.strip())
    # Add to conversation messages
    conversation.messages.append({
        'role': 'assistant',
        'content': greeting.strip(),
        'timestamp': timezone.now().isoformat()
    })
    conversation.total_messages = len(conversation.messages)
    conversation.save(update_fields=['messages', 'total_messages'])
```

- [ ] **Step 2: Commit**

```bash
git add p004_ai_nexelin/MASTER/clients/views_meta_whatsapp.py
git commit -m "feat: send universal greeting_message on first WhatsApp contact"
```

---

## Chunk 2: Leads Module — Backend

### Task 7: Lead model

**Files:**
- Modify: `p004_ai_nexelin/MASTER/clients/models.py` (add Lead model at end, add `leads_enabled` to Client)
- Create: `p004_ai_nexelin/MASTER/clients/migrations/0049_lead_and_leads_enabled.py` (auto-generated)

- [ ] **Step 1: Add leads_enabled to Client model**

In `models.py`, add after `pixel_dashboard_enabled` field (or near other feature toggles):

```python
leads_enabled = models.BooleanField(
    default=False,
    help_text="Enable lead collection from messenger conversations. LLM will extract contact data and interest score."
)
```

- [ ] **Step 2: Add Lead model**

At the end of `models.py`, add:

```python
class Lead(models.Model):
    """Lead collected from messenger conversations via LLM extraction."""

    STATUS_NEW = 'new'
    STATUS_CONTACTED = 'contacted'
    STATUS_CONVERTED = 'converted'
    STATUS_LOST = 'lost'
    STATUS_CHOICES = [
        (STATUS_NEW, 'New'),
        (STATUS_CONTACTED, 'Contacted'),
        (STATUS_CONVERTED, 'Converted'),
        (STATUS_LOST, 'Lost'),
    ]

    SOURCE_WEB = 'web'
    SOURCE_TELEGRAM = 'telegram'
    SOURCE_WHATSAPP = 'whatsapp'
    SOURCE_CHOICES = [
        (SOURCE_WEB, 'Web Chat'),
        (SOURCE_TELEGRAM, 'Telegram'),
        (SOURCE_WHATSAPP, 'WhatsApp'),
    ]

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='leads')
    conversation = models.ForeignKey(
        'ClientWhatsAppConversation',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='leads'
    )

    name = models.CharField(max_length=255, blank=True, default='')
    email = models.EmailField(blank=True, default='')
    phone = models.CharField(max_length=50, blank=True, default='')
    request_summary = models.TextField(blank=True, default='')

    interest_score = models.IntegerField(
        default=3,
        help_text="Interest level 1-5, determined by LLM based on conversation context"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_NEW,
    )
    source = models.CharField(
        max_length=20,
        choices=SOURCE_CHOICES,
        default=SOURCE_WEB,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['client', '-created_at']),
            models.Index(fields=['client', 'status']),
        ]

    def __str__(self):
        return f"Lead: {self.name or self.email or self.phone or 'Unknown'} ({self.get_status_display()})"
```

- [ ] **Step 3: Generate and apply migration**

Run:
```bash
cd /home/dchuprina/nexelin_web && python p004_ai_nexelin/manage.py makemigrations clients -n lead_and_leads_enabled
cd /home/dchuprina/nexelin_web && python p004_ai_nexelin/manage.py migrate clients
```

- [ ] **Step 4: Commit**

```bash
git add p004_ai_nexelin/MASTER/clients/models.py p004_ai_nexelin/MASTER/clients/migrations/0049_lead_and_leads_enabled.py
git commit -m "feat: add Lead model and leads_enabled field"
```

### Task 8: Lead admin

**Files:**
- Modify: `p004_ai_nexelin/MASTER/clients/admin.py`

- [ ] **Step 1: Add leads_enabled to ClientAdmin**

In `admin.py`, add `'leads_enabled'` to `list_display` (after `'telephony_enabled'`, line ~46).

Add `'leads_enabled'` to `list_filter` (line ~56).

Add new fieldset after Telephony section:

```python
(
    'Leads Collection',
    {
        'fields': ('leads_enabled',),
        'classes': ('collapse',),
        'description': 'Enable AI-powered lead collection from all messenger channels. LLM will extract contact data and interest score from conversations.',
    },
),
```

- [ ] **Step 2: Register LeadAdmin**

Add import of `Lead` model at top, then register:

```python
@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ['name', 'email', 'phone', 'source', 'interest_score', 'status', 'client', 'created_at']
    list_filter = ['status', 'source', 'interest_score', 'client']
    search_fields = ['name', 'email', 'phone', 'request_summary']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']
    raw_id_fields = ['client', 'conversation']
```

- [ ] **Step 3: Commit**

```bash
git add p004_ai_nexelin/MASTER/clients/admin.py
git commit -m "feat: add Lead to Django admin with filters"
```

### Task 9: Lead API endpoints

**Files:**
- Create: `p004_ai_nexelin/MASTER/clients/views_leads.py`
- Modify: `p004_ai_nexelin/MASTER/clients/urls.py`

- [ ] **Step 1: Create views_leads.py**

```python
import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, serializers
from django.db.models import Q

from MASTER.clients.models import Lead
from MASTER.clients.views import get_client_from_request

logger = logging.getLogger(__name__)


class LeadSerializer(serializers.ModelSerializer):
    conversation_id = serializers.IntegerField(source='conversation.id', read_only=True, default=None)

    class Meta:
        model = Lead
        fields = [
            'id', 'name', 'email', 'phone', 'request_summary',
            'interest_score', 'status', 'source',
            'conversation_id', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'conversation_id', 'source']


class LeadListView(APIView):
    """List leads for client. Supports filtering by status, source, interest_score."""
    permission_classes = []

    def get(self, request):
        client = get_client_from_request(request)
        if not client:
            return Response({'error': 'Client not found'}, status=401)

        if not getattr(client, 'leads_enabled', False):
            return Response({'error': 'Leads module is not enabled'}, status=403)

        leads = Lead.objects.filter(client=client)

        # Filters
        status_filter = request.GET.get('status')
        if status_filter:
            leads = leads.filter(status=status_filter)

        source_filter = request.GET.get('source')
        if source_filter:
            leads = leads.filter(source=source_filter)

        min_interest = request.GET.get('min_interest')
        if min_interest:
            leads = leads.filter(interest_score__gte=int(min_interest))

        search = request.GET.get('search')
        if search:
            leads = leads.filter(
                Q(name__icontains=search) |
                Q(email__icontains=search) |
                Q(phone__icontains=search) |
                Q(request_summary__icontains=search)
            )

        # Pagination
        page = int(request.GET.get('page', 1))
        per_page = min(int(request.GET.get('per_page', 25)), 100)
        total = leads.count()
        offset = (page - 1) * per_page

        leads_page = leads[offset:offset + per_page]
        serializer = LeadSerializer(leads_page, many=True)

        return Response({
            'results': serializer.data,
            'total': total,
            'page': page,
            'per_page': per_page,
        })


class LeadDetailView(APIView):
    """Get/Update/Delete a specific lead."""
    permission_classes = []

    def get(self, request, lead_id):
        client = get_client_from_request(request)
        if not client:
            return Response({'error': 'Client not found'}, status=401)

        try:
            lead = Lead.objects.get(id=lead_id, client=client)
        except Lead.DoesNotExist:
            return Response({'error': 'Lead not found'}, status=404)

        return Response(LeadSerializer(lead).data)

    def patch(self, request, lead_id):
        client = get_client_from_request(request)
        if not client:
            return Response({'error': 'Client not found'}, status=401)

        try:
            lead = Lead.objects.get(id=lead_id, client=client)
        except Lead.DoesNotExist:
            return Response({'error': 'Lead not found'}, status=404)

        updatable = {'name', 'email', 'phone', 'request_summary', 'interest_score', 'status'}
        data = request.data or {}

        for key, val in data.items():
            if key in updatable:
                if key == 'interest_score':
                    val = max(1, min(5, int(val)))
                setattr(lead, key, val)

        lead.save()
        return Response(LeadSerializer(lead).data)

    def delete(self, request, lead_id):
        client = get_client_from_request(request)
        if not client:
            return Response({'error': 'Client not found'}, status=401)

        try:
            lead = Lead.objects.get(id=lead_id, client=client)
        except Lead.DoesNotExist:
            return Response({'error': 'Lead not found'}, status=404)

        lead.delete()
        return Response({'success': True}, status=204)
```

- [ ] **Step 2: Register URLs in urls.py**

In `urls.py`, add import:

```python
from .views_leads import LeadListView, LeadDetailView
```

Add URL patterns (before the router include line ~88):

```python
# Leads
path('leads/', LeadListView.as_view(), name='lead-list'),
path('leads/<int:lead_id>/', LeadDetailView.as_view(), name='lead-detail'),
```

- [ ] **Step 3: Add leads_enabled to ClientSerializer and ClientEmailSMTPConfigView**

In `serializers.py`, add `'leads_enabled'` to `ClientSerializer.Meta.fields`.

In `views.py`, `ClientEmailSMTPConfigView.get()`, add:
```python
'leads_enabled': getattr(client, 'leads_enabled', False),
```

- [ ] **Step 4: Commit**

```bash
git add p004_ai_nexelin/MASTER/clients/views_leads.py p004_ai_nexelin/MASTER/clients/urls.py p004_ai_nexelin/MASTER/clients/serializers.py p004_ai_nexelin/MASTER/clients/views.py
git commit -m "feat: add Lead API endpoints (list, detail, update, delete)"
```

---

## Chunk 3: Leads Module — LLM Integration

### Task 10: Lead extraction service

**Files:**
- Create: `p004_ai_nexelin/MASTER/clients/services/lead_extraction.py`

- [ ] **Step 1: Create lead_extraction.py**

```python
"""
Lead extraction service — parses LLM responses for lead data
and creates/updates Lead records.
"""
import json
import re
import logging

from MASTER.clients.models import Lead, Client, ClientWhatsAppConversation

logger = logging.getLogger(__name__)

LEAD_DATA_PATTERN = re.compile(r'\[LEAD_DATA\](.*?)\[/LEAD_DATA\]', re.DOTALL)


def extract_lead_data_from_response(response_text: str) -> dict | None:
    """
    Parse [LEAD_DATA]{...}[/LEAD_DATA] block from LLM response.
    Returns parsed dict or None if no lead data found.
    """
    match = LEAD_DATA_PATTERN.search(response_text)
    if not match:
        return None

    try:
        data = json.loads(match.group(1).strip())
        return data
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning(f"Failed to parse LEAD_DATA JSON: {e}")
        return None


def clean_response(response_text: str) -> str:
    """Remove [LEAD_DATA] block from response before sending to customer."""
    return LEAD_DATA_PATTERN.sub('', response_text).strip()


def save_lead_from_extraction(
    client: Client,
    conversation: ClientWhatsAppConversation,
    lead_data: dict,
    source: str = 'web',
) -> Lead | None:
    """
    Create or update Lead from extracted data.
    Updates existing lead for same conversation, creates new otherwise.
    """
    if not lead_data:
        return None

    # Find existing lead for this conversation
    lead, created = Lead.objects.get_or_create(
        client=client,
        conversation=conversation,
        defaults={
            'source': source,
        }
    )

    # Update fields if provided (don't overwrite with empty values)
    if lead_data.get('name'):
        lead.name = lead_data['name'][:255]
    if lead_data.get('email'):
        lead.email = lead_data['email'][:254]
    if lead_data.get('phone'):
        lead.phone = lead_data['phone'][:50]
    if lead_data.get('request_summary'):
        lead.request_summary = lead_data['request_summary'][:1000]
    if lead_data.get('interest_score'):
        score = int(lead_data['interest_score'])
        lead.interest_score = max(1, min(5, score))

    lead.save()

    action = "Created" if created else "Updated"
    logger.info(f"{action} lead id={lead.id} for client={client.tag}, conversation={conversation.id}")
    return lead
```

- [ ] **Step 2: Create `__init__.py` for services package**

Check if `p004_ai_nexelin/MASTER/clients/services/__init__.py` exists, create if not:

```python
```

(Empty file)

- [ ] **Step 3: Commit**

```bash
git add p004_ai_nexelin/MASTER/clients/services/
git commit -m "feat: add lead extraction service for parsing LLM responses"
```

### Task 11: LLM system prompt injection for lead collection

**Files:**
- Modify: `p004_ai_nexelin/MASTER/rag/llm_client.py` (line ~178, where system prompt is enhanced)

- [ ] **Step 1: Add lead collection instruction to system prompt**

In `llm_client.py`, in the `generate_response` method, after the language instruction is added to `enhanced_system_prompt` (around line ~198), add lead collection instruction if enabled:

```python
# Lead collection instruction (if enabled for this client)
if client and getattr(client, 'leads_enabled', False):
    lead_instruction = """

=== LEAD COLLECTION ===
You are also collecting lead information from this conversation. Your tasks:
1. EXTRACT any contact information the user mentions naturally (name, email, phone).
2. If the user has not provided their name or contact info after 2-3 messages, NATURALLY ask for it in context of helping them better. Do NOT be pushy.
3. ASSESS interest level (1-5): 1=just browsing, 3=moderate interest, 5=ready to buy/commit.
4. SUMMARIZE their request/need in one sentence.

At the END of EVERY response, append a hidden data block (the user will not see this):
[LEAD_DATA]{"name": "...", "email": "...", "phone": "...", "request_summary": "...", "interest_score": N}[/LEAD_DATA]

Rules:
- Only include fields you actually know. Use empty string "" for unknown fields.
- Update interest_score based on the FULL conversation context.
- request_summary should reflect what the user is looking for.
- Be natural when asking for contact info — tie it to being helpful, not data collection.
- NEVER mention lead collection or data extraction to the user.
"""
    enhanced_system_prompt = enhanced_system_prompt + lead_instruction
```

- [ ] **Step 2: Commit**

```bash
git add p004_ai_nexelin/MASTER/rag/llm_client.py
git commit -m "feat: inject lead collection instructions into LLM system prompt"
```

### Task 12: Post-processing — extract leads from LLM responses

**Files:**
- Modify: `p004_ai_nexelin/MASTER/rag/response_generator.py` (line ~197, after answer is extracted)

- [ ] **Step 1: Add lead extraction post-processing**

In `response_generator.py`, in `_generate_complete()` method, after the answer is extracted (line ~186-195) and before the HITL escalation check (line ~197), add:

```python
# Lead extraction: parse and save lead data from LLM response
if client and getattr(client, 'leads_enabled', False):
    try:
        from MASTER.clients.services.lead_extraction import (
            extract_lead_data_from_response,
            clean_response,
        )
        lead_data = extract_lead_data_from_response(answer)
        if lead_data:
            # Clean the answer (remove [LEAD_DATA] block) before showing to customer
            answer = clean_response(answer)
            # Save lead data asynchronously — we'll handle in the view layer
            # Store in response metadata for the view to process
            # (We need conversation context which isn't available here)
    except Exception as e:
        logger.warning(f"Lead extraction error: {e}")
```

Actually, the better approach is to clean the response here and handle saving in the views where we have conversation context. Add `lead_data` to `RAGResponse`:

In the `RAGResponse` dataclass (line ~41), add:

```python
lead_data: dict | None = None
```

Then in `_generate_complete`, after answer extraction:

```python
# Lead extraction
lead_data_extracted = None
if client and getattr(client, 'leads_enabled', False):
    try:
        from MASTER.clients.services.lead_extraction import (
            extract_lead_data_from_response,
            clean_response,
        )
        lead_data_extracted = extract_lead_data_from_response(answer)
        if lead_data_extracted:
            answer = clean_response(answer)
    except Exception as e:
        logger.warning(f"Lead extraction error: {e}")
```

And in the `return RAGResponse(...)` at the bottom, add:

```python
lead_data=lead_data_extracted,
```

- [ ] **Step 2: Commit**

```bash
git add p004_ai_nexelin/MASTER/rag/response_generator.py
git commit -m "feat: extract lead data from LLM responses and clean output"
```

### Task 13: Save leads in message handler views

**Files:**
- Modify: `p004_ai_nexelin/MASTER/api/views.py` (PublicRAGChatView.post, around line ~340+)
- Modify: `p004_ai_nexelin/MASTER/clients/views_telegram.py` (handle_regular_message)
- Modify: `p004_ai_nexelin/MASTER/clients/views_meta_whatsapp.py` (message handling)

- [ ] **Step 1: Add lead saving to PublicRAGChatView (web chat)**

In `api/views.py`, after the RAG response is generated and before sending back to client, add lead saving logic. Find where `rag_response` is used and the conversation is available:

```python
# Save lead data if present
if hasattr(rag_response, 'lead_data') and rag_response.lead_data and conversation:
    try:
        from MASTER.clients.services.lead_extraction import save_lead_from_extraction
        save_lead_from_extraction(
            client=client,
            conversation=conversation,
            lead_data=rag_response.lead_data,
            source='web',
        )
    except Exception as e:
        logger.warning(f"Failed to save lead: {e}")
```

- [ ] **Step 2: Add lead saving to Telegram handler**

In `views_telegram.py`, in `handle_regular_message`, after RAG response, add same pattern with `source='telegram'`.

- [ ] **Step 3: Add lead saving to WhatsApp handler**

In `views_meta_whatsapp.py`, in message handling, after RAG response, add same pattern with `source='whatsapp'`.

- [ ] **Step 4: Commit**

```bash
git add p004_ai_nexelin/MASTER/api/views.py p004_ai_nexelin/MASTER/clients/views_telegram.py p004_ai_nexelin/MASTER/clients/views_meta_whatsapp.py
git commit -m "feat: save extracted leads from all messenger channels"
```

---

## Chunk 4: Leads Module — Frontend

### Task 14: Leads page component

**Files:**
- Create: `nextlen/src/pages/LeadsPage.jsx`

- [ ] **Step 1: Create LeadsPage.jsx**

```jsx
import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { Loader2, Search, ExternalLink, Star } from 'lucide-react';
import api from '../api/axios';

const STATUS_COLORS = {
  new: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400',
  contacted: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400',
  converted: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400',
  lost: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400',
};

const SOURCE_LABELS = {
  web: 'Web',
  telegram: 'Telegram',
  whatsapp: 'WhatsApp',
};

const LeadsPage = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [leads, setLeads] = useState([]);
  const [loading, setLoading] = useState(true);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [sourceFilter, setSourceFilter] = useState('');

  const loadLeads = async () => {
    try {
      setLoading(true);
      const params = { page, per_page: 25 };
      if (search) params.search = search;
      if (statusFilter) params.status = statusFilter;
      if (sourceFilter) params.source = sourceFilter;

      const res = await api.get('/clients/leads/', { params });
      setLeads(res.data?.results || []);
      setTotal(res.data?.total || 0);
    } catch (err) {
      console.error('Failed to load leads:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadLeads();
  }, [page, statusFilter, sourceFilter]);

  const handleSearch = (e) => {
    e.preventDefault();
    setPage(1);
    loadLeads();
  };

  const updateLeadStatus = async (leadId, newStatus) => {
    try {
      await api.patch(`/clients/leads/${leadId}/`, { status: newStatus });
      setLeads(prev => prev.map(l => l.id === leadId ? { ...l, status: newStatus } : l));
    } catch (err) {
      console.error('Failed to update lead:', err);
    }
  };

  const renderInterest = (score) => {
    return (
      <div className="flex gap-0.5">
        {[1, 2, 3, 4, 5].map(i => (
          <Star
            key={i}
            size={14}
            className={i <= score ? 'fill-yellow-400 text-yellow-400' : 'text-gray-300 dark:text-gray-600'}
          />
        ))}
      </div>
    );
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
          {t('leads.title') || 'Leads'}
        </h1>
        <p className="text-gray-600 dark:text-gray-400">
          {t('leads.subtitle') || 'Contacts collected from messenger conversations'}
        </p>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3 items-center">
        <form onSubmit={handleSearch} className="flex gap-2 flex-1 min-w-[200px]">
          <div className="relative flex-1">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder={t('leads.searchPlaceholder') || 'Search by name, email, phone...'}
              className="input pl-9 w-full"
            />
          </div>
          <button type="submit" className="btn-secondary">
            {t('common.search') || 'Search'}
          </button>
        </form>

        <select
          value={statusFilter}
          onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
          className="input w-auto"
        >
          <option value="">{t('leads.allStatuses') || 'All statuses'}</option>
          <option value="new">{t('leads.statusNew') || 'New'}</option>
          <option value="contacted">{t('leads.statusContacted') || 'Contacted'}</option>
          <option value="converted">{t('leads.statusConverted') || 'Converted'}</option>
          <option value="lost">{t('leads.statusLost') || 'Lost'}</option>
        </select>

        <select
          value={sourceFilter}
          onChange={(e) => { setSourceFilter(e.target.value); setPage(1); }}
          className="input w-auto"
        >
          <option value="">{t('leads.allSources') || 'All sources'}</option>
          <option value="web">Web</option>
          <option value="telegram">Telegram</option>
          <option value="whatsapp">WhatsApp</option>
        </select>
      </div>

      {/* Table */}
      {loading ? (
        <div className="flex justify-center py-12">
          <Loader2 className="w-8 h-8 animate-spin text-primary-500" />
        </div>
      ) : leads.length === 0 ? (
        <div className="text-center py-12 text-gray-500 dark:text-gray-400">
          {t('leads.noLeads') || 'No leads found'}
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200 dark:border-gray-700 text-left">
                <th className="pb-3 font-medium text-gray-600 dark:text-gray-400">{t('leads.name') || 'Name'}</th>
                <th className="pb-3 font-medium text-gray-600 dark:text-gray-400">{t('leads.email') || 'Email'}</th>
                <th className="pb-3 font-medium text-gray-600 dark:text-gray-400">{t('leads.phone') || 'Phone'}</th>
                <th className="pb-3 font-medium text-gray-600 dark:text-gray-400">{t('leads.source') || 'Source'}</th>
                <th className="pb-3 font-medium text-gray-600 dark:text-gray-400">{t('leads.interest') || 'Interest'}</th>
                <th className="pb-3 font-medium text-gray-600 dark:text-gray-400">{t('leads.status') || 'Status'}</th>
                <th className="pb-3 font-medium text-gray-600 dark:text-gray-400">{t('leads.date') || 'Date'}</th>
                <th className="pb-3 font-medium text-gray-600 dark:text-gray-400"></th>
              </tr>
            </thead>
            <tbody>
              {leads.map(lead => (
                <tr key={lead.id} className="border-b border-gray-100 dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-800/50">
                  <td className="py-3 font-medium text-gray-900 dark:text-gray-100">
                    {lead.name || <span className="text-gray-400">—</span>}
                  </td>
                  <td className="py-3 text-gray-700 dark:text-gray-300">{lead.email || '—'}</td>
                  <td className="py-3 text-gray-700 dark:text-gray-300">{lead.phone || '—'}</td>
                  <td className="py-3">
                    <span className="text-xs font-medium">{SOURCE_LABELS[lead.source] || lead.source}</span>
                  </td>
                  <td className="py-3">{renderInterest(lead.interest_score)}</td>
                  <td className="py-3">
                    <select
                      value={lead.status}
                      onChange={(e) => updateLeadStatus(lead.id, e.target.value)}
                      className={`text-xs font-medium px-2 py-1 rounded-full border-0 ${STATUS_COLORS[lead.status]}`}
                    >
                      <option value="new">{t('leads.statusNew') || 'New'}</option>
                      <option value="contacted">{t('leads.statusContacted') || 'Contacted'}</option>
                      <option value="converted">{t('leads.statusConverted') || 'Converted'}</option>
                      <option value="lost">{t('leads.statusLost') || 'Lost'}</option>
                    </select>
                  </td>
                  <td className="py-3 text-gray-500 dark:text-gray-400 text-xs">
                    {new Date(lead.created_at).toLocaleDateString()}
                  </td>
                  <td className="py-3">
                    {lead.conversation_id && (
                      <button
                        onClick={() => navigate(`/history?conversation=${lead.conversation_id}`)}
                        className="text-primary-500 hover:text-primary-600 dark:text-primary-400"
                        title={t('leads.viewConversation') || 'View conversation'}
                      >
                        <ExternalLink size={16} />
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Pagination */}
      {total > 25 && (
        <div className="flex justify-center gap-2">
          <button
            onClick={() => setPage(p => Math.max(1, p - 1))}
            disabled={page === 1}
            className="btn-secondary disabled:opacity-50"
          >
            {t('common.back') || 'Previous'}
          </button>
          <span className="flex items-center text-sm text-gray-600 dark:text-gray-400">
            {page} / {Math.ceil(total / 25)}
          </span>
          <button
            onClick={() => setPage(p => p + 1)}
            disabled={page >= Math.ceil(total / 25)}
            className="btn-secondary disabled:opacity-50"
          >
            {t('common.next') || 'Next'}
          </button>
        </div>
      )}
    </div>
  );
};

export default LeadsPage;
```

- [ ] **Step 2: Commit**

```bash
git add nextlen/src/pages/LeadsPage.jsx
git commit -m "feat: create LeadsPage component with table, filters, pagination"
```

### Task 15: Add Leads route and sidebar navigation

**Files:**
- Modify: `nextlen/src/App.jsx`
- Modify: `nextlen/src/components/layout/Sidebar.jsx`
- Modify: `nextlen/src/locales/en/translation.json` (and other locales)

- [ ] **Step 1: Add route in App.jsx**

Import LeadsPage:

```jsx
import LeadsPage from './pages/LeadsPage';
```

Add route inside the Layout routes (after `/settings` route, line ~42):

```jsx
<Route path="/leads" element={<LeadsPage />} />
```

- [ ] **Step 2: Add Leads tab to Sidebar**

In `Sidebar.jsx`, add `Users` icon import (line ~3):

```jsx
import {
  LayoutDashboard,
  GraduationCap,
  FlaskConical,
  Plug2,
  MessageSquare,
  BookOpen,
  Settings,
  CreditCard,
  Menu,
  X,
  Users
} from 'lucide-react';
```

Modify `navItems` to be dynamic based on `user` data. After the navItems definition (line ~72), add conditional Leads item. Change the navItems to a function or add conditionally:

```jsx
const navItems = [
  { to: '/dashboard', icon: LayoutDashboard, label: t('nav.dashboard') },
  { to: '/training', icon: GraduationCap, label: t('nav.training') },
  { to: '/sandbox', icon: FlaskConical, label: t('nav.sandbox'), badge: t('nav.sandboxBadge') || 'Also in Train AI' },
  { to: '/integrations', icon: Plug2, label: t('nav.integrations') },
  { to: '/history', icon: MessageSquare, label: t('nav.history') },
  // Leads tab — shown only if leads_enabled
  ...(user?.leads_enabled ? [{ to: '/leads', icon: Users, label: t('nav.leads') || 'Leads' }] : []),
  { to: '/setup', icon: BookOpen, label: t('nav.promptBook') || 'Prompt Book' },
  { to: '/settings', icon: Settings, label: t('nav.settings') || 'Settings' },
];
```

Note: `user` comes from `useAuth()` context. For this to work, `leads_enabled` must be returned by `/clients/me/` — which it already is via `ClientSerializer`.

- [ ] **Step 3: Add translations**

In `nextlen/src/locales/en/translation.json`, add:

```json
"nav": {
  ...existing...
  "leads": "Leads"
},
"leads": {
  "title": "Leads",
  "subtitle": "Contacts collected from messenger conversations",
  "searchPlaceholder": "Search by name, email, phone...",
  "allStatuses": "All statuses",
  "allSources": "All sources",
  "statusNew": "New",
  "statusContacted": "Contacted",
  "statusConverted": "Converted",
  "statusLost": "Lost",
  "noLeads": "No leads found",
  "name": "Name",
  "email": "Email",
  "phone": "Phone",
  "source": "Source",
  "interest": "Interest",
  "status": "Status",
  "date": "Date",
  "viewConversation": "View conversation"
}
```

Add corresponding translations for other locales (de, fr, es, it, nl, da).

- [ ] **Step 4: Commit**

```bash
git add nextlen/src/App.jsx nextlen/src/components/layout/Sidebar.jsx nextlen/src/locales/*/translation.json
git commit -m "feat: add Leads route and conditional sidebar navigation"
```

---

## Final Review

After all tasks, verify:
1. `greeting_message` is editable in Settings, visible in web chat on open, sent as first message in Telegram/WhatsApp
2. `leads_enabled` toggle in admin works
3. When leads_enabled, LLM collects contact data from conversations
4. Leads table shows in sidebar and displays data with filters
5. Lead status can be changed, conversation link works
