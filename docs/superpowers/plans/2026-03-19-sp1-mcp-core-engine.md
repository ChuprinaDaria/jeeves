# SP1: MCP Core Engine — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add ToolCard/ToolConnection/AgentConfig models, MCP executor, SSE streaming, feature flags, and language detection to Nexelin Django backend — all gated by per-client feature flags so only `srtyh` client is affected.

**Architecture:** New Django apps (`platform`, `tools`, `agents`, `mcp_hub`) alongside existing apps. All new code paths gated by `FeatureFlag.is_enabled()`. Dual-read migration: new models first, fallback to old Client fields.

**Tech Stack:** Django 5.0.9, PostgreSQL, Redis, Celery, `mcp` SDK, `lingua-language-detector`, `cryptography`, `uvicorn`

**Spec:** `docs/superpowers/specs/2026-03-19-sp1-mcp-core-engine-design.md`

**CRITICAL RULE:** Every new code path MUST check `FeatureFlag.is_enabled(key, client)`. If flag is off for a client — old code runs. Zero impact on clients other than `srtyh`.

---

## File Structure

```
p004_ai_nexelin/
├── MASTER/
│   ├── settings.py                          # MODIFY — add new apps, FIELD_ENCRYPTION_KEY
│   ├── urls.py                              # MODIFY — add new URL includes
│   ├── platform/                            # NEW APP
│   │   ├── __init__.py
│   │   ├── apps.py
│   │   ├── models.py                        # PlatformDefaults, FeatureFlag, SystemMessage
│   │   ├── fields.py                        # EncryptedJSONField
│   │   ├── language.py                      # detect_language() with lingua
│   │   ├── admin.py
│   │   ├── signals.py                       # FeatureFlag cache invalidation
│   │   ├── migrations/
│   │   │   ├── 0001_initial.py
│   │   │   ├── 0002_seed_platform_defaults.py
│   │   │   ├── 0003_seed_system_messages.py
│   │   │   └── 0004_seed_feature_flags.py
│   │   └── tests/
│   │       ├── __init__.py
│   │       ├── test_models.py
│   │       ├── test_encrypted_field.py
│   │       ├── test_feature_flags.py
│   │       ├── test_system_messages.py
│   │       └── test_language.py
│   ├── tools/                               # NEW APP
│   │   ├── __init__.py
│   │   ├── apps.py
│   │   ├── models.py                        # ToolCard, ToolConnection
│   │   ├── views.py                         # ToolCatalogView, ToolConnectView
│   │   ├── serializers.py
│   │   ├── urls.py
│   │   ├── compat.py                        # Dual-read helpers
│   │   ├── admin.py
│   │   ├── migrations/
│   │   │   ├── 0001_initial.py
│   │   │   ├── 0002_seed_tool_cards.py
│   │   │   └── 0003_migrate_connections.py
│   │   └── tests/
│   │       ├── __init__.py
│   │       ├── test_models.py
│   │       ├── test_views.py
│   │       ├── test_compat.py
│   │       └── test_admin.py
│   ├── agents/                              # NEW APP
│   │   ├── __init__.py
│   │   ├── apps.py
│   │   ├── models.py                        # AgentConfig, AgentSession, AgentLog
│   │   ├── views.py
│   │   ├── serializers.py
│   │   ├── urls.py
│   │   ├── admin.py
│   │   ├── migrations/
│   │   │   ├── 0001_initial.py
│   │   │   └── 0002_create_agent_configs.py
│   │   └── tests/
│   │       ├── __init__.py
│   │       ├── test_models.py
│   │       └── test_views.py
│   └── mcp_hub/                             # NEW APP
│       ├── __init__.py
│       ├── apps.py
│       ├── executor.py                      # MCPExecutor
│       ├── views.py                         # ChatSSEView
│       ├── urls.py
│       ├── builtin/                         # Builtin tool handlers
│       │   ├── __init__.py
│       │   └── rag_search.py
│       └── tests/
│           ├── __init__.py
│           ├── test_executor.py
│           └── test_sse.py
├── conftest.py                              # NEW — pytest fixtures
├── requirements.txt                         # MODIFY — add new deps
└── pyproject.toml                           # existing, no changes needed
```

---

## Task 0: Create clean branch and install dependencies

**Files:**
- Modify: `p004_ai_nexelin/requirements.txt`

- [ ] **Step 1: Create feature branch from dev**

```bash
cd /home/dchuprina/nexelin_web
git checkout dev
git checkout -b feature/sp1-mcp-core-engine
```

- [ ] **Step 2: Add new dependencies to requirements.txt**

Append to `requirements.txt`:
```
lingua-language-detector>=2.0.1
mcp>=1.0.0
cryptography>=42.0.0
uvicorn>=0.30.0
pytest-django>=4.8.0
pytest-asyncio>=0.23.0
factory-boy>=3.3.0
```

- [ ] **Step 3: Install dependencies**

```bash
cd /home/dchuprina/nexelin_web/p004_ai_nexelin
pip install -r requirements.txt
```

- [ ] **Step 4: Commit**

```bash
git add requirements.txt
git commit -m "chore: add SP1 dependencies — mcp, lingua, cryptography, uvicorn, test libs"
```

---

## Task 1: Platform app — EncryptedJSONField

**Files:**
- Create: `MASTER/platform/__init__.py`
- Create: `MASTER/platform/apps.py`
- Create: `MASTER/platform/fields.py`
- Create: `MASTER/platform/tests/__init__.py`
- Create: `MASTER/platform/tests/test_encrypted_field.py`
- Modify: `MASTER/settings.py` (add `FIELD_ENCRYPTION_KEY`)

- [ ] **Step 1: Create platform app directory structure**

```bash
cd /home/dchuprina/nexelin_web/p004_ai_nexelin
mkdir -p MASTER/platform/tests MASTER/platform/migrations
touch MASTER/platform/__init__.py MASTER/platform/tests/__init__.py MASTER/platform/migrations/__init__.py
```

- [ ] **Step 2: Write apps.py**

```python
# MASTER/platform/apps.py
from django.apps import AppConfig

class PlatformConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'MASTER.platform'
    verbose_name = 'Platform'

    def ready(self):
        import MASTER.platform.signals  # noqa
```

- [ ] **Step 3: Write the failing test for EncryptedJSONField**

