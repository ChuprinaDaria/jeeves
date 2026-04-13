from rest_framework import serializers
from Jeeves.clients.models import Client
from .models import FeatureFlag, SystemMessage


class FeatureFlagSerializer(serializers.ModelSerializer):
    enabled_clients = serializers.PrimaryKeyRelatedField(
        queryset=Client.objects.all(), many=True, required=False,
    )
    enabled_clients_display = serializers.SerializerMethodField()

    class Meta:
        model = FeatureFlag
        fields = [
            'id', 'key', 'description', 'rollout',
            'enabled_clients', 'enabled_clients_display',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'enabled_clients_display', 'created_at', 'updated_at']

    def get_enabled_clients_display(self, obj):
        return list(obj.enabled_clients.values('id', 'company_name', 'tag'))


class SystemMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = SystemMessage
        fields = ['id', 'key', 'translations', 'description']
        read_only_fields = ['id']
