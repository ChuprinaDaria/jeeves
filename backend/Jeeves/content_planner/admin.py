from django.contrib import admin

from Jeeves.content_planner.models import ContentPlan, ContentPost, ContentIdea


@admin.register(ContentPlan)
class ContentPlanAdmin(admin.ModelAdmin):
    list_display = ("title", "client", "status", "start_date", "end_date", "created_at")
    list_filter = ("status", "client")
    search_fields = ("title",)


@admin.register(ContentPost)
class ContentPostAdmin(admin.ModelAdmin):
    list_display = ("content_plan", "network", "scheduled_at", "status", "post_type")
    list_filter = ("status", "network", "post_type")
    search_fields = ("text",)


@admin.register(ContentIdea)
class ContentIdeaAdmin(admin.ModelAdmin):
    list_display = ("topic", "client", "network", "status", "created_at")
    list_filter = ("status", "network", "client")
    search_fields = ("topic", "details")
