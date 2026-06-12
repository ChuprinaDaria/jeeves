from django.contrib import admin
from .models import ToolCard, ToolConnection, EdgeMiddleware, Skill, SkillAssignment, IntegrationTrigger


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
            'fields': ('name', 'slug', 'tagline', 'tagline_i18n', 'description', 'icon',
                       'color', 'category', 'is_featured', 'sort_order'),
        }),
        ('MCP Connection', {
            'fields': ('transport_type', 'mcp_server_url', 'is_builtin',
                       'builtin_handler', 'tools_schema', 'scope_schema', 'skill_scopes'),
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
    list_display = ['client_name', 'tool_name', 'target', 'scope', 'status', 'enabled',
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


@admin.register(EdgeMiddleware)
class EdgeMiddlewareAdmin(admin.ModelAdmin):
    list_display = ['skill_card', 'connection', 'client', 'order', 'enabled', 'created_at']
    list_filter = ['enabled', 'skill_card']
    raw_id_fields = ['connection', 'skill_card', 'client']


@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'is_active', 'updated_at']
    list_filter = ['is_active']
    list_editable = ['is_active']
    search_fields = ['name', 'slug', 'description', 'content']
    prepopulated_fields = {'slug': ('name',)}
    fieldsets = (
        ('Identity', {'fields': ('name', 'slug', 'description', 'is_active')}),
        ('Skill content (markdown, appended to the agent system prompt)', {
            'fields': ('content', 'allowed_targets'),
        }),
    )


@admin.register(SkillAssignment)
class SkillAssignmentAdmin(admin.ModelAdmin):
    list_display = ['client', 'skill', 'target', 'enabled', 'created_at']
    list_filter = ['target', 'enabled', 'skill']
    search_fields = ['client__user', 'client__tag', 'skill__name']


@admin.register(IntegrationTrigger)
class IntegrationTriggerAdmin(admin.ModelAdmin):
    list_display = ['name', 'client', 'kind', 'target', 'enabled', 'fire_count', 'last_run_at']
    list_filter = ['kind', 'enabled', 'target']
    search_fields = ['name', 'client__tag', 'client__user']
    readonly_fields = ['token', 'fire_count', 'last_run_at', 'next_run_at', 'last_error']
