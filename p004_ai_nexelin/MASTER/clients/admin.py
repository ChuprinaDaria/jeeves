from django.contrib import admin
from django.utils.html import format_html
from django.conf import settings
from django.urls import reverse
from .models import Client, ClientAPIKey, ClientDocument, ClientAPIConfig, ClientEmbedding, ClientZeroConfig, KnowledgeBlock, WebParsingRequest, News
from django.shortcuts import render
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.contrib import messages
from django.http import HttpRequest
from MASTER.accounts.models import Roles, User

# Restaurant admin configurations moved to restaurant app


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ['user', 'tag', 'webchat_domain', 'specialization', 'company_name', 'client_type', 'llm_provider', 'llm_model_name', 'is_active', 'logo_preview', 'api_keys_count', 'zero_status', 'api_docs_link', 'created_by_display', 'created_at']
    list_display_links = ['user', 'tag']  # Поля, які будуть посиланнями на детальну сторінку
    list_filter = ['client_type', 'llm_provider', 'specialization__branch', 'specialization', 'is_active', 'created_by', 'created_at']
    search_fields = ['user', 'tag', 'company_name', 'description']
    ordering = ['-created_at']
    readonly_fields = ['created_by', 'created_at', 'updated_at', 'api_keys_count', 'zero_status', 'api_docs_link', 'client_portal_link', 'logo_preview']
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
        ('Features Configuration', {
            'fields': ('features',),
            'classes': ('collapse',),
            'description': 'Enable specific features for this client (e.g., restaurant menu, chat, ordering)'
        }),
        ('AI Configuration', {
            'fields': ('embedding_model', 'llm_provider', 'llm_model_name', 'custom_system_prompt',),
            'classes': ('collapse',),
            'description': 'Custom system prompt for AI assistant. Higher priority than specialization/branch prompts.'
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at', 'api_keys_count', 'api_docs_link', 'client_portal_link'),
            'classes': ('collapse',)
        }),
    )
    
    @admin.display(description='Active API Keys')
    def api_keys_count(self, obj):
        return obj.api_keys.filter(is_active=True).count()

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
        super().save_model(request, obj, form, change)

    


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


@admin.register(KnowledgeBlock)
class KnowledgeBlockAdmin(admin.ModelAdmin):
    list_display = ['name', 'client', 'description', 'entries_count', 'is_active', 'is_permanent', 'created_at']
    list_filter = ['is_active', 'is_permanent', 'created_at']
    search_fields = ['name', 'description', 'client__user', 'client__company_name']
    ordering = ['client', 'is_permanent', 'name']
    list_editable = ['is_active']
    readonly_fields = ['entries_count', 'created_at', 'updated_at']
    
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
        ('Basic Information', {
            'fields': ('title', 'description', 'news_type')
        }),
        ('Image', {
            'fields': ('image_url', 'image_preview'),
            'classes': ('collapse',)
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
    
    readonly_fields = ['created_at', 'updated_at', 'image_preview']
    
    @admin.display(description='Image')
    def image_preview(self, obj):
        if obj.image_url:
            return format_html(
                '<img src="{}" style="max-width: 200px; max-height: 150px; border: 1px solid #ddd;" />',
                obj.image_url
            )
        return format_html('<span style="color: gray;">No image</span>')
    
    def save_model(self, request, obj, form, change):
        """Auto-generate image URL if not provided"""
        if not obj.image_url:
            from MASTER.clients.news_utils import get_unsplash_image_url
            keyword = 'technology'
            if obj.related_integration:
                keyword = obj.related_integration.lower()
            elif obj.related_model:
                keyword = 'artificial intelligence'
            elif obj.related_feature:
                keyword = 'innovation'
            obj.image_url = get_unsplash_image_url(keyword)
        super().save_model(request, obj, form, change)
