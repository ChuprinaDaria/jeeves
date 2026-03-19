# SP1: MCP Core Engine — Design Spec

> Clean model system. Django as orchestrator. MCP servers via admin. SSE streaming.
> Zero hardcode. Feature flags per client. Dual-read migration.

---

## Overview

SP1 adds the foundational MCP infrastructure to Nexelin:

- **ToolCard** — catalog of tools (admin creates, clients see as cards)
- **ToolConnection** — client connects a tool (credentials, status)
- **AgentConfig** — per-client AI agent configuration (replaces scattered Client fields)
- **MCP Hub** — executor for builtin + external MCP servers, SSE streaming
- **PlatformDefaults** — singleton for all default values (no hardcode in code)
- **FeatureFlag** — per-client feature toggles (test on `srtyh`, then rollout to all)
- **SystemMessage** — all UI/system strings with translations (no hardcoded strings)
- **Language detection** — `lingua-py` replaces hand-rolled word lists

Existing code continues to work unchanged. New code activates per-client via FeatureFlag.

---

## CRITICAL RULE: Zero Impact on Other Clients

**Every new code path MUST be gated by `FeatureFlag.is_enabled(key, client)`.**

On initial deploy, all flags are `rollout='selected'` with only `srtyh` (tag) in `enabled_clients`. For every other client in the system, behavior is **100% identical** to before SP1 — old code runs, old fields are read, nothing changes.

**Implementation rule:** if you write a new view, task, or utility that touches agent/tool/language logic — it MUST check the feature flag first and fall back to old code if disabled. No exceptions. No "this is safe to run for everyone". Everything goes through flags.

```python
# CORRECT — every new path gated
if FeatureFlag.is_enabled('mcp_agent_config', client):
    # new code
else:
    # old code (exact same behavior as before)

# WRONG — new code runs for everyone
agent_config = AgentConfig.objects.get(client=client)  # breaks if no AgentConfig exists
```

Rollout to all clients happens **only** after manual testing on `srtyh` and explicit admin action (`rollout='all'`).

---

## Project Decomposition

This is SP1 of 4 sub-projects:

| SP | What | Depends on |
|----|------|------------|
| **SP1** | MCP Core Engine (this spec) | — |
| SP2 | React tool dashboard with cards, OAuth UI, statuses | SP1 |
| SP3 | Personal Assistant chat, tool calling, sub-agents | SP1, SP2 |
| SP4 | Migrate RAG pipeline to agent system | SP1 |

---

## New Django Apps

```
MASTER/
├── accounts/          # Existing — not modified
├── branches/          # Existing — not modified
├── specializations/   # Existing — not modified
├── EmbeddingModel/    # Existing — not modified
├── clients/           # Existing — kept as-is, fields not removed in SP1
├── core/              # Existing — Django project config (settings, urls, wsgi, asgi)
├── platform/          # NEW — PlatformDefaults, FeatureFlag, SystemMessage, language
├── tools/             # NEW — ToolCard, ToolConnection, catalog API
├── agents/            # NEW — AgentConfig, AgentSession, AgentLog
└── mcp_hub/           # NEW — MCPExecutor, SSE endpoint, builtin handlers
```

---

## Models

### platform/models.py

#### PlatformDefaults

Singleton. All default values live here. Admin edits. No hardcode anywhere.

```python
class PlatformDefaults(models.Model):
    class Meta:
        verbose_name = 'Platform Defaults'
        verbose_name_plural = 'Platform Defaults'

    # LLM
    default_llm_provider = models.ForeignKey('EmbeddingModel.LLMProvider',
        on_delete=models.SET_NULL, null=True, blank=True)
    default_embedding_model = models.ForeignKey('EmbeddingModel.EmbeddingModel',
        on_delete=models.SET_NULL, null=True, blank=True)
    default_temperature = models.FloatField(null=True, blank=True)
    default_max_tokens = models.IntegerField(null=True, blank=True)

    # RAG
    default_similarity_threshold = models.FloatField(null=True, blank=True)
    default_max_context_chunks = models.IntegerField(null=True, blank=True)
    default_top_k = models.IntegerField(null=True, blank=True)

    # Language
    supported_languages = models.JSONField(default=list,
        help_text="e.g. ['en', 'de', 'fr', 'es', 'it', 'nl', 'da']")
    default_language = models.CharField(max_length=5, blank=True)
    language_detection_method = models.CharField(max_length=20, choices=[
        ('llm', 'LLM-based'),
        ('library', 'lingua-py'),
        ('none', 'Disabled'),
    ], blank=True)

    # Agent
    default_greeting = models.TextField(blank=True)

    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
```