```python
# MASTER/platform/tests/test_encrypted_field.py
import pytest
from MASTER.platform.fields import EncryptedJSONField

@pytest.mark.django_db
class TestEncryptedJSONField:
    def test_round_trip(self):
        field = EncryptedJSONField()
        original = {'token': 'secret_abc123', 'nested': {'key': 'value'}}
        encrypted = field.get_prep_value(original)
        # Encrypted value should be a string, not the original dict
        assert isinstance(encrypted, str)
        assert 'secret_abc123' not in encrypted
        # Decrypt should return original
        decrypted = field.from_db_value(encrypted, None, None)
        assert decrypted == original

    def test_none_handling(self):
        field = EncryptedJSONField()
        assert field.get_prep_value(None) is None
        assert field.from_db_value(None, None, None) == {}

    def test_empty_dict(self):
        field = EncryptedJSONField()
        encrypted = field.get_prep_value({})
        decrypted = field.from_db_value(encrypted, None, None)
        assert decrypted == {}
```

- [ ] **Step 4: Add FIELD_ENCRYPTION_KEY to settings.py**

Add after existing env vars in `MASTER/settings.py`:
```python
FIELD_ENCRYPTION_KEY = env('FIELD_ENCRYPTION_KEY', default='ZmFrZS1rZXktZm9yLWRldmVsb3BtZW50LW9ubHk=')
```

Also add to INSTALLED_APPS:
```python
"MASTER.platform",
```

- [ ] **Step 5: Create conftest.py with basic fixtures**

```python
# p004_ai_nexelin/conftest.py
import pytest
from django.conf import settings

@pytest.fixture(autouse=True)
def _use_test_encryption_key(settings):
    """Use a stable test key for EncryptedJSONField."""
    from cryptography.fernet import Fernet
    settings.FIELD_ENCRYPTION_KEY = Fernet.generate_key().decode()
```

- [ ] **Step 6: Run test to verify it fails**

```bash
cd /home/dchuprina/nexelin_web/p004_ai_nexelin
python -m pytest MASTER/platform/tests/test_encrypted_field.py -v
```
Expected: FAIL — `ImportError: cannot import name 'EncryptedJSONField'`

- [ ] **Step 7: Implement EncryptedJSONField**

```python
# MASTER/platform/fields.py
from cryptography.fernet import Fernet
from django.conf import settings
from django.db import models
import json


class EncryptedJSONField(models.TextField):
    """Stores JSON data encrypted at rest with Fernet symmetric encryption."""

    def get_prep_value(self, value):
        if value is None:
            return None
        f = Fernet(settings.FIELD_ENCRYPTION_KEY.encode()
                   if isinstance(settings.FIELD_ENCRYPTION_KEY, str)
                   else settings.FIELD_ENCRYPTION_KEY)
        return f.encrypt(json.dumps(value).encode()).decode()

    def from_db_value(self, value, expression, connection):
        if value is None:
            return {}
        f = Fernet(settings.FIELD_ENCRYPTION_KEY.encode()
                   if isinstance(settings.FIELD_ENCRYPTION_KEY, str)
                   else settings.FIELD_ENCRYPTION_KEY)
        return json.loads(f.decrypt(value.encode()).decode())

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        return name, path, args, kwargs
```

- [ ] **Step 8: Run test to verify it passes**

```bash
python -m pytest MASTER/platform/tests/test_encrypted_field.py -v
```
Expected: 3 PASSED

- [ ] **Step 9: Commit**

```bash
git add MASTER/platform/ MASTER/settings.py conftest.py
git commit -m "feat(platform): add EncryptedJSONField with Fernet encryption"
```

---

## Task 2: Platform app — PlatformDefaults model

**Files:**
- Create: `MASTER/platform/models.py`
- Create: `MASTER/platform/tests/test_models.py`
- Create: `MASTER/platform/admin.py`

- [ ] **Step 1: Write the failing test**

```python
# MASTER/platform/tests/test_models.py
import pytest
from MASTER.platform.models import PlatformDefaults

@pytest.mark.django_db
class TestPlatformDefaults:
    def test_singleton_get_creates_if_missing(self):
        assert PlatformDefaults.objects.count() == 0
        defaults = PlatformDefaults.get()
        assert defaults.pk == 1
        assert PlatformDefaults.objects.count() == 1

    def test_singleton_get_returns_existing(self):
        PlatformDefaults.objects.create(pk=1)
        defaults = PlatformDefaults.get()
        assert defaults.pk == 1
        assert PlatformDefaults.objects.count() == 1

    def test_save_always_pk_1(self):
        d = PlatformDefaults()
        d.save()
        assert d.pk == 1
        d2 = PlatformDefaults()
        d2.save()
        assert d2.pk == 1
        assert PlatformDefaults.objects.count() == 1
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest MASTER/platform/tests/test_models.py::TestPlatformDefaults -v
```
Expected: FAIL — `ImportError`

- [ ] **Step 3: Implement PlatformDefaults model**

```python
# MASTER/platform/models.py
from django.db import models


class PlatformDefaults(models.Model):
    """Singleton. All platform default values. Admin edits. Zero hardcode."""

    class Meta:
        verbose_name = 'Platform Defaults'
        verbose_name_plural = 'Platform Defaults'

    # LLM — null = not configured yet
    default_llm_provider = models.ForeignKey(
        'EmbeddingModel.LLMProvider', on_delete=models.SET_NULL, null=True, blank=True)
    default_embedding_model = models.ForeignKey(
        'EmbeddingModel.EmbeddingModel', on_delete=models.SET_NULL, null=True, blank=True)
    default_temperature = models.FloatField(null=True, blank=True)
    default_max_tokens = models.IntegerField(null=True, blank=True)

    # RAG
    default_similarity_threshold = models.FloatField(null=True, blank=True)
    default_max_context_chunks = models.IntegerField(null=True, blank=True)
    default_top_k = models.IntegerField(null=True, blank=True)

    # Language
    supported_languages = models.JSONField(default=list, blank=True)
    default_language = models.CharField(max_length=5, blank=True)
    language_detection_method = models.CharField(
        max_length=20,
        choices=[
            ('llm', 'LLM-based'),
            ('library', 'lingua-py'),
            ('none', 'Disabled'),
        ],
        blank=True,
    )

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

    def __str__(self):
        return 'Platform Defaults'
```

- [ ] **Step 4: Create and run migrations**

```bash
cd /home/dchuprina/nexelin_web/p004_ai_nexelin
python MASTER/manage.py makemigrations platform
python -m pytest MASTER/platform/tests/test_models.py::TestPlatformDefaults -v
```
Expected: 3 PASSED

- [ ] **Step 5: Write admin**

