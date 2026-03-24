import os
from pathlib import Path
from datetime import timedelta
from environ import Env
from typing import Any
import mimetypes
mimetypes.add_type("application/javascript", ".js", True)

env: Any = Env()
BASE_DIR = Path(__file__).resolve().parent.parent
env.read_env(os.path.join(BASE_DIR, ".env"))

ROOT_URLCONF = "MASTER.urls"
WSGI_APPLICATION = "MASTER.wsgi.application"

# === SECURITY ===
SECRET_KEY = env("SECRET_KEY", default="dev-secret")
FIELD_ENCRYPTION_KEY = env('FIELD_ENCRYPTION_KEY', default='ZF864sWF1B0QvMRbkRgDD_NzEP4GUqPogPbdqzuwjhU=')
DEBUG = env.bool("DEBUG", default=False)

ALLOWED_HOSTS = [
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "web",       # Docker service name
    "nginx",     # Docker service name
    "frontend",  # Docker service name
    "192.168.0.40",
    "motional-sadie-unproportionally.ngrok-free.dev",
    "api.nexelin.com",
    "app.nexelin.com",  # Production фронтенд
    "nexelin.com",
    "www.nexelin.com",
    "mg.nexelin.com",
    "w020c360.kasserver.com",  # FTP хостинг для фронтенду
    ".ngrok-free.app",
]

USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

CSRF_TRUSTED_ORIGINS = [
    "http://localhost",
    "https://localhost",
    "http://127.0.0.1",
    "http://0.0.0.0",
    "https://0.0.0.0",
    "http://localhost:80",
    "https://localhost:443",
    "http://localhost:8000",
    "http://web:8000",
    "http://nginx:80",
    "http://192.168.0.40",
    "https://192.168.0.40",
    "http://192.168.0.40:8000",
    "http://frontend",
    "http://frontend:80",
    "http://nexelin.com",
    "http://www.nexelin.com",
    "https://nexelin.com",
    "https://www.nexelin.com",
    "http://api.nexelin.com",
    "https://api.nexelin.com",
    "https://app.nexelin.com",
    "https://app.nexelin.com",  # Production фронтенд
    "https://mg.nexelin.com",
    "http://mg.nexelin.com",
    # White-label domains
    "https://ai.bytekraft.net",
    "https://ai.bytekraft.net",
    # FTP хостинг для фронтенду (backup)
    "http://w020c360.kasserver.com",
    "https://w020c360.kasserver.com",
    "https://*.ngrok-free.app",
]

# Додатково дозволяємо домени через змінну середовища
CSRF_EXTRA_ORIGINS = env.list("CSRF_EXTRA_ORIGINS", default=[])
if CSRF_EXTRA_ORIGINS:
    CSRF_TRUSTED_ORIGINS.extend(CSRF_EXTRA_ORIGINS)

USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Session та CSRF cookies для роботи в iframe
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_SAMESITE = 'None'  # Дозволяє cookies в iframe (cross-site)
SESSION_COOKIE_HTTPONLY = True

CSRF_COOKIE_SECURE = True
CSRF_COOKIE_SAMESITE = 'None'  # Дозволяє CSRF token в iframe (cross-site)
CSRF_COOKIE_HTTPONLY = True

# === APPLICATIONS ===
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "MASTER.EmbeddingModel",
    "MASTER.accounts",
    "MASTER.branches",
    "MASTER.specializations",
    "MASTER.clients",
    "MASTER.api",
    "MASTER.processing",
    "MASTER.rag",
    "MASTER.restaurant",
    "MASTER.nexelin_platform",
    "MASTER.tools",
    "MASTER.agents",
    "MASTER.mcp_hub",
]

MIDDLEWARE = [
    "MASTER.fix_domain_middleware.FixDomainMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    # XFrameOptionsMiddleware замінений на кастомний для підтримки iframe
    # "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "MASTER.iframe_middleware.AllowIframeMiddleware",
    "MASTER.clients.middleware.ClientAPIKeyMiddleware",
    "MASTER.rate_limit_middleware.RateLimitMiddleware",
]

AUTH_USER_MODEL = "accounts.User"


# Використовуємо ManifestStaticFilesStorage - компресія виконується динамічно
# Якщо виникають проблеми з компресією, можна використати ManifestStaticFilesStorage
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.ManifestStaticFilesStorage'
WHITENOISE_USE_FINDERS = True
WHITENOISE_AUTOREFRESH = True
WHITENOISE_MANIFEST_STRICT = False