Initial values set by data migration from current `settings.py`.

#### FeatureFlag

Per-client feature toggles. Test on `srtyh`, rollout to all.

```python
class FeatureFlag(models.Model):
    ROLLOUT_CHOICES = [
        ('off', 'Off for everyone'),
        ('selected', 'Only selected clients'),
        ('all', 'On for everyone'),
    ]

    key = models.CharField(max_length=100, unique=True, db_index=True)
    description = models.TextField(blank=True)
    rollout = models.CharField(max_length=10, choices=ROLLOUT_CHOICES, default='off')
    enabled_clients = models.ManyToManyField('clients.Client', blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['key']

    @classmethod
    def is_enabled(cls, key: str, client=None) -> bool:
        from django.core.cache import cache
        cache_key = f'ff:{key}:{client.pk if client else "global"}'
        cached = cache.get(cache_key)
        if cached is not None:
            return cached
        flag = cls.objects.filter(key=key).first()
        if not flag:
            result = False
        elif flag.rollout == 'all':
            result = True
        elif flag.rollout == 'selected' and client:
            result = flag.enabled_clients.filter(pk=client.pk).exists()
        else:
            result = False
        cache.set(cache_key, result, 60)
        return result
```

Initial flags (all `rollout='off'`):

| key | description |
|-----|-------------|
| `mcp_tools_dashboard` | New tools dashboard UI |
| `mcp_agent_config` | New AgentConfig instead of Client fields |
| `mcp_sse_streaming` | SSE streaming for chat |
| `language_detection_v2` | lingua-py instead of word lists |
| `system_messages` | SystemMessage instead of hardcoded strings |

#### SystemMessage

All translated UI/system strings. Admin edits. Cached.

```python
class SystemMessage(models.Model):
    key = models.CharField(max_length=100, unique=True, db_index=True)
    translations = models.JSONField(default=dict,
        help_text='{"en": "Please wait...", "de": "Bitte warten..."}')
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['key']

    @classmethod
    def get(cls, key: str, lang: str = 'en') -> str:
        from django.core.cache import cache
        cache_key = f'sysmsg:{key}:{lang}'
        cached = cache.get(cache_key)
        if cached is not None:
            return cached
        msg = cls.objects.filter(key=key).first()
        if not msg:
            return ''
        text = msg.translations.get(lang) or msg.translations.get('en', '')
        cache.set(cache_key, text, 300)
        return text
```

Seed messages:

| key | en | de |
|-----|----|----|
| `chat.timeout` | Session timed out | Sitzung abgelaufen |
| `chat.waiting` | Please wait... | Bitte warten... |
| `chat.escalation` | Connecting to manager... | Verbinde mit Manager... |
| `chat.greeting_default` | Hello! How can I help? | Hallo! Wie kann ich helfen? |
| `chat.no_answer` | I don't have enough information | Ich habe nicht genug Informationen |

---

### tools/models.py

#### ToolCard

Catalog entry. Admin creates. Client sees as a card on dashboard.

