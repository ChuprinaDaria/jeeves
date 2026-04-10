from rest_framework import serializers

from Jeeves.EmbeddingModel.models import EmbeddingModel, LLMProvider, ModelPair

MASK_VISIBLE = 4


def _mask(api_key):
    if not api_key:
        return None
    if len(api_key) <= MASK_VISIBLE:
        return '****'
    return f"****{api_key[-MASK_VISIBLE:]}"


class _ApiKeyWriteMixin:
    """Shared update-semantics for the write-only api_key field.

    - absent/None in payload → keep existing value unchanged
    - non-empty string → replace
    - empty string '' → clear
    """

    def update(self, instance, validated_data):
        api_key = validated_data.pop('api_key', serializers.empty)
        if api_key is serializers.empty:
            pass  # keep existing
        else:
            instance.api_key = api_key if api_key is not None else ''
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class LLMProviderSerializer(_ApiKeyWriteMixin, serializers.ModelSerializer):
    api_key = serializers.CharField(
        write_only=True, required=False, allow_blank=True, allow_null=True,
    )
    api_key_masked = serializers.SerializerMethodField()
    api_key_set = serializers.SerializerMethodField()
    usage = serializers.SerializerMethodField()
    can_delete = serializers.SerializerMethodField()

    class Meta:
        model = LLMProvider
        fields = [
            'id', 'name', 'slug', 'provider_type', 'model_name', 'api_endpoint',
            'api_key', 'api_key_masked', 'api_key_set',
            'cost_per_1k_input_tokens', 'cost_per_1k_output_tokens',
            'max_tokens', 'temperature',
            'is_active', 'is_default', 'description',
            'usage', 'can_delete',
            'created_at',
        ]
        read_only_fields = [
            'id', 'slug', 'api_key_masked', 'api_key_set', 'usage', 'can_delete',
            'created_at',
        ]

    def get_api_key_masked(self, obj):
        return _mask(obj.api_key)

    def get_api_key_set(self, obj):
        return bool(obj.api_key)

    def get_usage(self, obj):
        def _count(attr):
            rel = getattr(obj, attr, None)
            if rel is None:
                return 0
            try:
                return rel.count()
            except Exception:
                return 0
        return {
            'branches': _count('branches'),
            'specializations': _count('specializations'),
            'clients': _count('clients'),
            'agents': _count('agents'),
        }

    def get_can_delete(self, obj):
        return True


class EmbeddingModelSerializer(_ApiKeyWriteMixin, serializers.ModelSerializer):
    api_key = serializers.CharField(
        write_only=True, required=False, allow_blank=True, allow_null=True,
    )
    api_key_masked = serializers.SerializerMethodField()
    api_key_set = serializers.SerializerMethodField()
    usage = serializers.SerializerMethodField()
    can_delete = serializers.SerializerMethodField()

    class Meta:
        model = EmbeddingModel
        fields = [
            'id', 'name', 'slug', 'provider', 'model_name', 'dimensions',
            'api_endpoint', 'is_local', 'server_type',
            'api_key', 'api_key_masked', 'api_key_set',
            'cost_per_1k_tokens', 'external_guid',
            'is_active', 'is_default',
            'usage', 'can_delete',
            'created_at',
        ]
        read_only_fields = [
            'id', 'slug', 'api_key_masked', 'api_key_set', 'usage', 'can_delete',
            'created_at',
        ]

    def validate_dimensions(self, value):
        if value is None or value <= 0:
            raise serializers.ValidationError('dimensions must be > 0')
        if value > 2000:
            raise serializers.ValidationError(
                'pgvector HNSW limit is 2000 dimensions',
            )
        return value

    def get_api_key_masked(self, obj):
        return _mask(obj.api_key)

    def get_api_key_set(self, obj):
        return bool(obj.api_key)

    def get_usage(self, obj):
        def _count(attr):
            rel = getattr(obj, attr, None)
            if rel is None:
                return 0
            try:
                return rel.count()
            except Exception:
                return 0
        return {
            'branches': _count('branchembedding_set'),
            'specializations': _count('specializationembedding_set'),
            'clients': _count('client_set'),
            'documents': _count('document_set'),
        }

    def get_can_delete(self, obj):
        usage = self.get_usage(obj)
        return sum(usage.values()) == 0


class ModelPairNestedLLMSerializer(serializers.ModelSerializer):
    class Meta:
        model = LLMProvider
        fields = ['id', 'name', 'is_default']


class ModelPairNestedEmbeddingSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmbeddingModel
        fields = ['id', 'name', 'is_default']


class ModelPairSerializer(serializers.ModelSerializer):
    llm_provider = ModelPairNestedLLMSerializer(read_only=True)
    embedding_model = ModelPairNestedEmbeddingSerializer(read_only=True)
    llm_provider_id = serializers.PrimaryKeyRelatedField(
        queryset=LLMProvider.objects.all(),
        source='llm_provider',
        write_only=True,
    )
    embedding_model_id = serializers.PrimaryKeyRelatedField(
        queryset=EmbeddingModel.objects.all(),
        source='embedding_model',
        write_only=True,
    )

    class Meta:
        model = ModelPair
        fields = [
            'id', 'llm_provider', 'embedding_model',
            'llm_provider_id', 'embedding_model_id',
            'external_guid', 'is_active', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']
