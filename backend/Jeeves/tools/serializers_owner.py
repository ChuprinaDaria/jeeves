from django.utils.text import slugify
from rest_framework import serializers

from .models import ToolCard


class ToolCardOwnerSerializer(serializers.ModelSerializer):
    connections_count = serializers.IntegerField(read_only=True, default=0)
    tools_count = serializers.SerializerMethodField()

    class Meta:
        model = ToolCard
        fields = [
            'id', 'name', 'slug', 'tagline', 'tagline_i18n', 'description',
            'icon', 'color', 'category',
            'mcp_server_url', 'transport_type', 'is_builtin', 'builtin_handler',
            'tools_schema', 'scope_schema', 'skill_scopes',
            'auth_type', 'auth_config',
            'is_active', 'is_featured', 'is_system',
            'sort_order',
            'connections_count', 'tools_count',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'connections_count', 'tools_count',
            'created_at', 'updated_at',
        ]

    def get_tools_count(self, obj):
        schema = obj.tools_schema
        if isinstance(schema, list):
            return len(schema)
        return 0

    def validate_slug(self, value):
        return value  # allow explicit slug

    def create(self, validated_data):
        if not validated_data.get('slug'):
            base = slugify(validated_data.get('name', ''))
            slug = base
            counter = 2
            while ToolCard.objects.filter(slug=slug).exists():
                slug = f"{base}-{counter}"
                counter += 1
            validated_data['slug'] = slug
        return super().create(validated_data)


class DiscoverRequestSerializer(serializers.Serializer):
    url = serializers.URLField()


class FromUrlRequestSerializer(serializers.Serializer):
    url = serializers.URLField()
    name = serializers.CharField(max_length=100, required=False, default='')
    icon = serializers.CharField(max_length=50, required=False, default='puzzle')
    color = serializers.CharField(max_length=7, required=False, default='#6366f1')
    category = serializers.ChoiceField(
        choices=ToolCard.CATEGORY_CHOICES, required=False, default='custom',
    )
    targets = serializers.ListField(
        child=serializers.ChoiceField(choices=['assistant', 'manager', 'leads']),
        required=False, default=['assistant'],
    )