```python
# MASTER/platform/admin.py
from django.contrib import admin
from .models import PlatformDefaults


@admin.register(PlatformDefaults)
class PlatformDefaultsAdmin(admin.ModelAdmin):
    fieldsets = (
        ('LLM', {
            'fields': ('default_llm_provider', 'default_embedding_model',
                       'default_temperature', 'default_max_tokens'),
        }),
        ('RAG', {
            'fields': ('default_similarity_threshold', 'default_max_context_chunks',
                       'default_top_k'),
        }),
        ('Language', {
            'fields': ('supported_languages', 'default_language',
                       'language_detection_method'),
        }),
        ('Agent', {
            'fields': ('default_greeting',),
        }),
    )

    def has_add_permission(self, request):
        return not PlatformDefaults.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
```

- [ ] **Step 6: Create empty signals.py (needed by apps.py ready())**

```python
# MASTER/platform/signals.py
# Signals registered here. Populated in Task 3.
```

- [ ] **Step 7: Commit**

```bash
git add MASTER/platform/
git commit -m "feat(platform): add PlatformDefaults singleton model + admin"
```

---

## Task 3: Platform app — FeatureFlag model

**Files:**
- Modify: `MASTER/platform/models.py`
- Modify: `MASTER/platform/admin.py`
- Modify: `MASTER/platform/signals.py`
- Create: `MASTER/platform/tests/test_feature_flags.py`

- [ ] **Step 1: Write the failing tests**

```python
# MASTER/platform/tests/test_feature_flags.py
import pytest
from django.core.cache import cache
from MASTER.platform.models import FeatureFlag

@pytest.fixture
def client_obj(db):
    from MASTER.clients.models import Client
    return Client.objects.create(
        user='test', description='test', api_key='rag_test_key_001',
        tag='test-client')

@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield
    cache.clear()

@pytest.mark.django_db
class TestFeatureFlag:
    def test_unknown_flag_returns_false(self, client_obj):
        assert FeatureFlag.is_enabled('nonexistent', client_obj) is False

    def test_rollout_off(self, client_obj):
        FeatureFlag.objects.create(key='test_flag', rollout='off')
        assert FeatureFlag.is_enabled('test_flag', client_obj) is False

    def test_rollout_all(self, client_obj):
        FeatureFlag.objects.create(key='test_flag', rollout='all')
        assert FeatureFlag.is_enabled('test_flag', client_obj) is True

    def test_rollout_selected_not_in_list(self, client_obj):
        flag = FeatureFlag.objects.create(key='test_flag', rollout='selected')
        assert FeatureFlag.is_enabled('test_flag', client_obj) is False

    def test_rollout_selected_in_list(self, client_obj):
        flag = FeatureFlag.objects.create(key='test_flag', rollout='selected')
        flag.enabled_clients.add(client_obj)
        cache.clear()  # clear stale cache
        assert FeatureFlag.is_enabled('test_flag', client_obj) is True

    def test_result_is_cached(self, client_obj):
        FeatureFlag.objects.create(key='test_flag', rollout='all')
        # First call hits DB
        assert FeatureFlag.is_enabled('test_flag', client_obj) is True
        # Delete from DB — cached result should still return True
        FeatureFlag.objects.all().delete()
        assert FeatureFlag.is_enabled('test_flag', client_obj) is True

    def test_cache_invalidated_on_save(self, client_obj):
        flag = FeatureFlag.objects.create(key='test_flag', rollout='all')
        assert FeatureFlag.is_enabled('test_flag', client_obj) is True
        # Change rollout — signal should clear cache
        flag.rollout = 'off'
        flag.save()
        assert FeatureFlag.is_enabled('test_flag', client_obj) is False
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest MASTER/platform/tests/test_feature_flags.py -v
```
Expected: FAIL — `ImportError: cannot import name 'FeatureFlag'`

- [ ] **Step 3: Add FeatureFlag model to models.py**

Append to `MASTER/platform/models.py`:

```python
class FeatureFlag(models.Model):
    """Per-client feature toggles. Test on srtyh, rollout to all."""

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

    def __str__(self):
        return f'{self.key} ({self.rollout})'

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

- [ ] **Step 4: Add cache invalidation signal**

```python
# MASTER/platform/signals.py
from django.core.cache import cache
from django.db.models.signals import post_save, m2m_changed


def invalidate_feature_flag_cache(sender, instance, **kwargs):
    """Clear all cache entries for this flag on any change."""
    # Delete pattern not available in all cache backends — delete known keys
    # For production, iterate enabled_clients + clear global
    from MASTER.clients.models import Client
    for client_pk in Client.objects.values_list('pk', flat=True):
        cache.delete(f'ff:{instance.key}:{client_pk}')
    cache.delete(f'ff:{instance.key}:global')


def invalidate_feature_flag_m2m(sender, instance, **kwargs):
    invalidate_feature_flag_cache(sender, instance, **kwargs)


def connect_signals():
    from MASTER.platform.models import FeatureFlag
    post_save.connect(invalidate_feature_flag_cache, sender=FeatureFlag)
    m2m_changed.connect(invalidate_feature_flag_m2m,
                        sender=FeatureFlag.enabled_clients.through)


connect_signals()
```

- [ ] **Step 5: Run migrations and tests**

```bash
python MASTER/manage.py makemigrations platform
python -m pytest MASTER/platform/tests/test_feature_flags.py -v
```
Expected: 7 PASSED

- [ ] **Step 6: Add FeatureFlag to admin**

Append to `MASTER/platform/admin.py`:

```python
from .models import PlatformDefaults, FeatureFlag

@admin.register(FeatureFlag)
class FeatureFlagAdmin(admin.ModelAdmin):
    list_display = ['key', 'rollout', 'client_list', 'updated_at']
    list_filter = ['rollout']
    list_editable = ['rollout']
    search_fields = ['key', 'description']
    filter_horizontal = ['enabled_clients']

    def client_list(self, obj):
        if obj.rollout == 'all':
            return 'ALL'
        if obj.rollout == 'off':
            return '—'
        clients = obj.enabled_clients.values_list('tag', flat=True)[:5]
        return ', '.join(c or '?' for c in clients)
    client_list.short_description = 'Clients'
```

- [ ] **Step 7: Commit**

```bash
git add MASTER/platform/
git commit -m "feat(platform): add FeatureFlag model with cache + invalidation signal"
```

---

## Task 4: Platform app — SystemMessage model

**Files:**
- Modify: `MASTER/platform/models.py`
- Modify: `MASTER/platform/admin.py`
- Create: `MASTER/platform/tests/test_system_messages.py`

- [ ] **Step 1: Write the failing tests**

```python
# MASTER/platform/tests/test_system_messages.py
import pytest
from django.core.cache import cache
from MASTER.platform.models import SystemMessage