```python
class ToolCard(models.Model):
    CATEGORY_CHOICES = [
        ('communication', 'Communication'),
        ('productivity', 'Productivity'),
        ('analytics', 'Analytics'),
        ('ai', 'AI & Knowledge'),
        ('crm', 'CRM & Sales'),
        ('custom', 'Custom'),
    ]

    TRANSPORT_CHOICES = [
        ('builtin', 'Built-in Django handler'),
        ('sse', 'SSE (Server-Sent Events)'),
        ('streamable_http', 'Streamable HTTP'),
    ]

    AUTH_TYPE_CHOICES = [
        ('none', 'No auth required'),
        ('oauth2', 'OAuth 2.0'),
        ('api_key', 'API Key'),
        ('credentials', 'Custom credentials form'),
        ('qr_code', 'QR Code scan'),
    ]

    # Identity (visible to client)
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    tagline = models.CharField(max_length=200,
        help_text="Short non-tech description for client")
    description = models.TextField()
    icon = models.CharField(max_length=50,
        help_text="Lucide icon name")
    color = models.CharField(max_length=7,
        help_text="Accent color hex")
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)

    # MCP connection
    mcp_server_url = models.CharField(max_length=500, blank=True)
    transport_type = models.CharField(max_length=20, choices=TRANSPORT_CHOICES)
    is_builtin = models.BooleanField(default=False)
    builtin_handler = models.CharField(max_length=200, blank=True,
        help_text="Python path: 'mcp_hub.builtin.whatsapp_meta'")
    tools_schema = models.JSONField(default=list,
        help_text="Cached tools/list from MCP server")

    # Auth
    auth_type = models.CharField(max_length=20, choices=AUTH_TYPE_CHOICES)
    auth_config = models.JSONField(default=dict,
        help_text="Auth fields definition per auth_type")

    # Admin control
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    sort_order = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['sort_order', 'name']
```

#### ToolConnection

Client connected a tool. Stores credentials and status.

```python
class ToolConnection(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending setup'),
        ('connected', 'Connected'),
        ('error', 'Error'),
        ('disconnected', 'Disconnected'),
        ('expired', 'Token expired'),
    ]

    client = models.ForeignKey('clients.Client', on_delete=models.CASCADE,
        related_name='tool_connections')
    tool_card = models.ForeignKey(ToolCard, on_delete=models.CASCADE,
        related_name='connections')

    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    credentials = EncryptedJSONField(default=dict,
        help_text="Encrypted at rest via cryptography.fernet")
    config = models.JSONField(default=dict)
    enabled = models.BooleanField(default=True)

    connected_at = models.DateTimeField(null=True, blank=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    error_count = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['client', 'tool_card']
        indexes = [
            models.Index(fields=['client', 'status']),
            models.Index(fields=['tool_card', 'status']),
        ]
```

**Migration mapping — existing Client fields to ToolCard + ToolConnection:**

| ToolCard slug | Client fields migrated | auth_type |
|---------------|----------------------|-----------|
| `whatsapp-meta` | `whatsapp_meta_enabled`, `meta_waba_id`, `meta_app_id`, `meta_app_secret`, `meta_access_token`, `meta_phone_number_id`, `meta_verify_token`, `meta_phone_number` | credentials |
| `telegram` | `telegram_enabled`, `telegram_bot_token`, `telegram_welcome_message` | api_key |
| `email-smtp` | `email_smtp_enabled`, `email_smtp_host`, `email_smtp_port`, `email_smtp_use_tls`, `email_smtp_username`, `email_smtp_password`, `email_from_address`, `email_from_name` | credentials |
| `whatsapp-bridge` | `whatsapp_bridge_enabled`, `whatsapp_bridge_phone`, `whatsapp_bridge_matrix_user_id`, `whatsapp_bridge_matrix_access_token`, `whatsapp_bridge_status` | qr_code |
| `web-widget` | `widget_enabled` | none |
| `hitl-matrix` | `matrix_hitl_enabled`, `matrix_manager_user_ids`, `matrix_homeserver_url` | credentials |
| `rag-search` | builtin, always available | none |

---

### agents/models.py

#### AgentConfig

Per-client AI agent. All nullable — falls back to PlatformDefaults.

