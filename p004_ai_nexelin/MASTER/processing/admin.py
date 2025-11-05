from django.contrib import admin
from django.db.models import Sum, Count
from django.utils.html import format_html
from .models import UsageStats


@admin.register(UsageStats)
class UsageStatsAdmin(admin.ModelAdmin):
    list_display = ['entity_display', 'embedding_model', 'operation_type', 'tokens_used', 'cost_display', 'date']
    list_filter = ['operation_type', 'embedding_model', 'date']
    search_fields = ['client__user__username', 'branch__name', 'specialization__name']
    ordering = ['-created_at']
    readonly_fields = ['branch', 'specialization', 'client', 'embedding_model', 'operation_type', 'tokens_used', 'cost', 'date', 'created_at', 'metadata']
    
    date_hierarchy = 'date'
    
    fieldsets = (
        ('Entity Info', {
            'fields': ('client', 'branch', 'specialization')
        }),
        ('Usage Info', {
            'fields': ('embedding_model', 'operation_type', 'tokens_used', 'cost')
        }),
        ('Timestamps', {
            'fields': ('date', 'created_at', 'metadata'),
            'classes': ('collapse',)
        }),
    )
    
    @admin.display(description='Entity')
    def entity_display(self, obj):
        if obj.client:
            return f"CLIENT: {obj.client.user}"  # client.user is CharField
        elif obj.branch:
            return f"BRANCH: {obj.branch.name}"
        elif obj.specialization:
            return f"SPEC: {obj.specialization.name}"
        return "Unknown"
    
    
    @admin.display(description='Cost')
    def cost_display(self, obj):
        color = 'red' if obj.cost > 1 else 'green'
        return format_html(
            '<span style="color: {};">${}</span>',
            color,
            obj.cost
        )
    
    
    def has_add_permission(self, request):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return bool(getattr(request.user, "is_superuser", False))
    
    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        
        total_stats = UsageStats.objects.aggregate(
            total_tokens=Sum('tokens_used'),
            total_cost=Sum('cost'),
            total_operations=Count('id')
        )
        
        branch_stats = UsageStats.objects.filter(branch__isnull=False).aggregate(
            tokens=Sum('tokens_used'),
            cost=Sum('cost')
        )
        
        spec_stats = UsageStats.objects.filter(specialization__isnull=False).aggregate(
            tokens=Sum('tokens_used'),
            cost=Sum('cost')
        )
        
        client_stats = UsageStats.objects.filter(client__isnull=False).aggregate(
            tokens=Sum('tokens_used'),
            cost=Sum('cost')
        )
        
        extra_context['total_stats'] = total_stats
        extra_context['branch_stats'] = branch_stats
        extra_context['spec_stats'] = spec_stats
        extra_context['client_stats'] = client_stats
        
        return super().changelist_view(request, extra_context=extra_context)