@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield
    cache.clear()

@pytest.mark.django_db
class TestSystemMessage:
    def test_get_existing_key(self):
        SystemMessage.objects.create(
            key='chat.timeout',
            translations={'en': 'Session timed out', 'de': 'Sitzung abgelaufen'})
        assert SystemMessage.get('chat.timeout', 'en') == 'Session timed out'
        assert SystemMessage.get('chat.timeout', 'de') == 'Sitzung abgelaufen'

    def test_get_fallback_to_english(self):
        SystemMessage.objects.create(
            key='chat.timeout',
            translations={'en': 'Session timed out'})
        assert SystemMessage.get('chat.timeout', 'fr') == 'Session timed out'

    def test_get_missing_key_returns_empty(self):
        assert SystemMessage.get('nonexistent', 'en') == ''

    def test_result_is_cached(self):
        SystemMessage.objects.create(key='test', translations={'en': 'hello'})
        assert SystemMessage.get('test', 'en') == 'hello'
        SystemMessage.objects.all().delete()
        # Still cached
        assert SystemMessage.get('test', 'en') == 'hello'
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest MASTER/platform/tests/test_system_messages.py -v
```
Expected: FAIL

- [ ] **Step 3: Add SystemMessage model**

Append to `MASTER/platform/models.py`:

```python
class SystemMessage(models.Model):
    """All UI/system translated strings. Admin edits. Cached."""

    key = models.CharField(max_length=100, unique=True, db_index=True)
    translations = models.JSONField(
        default=dict, help_text='{"en": "Text", "de": "Text"}')
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['key']

    def __str__(self):
        return self.key

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

- [ ] **Step 4: Run migrations and tests**

```bash
python MASTER/manage.py makemigrations platform
python -m pytest MASTER/platform/tests/test_system_messages.py -v
```
Expected: 4 PASSED

- [ ] **Step 5: Add SystemMessage admin**

Append to `MASTER/platform/admin.py`:

```python
from .models import PlatformDefaults, FeatureFlag, SystemMessage

@admin.register(SystemMessage)
class SystemMessageAdmin(admin.ModelAdmin):
    list_display = ['key', 'preview_en', 'languages_count', 'description']
    search_fields = ['key', 'description']

    def preview_en(self, obj):
        text = obj.translations.get('en', '')
        return (text[:60] + '...') if len(text) > 60 else text

    def languages_count(self, obj):
        return len(obj.translations)
```

- [ ] **Step 6: Commit**

```bash
git add MASTER/platform/
git commit -m "feat(platform): add SystemMessage model with translations + cache"
```

---

## Task 5: Platform app — Language detection

**Files:**
- Create: `MASTER/platform/language.py`
- Create: `MASTER/platform/tests/test_language.py`

- [ ] **Step 1: Write the failing tests**

```python
# MASTER/platform/tests/test_language.py
import pytest
from MASTER.platform.language import detect_language

class TestLanguageDetection:
    def test_english(self):
        assert detect_language('Hello, how are you doing today?') == 'en'

    def test_german(self):
        assert detect_language('Guten Tag, wie geht es Ihnen?') == 'de'

    def test_french(self):
        assert detect_language('Bonjour, comment allez-vous aujourd\'hui?') == 'fr'

    def test_short_text_returns_fallback(self):
        assert detect_language('hi', fallback='de') == 'de'

    def test_empty_returns_fallback(self):
        assert detect_language('', fallback='en') == 'en'

    def test_none_returns_fallback(self):
        assert detect_language(None, fallback='en') == 'en'
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest MASTER/platform/tests/test_language.py -v
```
Expected: FAIL

- [ ] **Step 3: Implement language detection**

```python
# MASTER/platform/language.py
from lingua import Language, LanguageDetectorBuilder

# Map ISO 639-1 codes to lingua Language enum
_CODE_TO_LINGUA = {
    'en': Language.ENGLISH,
    'de': Language.GERMAN,
    'fr': Language.FRENCH,
    'es': Language.SPANISH,
    'it': Language.ITALIAN,
    'nl': Language.DUTCH,
    'da': Language.DANISH,
}

# Reverse mapping
_LINGUA_TO_CODE = {v: k for k, v in _CODE_TO_LINGUA.items()}

# Build detector once with all supported languages
_detector = LanguageDetectorBuilder.from_languages(
    *_CODE_TO_LINGUA.values()
).build()


def detect_language(text: str, fallback: str = 'en') -> str:
    """Detect language from text. Returns ISO 639-1 code.
    Short text (<4 chars) or undetectable → fallback."""
    if not text or len(text.strip()) < 4:
        return fallback
    result = _detector.detect_language_of(text.strip())
    if result is None:
        return fallback
    return _LINGUA_TO_CODE.get(result, fallback)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest MASTER/platform/tests/test_language.py -v
```
Expected: 6 PASSED

- [ ] **Step 5: Commit**

```bash
git add MASTER/platform/language.py MASTER/platform/tests/test_language.py
git commit -m "feat(platform): add lingua-based language detection"
```

---

## Task 6: Platform app — Seed data migrations

**Files:**
- Create: `MASTER/platform/migrations/0002_seed_platform_defaults.py`
- Create: `MASTER/platform/migrations/0003_seed_system_messages.py`
- Create: `MASTER/platform/migrations/0004_seed_feature_flags.py`

- [ ] **Step 1: Create seed migration for PlatformDefaults**

```python
# MASTER/platform/migrations/0002_seed_platform_defaults.py
from django.db import migrations

def forward(apps, schema_editor):
    PlatformDefaults = apps.get_model('platform', 'PlatformDefaults')
    PlatformDefaults.objects.get_or_create(
        pk=1,
        defaults={
            'default_temperature': 0.7,
            'default_max_tokens': 2000,
            'default_similarity_threshold': 0.1,
            'default_max_context_chunks': 5,
            'default_top_k': 5,
            'supported_languages': ['en', 'de', 'fr', 'es', 'it', 'nl', 'da'],
            'default_language': 'en',
            'language_detection_method': 'library',
            'default_greeting': '',
        },
    )

def reverse(apps, schema_editor):
    PlatformDefaults = apps.get_model('platform', 'PlatformDefaults')
    PlatformDefaults.objects.filter(pk=1).delete()

class Migration(migrations.Migration):
    dependencies = [('platform', '0001_initial')]
    operations = [migrations.RunPython(forward, reverse)]
```