```python
class AgentConfig(models.Model):
    client = models.OneToOneField('clients.Client', on_delete=models.CASCADE,
        related_name='agent_config')

    # LLM — null = platform default
    llm_provider = models.ForeignKey('EmbeddingModel.LLMProvider',
        on_delete=models.SET_NULL, null=True, blank=True)
    embedding_model = models.ForeignKey('EmbeddingModel.EmbeddingModel',
        on_delete=models.SET_NULL, null=True, blank=True)

    # Prompts
    system_prompt = models.TextField(blank=True)
    greeting_message = models.TextField(blank=True)

    # Generation — null = platform default
    temperature = models.FloatField(null=True, blank=True)
    max_tokens = models.IntegerField(null=True, blank=True)

    # RAG — null = platform default
    similarity_threshold = models.FloatField(null=True, blank=True)
    max_context_chunks = models.IntegerField(null=True, blank=True)
    top_k = models.IntegerField(null=True, blank=True)

    # Language — empty = platform default
    language = models.CharField(max_length=5, blank=True)
    supported_languages = models.JSONField(default=list, blank=True)
    language_detection = models.BooleanField(null=True, blank=True)

    # Tools — no M2M. Available tools derived from:
    # ToolConnection.objects.filter(client=self.client, enabled=True, status='connected')

    # Behaviour
    escalation_enabled = models.BooleanField(default=False)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

Resolution chain for any param:

```
AgentConfig.field  →  if null  →  PlatformDefaults.default_field
```

#### AgentSession

```python
class AgentSession(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    agent_config = models.ForeignKey(AgentConfig, on_delete=models.CASCADE,
        related_name='sessions')
    CHANNEL_CHOICES = [
        ('web', 'Web Chat'),
        ('telegram', 'Telegram'),
        ('whatsapp_meta', 'WhatsApp Meta'),
        ('whatsapp_bridge', 'WhatsApp Bridge'),
        ('email', 'Email'),
        ('api', 'API'),
    ]
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES)
    external_user_id = models.CharField(max_length=255, blank=True)
    language = models.CharField(max_length=5, blank=True)
    metadata = models.JSONField(default=dict)
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
```

#### AgentLog

```python
class AgentLog(models.Model):
    CALL_TYPE_CHOICES = [
        ('llm', 'LLM Generation'),
        ('tool', 'MCP Tool Call'),
        ('rag', 'RAG Search'),
        ('escalation', 'HITL Escalation'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('ok', 'Success'),
        ('error', 'Error'),
        ('timeout', 'Timeout'),
    ]

    session = models.ForeignKey(AgentSession, on_delete=models.CASCADE,
        related_name='logs')
    tool_connection = models.ForeignKey('tools.ToolConnection',
        on_delete=models.SET_NULL, null=True, blank=True)
    call_type = models.CharField(max_length=20, choices=CALL_TYPE_CHOICES)
    tool_name = models.CharField(max_length=100, blank=True)
    input_data = models.JSONField(default=dict)
    output_data = models.JSONField(default=dict)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    error_message = models.TextField(blank=True)
    latency_ms = models.IntegerField(null=True)
    tokens_used = models.IntegerField(null=True)
    cost = models.DecimalField(max_digits=10, decimal_places=6, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['session', 'created_at']),
            models.Index(fields=['call_type', 'status']),
            models.Index(fields=['tool_connection', 'created_at']),
        ]
```

---

## MCP Hub

### MCPExecutor

Single entry point for calling any tool — builtin or external MCP server.

```python
# mcp_hub/executor.py

class MCPExecutor:
    async def call_tool(self, tool_connection, tool_name, arguments, session):
        tool_card = tool_connection.tool_card
        log = await AgentLog.objects.acreate(
            session=session, tool_connection=tool_connection,
            call_type='tool', tool_name=tool_name,
            input_data=arguments, status='pending')

        start = time.monotonic()
        try:
            if tool_card.transport_type == 'builtin':
                result = await self._call_builtin(tool_card, tool_connection, tool_name, arguments)
            else:
                result = await self._call_mcp(tool_card, tool_connection, tool_name, arguments)
            log.status = 'ok'
            log.output_data = result
            log.latency_ms = int((time.monotonic() - start) * 1000)
            await log.asave()
            return result
        except Exception as e:
            log.status = 'error'
            log.error_message = str(e)
            log.latency_ms = int((time.monotonic() - start) * 1000)
            await log.asave()
            raise

    async def _call_builtin(self, tool_card, connection, tool_name, arguments):
        module_path, func_name = tool_card.builtin_handler.rsplit('.', 1)
        module = importlib.import_module(module_path)
        handler = getattr(module, func_name)
        return await handler(connection=connection, tool_name=tool_name, **arguments)

    async def _call_mcp(self, tool_card, connection, tool_name, arguments):
        from mcp import ClientSession
        from mcp.client.sse import sse_client
        async with sse_client(tool_card.mcp_server_url) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments)
                return {'content': [c.model_dump() for c in result.content]}