# === DATABASE ===
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("DB_NAME", default="admin_db"),
        "USER": env("DB_USER", default="admin_user"),
        "PASSWORD": env("DB_PASS", default="admin_pass"),
        "HOST": env("DB_HOST", default="127.0.0.1"),
        "PORT": env("DB_PORT", default="5432"),
        "OPTIONS": {
            "options": "-c default_table_access_method=heap"
        }
    }
}

# === REST FRAMEWORK ===
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        # SessionAuthentication вимагає CSRF token, що ламає API запити з X-Client-Token
        # Тому видаляємо його як дефолтну автентифікацію
        # Views, яким потрібна SessionAuthentication, мають явно її вказувати
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        # Дозволяємо доступ без автентифікації за замовчуванням
        # Views, яким потрібна автентифікація, мають явно вказувати permission_classes
        "rest_framework.permissions.AllowAny",
    ),
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "SIGNING_KEY": SECRET_KEY,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

# === AUTH REDIRECTS ===
LOGIN_URL = "/admin/login/"
LOGIN_REDIRECT_URL = "/admin/"
LOGOUT_REDIRECT_URL = "/admin/login/"

# === STATIC & MEDIA ===
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = []

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# === TEMPLATES ===
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# === EMAIL ===
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = "noreply@system.local"

# === LOCALE ===
LANGUAGE_CODE = "en"
TIME_ZONE = "Europe/Kyiv"
USE_I18N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# === CELERY ===
CELERY_BROKER_URL = env("CELERY_BROKER_URL", default="redis://127.0.0.1:6379/0")
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default="redis://127.0.0.1:6379/0")
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'Europe/Kyiv'
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60
CELERY_TASK_ANNOTATIONS = {
    "MASTER.processing.tasks.process_client_document": {"rate_limit": "10/m"},
    "MASTER.processing.tasks.process_branch_document": {"rate_limit": "10/m"},
    "MASTER.processing.tasks.process_specialization_document": {"rate_limit": "10/m"},
}
CELERY_WORKER_CONCURRENCY = env.int("CELERY_WORKER_CONCURRENCY", default=1)

# === INTEGRATION SERVICE (Matrix HITL) ===
INTEGRATION_SERVICE_URL = env("INTEGRATION_SERVICE_URL", default="http://ai_nexelin_integration_service:8080")

# Celery Beat schedule for periodic tasks
from celery.schedules import crontab
CELERY_BEAT_SCHEDULE = {
    'check-inactive-chat-sessions': {
        'task': 'MASTER.clients.tasks.check_inactive_chat_sessions',
        'schedule': 60.0,  # Run every 60 seconds (1 minute)
    },
    'send-daily-digest': {
        'task': 'MASTER.clients.tasks.send_daily_digest',
        'schedule': crontab(hour=17, minute=0),  # Every day at 17:00 (Europe/Kyiv)
    },
    'check-escalation-timeouts': {
        'task': 'MASTER.clients.tasks.check_escalation_timeouts',
        'schedule': 300.0,  # Run every 5 minutes to check for timed out escalations
    },
}

# === RAG CONFIGS (SHORTENED) ===
VECTOR_SEARCH_CONFIG = { 'ivfflat_probes': 10 }
RAG_CONFIG = {
    'chunk_context_window': 1,
    'similarity_threshold': 0.1,  # Значно знижуємо для RAG також
    'min_chunks_for_answer': 0,  # Відповідаємо навіть без контексту
    'max_results': 5,
    'max_context_chunks': 5,
    'max_context_tokens': 2000  # Обмежуємо контекст для Ollama (4096 - system_prompt - query ~= 2000)
}

VECTOR_SEARCH_CONFIG = {
    'similarity_threshold': 0.1,  # Значно знижуємо поріг для широкого пошуку
    'max_results_per_level': 5,
    'weights': {
        'branch': 0.3,
        'specialization': 0.5,
        'client': 0.8  # Збільшуємо вагу клієнтських документів
    },
    'explain_queries': False,
    'ivfflat_probes': 10,
    'hnsw_ef_search': 40,
    'force_index_usage': False
}

