from rest_framework import serializers
from .models import ToolCard, ToolConnection


class ToolCardSerializer(serializers.ModelSerializer):
    class Meta:
        model = ToolCard
        fields = ['slug', 'name', 'tagline', 'tagline_i18n', 'description',
                  'icon', 'color', 'category', 'is_featured', 'auth_type',
                  'auth_config']


class ToolConnectionSerializer(serializers.ModelSerializer):
    tool = ToolCardSerializer(source='tool_card', read_only=True)

    class Meta:
        model = ToolConnection
        fields = ['id', 'tool', 'status', 'target', 'enabled',
                  'position_x', 'position_y',
                  'connected_at', 'last_used_at', 'last_error', 'error_count']


class FlowConnectionSerializer(serializers.ModelSerializer):
    """Lightweight serializer for flow canvas connections."""
    slug = serializers.CharField(source='tool_card.slug', read_only=True)
    name = serializers.CharField(source='tool_card.name', read_only=True)
    icon = serializers.CharField(source='tool_card.icon', read_only=True)
    color = serializers.CharField(source='tool_card.color', read_only=True)
    category = serializers.CharField(source='tool_card.category', read_only=True)

    class Meta:
        model = ToolConnection
        fields = ['id', 'slug', 'name', 'icon', 'color', 'category',
                  'status', 'target', 'enabled',
                  'position_x', 'position_y', 'connected_at']


class FlowConnectionUpdateSerializer(serializers.Serializer):
    """For PATCH — update target, position, or enabled."""
    target = serializers.ChoiceField(
        choices=ToolConnection.TARGET_CHOICES, required=False)
    position_x = serializers.FloatField(required=False, allow_null=True)
    position_y = serializers.FloatField(required=False, allow_null=True)
    enabled = serializers.BooleanField(required=False)


class ToolCatalogItemSerializer(serializers.Serializer):
    """ToolCard + connection status for this client."""
    slug = serializers.CharField()
    name = serializers.CharField()
    tagline = serializers.CharField()
    tagline_i18n = serializers.JSONField()
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
