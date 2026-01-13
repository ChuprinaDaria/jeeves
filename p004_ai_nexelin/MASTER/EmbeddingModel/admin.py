from django.contrib import admin
from django.contrib import messages
from .models import EmbeddingModel, LLMProvider
import requests
from django.conf import settings


@admin.register(EmbeddingModel)
class EmbeddingModelAdmin(admin.ModelAdmin):
    list_display = ['name', 'provider', 'model_name', 'dimensions', 'dimensions_status', 'external_guid', 'is_local', 'server_type', 'api_endpoint', 'is_active', 'is_default', 'reindex_required', 'created_at']
    list_filter = ['provider', 'is_local', 'server_type', 'is_active', 'is_default', 'reindex_required', 'created_at']
    search_fields = ['name', 'model_name', 'slug', 'external_guid']
    ordering = ['provider', 'name']
    list_editable = ['is_active', 'is_default']
    actions = [
        'trigger_reindex', 'sync_from_nexelin', 'deactivate_invalid_models',
        'add_text_embedding_3_small', 'add_text_embedding_3_large', 'add_text_embedding_ada_002',
        'add_anthropic_embedding_placeholder'
    ]
    readonly_fields = ('slug', 'created_at', 'updated_at')
    
    def dimensions_status(self, obj):
        """Показує статус dimensions (чи підтримується pgvector)"""
        if obj.dimensions > 2000:
            return f"⚠️ {obj.dimensions} (TOO LARGE - max 2000)"
        return f"✓ {obj.dimensions}"
    dimensions_status.short_description = 'Dimensions Status'
    
    fieldsets = (
        ('Basic Info', {
            'fields': ('name', 'slug', 'provider', 'model_name')
        }),
        ('Configuration', {
            'fields': ('dimensions', 'cost_per_1k_tokens', 'external_guid', 'is_local', 'server_type', 'api_endpoint', 'api_key')
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
    
    def deactivate_invalid_models(self, request, queryset):
        """Деактивувати моделі з dimensions > 2000 (pgvector limit)"""
        invalid_models = queryset.filter(dimensions__gt=2000)
        count = invalid_models.update(is_active=False)
        if count > 0:
            self.message_user(
                request,
                f"Деактивовано {count} модель(ей) з dimensions > 2000",
                level=messages.WARNING
            )
        else:
            self.message_user(request, "Невалідних моделей не знайдено")
    deactivate_invalid_models.short_description = "Деактивувати моделі з dimensions > 2000"
    
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
    
    @admin.action(description='➕ Додати text-embedding-3-small')
    def add_text_embedding_3_small(self, request, queryset):
        """Додати OpenAI text-embedding-3-small модель"""
        model, created = EmbeddingModel.objects.get_or_create(
            slug='text-embedding-3-small',
            defaults={
                'name': 'text-embedding-3-small',
                'provider': 'openai',
                'model_name': 'text-embedding-3-small',
                'dimensions': 1536,
                'api_key': getattr(settings, 'OPENAI_API_KEY', '').strip() or '',
                'cost_per_1k_tokens': 0.00002,  # $0.02 per 1M tokens
                'is_active': True,
                'is_default': True,
                'is_local': False,
            }
        )
        
        if created:
            self.message_user(request, f'✅ text-embedding-3-small успішно додано!', level=messages.SUCCESS)
        else:
            self.message_user(request, f'⚠️ text-embedding-3-small вже існує', level=messages.WARNING)
    
    @admin.action(description='➕ Додати text-embedding-3-large')
    def add_text_embedding_3_large(self, request, queryset):
        """Додати OpenAI text-embedding-3-large модель"""
        model, created = EmbeddingModel.objects.get_or_create(
            slug='text-embedding-3-large',
            defaults={
                'name': 'text-embedding-3-large',
                'provider': 'openai',
                'model_name': 'text-embedding-3-large',
                'dimensions': 3072,
                'api_key': getattr(settings, 'OPENAI_API_KEY', '').strip() or '',
                'cost_per_1k_tokens': 0.00013,  # $0.13 per 1M tokens
                'is_active': False,  # Неактивна за замовчуванням (dimensions > 2000)
                'is_default': False,
                'is_local': False,
            }
        )
        
        if created:
            self.message_user(
                request, 
                f'⚠️ text-embedding-3-large додано, але dimensions=3072 > 2000 (pgvector limit). Модель неактивна.', 
                level=messages.WARNING
            )
        else:
            self.message_user(request, f'⚠️ text-embedding-3-large вже існує', level=messages.WARNING)
    
    @admin.action(description='➕ Додати text-embedding-ada-002')
    def add_text_embedding_ada_002(self, request, queryset):
        """Додати OpenAI text-embedding-ada-002 модель (legacy)"""
        model, created = EmbeddingModel.objects.get_or_create(
            slug='text-embedding-ada-002',
            defaults={
                'name': 'text-embedding-ada-002',
                'provider': 'openai',
                'model_name': 'text-embedding-ada-002',
                'dimensions': 1536,
                'api_key': getattr(settings, 'OPENAI_API_KEY', '').strip() or '',
                'cost_per_1k_tokens': 0.0001,  # $0.10 per 1M tokens
                'is_active': True,
                'is_default': False,
                'is_local': False,
            }
        )
        
        if created:
            self.message_user(request, f'✅ text-embedding-ada-002 успішно додано!', level=messages.SUCCESS)
        else:
            self.message_user(request, f'⚠️ text-embedding-ada-002 вже існує', level=messages.WARNING)
    
    @admin.action(description='➕ Додати Anthropic Embedding (placeholder)')
    def add_anthropic_embedding_placeholder(self, request, queryset):
        """Додати Anthropic Embedding модель (placeholder - поки не доступна)"""
        model, created = EmbeddingModel.objects.get_or_create(
            slug='anthropic-embedding',
            defaults={
                'name': 'Anthropic Embedding (placeholder)',
                'provider': 'anthropic',
                'model_name': 'claude-embedding',  # Оновіть коли з'явиться реальна модель
                'dimensions': 1024,  # Оновіть коли з'явиться реальна модель
                'api_key': getattr(settings, 'ANTHROPIC_API_KEY', '').strip() or '',
                'cost_per_1k_tokens': 0.0,  # Оновіть коли з'явиться реальна модель
                'is_active': False,  # Неактивна поки не з'явиться API
                'is_default': False,
                'is_local': False,
            }
        )
        
        if created:
            self.message_user(
                request,
                f'⚠️ Anthropic Embedding додано як placeholder. Anthropic поки що не має публічних embedding моделей. Модель неактивна.',
                level=messages.WARNING
            )
        else:
            self.message_user(request, f'⚠️ Anthropic Embedding placeholder вже існує', level=messages.WARNING)


@admin.register(LLMProvider)
class LLMProviderAdmin(admin.ModelAdmin):
    list_display = ['name', 'provider_type', 'model_name', 'api_endpoint', 'is_active', 'is_default', 'created_at']
    list_filter = ['provider_type', 'is_active', 'is_default', 'created_at']
    search_fields = ['name', 'model_name', 'slug']
    ordering = ['provider_type', 'name']
    list_editable = ['is_active', 'is_default']
    readonly_fields = ('slug', 'created_at', 'updated_at')
    actions = [
        'add_gpt_5_1', 'add_gpt_4o', 'add_gpt_4o_mini', 'add_gpt_4_turbo', 'add_gpt_4', 
        'add_gpt_3_5_turbo', 'add_gpt_3_5_turbo_16k', 'add_o1_preview', 'add_o1_mini',
        'add_claude_3_5_sonnet', 'add_claude_3_5_haiku', 'add_claude_3_sonnet', 
        'add_claude_3_haiku', 'add_claude_3_opus', 'add_claude_4'
    ]
    
    fieldsets = (
        ('Basic Info', {
            'fields': ('name', 'slug', 'provider_type', 'model_name', 'description')
        }),
        ('Connection', {
            'fields': ('api_endpoint', 'api_key')
        }),
        ('Model Parameters', {
            'fields': ('max_tokens', 'temperature')
        }),
        ('Pricing', {
            'fields': ('cost_per_1k_input_tokens', 'cost_per_1k_output_tokens'),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': ('is_active', 'is_default')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    @admin.action(description='➕ Додати GPT-5.1')
    def add_gpt_5_1(self, request, queryset):
        """Додати GPT-5.1 провайдер"""
        provider, created = LLMProvider.objects.get_or_create(
            slug='gpt-5-1',
            defaults={
                'name': 'GPT-5.1',
                'provider_type': 'openai',
                'model_name': 'gpt-5.1',
                'api_key': getattr(settings, 'OPENAI_API_KEY', '').strip() or '',
                'max_tokens': 16384,
                'temperature': 0.7,
                'cost_per_1k_input_tokens': 0.0025,
                'cost_per_1k_output_tokens': 0.010,
                'is_active': True,
                'is_default': False,
                'description': 'OpenAI GPT-5.1 - найновіша модель'
            }
        )
        
        if created:
            self.message_user(request, f'✅ GPT-5.1 успішно додано!', level=messages.SUCCESS)
        else:
            self.message_user(request, f'⚠️ GPT-5.1 вже існує (slug: {provider.slug})', level=messages.WARNING)
    
    @admin.action(description='➕ Додати GPT-4o')
    def add_gpt_4o(self, request, queryset):
        """Додати GPT-4o провайдер"""
        provider, created = LLMProvider.objects.get_or_create(
            slug='gpt-4o',
            defaults={
                'name': 'GPT-4o',
                'provider_type': 'openai',
                'model_name': 'gpt-4o',
                'api_key': getattr(settings, 'OPENAI_API_KEY', '').strip() or '',
                'max_tokens': 16384,
                'temperature': 0.7,
                'cost_per_1k_input_tokens': 0.0025,
                'cost_per_1k_output_tokens': 0.010,
                'is_active': True,
                'is_default': False,
                'description': 'OpenAI GPT-4o - оптимізована модель'
            }
        )
        
        if created:
            self.message_user(request, f'✅ GPT-4o успішно додано!', level=messages.SUCCESS)
        else:
            self.message_user(request, f'⚠️ GPT-4o вже існує', level=messages.WARNING)
    
    @admin.action(description='➕ Додати GPT-4o Mini')
    def add_gpt_4o_mini(self, request, queryset):
        """Додати GPT-4o Mini провайдер"""
        provider, created = LLMProvider.objects.get_or_create(
            slug='gpt-4o-mini',
            defaults={
                'name': 'GPT-4o Mini',
                'provider_type': 'openai',
                'model_name': 'gpt-4o-mini',
                'api_key': getattr(settings, 'OPENAI_API_KEY', '').strip() or '',
                'max_tokens': 16384,
                'temperature': 0.7,
                'cost_per_1k_input_tokens': 0.00015,
                'cost_per_1k_output_tokens': 0.0006,
                'is_active': True,
                'is_default': True,
                'description': 'OpenAI GPT-4o Mini - швидка та економна модель'
            }
        )
        
        if created:
            self.message_user(request, f'✅ GPT-4o Mini успішно додано!', level=messages.SUCCESS)
        else:
            self.message_user(request, f'⚠️ GPT-4o Mini вже існує', level=messages.WARNING)
    
    @admin.action(description='➕ Додати GPT-4 Turbo')
    def add_gpt_4_turbo(self, request, queryset):
        """Додати GPT-4 Turbo провайдер"""
        provider, created = LLMProvider.objects.get_or_create(
            slug='gpt-4-turbo',
            defaults={
                'name': 'GPT-4 Turbo',
                'provider_type': 'openai',
                'model_name': 'gpt-4-turbo',
                'api_key': getattr(settings, 'OPENAI_API_KEY', '').strip() or '',
                'max_tokens': 4096,
                'temperature': 0.7,
                'cost_per_1k_input_tokens': 0.01,
                'cost_per_1k_output_tokens': 0.03,
                'is_active': True,
                'is_default': False,
                'description': 'OpenAI GPT-4 Turbo - швидка версія GPT-4'
            }
        )
        
        if created:
            self.message_user(request, f'✅ GPT-4 Turbo успішно додано!', level=messages.SUCCESS)
        else:
            self.message_user(request, f'⚠️ GPT-4 Turbo вже існує', level=messages.WARNING)
    
    @admin.action(description='➕ Додати GPT-4')
    def add_gpt_4(self, request, queryset):
        """Додати GPT-4 провайдер"""
        provider, created = LLMProvider.objects.get_or_create(
            slug='gpt-4',
            defaults={
                'name': 'GPT-4',
                'provider_type': 'openai',
                'model_name': 'gpt-4',
                'api_key': getattr(settings, 'OPENAI_API_KEY', '').strip() or '',
                'max_tokens': 4096,
                'temperature': 0.7,
                'cost_per_1k_input_tokens': 0.03,
                'cost_per_1k_output_tokens': 0.06,
                'is_active': True,
                'is_default': False,
                'description': 'OpenAI GPT-4 - класична потужна модель'
            }
        )
        
        if created:
            self.message_user(request, f'✅ GPT-4 успішно додано!', level=messages.SUCCESS)
        else:
            self.message_user(request, f'⚠️ GPT-4 вже існує', level=messages.WARNING)
    
    @admin.action(description='➕ Додати GPT-3.5 Turbo')
    def add_gpt_3_5_turbo(self, request, queryset):
        """Додати GPT-3.5 Turbo провайдер"""
        provider, created = LLMProvider.objects.get_or_create(
            slug='gpt-3-5-turbo',
            defaults={
                'name': 'GPT-3.5 Turbo',
                'provider_type': 'openai',
                'model_name': 'gpt-3.5-turbo',
                'api_key': getattr(settings, 'OPENAI_API_KEY', '').strip() or '',
                'max_tokens': 4096,
                'temperature': 0.7,
                'cost_per_1k_input_tokens': 0.0005,
                'cost_per_1k_output_tokens': 0.0015,
                'is_active': True,
                'is_default': False,
                'description': 'OpenAI GPT-3.5 Turbo - економна та швидка модель'
            }
        )
        
        if created:
            self.message_user(request, f'✅ GPT-3.5 Turbo успішно додано!', level=messages.SUCCESS)
        else:
            self.message_user(request, f'⚠️ GPT-3.5 Turbo вже існує', level=messages.WARNING)
    
    @admin.action(description='➕ Додати GPT-3.5 Turbo 16k')
    def add_gpt_3_5_turbo_16k(self, request, queryset):
        """Додати GPT-3.5 Turbo 16k провайдер"""
        provider, created = LLMProvider.objects.get_or_create(
            slug='gpt-3-5-turbo-16k',
            defaults={
                'name': 'GPT-3.5 Turbo 16k',
                'provider_type': 'openai',
                'model_name': 'gpt-3.5-turbo-16k',
                'api_key': getattr(settings, 'OPENAI_API_KEY', '').strip() or '',
                'max_tokens': 16384,
                'temperature': 0.7,
                'cost_per_1k_input_tokens': 0.003,
                'cost_per_1k_output_tokens': 0.004,
                'is_active': True,
                'is_default': False,
                'description': 'OpenAI GPT-3.5 Turbo 16k - версія з розширеним контекстом'
            }
        )
        
        if created:
            self.message_user(request, f'✅ GPT-3.5 Turbo 16k успішно додано!', level=messages.SUCCESS)
        else:
            self.message_user(request, f'⚠️ GPT-3.5 Turbo 16k вже існує', level=messages.WARNING)
    
    @admin.action(description='➕ Додати o1-preview')
    def add_o1_preview(self, request, queryset):
        """Додати o1-preview провайдер"""
        provider, created = LLMProvider.objects.get_or_create(
            slug='o1-preview',
            defaults={
                'name': 'o1-preview',
                'provider_type': 'openai',
                'model_name': 'o1-preview',
                'api_key': getattr(settings, 'OPENAI_API_KEY', '').strip() or '',
                'max_tokens': 16384,
                'temperature': 0.0,  # o1 моделі не підтримують temperature
                'cost_per_1k_input_tokens': 0.015,
                'cost_per_1k_output_tokens': 0.06,
                'is_active': True,
                'is_default': False,
                'description': 'OpenAI o1-preview - модель з покращеним міркуванням'
            }
        )
        
        if created:
            self.message_user(request, f'✅ o1-preview успішно додано!', level=messages.SUCCESS)
        else:
            self.message_user(request, f'⚠️ o1-preview вже існує', level=messages.WARNING)
    
    @admin.action(description='➕ Додати o1-mini')
    def add_o1_mini(self, request, queryset):
        """Додати o1-mini провайдер"""
        provider, created = LLMProvider.objects.get_or_create(
            slug='o1-mini',
            defaults={
                'name': 'o1-mini',
                'provider_type': 'openai',
                'model_name': 'o1-mini',
                'api_key': getattr(settings, 'OPENAI_API_KEY', '').strip() or '',
                'max_tokens': 16384,
                'temperature': 0.0,  # o1 моделі не підтримують temperature
                'cost_per_1k_input_tokens': 0.003,
                'cost_per_1k_output_tokens': 0.012,
                'is_active': True,
                'is_default': False,
                'description': 'OpenAI o1-mini - компактна версія o1 з покращеним міркуванням'
            }
        )
        
        if created:
            self.message_user(request, f'✅ o1-mini успішно додано!', level=messages.SUCCESS)
        else:
            self.message_user(request, f'⚠️ o1-mini вже існує', level=messages.WARNING)
    
    @admin.action(description='➕ Додати Claude 3.5 Sonnet')
    def add_claude_3_5_sonnet(self, request, queryset):
        """Додати Claude 3.5 Sonnet провайдер"""
        provider, created = LLMProvider.objects.get_or_create(
            slug='claude-3-5-sonnet',
            defaults={
                'name': 'Claude 3.5 Sonnet',
                'provider_type': 'anthropic',
                'model_name': 'claude-3-5-sonnet-20241022',
                'api_key': getattr(settings, 'ANTHROPIC_API_KEY', '').strip() or '',
                'max_tokens': 8192,
                'temperature': 0.7,
                'cost_per_1k_input_tokens': 0.003,
                'cost_per_1k_output_tokens': 0.015,
                'is_active': True,
                'is_default': False,
                'description': 'Anthropic Claude 3.5 Sonnet - найпотужніша модель Claude 3.5 серії'
            }
        )
        
        if created:
            self.message_user(request, f'✅ Claude 3.5 Sonnet успішно додано!', level=messages.SUCCESS)
        else:
            self.message_user(request, f'⚠️ Claude 3.5 Sonnet вже існує', level=messages.WARNING)
    
    @admin.action(description='➕ Додати Claude 4')
    def add_claude_4(self, request, queryset):
        """Додати Claude 4 провайдер (якщо доступна)"""
        provider, created = LLMProvider.objects.get_or_create(
            slug='claude-4',
            defaults={
                'name': 'Claude 4',
                'provider_type': 'anthropic',
                'model_name': 'claude-4',  # Оновіть на актуальну версію коли з'явиться
                'api_key': getattr(settings, 'ANTHROPIC_API_KEY', '').strip() or '',
                'max_tokens': 8192,
                'temperature': 0.7,
                'cost_per_1k_input_tokens': 0.005,
                'cost_per_1k_output_tokens': 0.025,
                'is_active': False,  # Неактивна поки не вийде
                'is_default': False,
                'description': 'Anthropic Claude 4 - найновіша модель Claude (очікується)'
            }
        )
        
        if created:
            self.message_user(request, f'✅ Claude 4 успішно додано!', level=messages.SUCCESS)
        else:
            self.message_user(request, f'⚠️ Claude 4 вже існує', level=messages.WARNING)
    
    @admin.action(description='➕ Додати Claude 3.5 Haiku')
    def add_claude_3_5_haiku(self, request, queryset):
        """Додати Claude 3.5 Haiku провайдер"""
        provider, created = LLMProvider.objects.get_or_create(
            slug='claude-3-5-haiku',
            defaults={
                'name': 'Claude 3.5 Haiku',
                'provider_type': 'anthropic',
                'model_name': 'claude-3-5-haiku-20241022',
                'api_key': getattr(settings, 'ANTHROPIC_API_KEY', '').strip() or '',
                'max_tokens': 8192,
                'temperature': 0.7,
                'cost_per_1k_input_tokens': 0.0008,
                'cost_per_1k_output_tokens': 0.004,
                'is_active': True,
                'is_default': False,
                'description': 'Anthropic Claude 3.5 Haiku - швидка та економна модель'
            }
        )
        
        if created:
            self.message_user(request, f'✅ Claude 3.5 Haiku успішно додано!', level=messages.SUCCESS)
        else:
            self.message_user(request, f'⚠️ Claude 3.5 Haiku вже існує', level=messages.WARNING)
    
    @admin.action(description='➕ Додати Claude 3 Sonnet')
    def add_claude_3_sonnet(self, request, queryset):
        """Додати Claude 3 Sonnet провайдер"""
        provider, created = LLMProvider.objects.get_or_create(
            slug='claude-3-sonnet',
            defaults={
                'name': 'Claude 3 Sonnet',
                'provider_type': 'anthropic',
                'model_name': 'claude-3-sonnet-20240229',
                'api_key': getattr(settings, 'ANTHROPIC_API_KEY', '').strip() or '',
                'max_tokens': 4096,
                'temperature': 0.7,
                'cost_per_1k_input_tokens': 0.003,
                'cost_per_1k_output_tokens': 0.015,
                'is_active': True,
                'is_default': False,
                'description': 'Anthropic Claude 3 Sonnet - балансована модель серії Claude 3'
            }
        )
        
        if created:
            self.message_user(request, f'✅ Claude 3 Sonnet успішно додано!', level=messages.SUCCESS)
        else:
            self.message_user(request, f'⚠️ Claude 3 Sonnet вже існує', level=messages.WARNING)
    
    @admin.action(description='➕ Додати Claude 3 Haiku')
    def add_claude_3_haiku(self, request, queryset):
        """Додати Claude 3 Haiku провайдер"""
        provider, created = LLMProvider.objects.get_or_create(
            slug='claude-3-haiku',
            defaults={
                'name': 'Claude 3 Haiku',
                'provider_type': 'anthropic',
                'model_name': 'claude-3-haiku-20240307',
                'api_key': getattr(settings, 'ANTHROPIC_API_KEY', '').strip() or '',
                'max_tokens': 4096,
                'temperature': 0.7,
                'cost_per_1k_input_tokens': 0.00025,
                'cost_per_1k_output_tokens': 0.00125,
                'is_active': True,
                'is_default': False,
                'description': 'Anthropic Claude 3 Haiku - найшвидша та найдешевша модель серії Claude 3'
            }
        )
        
        if created:
            self.message_user(request, f'✅ Claude 3 Haiku успішно додано!', level=messages.SUCCESS)
        else:
            self.message_user(request, f'⚠️ Claude 3 Haiku вже існує', level=messages.WARNING)
    
    @admin.action(description='➕ Додати Claude 3 Opus')
    def add_claude_3_opus(self, request, queryset):
        """Додати Claude 3 Opus провайдер"""
        provider, created = LLMProvider.objects.get_or_create(
            slug='claude-3-opus',
            defaults={
                'name': 'Claude 3 Opus',
                'provider_type': 'anthropic',
                'model_name': 'claude-3-opus-20240229',
                'api_key': getattr(settings, 'ANTHROPIC_API_KEY', '').strip() or '',
                'max_tokens': 4096,
                'temperature': 0.7,
                'cost_per_1k_input_tokens': 0.015,
                'cost_per_1k_output_tokens': 0.075,
                'is_active': True,
                'is_default': False,
                'description': 'Anthropic Claude 3 Opus - найпотужніша модель серії Claude 3'
            }
        )
        
        if created:
            self.message_user(request, f'✅ Claude 3 Opus успішно додано!', level=messages.SUCCESS)
        else:
            self.message_user(request, f'⚠️ Claude 3 Opus вже існує', level=messages.WARNING)