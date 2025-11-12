from django.contrib import admin
from django.contrib import messages
from .models import EmbeddingModel
import requests
from django.conf import settings


@admin.register(EmbeddingModel)
class EmbeddingModelAdmin(admin.ModelAdmin):
    list_display = ['name', 'provider', 'model_name', 'dimensions', 'is_local', 'server_type', 'api_endpoint', 'is_active', 'is_default', 'reindex_required', 'created_at']
    list_filter = ['provider', 'is_local', 'server_type', 'is_active', 'is_default', 'reindex_required', 'created_at']
    search_fields = ['name', 'model_name', 'slug']
    ordering = ['provider', 'name']
    list_editable = ['is_active', 'is_default']
    actions = ['trigger_reindex', 'sync_from_nexelin']
    readonly_fields = ('slug', 'created_at', 'updated_at')
    
    fieldsets = (
        ('Basic Info', {
            'fields': ('name', 'slug', 'provider', 'model_name')
        }),
        ('Configuration', {
            'fields': ('dimensions', 'cost_per_1k_tokens', 'is_local', 'server_type', 'api_endpoint', 'api_key')
        }),
        ('Status', {
            'fields': ('is_active', 'is_default', 'reindex_required')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def trigger_reindex(self, request, queryset):
        """Mark selected models for reindexing"""
        queryset.update(reindex_required=True)
        count = queryset.count()
        self.message_user(request, f"Reindex flag set for {count} model(s).")
    trigger_reindex.short_description = "Mark selected models for reindexing"
    
    def sync_from_nexelin(self, request, queryset):
        """Синхронізувати моделі з mg.nexelin.com"""
        try:
            external_url = 'https://mg.nexelin.com/api/ai-models'
            response = requests.get(external_url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data.get('status') != 'ok':
                self.message_user(request, 'Failed to fetch models from mg.nexelin.com', level=messages.ERROR)
                return
            
            ai_models = data.get('models', [])
            created_count = 0
            updated_count = 0
            
            for ai_model in ai_models:
                model_name = ai_model.get('name', '')
                description = ai_model.get('description', '')
                
                # Перевіряємо чи модель вже існує
                embedding_model, created = EmbeddingModel.objects.get_or_create(
                    name=model_name,
                    defaults={
                        'provider': 'openai',  # Можна змінити на динамічне визначення
                        'model_name': model_name,
                        'dimensions': 1536,  # Можна змінити на динамічне визначення
                        'cost_per_1k_tokens': 0.0,
                        'is_active': ai_model.get('active', True),
                    }
                )
                
                if created:
                    created_count += 1
                else:
                    # Оновлюємо статус активності
                    if embedding_model.is_active != ai_model.get('active', True):
                        embedding_model.is_active = ai_model.get('active', True)
                        embedding_model.save()
                        updated_count += 1
            
            self.message_user(
                request,
                f"Синхронізовано: {created_count} нових моделей, {updated_count} оновлено",
                level=messages.SUCCESS
            )
        except requests.RequestException as e:
            self.message_user(
                request,
                f'Error syncing from mg.nexelin.com: {str(e)}',
                level=messages.ERROR
            )
    sync_from_nexelin.short_description = "Синхронізувати моделі з mg.nexelin.com"