```

### SSE Streaming

```python
# mcp_hub/views.py

class ChatSSEView(View):
    async def post(self, request):
        if not FeatureFlag.is_enabled('mcp_sse_streaming', request.client):
            return await self._legacy_response(request)

        response = StreamingHttpResponse(
            self._stream(request), content_type='text/event-stream')
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'
        return response

    async def _stream(self, request):
        data = json.loads(request.body)
        session = await self._get_or_create_session(request)
        agent_config = await AgentConfig.objects.select_related(
            'llm_provider', 'embedding_model').aget(client=request.client)

        yield self._sse_event('status', {'step': 'thinking'})

        rag_connection = await self._get_tool(agent_config, 'rag-search')
        if rag_connection:
            yield self._sse_event('status', {'step': 'searching'})
            chunks = await self.executor.call_tool(
                rag_connection, 'search', {'query': data['message']}, session)
            yield self._sse_event('sources', chunks)

        yield self._sse_event('status', {'step': 'generating'})
        async for token in self._stream_llm(agent_config, data['message'], chunks):
            yield self._sse_event('token', {'text': token})

        yield self._sse_event('done', {})

    def _sse_event(self, event, data):
        return f"event: {event}\ndata: {json.dumps(data)}\n\n"
```

---

## Language Detection

Single module. No hardcoded word lists. `lingua-py` for detection.

```python
# platform/language.py

from lingua import LanguageDetectorBuilder

_detector = None

def get_detector():
    global _detector
    if _detector is None:
        defaults = PlatformDefaults.get()
        languages = _map_codes_to_lingua(defaults.supported_languages)
        _detector = LanguageDetectorBuilder.from_languages(*languages).build()
    return _detector

def detect_language(text: str, fallback: str = 'en') -> str:
    if not text or len(text.strip()) < 3:
        return fallback
    detector = get_detector()
    result = detector.detect_language_of(text)
    if result is None:
        return fallback
    return result.iso_code_639_1.name.lower()
```

Language resolution per session:

1. User explicitly requested language -> lock it
2. `AgentConfig.language_detection=True` -> detect from first message, then sticky for session
3. `AgentConfig.language` -> fallback
4. `PlatformDefaults.default_language` -> final fallback

Language is set **once** at session start. No re-detection per message.

---

## Dual-Read Migration

```python
# tools/compat.py

def get_credentials(client, tool_slug, field, default=''):
    if FeatureFlag.is_enabled('mcp_agent_config', client):
        connection = ToolConnection.objects.filter(
            client=client, tool_card__slug=tool_slug, status='connected').first()
        if connection:
            return connection.credentials.get(field, default)
    # Fallback to old Client fields
    FIELD_MAP = {
        ('whatsapp-meta', 'access_token'): 'meta_access_token',
        ('whatsapp-meta', 'phone_number_id'): 'meta_phone_number_id',
        ('telegram', 'bot_token'): 'telegram_bot_token',
        # ... full mapping
    }
    old_field = FIELD_MAP.get((tool_slug, field))
    return getattr(client, old_field, default) if old_field else default