- [ ] **Step 2: Create seed migration for SystemMessages**

```python
# MASTER/platform/migrations/0003_seed_system_messages.py
from django.db import migrations

MESSAGES = [
    ('chat.timeout', 'Shown when chat session times out', {
        'en': 'Session timed out. Please start a new conversation.',
        'de': 'Sitzung abgelaufen. Bitte starten Sie eine neue Konversation.',
        'fr': 'Session expirée. Veuillez démarrer une nouvelle conversation.',
        'es': 'Sesión expirada. Por favor, inicie una nueva conversación.',
        'it': 'Sessione scaduta. Si prega di iniziare una nuova conversazione.',
        'nl': 'Sessie verlopen. Start een nieuw gesprek.',
        'da': 'Session udløbet. Start venligst en ny samtale.',
    }),
    ('chat.waiting', 'Shown while AI is processing', {
        'en': 'Please wait...',
        'de': 'Bitte warten...',
        'fr': 'Veuillez patienter...',
        'es': 'Por favor, espere...',
        'it': 'Attendere prego...',
        'nl': 'Even geduld...',
        'da': 'Vent venligst...',
    }),
    ('chat.escalation', 'Shown when escalating to manager', {
        'en': 'Connecting you to a manager...',
        'de': 'Verbinde Sie mit einem Manager...',
        'fr': 'Connexion avec un responsable...',
        'es': 'Conectando con un gerente...',
        'it': 'Collegamento con un responsabile...',
        'nl': 'Verbinden met een manager...',
        'da': 'Forbinder dig med en leder...',
    }),
    ('chat.greeting_default', 'Default greeting when none configured', {
        'en': 'Hello! How can I help you?',
        'de': 'Hallo! Wie kann ich Ihnen helfen?',
        'fr': 'Bonjour! Comment puis-je vous aider?',
        'es': '¡Hola! ¿Cómo puedo ayudarle?',
        'it': 'Ciao! Come posso aiutarti?',
        'nl': 'Hallo! Hoe kan ik u helpen?',
        'da': 'Hej! Hvordan kan jeg hjælpe dig?',
    }),
    ('chat.no_answer', 'When AI cannot find relevant information', {
        'en': 'I don\'t have enough information to answer this question.',
        'de': 'Ich habe nicht genug Informationen, um diese Frage zu beantworten.',
        'fr': 'Je n\'ai pas assez d\'informations pour répondre à cette question.',
        'es': 'No tengo suficiente información para responder a esta pregunta.',
        'it': 'Non ho abbastanza informazioni per rispondere a questa domanda.',
        'nl': 'Ik heb niet genoeg informatie om deze vraag te beantwoorden.',
        'da': 'Jeg har ikke nok information til at besvare dette spørgsmål.',
    }),
]

def forward(apps, schema_editor):
    SystemMessage = apps.get_model('platform', 'SystemMessage')
    for key, desc, translations in MESSAGES:
        SystemMessage.objects.get_or_create(
            key=key, defaults={'description': desc, 'translations': translations})

def reverse(apps, schema_editor):
    SystemMessage = apps.get_model('platform', 'SystemMessage')
    keys = [m[0] for m in MESSAGES]
    SystemMessage.objects.filter(key__in=keys).delete()

class Migration(migrations.Migration):
    dependencies = [('platform', '0002_seed_platform_defaults')]
    operations = [migrations.RunPython(forward, reverse)]
```

- [ ] **Step 3: Create seed migration for FeatureFlags**

```python
# MASTER/platform/migrations/0004_seed_feature_flags.py
from django.db import migrations

FLAGS = [
    ('mcp_tools_dashboard', 'New tools dashboard UI'),
    ('mcp_agent_config', 'New AgentConfig instead of Client fields'),
    ('mcp_sse_streaming', 'SSE streaming for chat'),
    ('language_detection_v2', 'lingua-py instead of word lists'),
    ('system_messages', 'SystemMessage instead of hardcoded strings'),
]

def forward(apps, schema_editor):
    FeatureFlag = apps.get_model('platform', 'FeatureFlag')
    for key, desc in FLAGS:
        FeatureFlag.objects.get_or_create(
            key=key, defaults={'description': desc, 'rollout': 'off'})

def reverse(apps, schema_editor):
    FeatureFlag = apps.get_model('platform', 'FeatureFlag')
    keys = [f[0] for f in FLAGS]
    FeatureFlag.objects.filter(key__in=keys).delete()

class Migration(migrations.Migration):
    dependencies = [('platform', '0003_seed_system_messages')]
    operations = [migrations.RunPython(forward, reverse)]
```

- [ ] **Step 4: Run migrations**

```bash
python MASTER/manage.py migrate platform
```

- [ ] **Step 5: Run all platform tests**

```bash
python -m pytest MASTER/platform/tests/ -v
```
Expected: ALL PASSED

- [ ] **Step 6: Commit**

```bash
git add MASTER/platform/migrations/
git commit -m "feat(platform): add seed migrations — defaults, messages, feature flags"
```

---

## Task 7: Tools app — ToolCard and ToolConnection models

**Files:**
- Create: `MASTER/tools/__init__.py`, `apps.py`, `models.py`
- Create: `MASTER/tools/tests/test_models.py`
- Create: `MASTER/tools/admin.py`
- Modify: `MASTER/settings.py` (add to INSTALLED_APPS)

- [ ] **Step 1: Create tools app directory structure**

```bash
mkdir -p MASTER/tools/tests MASTER/tools/migrations
touch MASTER/tools/__init__.py MASTER/tools/tests/__init__.py MASTER/tools/migrations/__init__.py
```

- [ ] **Step 2: Write apps.py**

```python
# MASTER/tools/apps.py
from django.apps import AppConfig

class ToolsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'MASTER.tools'
    verbose_name = 'Tools'
```

- [ ] **Step 3: Add to INSTALLED_APPS in settings.py**

Add `"MASTER.tools",` after `"MASTER.platform",`

- [ ] **Step 4: Write failing tests**

