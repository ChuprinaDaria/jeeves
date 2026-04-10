from django.contrib import admin
from django.utils.html import format_html
import json
from django.db import models
from .models import Branch, BranchDocument, BranchEmbedding


class HasMetadataFilter(admin.SimpleListFilter):
    title = 'Has Metadata'
    parameter_name = 'has_metadata'

    def lookups(self, request, model_admin):
        return (
            ('yes', 'Yes'),
            ('no', 'No'),
        )

    def queryset(self, request, queryset):
        value = self.value()
        if value == 'yes':
            return queryset.exclude(metadata={}).exclude(metadata__isnull=True)
        if value == 'no':
            return queryset.filter(models.Q(metadata={}) | models.Q(metadata__isnull=True))
        return queryset


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'owner', 'embedding_model', 'is_active', 'total_documents', 'total_embeddings', 'created_at']
    list_filter = ['is_active', 'embedding_model', 'created_at']
    search_fields = ['name', 'slug', 'description']
    ordering = ['name']
    prepopulated_fields = {'slug': ('name',)}
    list_editable = ['is_active']
    readonly_fields = ['created_by', 'created_at', 'updated_at', 'total_documents', 'total_embeddings']
    
    fieldsets = (
        ('Basic Info', {
            'fields': ('name', 'slug', 'description', 'is_active')
        }),
        ('Configuration', {
            'fields': ('embedding_model', 'owner')
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
        ('Statistics', {
            'fields': ('total_documents', 'total_embeddings'),
            'classes': ('collapse',)
        }),
    )
    
    @admin.display(description='Documents')
    def total_documents(self, obj):
        return obj.documents.count()
    
    @admin.display(description='Embeddings')
    def total_embeddings(self, obj):
        return obj.embeddings.count()
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(BranchDocument)
class BranchDocumentAdmin(admin.ModelAdmin):
    list_display = ['title', 'branch', 'file_type', 'file_size_mb', 'is_processed', 'chunks_count', 'uploaded_by', 'uploaded_at']
    list_filter = ['branch', 'file_type', 'is_processed', 'uploaded_at', HasMetadataFilter]
    search_fields = ['title', 'branch__name']
    ordering = ['-uploaded_at']
    readonly_fields = ['uploaded_by', 'uploaded_at', 'file_size', 'is_processed', 'chunks_count', 'processing_error', 'metadata_display']
    
    fieldsets = (
        ('Document Info', {
            'fields': ('branch', 'title', 'file', 'file_type')
        }),
        ('Processing Status', {
            'fields': ('is_processed', 'chunks_count', 'processing_error')
        }),
        ('Metadata', {
            'fields': ('uploaded_by', 'uploaded_at', 'file_size', 'metadata_display'),
            'classes': ('collapse',)
        }),
    )
    
    @admin.display(description='Size')
    def file_size_mb(self, obj):
        return f"{obj.file_size / (1024 * 1024):.2f} MB"
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.uploaded_by = request.user
        super().save_model(request, obj, form, change)

    @admin.display(description='Metadata')
    def metadata_display(self, obj):
        try:
            pretty = json.dumps(obj.metadata or {}, ensure_ascii=False, indent=2)
        except Exception:
            pretty = str(obj.metadata)
        return format_html('<pre style="max-height:400px; overflow:auto;">{}</pre>', pretty)
 


@admin.register(BranchEmbedding)
class BranchEmbeddingAdmin(admin.ModelAdmin):
    list_display = ['id', 'branch', 'document', 'embedding_model', 'content_preview', 'created_at']
    list_filter = ['branch', 'embedding_model', 'created_at']
    search_fields = ['content', 'branch__name']
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'vector', 'vector_dimensions', 'metadata_display']
    
    fieldsets = (
        ('Relations', {
            'fields': ('branch', 'document', 'embedding_model'),
            'description': 'Виберіть Branch, Document (опційно) та Embedding Model'
        }),
        ('Content', {
            'fields': ('content', 'metadata', 'metadata_display'),
            'description': 'Введіть текст у поле Content. Вектор згенерується автоматично при збереженні.'
        }),
        ('Vector (Auto-generated)', {
            'fields': ('vector', 'vector_dimensions'),
            'classes': ('collapse',),
            'description': 'Вектор генерується автоматично на основі Content та Embedding Model'
        }),
        ('Metadata', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
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
            pretty = json.dumps(obj.metadata or {}, ensure_ascii=False, indent=2)
        except Exception:
            pretty = str(obj.metadata)
        return format_html('<pre style="max-height:400px; overflow:auto;">{}</pre>', pretty)