CONTEXT_BUILDER_CONFIG = {
    'max_context_chunks': 5,
    'chunk_context_window': 1,
    'max_tokens': 2000  # Зменшено для Ollama (буде використовуватись RAG_CONFIG)
}
LLM_CONFIG = {
    'provider': 'openai',
    'model': 'gpt-4o-mini',
    'temperature': 0.7,
    'max_tokens': 2000,  # Обмежуємо відповідь для Ollama (щоб разом з контекстом не перевищити 4096)
    'top_p': 1.0,
    'frequency_penalty': 0.0,
    'presence_penalty': 0.0,
    'timeout_seconds': 30,
    'max_retries': 3,
    'retry_delay_seconds': 2
}
SYSTEM_PROMPTS = { 'default': "..." }

# === OTHER ===
EMBEDDINGS_FALLBACK_LOCAL = env.bool("EMBEDDINGS_FALLBACK_LOCAL", default=True)

# API keys for external AI providers
OPENAI_API_KEY = env("OPENAI_API_KEY", default="")
ANTHROPIC_API_KEY = env("ANTHROPIC_API_KEY", default="")
HUGGINGFACE_API_KEY = env("HUGGINGFACE_API_KEY", default="")
COHERE_API_KEY = env("COHERE_API_KEY", default="")
COHERE_RERANK_MODEL = env("COHERE_RERANK_MODEL", default="rerank-multilingual-v3.0")

# Qdrant vector search
USE_QDRANT = env.bool("USE_QDRANT", default=True)
QDRANT_HOST = env("QDRANT_HOST", default="ai_nexelin_qdrant")
QDRANT_PORT = env.int("QDRANT_PORT", default=6333)
QDRANT_COLLECTION = env("QDRANT_COLLECTION", default="nexelin_embeddings")
WHATSAPP_QR_SECRET = env("WHATSAPP_QR_SECRET", default="")
BOOTSTRAP_SECRET = env("BOOTSTRAP_SECRET", default="")
TWILIO_ACCOUNT_SID = env("TWILIO_ACCOUNT_SID", default="")
TWILIO_AUTH_TOKEN = env("TWILIO_AUTH_TOKEN", default="")
TWILIO_WHATSAPP_NUMBER = env("TWILIO_WHATSAPP_NUMBER", default="whatsapp:+14155238886")
CLIENT_PORTAL_BASE_URL = env("CLIENT_PORTAL_BASE_URL", default="https://app.nexelin.com")

# Ollama Local LLM Configuration
OLLAMA_ENABLED = os.getenv('OLLAMA_ENABLED', 'false').lower() == 'true'

# Main server (large models)
OLLAMA_MAIN_ENDPOINT = os.getenv('OLLAMA_MAIN_ENDPOINT', 'http://192.168.0.51:11434')
OLLAMA_MAIN_LLM_MODEL = 'qwen2.5:7b'
OLLAMA_MAIN_EMBED_MODEL = 'bge-m3'

# Light server (small models, fast CPU)
OLLAMA_LIGHT_ENDPOINT = os.getenv('OLLAMA_LIGHT_ENDPOINT', 'http://192.168.0.52:11434')
OLLAMA_LIGHT_LLM_MODEL = 'qwen2.5:1.5b'
OLLAMA_LIGHT_EMBED_MODEL = 'nomic-embed-text'

# Backwards compatibility
OLLAMA_ENDPOINT = OLLAMA_MAIN_ENDPOINT
OLLAMA_DEFAULT_LLM_MODEL = os.getenv('OLLAMA_DEFAULT_LLM_MODEL', OLLAMA_MAIN_LLM_MODEL)
OLLAMA_DEFAULT_EMBED_MODEL = os.getenv('OLLAMA_DEFAULT_EMBED_MODEL', OLLAMA_MAIN_EMBED_MODEL)

# Kimi API (Moonshot)
KIMI_API_KEY = os.getenv('KIMI_API_KEY', '')

# === MG (Main Front) Integration ===
# Endpoint to send AI token usage events (hardcoded per request)
MG_AI_USAGE_URL = 'https://mg.nexelin.com/api/ai-token-usage'
# Endpoint to create/update packages on MG
MG_PACKAGE_URL = os.getenv('MG_PACKAGE_URL', 'https://mg.nexelin.com/api/package')
# Base package GUID for cloning (optional, used when creating packages with parent)
MG_BASE_PACKAGE_GUID = os.getenv('MG_BASE_PACKAGE_GUID', '')
# Access token to authenticate our requests to MG (used in Authorization: Bearer header)
MG_SYNC_API_KEY = os.getenv('MG_SYNC_API_KEY', os.getenv('MG_ACCESS_TOKEN', ''))
# Optional: Custom mapping between client_type and package_type
# Format: {'client_type': 'package_type', 'default': 'AI_TYPE_GENERIC'}
# Example: {'restaurant': 'AI_TYPE_RESTAURANT', 'generic': 'AI_TYPE_GENERIC', 'default': 'AI_TYPE_GENERIC'}
# If not set, default mapping is used (see MASTER.clients.package_sync)
# MG_PACKAGE_TYPE_MAP = {}