def is_tool_connected(client, tool_slug):
    if FeatureFlag.is_enabled('mcp_agent_config', client):
        return ToolConnection.objects.filter(
            client=client, tool_card__slug=tool_slug,
            status='connected', enabled=True).exists()
    ENABLED_MAP = {
        'whatsapp-meta': 'whatsapp_meta_enabled',
        'telegram': 'telegram_enabled',
        'email-smtp': 'email_smtp_enabled',
        'whatsapp-bridge': 'whatsapp_bridge_enabled',
        'web-widget': 'widget_enabled',
        'hitl-matrix': 'matrix_hitl_enabled',
    }
    old_field = ENABLED_MAP.get(tool_slug)
    return getattr(client, old_field, False) if old_field else False
```

---

## API Endpoints

```
# tools
GET    /api/tools/catalog/                  — all available tools with connection status
POST   /api/tools/{slug}/connect/           — connect a tool (sends credentials)
POST   /api/tools/{slug}/disconnect/        — disconnect
GET    /api/tools/{slug}/status/            — connection status
GET    /api/tools/{slug}/oauth/callback/    — OAuth redirect handler
GET    /api/tools/my/                       — client's connected tools

# mcp
POST   /api/mcp/chat/                       — SSE streaming chat
POST   /api/mcp/mcp/                        — MCP server endpoint (Django as MCP server)

# agents
GET    /api/agents/config/                  — agent config
PATCH  /api/agents/config/                  — update agent config
GET    /api/agents/logs/                    — agent logs
GET    /api/agents/sessions/                — sessions
```

---

## Django Admin

Full control over everything:

- **ToolCard** — create tools, set descriptions/icons/auth, activate/deactivate
- **ToolConnection** — per-client enable/disable, see statuses, reset errors, disconnect (list_editable, bulk actions)
- **AgentConfig** — per-client LLM/RAG params, prompts, tools, language
- **PlatformDefaults** — singleton, all global defaults
- **FeatureFlag** — per-client toggles, rollout control (list_editable)
- **SystemMessage** — all translated strings
- **AgentLog** — readonly, filterable, date_hierarchy

---

## EncryptedJSONField

GDPR requirement — credentials encrypted at rest from day one.

```python
# platform/fields.py

from cryptography.fernet import Fernet
from django.conf import settings
from django.db import models
import json

class EncryptedJSONField(models.TextField):
    """Stores JSON encrypted with Fernet. Transparent encrypt/decrypt."""

    def get_prep_value(self, value):
        if value is None:
            return None
        f = Fernet(settings.FIELD_ENCRYPTION_KEY)
        return f.encrypt(json.dumps(value).encode()).decode()

    def from_db_value(self, value, expression, connection):
        if value is None:
            return {}
        f = Fernet(settings.FIELD_ENCRYPTION_KEY)
        return json.loads(f.decrypt(value.encode()).decode())
```

`FIELD_ENCRYPTION_KEY` in `.env`, generated once via `Fernet.generate_key()`.

---

## FeatureFlag Cache Invalidation

Instant cache clear on admin save — no waiting 60 seconds during testing.

```python
# platform/signals.py

from django.db.models.signals import post_save, m2m_changed
from django.core.cache import cache

def invalidate_feature_flag_cache(sender, instance, **kwargs):
    cache.delete_pattern(f'ff:{instance.key}:*')

post_save.connect(invalidate_feature_flag_cache, sender='platform.FeatureFlag')
m2m_changed.connect(
    lambda sender, instance, **kw: invalidate_feature_flag_cache(sender, instance, **kw),
    sender=FeatureFlag.enabled_clients.through)
```

---

## Infrastructure Requirements

SSE streaming (`ChatSSEView`) requires async support:

- **ASGI server**: Uvicorn alongside Gunicorn
- **Deployment**: Gunicorn handles sync Django (existing code), Uvicorn handles `/api/mcp/chat/` (SSE)
- **Nginx config**: `proxy_buffering off;` and `proxy_read_timeout 300s;` for SSE endpoint
- Docker compose: add `uvicorn` service for async endpoints

```yaml
# docker-compose.yml addition
  uvicorn:
    build: .
    command: uvicorn MASTER.core.asgi:application --host 0.0.0.0 --port 8001
    env_file: .env
    depends_on:
      postgres: { condition: service_healthy }
      redis: { condition: service_healthy }
