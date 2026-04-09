from django.contrib import admin
from .models import PlatformDefaults, FeatureFlag, SystemMessage


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
        ('Agent', {'fields': ('default_greeting',)}),
    )

    def has_add_permission(self, request):
        return not PlatformDefaults.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


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


@admin.register(SystemMessage)
class SystemMessageAdmin(admin.ModelAdmin):
    list_display = ['key', 'preview_en', 'languages_count', 'description']
    search_fields = ['key', 'description']

    def preview_en(self, obj):
        text = obj.translations.get('en', '')
        return (text[:60] + '...') if len(text) > 60 else text

    def languages_count(self, obj):
        return len(obj.translations)