```python
# MASTER/tools/tests/test_models.py
import pytest
from MASTER.tools.models import ToolCard, ToolConnection

@pytest.fixture
def client_obj(db):
    from MASTER.clients.models import Client
    return Client.objects.create(
        user='test', description='test', api_key='rag_test_tools_001', tag='test-tools')

@pytest.fixture
def tool_card(db):
    return ToolCard.objects.create(
        name='Test Tool', slug='test-tool', tagline='A test tool',
        description='For testing', icon='wrench', color='#000000',
        category='custom', transport_type='builtin', auth_type='none')

@pytest.mark.django_db
class TestToolCard:
    def test_create(self, tool_card):
        assert tool_card.pk is not None
        assert tool_card.slug == 'test-tool'

    def test_ordering(self, db):
        t1 = ToolCard.objects.create(name='B', slug='b', tagline='b', description='b',
            icon='x', color='#000', category='custom', transport_type='builtin',
            auth_type='none', sort_order=2)
        t2 = ToolCard.objects.create(name='A', slug='a', tagline='a', description='a',
            icon='x', color='#000', category='custom', transport_type='builtin',
            auth_type='none', sort_order=1)
        slugs = list(ToolCard.objects.values_list('slug', flat=True))
        assert slugs == ['a', 'b']

@pytest.mark.django_db
class TestToolConnection:
    def test_create_connection(self, client_obj, tool_card):
        conn = ToolConnection.objects.create(
            client=client_obj, tool_card=tool_card,
            status='connected', enabled=True)
        assert conn.pk is not None

    def test_unique_together(self, client_obj, tool_card):
        ToolConnection.objects.create(
            client=client_obj, tool_card=tool_card, status='connected')
        with pytest.raises(Exception):
            ToolConnection.objects.create(
                client=client_obj, tool_card=tool_card, status='connected')

    def test_credentials_encrypted(self, client_obj, tool_card):
        conn = ToolConnection.objects.create(
            client=client_obj, tool_card=tool_card,
            status='connected',
            credentials={'token': 'super_secret_123'})
        # Reload from DB
        conn.refresh_from_db()
        assert conn.credentials == {'token': 'super_secret_123'}
        # Raw DB value should be encrypted (not contain plaintext)
        from django.db import connection as db_conn
        with db_conn.cursor() as cursor:
            cursor.execute(
                'SELECT credentials FROM tools_toolconnection WHERE id = %s',
                [conn.pk])
            raw = cursor.fetchone()[0]
            assert 'super_secret_123' not in raw
```

- [ ] **Step 5: Run test to verify it fails**

```bash
python -m pytest MASTER/tools/tests/test_models.py -v
```
Expected: FAIL

- [ ] **Step 6: Implement models**

```python
# MASTER/tools/models.py
from django.db import models
from MASTER.platform.fields import EncryptedJSONField


class ToolCard(models.Model):
    """Tool catalog entry. Admin creates. Client sees as card on dashboard."""

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

    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    tagline = models.CharField(max_length=200)
    description = models.TextField()
    icon = models.CharField(max_length=50)
    color = models.CharField(max_length=7)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)

    mcp_server_url = models.CharField(max_length=500, blank=True)
    transport_type = models.CharField(max_length=20, choices=TRANSPORT_CHOICES)
    is_builtin = models.BooleanField(default=False)
    builtin_handler = models.CharField(max_length=200, blank=True)
    tools_schema = models.JSONField(default=list, blank=True)

    auth_type = models.CharField(max_length=20, choices=AUTH_TYPE_CHOICES)
    auth_config = models.JSONField(default=dict, blank=True)

    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    sort_order = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['sort_order', 'name']

    def __str__(self):
        return self.name


class ToolConnection(models.Model):
    """Client connected a tool. Credentials encrypted at rest."""

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

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    credentials = EncryptedJSONField(default=dict, blank=True)
    config = models.JSONField(default=dict, blank=True)
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

    def __str__(self):
        return f'{self.client} — {self.tool_card.name} ({self.status})'
```

- [ ] **Step 7: Run migrations and tests**

```bash
python MASTER/manage.py makemigrations tools
python -m pytest MASTER/tools/tests/test_models.py -v
```
Expected: 5 PASSED

- [ ] **Step 8: Write admin**

```python
# MASTER/tools/admin.py
from django.contrib import admin
from .models import ToolCard, ToolConnection


@admin.register(ToolCard)
class ToolCardAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'transport_type', 'auth_type',
                    'is_builtin', 'is_active', 'connections_count']
    list_filter = ['category', 'transport_type', 'is_builtin', 'is_active']
    list_editable = ['is_active']
    search_fields = ['name', 'slug', 'description']
    prepopulated_fields = {'slug': ('name',)}

    fieldsets = (
        ('Identity', {
            'fields': ('name', 'slug', 'tagline', 'description', 'icon',
                       'color', 'category', 'is_featured', 'sort_order'),
        }),
        ('MCP Connection', {
            'fields': ('transport_type', 'mcp_server_url', 'is_builtin',
                       'builtin_handler', 'tools_schema'),
            'classes': ('collapse',),
        }),
        ('Auth', {
            'fields': ('auth_type', 'auth_config'),
            'classes': ('collapse',),
        }),
        ('Status', {'fields': ('is_active',)}),
    )

    def connections_count(self, obj):
        connected = obj.connections.filter(status='connected').count()
        total = obj.connections.count()
        return f'{connected}/{total}'
    connections_count.short_description = 'Connected/Total'


@admin.register(ToolConnection)
class ToolConnectionAdmin(admin.ModelAdmin):
    list_display = ['client_name', 'tool_name', 'status', 'enabled',
                    'connected_at', 'last_used_at', 'error_count']
    list_filter = ['status', 'enabled', 'tool_card', 'tool_card__category']
    list_editable = ['enabled', 'status']
    search_fields = ['client__company_name', 'client__tag', 'tool_card__name']
    raw_id_fields = ['client']
    actions = ['enable_selected', 'disable_selected', 'disconnect_selected', 'reset_errors']

    def client_name(self, obj):
        return obj.client.company_name or obj.client.tag
    client_name.short_description = 'Client'

    def tool_name(self, obj):
        return obj.tool_card.name
    tool_name.short_description = 'Tool'

    @admin.action(description='Enable selected')
    def enable_selected(self, request, queryset):
        queryset.update(enabled=True)

    @admin.action(description='Disable selected')
    def disable_selected(self, request, queryset):
        queryset.update(enabled=False)

    @admin.action(description='Disconnect selected')
    def disconnect_selected(self, request, queryset):
        queryset.update(status='disconnected', enabled=False)

    @admin.action(description='Reset errors')
    def reset_errors(self, request, queryset):
        queryset.update(error_count=0, last_error='', status='connected')
```

- [ ] **Step 9: Commit**

```bash
git add MASTER/tools/ MASTER/settings.py
git commit -m "feat(tools): add ToolCard + ToolConnection models with encrypted credentials"
```

---