```

Nginx routes `/api/mcp/` to Uvicorn (port 8001), everything else to Gunicorn (port 8000).

---

## Migrations

Per-app migration numbering:

```
platform/migrations/
  0001_initial.py                  — PlatformDefaults, FeatureFlag, SystemMessage
  0002_seed_platform_defaults.py   — from current settings.py values
  0003_seed_system_messages.py     — timeout, waiting, escalation, greeting, no_answer
  0004_seed_feature_flags.py       — 5 flags, all rollout='off'

tools/migrations/
  0001_initial.py                  — ToolCard, ToolConnection
  0002_seed_tool_cards.py          — 7 builtin tools
  0003_migrate_connections.py      — Client fields → ToolConnection (reversible)

agents/migrations/
  0001_initial.py                  — AgentConfig, AgentSession, AgentLog
  0002_create_agent_configs.py     — Client fields → AgentConfig (reversible)
```

All data migrations: `RunPython(forward, reverse)` — reversible.
Client model fields NOT removed in SP1.

---

## Client Fields NOT Migrated in SP1

These stay in Client model. Migrated in later sub-projects:

| Field(s) | Migrates in |
|----------|-------------|
| `extension_enabled` | SP2 (Chrome extension tool card) |
| `telephony_enabled`, `ClientTelephonyConfig` | SP2 (telephony tool card) |
| `leads_enabled`, `Lead` model | SP3 (leads agent) |
| `pixel_dashboard_enabled` | SP2 (dashboard) |
| `email_report_enabled`, `email_report_recipients` | SP2 (email tool config) |
| `notification_language` | SP1 covers via AgentConfig.language |
| `dashboard_layout`, `dashboard_custom_widgets`, `dashboard_custom_style` | SP2 |
| `custom_system_prompt`, `active_custom_prompt` | SP1 covers via AgentConfig.system_prompt |
| `llm_provider` (legacy CharField), `llm_model_name` | SP1 covers via AgentConfig.llm_provider FK |
| `greeting_message` | SP1 covers via AgentConfig.greeting_message |
| `ClientWhatsAppConversation` | Not migrated — stays as-is |
| `ClientDocument`, `ClientEmbedding` | SP4 (RAG migration) |
| `KnowledgeBlock` | SP4 |
| `hitl_enabled`, `manager_telegram_ids` (Telegram HITL) | SP2 (hitl-telegram tool card) |

---

## Dependencies

```
lingua-language-detector>=2.0    — language detection
mcp>=1.0                         — official MCP Python SDK (Anthropic)
cryptography>=42.0               — EncryptedJSONField
uvicorn>=0.30                    — ASGI server for SSE endpoints
```

---

## Tests

```
tests/
├── test_models.py              — ToolCard, ToolConnection, AgentConfig CRUD
├── test_encrypted_field.py     — EncryptedJSONField encrypt/decrypt round-trip
├── test_feature_flags.py       — is_enabled(), cache, per-client, invalidation
├── test_system_messages.py     — get(), fallback, cache
├── test_platform_defaults.py   — singleton, get()
├── test_language.py            — detect_language() with lingua
├── test_compat.py              — dual-read: new path vs fallback
├── test_catalog_api.py         — /api/tools/catalog/, connect, disconnect
├── test_executor.py            — MCPExecutor builtin + mcp calls
├── test_sse.py                 — ChatSSEView streaming
├── test_migrations.py          — data migrations correctness
├── test_admin.py               — admin actions
```

---

## Rollout Strategy

1. Deploy with all FeatureFlags `rollout='off'`
2. In admin: set `rollout='selected'`, add `srtyh` client to each flag
3. Test on srtyh — all new code paths
4. Fix issues
5. In admin: set `rollout='all'`
6. After stable period: remove old code paths, remove compat.py, remove old Client fields

---

## What SP1 Does NOT Include

- React dashboard UI (SP2)
- Personal Assistant chat mode (SP3)
- RAG pipeline rewrite to agents (SP4)
- Removal of old Client fields (see table above)
- OAuth2 provider implementation (framework only, actual OAuth flows in SP2)
