from django.contrib import admin
from django.utils.html import format_html
from django.conf import settings
from django.urls import reverse
from .models import (
    Client,
    ClientAPIKey,
    ClientDocument,
    ClientAPIConfig,
    ClientEmbedding,
    ClientZeroConfig,
    KnowledgeBlock,
    WebParsingRequest,
    News,
    ExtensionPage,
    ExtensionEntity,
)
from django.shortcuts import render
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.contrib import messages
from django.http import HttpRequest
from MASTER.accounts.models import Roles, User

# Restaurant admin configurations moved to restaurant app


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = [
        'user',
        'tag',
        'webchat_domain',
        'specialization',
        'company_name',
        'client_type',
        'llm_provider',
        'llm_model_name',
        'is_active',
        'telegram_enabled',
        'matrix_hitl_enabled',
        'matrix_managers_count',
        'extension_enabled',
        'logo_preview',
        'api_keys_count',
        'chats_statistics',
        'zero_status',
        'api_docs_link',
        'created_by_display',
        'created_at',
    ]
    list_display_links = ['user', 'tag']  # Поля, які будуть посиланнями на детальну сторінку
    list_filter = ['client_type', 'llm_provider', 'specialization__branch', 'specialization', 'is_active', 'created_by', 'created_at']
    search_fields = ['user', 'tag', 'company_name', 'description']
    ordering = ['-created_at']
    readonly_fields = ['created_by', 'created_at', 'updated_at', 'api_keys_count', 'chats_statistics', 'zero_status', 'api_docs_link', 'client_portal_link', 'logo_preview']
    actions = ['test_rag', 'start_zero_service', 'stop_zero_service', 'restart_zero_service', 'check_zero_health']
    
    def get_queryset(self, request):
        """Переконаємося, що всі записи відображаються, включаючи ті з null значеннями"""
        qs = super().get_queryset(request)
        return qs.select_related('specialization', 'specialization__branch', 'created_by')
    
    @admin.display(description='Created By', ordering='created_by')
    def created_by_display(self, obj):
        """Відображаємо created_by, показуючи 'System (API)' для записів без created_by"""
        if obj.created_by:
            return str(obj.created_by)
        return format_html('<span style="color: #888;">System (API)</span>')
    
    fieldsets = (
        ('Basic Info', {
            'fields': ('user', 'tag', 'webchat_domain', 'description', 'specialization', 'company_name', 'is_active', 'client_type')
        }),
        ('Logo', {
            'fields': ('logo', 'logo_preview'),
            'classes': ('collapse',)
        }),
        ('WhatsApp (Meta)', {
            'fields': (
                'whatsapp_meta_enabled',
                'meta_waba_id',
                'meta_app_id',
                'meta_app_secret',
                'meta_access_token',
                'meta_phone_number_id',
                'meta_phone_number',
                'meta_verify_token',
            ),
            'classes': ('collapse',),
            'description': 'Per-client Meta WhatsApp Business configuration. Use verify token for webhook validation.'
        }),
        ('Telegram Bot', {
            'fields': (
                'telegram_enabled',
                'telegram_bot_token',
                'telegram_webhook_url',
            ),
            'classes': ('collapse',),
            'description': 'Telegram Bot configuration for this client. Set bot token from @BotFather and enable integration.'
        }),
        (
            'Features Configuration',
            {
                'fields': ('features',),
                'classes': ('collapse',),
                'description': 'Enable specific features for this client (e.g., restaurant menu, chat, ordering)',
            },
        ),
        (
            'Browser Extension',
            {
                'fields': ('extension_enabled',),
                'classes': ('collapse',),
                'description': 'Enable Google Chrome extension (web scraping & semantic data collection) for this client',
            },
        ),
        ('AI Configuration', {
            'fields': ('embedding_model', 'llm_provider', 'llm_model_name', 'custom_system_prompt',),
            'classes': ('collapse',),
            'description': 'Custom system prompt for AI assistant. Higher priority than specialization/branch prompts.'
        }),
        ('Usage Statistics', {
            'fields': ('sync_usage_stats',),
            'description': 'Control whether usage statistics are sent to MG for this client'
        }),
        ('Email Reports', {
            'fields': ('email_report_enabled', 'email_smtp_enabled', 'email_smtp_host', 'email_smtp_port', 'email_smtp_use_tls', 'email_smtp_username', 'email_smtp_password', 'email_from_address', 'email_from_name', 'email_report_recipients'),
            'classes': ('collapse',),
            'description': 'Email configuration for sending chat summary reports. Enabled by default.'
        }),
        ('HITL (Human-in-the-Loop)', {
            'fields': ('hitl_enabled', 'manager_telegram_ids'),
            'classes': ('collapse',),
            'description': '''
                Human-in-the-Loop configuration for manager escalation.
                When enabled, the AI will escalate questions it cannot confidently answer to human managers via Telegram.
                
                Manager Telegram IDs: Add Telegram user IDs (not usernames) of managers who should receive escalations.
                To get a user ID, ask the manager to message @userinfobot on Telegram.
                Example: [123456789, 987654321]
            '''
        }),
        ('Matrix.org HITL (Unified Interface)', {
            'fields': ('matrix_hitl_enabled', 'matrix_manager_user_ids', 'matrix_homeserver_url'),
            'classes': ('collapse',),
            'description': '''
                Matrix.org HITL configuration for unified escalation interface.
                When enabled, escalations are created in Matrix rooms where managers can collaborate.
                Supports all channels (Telegram, WhatsApp, Web) in one unified interface.
                
                Matrix Manager User IDs: Add Matrix user IDs (e.g., @manager1:matrix.org) of managers.
                Managers will receive invitations to Matrix rooms for escalations.
                Example: ["@manager1:matrix.org", "@manager2:matrix.org"]
                
                Matrix Homeserver URL: Your Matrix homeserver (default: https://matrix.org)
            '''
        }),
        ('Chat Statistics', {
            'fields': ('chats_statistics',),
            'classes': ('collapse',),
            'description': 'Statistics of conversations by integration type (Web, Telegram, WhatsApp)'
        }),
        ('Dashboard Configuration', {
            'fields': (
                'dashboard_layout',
                'dashboard_show_info_center',
                'dashboard_show_top_prompts',
                'dashboard_custom_widgets',
                'dashboard_custom_style',
            ),
            'classes': ('collapse',),
            'description': '''
                Configure dashboard layout and widgets for this client.
                - Layout: Choose between default, minimal, white_label (custom only), or hybrid
                - Show/Hide: Toggle standard widgets (Info Center, Top Prompts)
                - Custom Widgets: JSON config for white label widgets (html_block, iframe, video, etc.)
                - Custom Style: JSON config for branding (colors, logo, CSS)
            '''
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at', 'api_keys_count', 'api_docs_link', 'client_portal_link'),
            'classes': ('collapse',)
        }),
    )
    
    @admin.display(description='Active API Keys')
    def api_keys_count(self, obj):
        return obj.api_keys.filter(is_active=True).count()
    
    @admin.display(description='Matrix Managers')
    def matrix_managers_count(self, obj):
        """Показує кількість Matrix менеджерів для клієнта"""
        if not obj.pk:
            return '-'
        manager_ids = getattr(obj, 'matrix_manager_user_ids', [])
        if isinstance(manager_ids, list):
            count = len([m for m in manager_ids if m and str(m).strip()])
            if count > 0:
                return format_html(
                    '<span style="color: green; font-weight: bold;">{}</span>',
                    count
                )
        return format_html('<span style="color: gray;">0</span>')
    
    @admin.display(description='Chats Statistics')
    def chats_statistics(self, obj):
        """Відображає статистику по кількості чатів для кожної інтеграції"""
        from django.db.models import Q
        from MASTER.clients.models import ClientWhatsAppConversation
        
        if not obj.pk:
            return '-'
        
        # Отримуємо всі розмови клієнта
        conversations = ClientWhatsAppConversation.objects.filter(client=obj)
        
        # Підрахунок по типах інтеграцій
        web_chats = 0
        telegram_chats = 0
        whatsapp_chats = 0
        
        for conv in conversations:
            platform = None
            if conv.context_metadata:
                platform = conv.context_metadata.get('platform')
            
            # Визначаємо тип інтеграції
            if platform == 'telegram' or (conv.telegram_chat_id and conv.telegram_chat_id.strip()) or (conv.customer_phone and conv.customer_phone.startswith('telegram_')):
                telegram_chats += 1
            elif platform == 'web' or platform == 'web_widget' or (conv.customer_phone and conv.customer_phone.startswith('web_')):
                web_chats += 1
            else:
                whatsapp_chats += 1
        
        total = web_chats + telegram_chats + whatsapp_chats
        
        return format_html(
            '<div style="white-space: nowrap;">'
            '<span style="color: #0066cc;">🌐 Web: <strong>{}</strong></span><br>'
            '<span style="color: #0088cc;">📱 Telegram: <strong>{}</strong></span><br>'
            '<span style="color: #25D366;">💬 WhatsApp: <strong>{}</strong></span><br>'
            '<span style="font-weight: bold;">Total: <strong>{}</strong></span>'
            '</div>',
            web_chats, telegram_chats, whatsapp_chats, total
        )

    @admin.action(description='Test RAG for selected client')
    def test_rag(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(request, 'Please select exactly one client', level=messages.ERROR)
            return
        client = queryset.first()
        context = {
            'client': client,
            'branch': client.specialization.branch if client.specialization else None,
            'specialization': client.specialization,
            'opts': self.model._meta,
            'has_view_permission': self.has_view_permission(request),
        }
        return render(request, 'admin/clients/test_rag.html', context)

    @admin.display(description='API Docs')
    def api_docs_link(self, obj):
        if not getattr(obj, 'pk', None):
            return '-'
        url = reverse('generate_api_docs', args=[obj.id])
        return format_html('<a target="_blank" class="button" href="{}">Generate API Documentation</a>', url)

    @admin.display(description='Client Portal (test link)')
    def client_portal_link(self, obj):
        """One-click test link to the client portal for this client (opens in new tab)."""
        if not getattr(obj, 'pk', None) or not obj.tag:
            return '-'
        
        # 1) Custom per-client domain (white-label), if configured
        custom_domain = (getattr(obj, "webchat_domain", "") or "").strip()
        if custom_domain:
            if custom_domain.startswith("http://") or custom_domain.startswith("https://"):
                base_url = custom_domain.rstrip("/")
            else:
                base_url = f"https://{custom_domain}".rstrip("/")
        else:
            # 2) Fallback to global client portal base URL
            base_url = settings.CLIENT_PORTAL_BASE_URL.rstrip('/')
        
        # Формат: https://<domain>/l?tag={client_tag}
        url = f"{base_url}/l?tag={obj.tag}"
        return format_html('<a target="_blank" class="button" href="{}">Open Client Portal</a>', url)
    
    @admin.display(description='Zero Status')
    def zero_status(self, obj):
        """Показати статус Zero service для клієнта."""
        try:
            config = obj.zero_config
            status_colors = {
                ClientZeroConfig.STATUS_DISABLED: 'gray',
                ClientZeroConfig.STATUS_STARTING: 'blue',
                ClientZeroConfig.STATUS_RUNNING: 'green',
                ClientZeroConfig.STATUS_STOPPING: 'orange',
                ClientZeroConfig.STATUS_STOPPED: 'red',
                ClientZeroConfig.STATUS_ERROR: 'darkred',
            }
            color = status_colors.get(config.status, 'gray')
            enabled_icon = '✓' if config.enabled else '✗'
            return format_html(
                '<span style="color: {}; font-weight: bold;">{}</span> {}',
                color,
                config.get_status_display(),
                enabled_icon
            )
        except ClientZeroConfig.DoesNotExist:
            return format_html('<span style="color: gray;">Not configured</span>')
    
    @admin.action(description='🚀 Start Zero Service (Admin/Manager only)')
    def start_zero_service(self, request, queryset):
        """Запустити Zero service для вибраних клієнтів."""
        # Перевірка прав
        if request.user.role not in [Roles.ADMIN, Roles.MANAGER]:
            self.message_user(
                request,
                'Only administrators and managers can start Zero services.',
                level=messages.ERROR
            )
            return
        
        from MASTER.clients.tasks import start_zero_container_task
        
        started_count = 0
        for client in queryset:
            try:
                config = client.zero_config
                if not config.enabled:
                    self.message_user(
                        request,
                        f'Zero service is disabled for {client.user}. Enable it first.',  # client.user is CharField
                        level=messages.WARNING
                    )
                    continue
                
                # Запустити асинхронну задачу
                start_zero_container_task.delay(config.id)
                started_count += 1
                
            except ClientZeroConfig.DoesNotExist:
                self.message_user(
                    request,
                    f'No Zero configuration found for {client.user}',  # client.user is CharField
                    level=messages.WARNING
                )
        
        if started_count > 0:
            self.message_user(
                request,
                f'Started Zero service for {started_count} client(s). Check status in a few moments.',
                level=messages.SUCCESS
            )
    
    @admin.action(description='🛑 Stop Zero Service (Admin/Manager only)')
    def stop_zero_service(self, request, queryset):
        """Зупинити Zero service для вибраних клієнтів."""
        # Перевірка прав
        if request.user.role not in [Roles.ADMIN, Roles.MANAGER]:
            self.message_user(
                request,
                'Only administrators and managers can stop Zero services.',
                level=messages.ERROR
            )
            return
        
        from MASTER.clients.tasks import stop_zero_container_task
        
        stopped_count = 0
        for client in queryset:
            try:
                config = client.zero_config
                stop_zero_container_task.delay(config.id, remove=False)
                stopped_count += 1
            except ClientZeroConfig.DoesNotExist:
                pass
        
        if stopped_count > 0:
            self.message_user(
                request,
                f'Stopping Zero service for {stopped_count} client(s).',
                level=messages.SUCCESS
            )
    
    @admin.action(description='🔄 Restart Zero Service (Admin/Manager only)')
    def restart_zero_service(self, request, queryset):
        """Перезапустити Zero service для вибраних клієнтів."""
        # Перевірка прав
        if request.user.role not in [Roles.ADMIN, Roles.MANAGER]:
            self.message_user(
                request,
                'Only administrators and managers can restart Zero services.',
                level=messages.ERROR
            )
            return
        
        from MASTER.clients.tasks import restart_zero_container_task
        
        restarted_count = 0
        for client in queryset:
            try:
                config = client.zero_config
                restart_zero_container_task.delay(config.id)
                restarted_count += 1
            except ClientZeroConfig.DoesNotExist:
                pass
        
        if restarted_count > 0:
            self.message_user(
                request,
                f'Restarting Zero service for {restarted_count} client(s).',
                level=messages.SUCCESS
            )
    
    @admin.action(description='🏥 Check Zero Health (Admin/Manager only)')
    def check_zero_health(self, request, queryset):
        """Перевірити стан Zero service для вибраних клієнтів."""
        # Перевірка прав
        if request.user.role not in [Roles.ADMIN, Roles.MANAGER]:
            self.message_user(
                request,
                'Only administrators and managers can check Zero health.',
                level=messages.ERROR
            )
            return
        
        from MASTER.clients.tasks import check_zero_container_health_task
        
        checked_count = 0
        for client in queryset:
            try:
                config = client.zero_config
                check_zero_container_health_task.delay(config.id)
                checked_count += 1
            except ClientZeroConfig.DoesNotExist:
                pass
        
        if checked_count > 0:
            self.message_user(
                request,
                f'Health check initiated for {checked_count} client(s). Refresh to see updated status.',
                level=messages.SUCCESS
            )
    
    @admin.display(description='Логотип')
    def logo_preview(self, obj):
        if not obj.logo:
            return format_html('<span style="color: gray;">Немає логотипу</span>')
        return format_html(
            '<img src="{}" style="max-width: 50px; max-height: 50px; border: 1px solid #ddd;" />',
            obj.logo.url
        )
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user

        # Detect newly added Matrix manager IDs for admin feedback
        old_manager_ids = set()
        if change and obj.pk:
            try:
                from .models import Client
                old = Client.objects.filter(pk=obj.pk).values_list(
                    'matrix_manager_user_ids', flat=True
                ).first()
                old_manager_ids = set(old or [])
            except Exception:
                pass

        super().save_model(request, obj, form, change)

        # Show feedback for newly added managers
        if change:
            new_manager_ids = set(obj.matrix_manager_user_ids or [])
            added = new_manager_ids - old_manager_ids
            for mid in added:
                if mid and mid.strip():
                    messages.success(request, f"Matrix welcome DM queued for {mid}")

    


@admin.register(ClientAPIKey)
class ClientAPIKeyAdmin(admin.ModelAdmin):
    list_display = ['name', 'client', 'key_preview', 'is_active', 'usage_count', 'last_used_at', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'client__user__username', 'key']
    ordering = ['-created_at']
    readonly_fields = ['key', 'usage_count', 'last_used_at', 'created_at']
    
    fieldsets = (
        ('API Key Info', {
            'fields': ('client', 'name', 'key', 'is_active')
        }),
        ('Rate Limits', {
            'fields': ('rate_limit_per_minute', 'rate_limit_per_day')
        }),
        ('Usage Stats', {
            'fields': ('usage_count', 'last_used_at', 'expires_at'),
            'classes': ('collapse',)
        }),
    )
    
    @admin.display(description='API Key')
    def key_preview(self, obj):
        return f"{obj.key[:15]}...{obj.key[-8:]}"


class ClientAPIConfigInline(admin.StackedInline):
    model = ClientAPIConfig
    can_delete = False
    extra = 0


class ClientZeroConfigInline(admin.StackedInline):
    """Inline для керування Zero-контейнером клієнта (тільки для admin/manager)."""
    model = ClientZeroConfig
    can_delete = False
    extra = 0
    verbose_name = 'Zero Email Service Configuration'
    verbose_name_plural = 'Zero Email Service Configuration'
    
    fieldsets = (
        ('Service Control', {
            'fields': ('enabled', 'status', 'last_error'),
            'description': 'Enable/disable the Zero email service for this client. Status is updated automatically.'
        }),
        ('Container Configuration', {
            'fields': ('image', 'repo_url', 'repo_branch', 'container_name'),
            'classes': ('collapse',),
        }),
        ('Network & Routing', {
            'fields': ('subdomain', 'domain', 'host_port'),
            'classes': ('collapse',),
        }),
        ('Database Configuration', {
            'fields': ('db_name', 'db_user', 'db_password', 'db_host', 'db_port'),
            'classes': ('collapse',),
            'description': 'Separate PostgreSQL database for this client\'s Zero instance.'
        }),
        ('Integration Secrets', {
            'fields': (
                'better_auth_secret', 
                'google_client_id', 
                'google_client_secret',
                'autumn_secret_key',
                'twilio_account_sid',
                'twilio_auth_token',
                'twilio_phone_number',
            ),
            'classes': ('collapse',),
        }),
        ('Sync Settings', {
            'fields': ('drop_agent_tables', 'thread_sync_max_count', 'thread_sync_loop'),
            'classes': ('collapse',),
        }),
        ('Advanced', {
            'fields': ('custom_env', 'container_id', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
    
    readonly_fields = ['status', 'container_id', 'created_at', 'updated_at']
    
    def has_add_permission(self, request: HttpRequest, obj=None) -> bool:
        """Тільки admin та manager можуть додавати Zero config."""
        if not request.user.is_authenticated:
            return False
        user = request.user
        if isinstance(user, User):
            return user.role in [Roles.ADMIN, Roles.MANAGER]
        return False
    
    def has_change_permission(self, request: HttpRequest, obj=None) -> bool:
        """Тільки admin та manager можуть змінювати Zero config."""
        if not request.user.is_authenticated:
            return False
        user = request.user
        if isinstance(user, User):
            return user.role in [Roles.ADMIN, Roles.MANAGER]
        return False
    
    def has_delete_permission(self, request: HttpRequest, obj=None) -> bool:
        """Тільки admin може видаляти Zero config."""
        if not request.user.is_authenticated:
            return False
        user = request.user
        if isinstance(user, User):
            return user.role == Roles.ADMIN
        return False
    
    def has_view_permission(self, request: HttpRequest, obj=None) -> bool:
        """Тільки admin та manager можуть переглядати Zero config."""
        if not request.user.is_authenticated:
            return False
        user = request.user
        if isinstance(user, User):
            return user.role in [Roles.ADMIN, Roles.MANAGER]
        return False


ClientAdmin.inlines = [ClientAPIConfigInline, ClientZeroConfigInline]


@admin.register(ClientDocument)
class ClientDocumentAdmin(admin.ModelAdmin):
    list_display = ['title', 'client', 'file_type', 'file_size_mb', 'is_processed', 'chunks_count', 'uploaded_at']
    list_filter = ['client', 'client__specialization', 'file_type', 'is_processed', 'uploaded_at']
    search_fields = ['title', 'client__user__username', 'client__user__email']
    ordering = ['-uploaded_at']
    readonly_fields = ['file_size', 'is_processed', 'chunks_count', 'uploaded_at', 'metadata_display']
    fieldsets = (
        ('Document Info', {
            'fields': ('client', 'title', 'file', 'file_type')
        }),
        ('Processing Status', {
            'fields': ('is_processed', 'chunks_count')
        }),
        ('Metadata', {
            'fields': ('uploaded_at', 'file_size', 'metadata_display'),
            'classes': ('collapse',)
        }),
    )
    
    @admin.display(description='Size')
    def file_size_mb(self, obj):
        return f"{obj.file_size / (1024 * 1024):.2f} MB"

    @admin.display(description='Metadata')
    def metadata_display(self, obj):
        try:
            import json
            pretty = json.dumps(obj.metadata or {}, ensure_ascii=False, indent=2)
        except Exception:
            pretty = str(obj.metadata)
        return format_html('<pre style="max-height:400px; overflow:auto;">{}</pre>', pretty)


@admin.register(ClientEmbedding)
class ClientEmbeddingAdmin(admin.ModelAdmin):
    list_display = ['id', 'client', 'document', 'embedding_model', 'created_at']
    list_filter = ['client', 'embedding_model', 'created_at']
    search_fields = ['content', 'client__user__username']
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'vector']


class ExtensionPageInline(admin.TabularInline):
    """Inline для перегляду Extension Pages в Knowledge Block"""
    model = ExtensionPage
    extra = 0
    readonly_fields = ['url', 'title', 'site_name', 'created_at', 'full_text_preview', 'headings_count', 'lists_count']
    fields = ['url', 'title', 'site_name', 'headings_count', 'lists_count', 'created_at', 'full_text_preview']
    can_delete = False
    show_change_link = True
    
    def full_text_preview(self, obj):
        if obj.full_text:
            preview = obj.full_text[:200] + '...' if len(obj.full_text) > 200 else obj.full_text
            return format_html('<div style="max-height:100px; overflow:auto; font-size:11px;">{}</div>', preview)
        return '-'
    full_text_preview.short_description = 'Text Preview'
    
    def headings_count(self, obj):
        return len(obj.headings) if obj.headings else 0
    headings_count.short_description = 'Headings'
    
    def lists_count(self, obj):
        return len(obj.lists) if obj.lists else 0
    lists_count.short_description = 'Lists'
    
    def has_add_permission(self, request, obj=None):
        return False


@admin.register(KnowledgeBlock)
class KnowledgeBlockAdmin(admin.ModelAdmin):
    list_display = ['name', 'client', 'description', 'entries_count', 'is_active', 'is_permanent', 'created_at']
    list_filter = ['is_active', 'is_permanent', 'created_at']
    search_fields = ['name', 'description', 'client__user', 'client__company_name']
    ordering = ['client', 'is_permanent', 'name']
    list_editable = ['is_active']
    readonly_fields = ['entries_count', 'created_at', 'updated_at']
    inlines = [ExtensionPageInline]
    
    fieldsets = (
        ('Basic Info', {
            'fields': ('client', 'name', 'description')
        }),
        ('Status', {
            'fields': ('is_active', 'is_permanent')
        }),
        ('Metadata', {
            'fields': ('entries_count', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    @admin.display(description='Documents')
    def entries_count(self, obj):
        return obj.entries_count

    @admin.display(description='Content Preview')
    def content_preview(self, obj):
        return obj.content[:100] + '...' if len(obj.content) > 100 else obj.content

    @admin.display(description='Vector Dimensions')
    def vector_dimensions(self, obj):
        try:
            if isinstance(obj.metadata, dict) and 'dimensions' in obj.metadata:
                return int(obj.metadata.get('dimensions') or 0)
        except Exception:
            pass
        return len(obj.vector) if obj.vector else 0

    @admin.display(description='Metadata')
    def metadata_display(self, obj):
        try:
            import json
            pretty = json.dumps(obj.metadata or {}, ensure_ascii=False, indent=2)
        except Exception:
            pretty = str(obj.metadata)
        return format_html('<pre style="max-height:400px; overflow:auto;">{}</pre>', pretty)


@admin.register(ExtensionPage)
class ExtensionPageAdmin(admin.ModelAdmin):
    """Admin для перегляду зіскрапленого контенту з розширення"""
    list_display = ['title', 'site_name', 'client', 'knowledge_block', 'headings_count', 'lists_count', 'created_at']
    list_filter = ['site_name', 'created_at', 'client', 'knowledge_block']
    search_fields = ['title', 'url', 'site_name', 'full_text', 'client__company_name']
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'full_text_display', 'headings_display', 'lists_display', 'tables_display', 'quotes_display']
    
    fieldsets = (
        ('Page Information', {
            'fields': ('client', 'knowledge_block', 'url', 'site_name', 'title', 'created_at')
        }),
        ('Structured Content', {
            'fields': ('headings_display', 'lists_display', 'tables_display', 'quotes_display'),
            'classes': ('collapse',)
        }),
        ('Full Text', {
            'fields': ('full_text_display',),
        }),
    )
    
    def headings_count(self, obj):
        return len(obj.headings) if obj.headings else 0
    headings_count.short_description = 'Headings'
    
    def lists_count(self, obj):
        return len(obj.lists) if obj.lists else 0
    lists_count.short_description = 'Lists'
    
    def full_text_display(self, obj):
        if obj.full_text:
            return format_html('<pre style="max-height:500px; overflow:auto; white-space:pre-wrap; font-size:12px;">{}</pre>', obj.full_text)
        return '-'
    full_text_display.short_description = 'Full Text Content'
    
    def headings_display(self, obj):
        if obj.headings:
            import json
            pretty = json.dumps(obj.headings, ensure_ascii=False, indent=2)
            return format_html('<pre style="max-height:300px; overflow:auto; font-size:11px;">{}</pre>', pretty)
        return '-'
    headings_display.short_description = 'Headings (H1-H6)'
    
    def lists_display(self, obj):
        if obj.lists:
            import json
            pretty = json.dumps(obj.lists, ensure_ascii=False, indent=2)
            return format_html('<pre style="max-height:300px; overflow:auto; font-size:11px;">{}</pre>', pretty)
        return '-'
    lists_display.short_description = 'Lists (UL/OL)'
    
    def tables_display(self, obj):
        if obj.tables:
            import json
            pretty = json.dumps(obj.tables, ensure_ascii=False, indent=2)
            return format_html('<pre style="max-height:300px; overflow:auto; font-size:11px;">{}</pre>', pretty)
        return '-'
    tables_display.short_description = 'Tables'
    
    def quotes_display(self, obj):
        if obj.quotes:
            import json
            pretty = json.dumps(obj.quotes, ensure_ascii=False, indent=2)
            return format_html('<pre style="max-height:300px; overflow:auto; font-size:11px;">{}</pre>', pretty)
        return '-'
    quotes_display.short_description = 'Quotes / Highlights'


@admin.register(ExtensionEntity)
class ExtensionEntityAdmin(admin.ModelAdmin):
    """Admin для перегляду витягнутих сутностей (emails, phones, addresses)"""
    list_display = ['site_name', 'client', 'emails_count', 'phones_count', 'addresses_count', 'page', 'created_at']
    list_filter = ['created_at', 'client', 'site_name']
    search_fields = ['site_name', 'url', 'client__company_name']
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'emails_display', 'phones_display', 'addresses_display']
    
    fieldsets = (
        ('Page Information', {
            'fields': ('client', 'page', 'site_name', 'url', 'created_at')
        }),
        ('Extracted Entities', {
            'fields': ('emails_display', 'phones_display', 'addresses_display'),
        }),
    )
    
    def emails_count(self, obj):
        return len(obj.emails) if obj.emails else 0
    emails_count.short_description = 'Emails'
    
    def phones_count(self, obj):
        return len(obj.phones) if obj.phones else 0
    phones_count.short_description = 'Phones'
    
    def addresses_count(self, obj):
        return len(obj.addresses) if obj.addresses else 0
    addresses_count.short_description = 'Addresses'
    
    def emails_display(self, obj):
        if obj.emails:
            import json
            pretty = json.dumps(obj.emails, ensure_ascii=False, indent=2)
            return format_html('<pre style="max-height:300px; overflow:auto; font-size:11px;">{}</pre>', pretty)
        return '-'
    emails_display.short_description = 'Emails'
    
    def phones_display(self, obj):
        if obj.phones:
            import json
            pretty = json.dumps(obj.phones, ensure_ascii=False, indent=2)
            return format_html('<pre style="max-height:300px; overflow:auto; font-size:11px;">{}</pre>', pretty)
        return '-'
    phones_display.short_description = 'Phone Numbers'
    
    def addresses_display(self, obj):
        if obj.addresses:
            import json
            pretty = json.dumps(obj.addresses, ensure_ascii=False, indent=2)
            return format_html('<pre style="max-height:300px; overflow:auto; font-size:11px;">{}</pre>', pretty)
        return '-'
    addresses_display.short_description = 'Addresses'


@admin.register(WebParsingRequest)
class WebParsingRequestAdmin(admin.ModelAdmin):
    list_display = ['website_url', 'client', 'status', 'price', 'knowledge_block', 'created_at']
    list_filter = ['status', 'created_at', 'client']
    search_fields = ['website_url', 'description', 'client__company_name', 'client__user']
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'updated_at', 'knowledge_block_link']
    
    fieldsets = (
        ('Client Information', {
            'fields': ('client', 'website_url', 'description')
        }),
        ('Admin Only', {
            'fields': ('price', 'status', 'path_to_documents'),
            'description': 'These fields are only visible to administrators'
        }),
        ('Results', {
            'fields': ('knowledge_block', 'knowledge_block_link'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_readonly_fields(self, request, obj=None):
        """Make client-provided fields readonly for non-admins"""
        readonly = list(self.readonly_fields)
        if not request.user.is_superuser:
            readonly.extend(['price', 'status', 'path_to_documents'])
        return readonly
    
    def get_fieldsets(self, request, obj=None):
        """Hide admin-only fields for non-admins"""
        fieldsets = list(self.fieldsets)
        if not request.user.is_superuser:
            # Remove admin-only fieldset
            fieldsets = [fs for fs in fieldsets if fs[0] != 'Admin Only']
        return fieldsets
    
    @admin.display(description='Knowledge Block')
    def knowledge_block_link(self, obj):
        if obj.knowledge_block:
            url = reverse('admin:clients_knowledgeblock_change', args=[obj.knowledge_block.id])
            return format_html('<a href="{}">{}</a>', url, obj.knowledge_block.name)
        return '-'


@admin.register(News)
class NewsAdmin(admin.ModelAdmin):
    """Admin interface for managing system news"""
    list_display = ['title', 'news_type', 'is_active', 'is_featured', 'created_at', 'image_preview']
    list_filter = ['news_type', 'is_active', 'is_featured', 'created_at']
    search_fields = ['title', 'description', 'related_integration', 'related_model', 'related_feature']
    ordering = ['-is_featured', '-created_at']
    list_editable = ['is_active', 'is_featured']
    
    fieldsets = (
        ('Basic Information (English)', {
            'fields': ('title', 'description', 'news_type'),
            'description': 'Enter title and description in English. Translations will be generated automatically.'
        }),
        ('Translations', {
            'fields': ('translations', 'translations_preview'),
            'classes': ('collapse',),
            'description': 'Automatically generated translations. Click "Save and continue editing" to regenerate translations if needed.'
        }),
        ('Image', {
            'fields': ('image', 'image_url', 'image_preview'),
            'description': 'Upload an image file OR provide an image URL. If both are provided, uploaded image takes priority.'
        }),
        ('Status', {
            'fields': ('is_active', 'is_featured')
        }),
        ('Related Information', {
            'fields': ('related_integration', 'related_model', 'related_feature'),
            'classes': ('collapse',),
            'description': 'Optional metadata for automatic news generation'
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['created_at', 'updated_at', 'image_preview', 'translations_preview']
    
    @admin.display(description='Image Preview')
    def image_preview(self, obj):
        """Display preview of uploaded image or image URL"""
        if obj.pk and obj.image:
            # Show uploaded image
            try:
                # Try to get request from admin site
                from django.contrib import admin
                admin_site = admin.site
                # Build absolute URL for uploaded image
                image_url = obj.image.url
                # In list view, use relative URL; in detail view, try to build absolute
                return format_html(
                    '<img src="{}" style="max-width: 150px; max-height: 100px; border: 1px solid #ddd; border-radius: 4px; object-fit: cover;" /><br/><small style="color: green;">✓ Uploaded</small>',
                    image_url
                )
            except Exception:
                return format_html('<span style="color: gray;">Image uploaded</span>')
        elif obj.image_url:
            # Show image from URL
            return format_html(
                '<img src="{}" style="max-width: 150px; max-height: 100px; border: 1px solid #ddd; border-radius: 4px; object-fit: cover;" /><br/><small style="color: blue;">URL</small>',
                obj.image_url
            )
        return format_html('<span style="color: gray;">No image</span>')
    
    @admin.display(description='Translations Preview')
    def translations_preview(self, obj):
        """Display preview of translations"""
        if not obj.translations:
            return format_html('<span style="color: gray;">No translations yet. Save to generate.</span>')
        
        preview_html = '<div style="max-height: 300px; overflow-y: auto;">'
        for lang_code, trans in obj.translations.items():
            lang_name = {'uk': '🇺🇦 Ukrainian', 'en': '🇬🇧 English', 'de': '🇩🇪 German', 
                        'es': '🇪🇸 Spanish', 'fr': '🇫🇷 French', 'it': '🇮🇹 Italian',
                        'nl': '🇳🇱 Dutch', 'da': '🇩🇰 Danish'}.get(lang_code, lang_code)
            preview_html += f'''
            <div style="margin-bottom: 15px; padding: 10px; border: 1px solid #ddd; border-radius: 4px;">
                <strong>{lang_name}:</strong><br/>
                <strong>Title:</strong> {trans.get('title', 'N/A')[:100]}<br/>
                <strong>Description:</strong> {trans.get('description', 'N/A')[:200]}...
            </div>
            '''
        preview_html += '</div>'
        return format_html(preview_html)
    
    def save_model(self, request, obj, form, change):
        """Auto-generate image URL and translations if needed"""
        # Only auto-generate image_url if no image file is uploaded and no image_url is provided
        if not obj.image and not obj.image_url:
            from MASTER.clients.news_utils import get_unsplash_image_url
            keyword = 'technology'
            if obj.related_integration:
                keyword = obj.related_integration.lower()
            elif obj.related_model:
                keyword = 'artificial intelligence'
            elif obj.related_feature:
                keyword = 'innovation'
            obj.image_url = get_unsplash_image_url(keyword)
        
        # Auto-generate translations if not present or if title/description changed
        if not obj.translations or (change and ('title' in form.changed_data or 'description' in form.changed_data)):
            from MASTER.clients.news_utils import generate_translations
            try:
                obj.translations = generate_translations(obj.title, obj.description)
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Failed to generate translations: {e}", exc_info=True)
        
        super().save_model(request, obj, form, change)