META_WABA_ID = os.environ.get("META_WABA_ID", "")
META_APP_ID = os.environ.get("META_APP_ID", "")
META_APP_SECRET = os.environ.get("META_APP_SECRET", "")
META_ACCESS_TOKEN = os.environ.get("META_ACCESS_TOKEN", "")
META_PHONE_NUMBER_ID = os.environ.get("META_PHONE_NUMBER_ID", "")
META_VERIFY_TOKEN = os.environ.get("META_VERIFY_TOKEN", "")


# === CORS ===
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_ALL_ORIGINS = DEBUG

# Дозволені домени для CORS (додатково до тих, що в DEBUG режимі)
CORS_ALLOWED_ORIGINS = [
    'http://localhost:3000',
    'http://localhost:5173',
    'http://localhost:8080',
    'http://localhost:80',
    'http://localhost:443',
    "http://127.0.0.1:5173",
    "http://127.0.0.1:80",
    "http://frontend:80",
    "https://app.nexelin.com",
    "https://app.nexelin.com",  # Production фронтенд
    "https://api.nexelin.com",
    "https://mg.nexelin.com",
    "http://mg.nexelin.com",
    # FTP хостинг для фронтенду (backup)
    "http://w020c360.kasserver.com",
    "https://w020c360.kasserver.com",
]

# Allow any Nexelin subdomain (useful for white-label + app/api)
CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^https:\/\/.*\.nexelin\.com$",
    r"^https:\/\/app\.nexelin\.com$",
]

# Додатково дозволяємо домени через змінну середовища (для динамічного додавання)
CORS_EXTRA_ORIGINS = env.list("CORS_EXTRA_ORIGINS", default=[])
if CORS_EXTRA_ORIGINS:
    CORS_ALLOWED_ORIGINS.extend(CORS_EXTRA_ORIGINS)

CORS_ALLOW_HEADERS = [
    "accept",
    "accept-language",
    "content-type",
    "authorization",
    "x-api-key",
    "x-client-token",
    "accept-encoding",
    "dnt",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
]
CORS_ALLOW_METHODS = [
    'DELETE',
    'GET',
    'OPTIONS',
    'PATCH',
    'POST',
    'PUT',
]

# White-label domain support
ALLOWED_HOSTS.append('*')  # Accept all domains for white-label clients

# ── MCP Server Configuration (STDIO subprocess) ─────────────
MCP_SERVERS = {
    'rag': {
        'command': 'python',
        'args': ['-m', 'mcp_servers.rag.server'],
        'enabled': True,
    },
    'escalation': {
        'command': 'python',
        'args': ['-m', 'mcp_servers.escalation.server'],
        'enabled': True,
    },
    'xlsx': {
        'command': 'python',
        'args': ['-m', 'mcp_servers.xlsx.server'],
        'enabled': True,
    },
    'leads': {
        'command': 'python',
        'args': ['-m', 'mcp_servers.leads.server'],
        'enabled': True,
    },
    'sales-intel': {
        'command': 'python',
        'args': ['-m', 'mcp_servers.sales_intel.server'],
        'enabled': True,
    },
    'email': {
        'command': 'python',
        'args': ['-m', 'mcp_servers.email.server'],
        'enabled': True,
    },
    'coaching': {
        'command': 'python',
        'args': ['-m', 'mcp_servers.coaching.server'],
        'enabled': True,
    },
    'memory': {
        'command': 'python',
        'args': ['-m', 'mcp_servers.memory.server'],
        'enabled': True,
    },
    'sequential-thinking': {
        'command': 'npx',
        'args': ['-y', '@modelcontextprotocol/server-sequential-thinking'],
        'enabled': True,
    },
}

MCP_TOOL_SCOPES = {
    'send_email': ['assistant'],
    'send_email_with_attachment': ['assistant'],
    'read_emails': ['assistant'],
    'search_emails': ['assistant'],
    'analyze_emails': ['assistant'],
    'send_commercial_email': ['manager'],
    'update_knowledge_base': [],
    'update_consultant_instructions': [],
}

