from rest_framework import serializers
from .models import ToolCard, ToolConnection


class ToolCardSerializer(serializers.ModelSerializer):
    class Meta:
        model = ToolCard
        fields = ['slug', 'name', 'tagline', 'description', 'icon', 'color',
                  'category', 'is_featured', 'auth_type', 'auth_config']


class ToolConnectionSerializer(serializers.ModelSerializer):
    tool = ToolCardSerializer(source='tool_card', read_only=True)

    class Meta:
        model = ToolConnection
        fields = ['tool', 'status', 'enabled', 'connected_at', 'last_used_at',
                  'last_error', 'error_count']


class ToolCatalogItemSerializer(serializers.Serializer):
    """ToolCard + connection status for this client."""
    slug = serializers.CharField()
    name = serializers.CharField()
    tagline = serializers.CharField()
    description = serializers.CharField()
    icon = serializers.CharField()
    color = serializers.CharField()
    category = serializers.CharField()
    is_featured = serializers.BooleanField()
    auth_type = serializers.CharField()
    auth_config = serializers.JSONField()
    connection = serializers.DictField(allow_null=True)


class ConnectCredentialsSerializer(serializers.Serializer):
    """Dynamic credentials based on ToolCard.auth_config."""
    credentials = serializers.DictField(required=False, default=dict)