## Task 8: Tools app — Seed ToolCards + migrate existing connections

**Files:**
- Create: `MASTER/tools/migrations/0002_seed_tool_cards.py`
- Create: `MASTER/tools/migrations/0003_migrate_connections.py`

- [ ] **Step 1: Create seed ToolCards migration**

Create `MASTER/tools/migrations/0002_seed_tool_cards.py` with the 7 builtin tools from the spec (whatsapp-meta, telegram, email-smtp, whatsapp-bridge, web-widget, hitl-matrix, rag-search). Use the full auth_config fields from the spec document section "Секція 8".

- [ ] **Step 2: Create data migration for existing Client connections**

Create `MASTER/tools/migrations/0003_migrate_connections.py` — iterate all Clients, create ToolConnection records from existing Client fields (whatsapp_meta_enabled → whatsapp-meta, telegram_enabled → telegram, etc). Both forward and reverse functions. Use the mapping from the spec.

- [ ] **Step 3: Run migrations**

```bash
python MASTER/manage.py migrate tools
```

- [ ] **Step 4: Commit**

```bash
git add MASTER/tools/migrations/
git commit -m "feat(tools): seed 7 builtin ToolCards + migrate existing connections"
```

---

## Task 9: Tools app — Dual-read compat layer

**Files:**
- Create: `MASTER/tools/compat.py`
- Create: `MASTER/tools/tests/test_compat.py`

- [ ] **Step 1: Write failing tests**

```python
# MASTER/tools/tests/test_compat.py
import pytest
from django.core.cache import cache
from MASTER.tools.compat import get_credentials, is_tool_connected
from MASTER.tools.models import ToolCard, ToolConnection
from MASTER.platform.models import FeatureFlag

@pytest.fixture
def client_obj(db):
    from MASTER.clients.models import Client
    c = Client.objects.create(
        user='test', description='test', api_key='rag_compat_001', tag='compat-test',
        telegram_enabled=True, telegram_bot_token='old_bot_token_123')
    return c

@pytest.fixture
def telegram_card(db):
    return ToolCard.objects.create(
        name='Telegram', slug='telegram', tagline='t', description='t',
        icon='send', color='#000', category='communication',
        transport_type='builtin', auth_type='api_key')

@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield
    cache.clear()

@pytest.mark.django_db
class TestCompat:
    def test_fallback_to_client_field_when_flag_off(self, client_obj):
        """Flag off → reads from old Client field."""
        assert get_credentials(client_obj, 'telegram', 'bot_token') == 'old_bot_token_123'

    def test_reads_from_tool_connection_when_flag_on(self, client_obj, telegram_card):
        """Flag on → reads from ToolConnection."""
        flag = FeatureFlag.objects.create(key='mcp_agent_config', rollout='selected')
        flag.enabled_clients.add(client_obj)
        cache.clear()
        ToolConnection.objects.create(
            client=client_obj, tool_card=telegram_card,
            status='connected', credentials={'bot_token': 'new_token_456'})
        assert get_credentials(client_obj, 'telegram', 'bot_token') == 'new_token_456'

    def test_is_tool_connected_fallback(self, client_obj):
        assert is_tool_connected(client_obj, 'telegram') is True
        assert is_tool_connected(client_obj, 'whatsapp-meta') is False

    def test_is_tool_connected_with_flag(self, client_obj, telegram_card):
        flag = FeatureFlag.objects.create(key='mcp_agent_config', rollout='selected')
        flag.enabled_clients.add(client_obj)
        cache.clear()
        # No ToolConnection yet
        assert is_tool_connected(client_obj, 'telegram') is False
        # Add connection
        ToolConnection.objects.create(
            client=client_obj, tool_card=telegram_card,
            status='connected', enabled=True)
        assert is_tool_connected(client_obj, 'telegram') is True
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest MASTER/tools/tests/test_compat.py -v
```

- [ ] **Step 3: Implement compat.py**

```python
# MASTER/tools/compat.py
from MASTER.platform.models import FeatureFlag


FIELD_MAP = {
    ('whatsapp-meta', 'waba_id'): 'meta_waba_id',
    ('whatsapp-meta', 'app_id'): 'meta_app_id',
    ('whatsapp-meta', 'app_secret'): 'meta_app_secret',
    ('whatsapp-meta', 'access_token'): 'meta_access_token',
    ('whatsapp-meta', 'phone_number_id'): 'meta_phone_number_id',
    ('whatsapp-meta', 'verify_token'): 'meta_verify_token',
    ('whatsapp-meta', 'phone_number'): 'meta_phone_number',
    ('telegram', 'bot_token'): 'telegram_bot_token',
    ('email-smtp', 'smtp_host'): 'email_smtp_host',
    ('email-smtp', 'smtp_port'): 'email_smtp_port',
    ('email-smtp', 'username'): 'email_smtp_username',
    ('email-smtp', 'password'): 'email_smtp_password',
    ('email-smtp', 'from_address'): 'email_from_address',
    ('email-smtp', 'from_name'): 'email_from_name',
    ('email-smtp', 'use_tls'): 'email_smtp_use_tls',
    ('whatsapp-bridge', 'phone'): 'whatsapp_bridge_phone',
    ('whatsapp-bridge', 'matrix_user_id'): 'whatsapp_bridge_matrix_user_id',
    ('whatsapp-bridge', 'matrix_access_token'): 'whatsapp_bridge_matrix_access_token',
    ('hitl-matrix', 'manager_user_ids'): 'matrix_manager_user_ids',
    ('hitl-matrix', 'homeserver_url'): 'matrix_homeserver_url',
}

ENABLED_MAP = {
    'whatsapp-meta': 'whatsapp_meta_enabled',
    'telegram': 'telegram_enabled',
    'email-smtp': 'email_smtp_enabled',
    'whatsapp-bridge': 'whatsapp_bridge_enabled',
    'web-widget': 'widget_enabled',
    'hitl-matrix': 'matrix_hitl_enabled',
}


def get_credentials(client, tool_slug: str, field: str, default=''):
    if FeatureFlag.is_enabled('mcp_agent_config', client):
        from MASTER.tools.models import ToolConnection
        connection = ToolConnection.objects.filter(
            client=client, tool_card__slug=tool_slug, status='connected'
        ).first()
        if connection:
            return connection.credentials.get(field, default)
    old_field = FIELD_MAP.get((tool_slug, field))
    if old_field:
        return getattr(client, old_field, default)
    return default


def is_tool_connected(client, tool_slug: str) -> bool:
    if FeatureFlag.is_enabled('mcp_agent_config', client):
        from MASTER.tools.models import ToolConnection
        return ToolConnection.objects.filter(
            client=client, tool_card__slug=tool_slug,
            status='connected', enabled=True,
        ).exists()
    old_field = ENABLED_MAP.get(tool_slug)
    if old_field:
        return bool(getattr(client, old_field, False))
    return False
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest MASTER/tools/tests/test_compat.py -v
```
Expected: 4 PASSED

