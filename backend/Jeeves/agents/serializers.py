from rest_framework import serializers
from .models import AgentConfig, AgentSession, AgentLog


class AgentConfigSerializer(serializers.ModelSerializer):
    llm_provider_name = serializers.CharField(source='llm_provider.name', read_only=True, default=None)
    embedding_model_name = serializers.CharField(source='embedding_model.name', read_only=True, default=None)
    # Resolved values (with platform defaults fallback)
    resolved_temperature = serializers.SerializerMethodField()
    resolved_max_tokens = serializers.SerializerMethodField()
    resolved_language = serializers.SerializerMethodField()

    class Meta:
        model = AgentConfig
        fields = [
            'llm_provider', 'llm_provider_name',
            'embedding_model', 'embedding_model_name',
            'system_prompt', 'greeting_message',
            'assistant_prompt', 'consultant_prompt',
            'assistant_description', 'consultant_description',
            'temperature', 'max_tokens',
            'similarity_threshold', 'max_context_chunks', 'top_k',
            'language', 'supported_languages', 'language_detection',
            'escalation_enabled', 'is_active',
            'resolved_temperature', 'resolved_max_tokens', 'resolved_language',
        ]

    def get_resolved_temperature(self, obj):
        return obj.get_temperature()

    def get_resolved_max_tokens(self, obj):
        return obj.get_max_tokens()

    def get_resolved_language(self, obj):
        return obj.get_language()


class AgentSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentSession
        fields = ['id', 'channel', 'external_user_id', 'language', 'started_at', 'ended_at']


class AgentLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentLog
        fields = ['call_type', 'tool_name', 'status', 'error_message',
                  'latency_ms', 'tokens_used', 'cost', 'created_at']
