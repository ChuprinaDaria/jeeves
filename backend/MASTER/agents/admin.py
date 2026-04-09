from django.contrib import admin
from .models import AgentConfig, AgentSession, AgentLog


@admin.register(AgentConfig)
class AgentConfigAdmin(admin.ModelAdmin):
    list_display = ['client_name', 'llm_provider', 'language', 'escalation_enabled', 'is_active']
    list_filter = ['is_active', 'llm_provider', 'escalation_enabled']
    list_editable = ['is_active']
    search_fields = ['client__company_name', 'client__tag']
    raw_id_fields = ['client']

    fieldsets = (
        ('Client', {'fields': ('client', 'is_active')}),
        ('LLM', {
            'fields': ('llm_provider', 'embedding_model', 'temperature', 'max_tokens'),
            'description': 'Empty = platform defaults',
        }),
        ('Prompts (Legacy)', {
            'fields': ('system_prompt', 'greeting_message'),
            'description': 'Used by legacy pipeline. MCP uses dual prompts below.',
            'classes': ('collapse',),
        }),
        ('Prompts (MCP Dual Agent)', {
            'fields': ('assistant_prompt', 'assistant_description',
                       'consultant_prompt', 'consultant_description'),
            'description': 'Assistant = Nexy (Sandbox). Consultant (messengers).',
        }),
        ('RAG', {
            'fields': ('similarity_threshold', 'max_context_chunks', 'top_k'),
            'description': 'Empty = platform defaults',
        }),
        ('Language', {
            'fields': ('language', 'supported_languages', 'language_detection'),
            'description': 'Empty = platform defaults',
        }),
        ('Behaviour', {'fields': ('escalation_enabled',)}),
    )

    def client_name(self, obj):
        return obj.client.company_name or obj.client.tag
    client_name.short_description = 'Client'


@admin.register(AgentSession)
class AgentSessionAdmin(admin.ModelAdmin):
    list_display = ['id', 'agent_client', 'channel', 'language', 'started_at', 'ended_at']
    list_filter = ['channel', 'started_at']
    readonly_fields = ['id', 'agent_config', 'channel', 'external_user_id',
                       'language', 'metadata', 'started_at', 'ended_at']
    date_hierarchy = 'started_at'

    def agent_client(self, obj):
        return obj.agent_config.client.tag or obj.agent_config.client.company_name
    agent_client.short_description = 'Client'

    def has_add_permission(self, request):
        return False


@admin.register(AgentLog)
class AgentLogAdmin(admin.ModelAdmin):
    list_display = ['created_at', 'session_client', 'call_type', 'tool_name',
                    'status', 'latency_ms']
    list_filter = ['call_type', 'status', 'created_at']
    readonly_fields = ['session', 'tool_connection', 'call_type', 'tool_name',
                       'input_data', 'output_data', 'status', 'error_message',
                       'latency_ms', 'tokens_used', 'cost', 'created_at']
    date_hierarchy = 'created_at'

    def session_client(self, obj):
        return obj.session.agent_config.client.tag
    session_client.short_description = 'Client'

    def has_add_permission(self, request):
        return False