- [ ] **Step 5: Commit**

```bash
git add MASTER/tools/compat.py MASTER/tools/tests/test_compat.py
git commit -m "feat(tools): add dual-read compat layer with FeatureFlag gating"
```

---

## Task 10: Tools app — API views (catalog, connect, disconnect)

**Files:**
- Create: `MASTER/tools/serializers.py`
- Create: `MASTER/tools/views.py`
- Create: `MASTER/tools/urls.py`
- Create: `MASTER/tools/tests/test_views.py`
- Modify: `MASTER/urls.py`

- [ ] **Step 1: Write failing tests**

Tests for `GET /api/tools/catalog/` and `POST /api/tools/{slug}/connect/` — test that catalog returns tools with connection status, connect creates ToolConnection. Use DRF's `APIClient`.

- [ ] **Step 2: Implement serializers, views, urls**

- `ToolCatalogView` — GET returns all active ToolCards with connection status for requesting client
- `ToolConnectView` — POST validates credentials per auth_config, creates/updates ToolConnection
- `ToolDisconnectView` — POST sets status='disconnected'
- `ToolStatusView` — GET returns connection status
- `MyToolsView` — GET returns client's connected tools

- [ ] **Step 3: Add URL include to MASTER/urls.py**

```python
path('api/tools/', include('MASTER.tools.urls')),
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest MASTER/tools/tests/test_views.py -v
```

- [ ] **Step 5: Commit**

```bash
git add MASTER/tools/serializers.py MASTER/tools/views.py MASTER/tools/urls.py MASTER/tools/tests/test_views.py MASTER/urls.py
git commit -m "feat(tools): add catalog/connect/disconnect API endpoints"
```

---

## Task 11: Agents app — AgentConfig, AgentSession, AgentLog models

**Files:**
- Create: `MASTER/agents/__init__.py`, `apps.py`, `models.py`, `admin.py`
- Create: `MASTER/agents/tests/test_models.py`
- Modify: `MASTER/settings.py`

- [ ] **Step 1: Create app structure, apps.py**

- [ ] **Step 2: Write failing tests** — AgentConfig CRUD, param resolution (null → PlatformDefaults), AgentSession, AgentLog

- [ ] **Step 3: Implement models** per spec — AgentConfig (OneToOne Client, all nullable params), AgentSession (UUID pk, channel choices), AgentLog (pending/ok/error/timeout statuses)

- [ ] **Step 4: Run migrations and tests**

- [ ] **Step 5: Write admin** — AgentConfigAdmin with fieldsets, AgentLogAdmin readonly, AgentSession read-only

- [ ] **Step 6: Create data migration** `0002_create_agent_configs.py` — for each Client, create AgentConfig from existing fields (llm_provider_model, embedding_model, custom_system_prompt, greeting_message)

- [ ] **Step 7: Add URL include** `path('api/agents/', include('MASTER.agents.urls'))`

- [ ] **Step 8: Commit**

```bash
git add MASTER/agents/ MASTER/settings.py MASTER/urls.py
git commit -m "feat(agents): add AgentConfig/Session/Log models + data migration"
```

---

## Task 12: MCP Hub — Executor and SSE view

**Files:**
- Create: `MASTER/mcp_hub/__init__.py`, `apps.py`, `executor.py`, `views.py`, `urls.py`
- Create: `MASTER/mcp_hub/builtin/__init__.py`, `rag_search.py`
- Create: `MASTER/mcp_hub/tests/test_executor.py`, `test_sse.py`
- Modify: `MASTER/settings.py`, `MASTER/urls.py`

- [ ] **Step 1: Create app structure**

- [ ] **Step 2: Write failing tests for MCPExecutor** — test builtin handler call, test log creation with pending→ok status, test error handling with pending→error status

- [ ] **Step 3: Implement MCPExecutor** per spec — `call_tool()` with builtin and MCP paths, logging

- [ ] **Step 4: Implement builtin rag_search handler** — wraps existing `MASTER.rag.qdrant_search`

- [ ] **Step 5: Write failing tests for ChatSSEView** — test SSE event format, test feature flag gating

- [ ] **Step 6: Implement ChatSSEView** per spec — StreamingHttpResponse, SSE events, feature flag check

- [ ] **Step 7: Run all tests**

```bash
python -m pytest MASTER/mcp_hub/tests/ -v
```

- [ ] **Step 8: Add URL include and commit**

```bash
git add MASTER/mcp_hub/ MASTER/settings.py MASTER/urls.py
git commit -m "feat(mcp_hub): add MCPExecutor + ChatSSEView with SSE streaming"
```

---

## Task 13: Full integration test + run all tests

**Files:**
- All test files

- [ ] **Step 1: Run complete test suite**

```bash
cd /home/dchuprina/nexelin_web/p004_ai_nexelin
python -m pytest MASTER/platform/tests/ MASTER/tools/tests/ MASTER/agents/tests/ MASTER/mcp_hub/tests/ -v --tb=short
```

- [ ] **Step 2: Run Django check**

```bash
python MASTER/manage.py check
python MASTER/manage.py makemigrations --check --dry-run
```
Expected: No issues, no unapplied migrations

- [ ] **Step 3: Fix any failures**

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "test: full SP1 integration test suite passing"
```

---

## Summary

| Task | What | Files |
|------|------|-------|
| 0 | Branch + deps | requirements.txt |
| 1 | EncryptedJSONField | platform/fields.py |
| 2 | PlatformDefaults | platform/models.py |
| 3 | FeatureFlag | platform/models.py, signals.py |
| 4 | SystemMessage | platform/models.py |
| 5 | Language detection | platform/language.py |
| 6 | Platform seed data | platform/migrations/ |
| 7 | ToolCard + ToolConnection | tools/models.py |
| 8 | Seed tools + migrate | tools/migrations/ |
| 9 | Dual-read compat | tools/compat.py |
| 10 | Tools API views | tools/views.py, urls.py |
| 11 | Agent models | agents/models.py |
| 12 | MCP executor + SSE | mcp_hub/executor.py, views.py |
| 13 | Integration tests | all tests |
