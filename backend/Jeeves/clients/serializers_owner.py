from rest_framework import serializers

from Jeeves.branches.models import Branch
from Jeeves.EmbeddingModel.models import EmbeddingModel, LLMProvider
from Jeeves.specializations.models import Specialization
from .models import Client

MASK_VISIBLE = 4


def _mask(value):
    if not value:
        return None
    if len(value) <= MASK_VISIBLE:
        return '****'
    return f"****{value[-MASK_VISIBLE:]}"


# ---------------------------------------------------------------------------
# Nested serializers (read-only, id + name only)
# ---------------------------------------------------------------------------

class BranchNestedSerializer(serializers.ModelSerializer):
    class Meta:
        model = Branch
        fields = ['id', 'name']


class SpecializationNestedSerializer(serializers.ModelSerializer):
    class Meta:
        model = Specialization
        fields = ['id', 'name']


class LLMProviderNestedSerializer(serializers.ModelSerializer):
    class Meta:
        model = LLMProvider
        fields = ['id', 'name']


class EmbeddingModelNestedSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmbeddingModel
        fields = ['id', 'name']


# ---------------------------------------------------------------------------
# Main serializer
# ---------------------------------------------------------------------------

class ClientOwnerSerializer(serializers.ModelSerializer):
    # Basic Info — nested FK reads + write-only ID fields
    branch = BranchNestedSerializer(read_only=True)
    branch_id = serializers.PrimaryKeyRelatedField(
        queryset=Branch.objects.all(),
        source='branch',
        write_only=True,
        required=False,
        allow_null=True,
    )
    specialization = SpecializationNestedSerializer(read_only=True)
    specialization_id = serializers.PrimaryKeyRelatedField(
        queryset=Specialization.objects.all(),
        source='specialization',
        write_only=True,
        required=False,
        allow_null=True,
    )

    # AI Config — nested FK reads + write-only ID fields
    llm_provider_model = LLMProviderNestedSerializer(read_only=True)
    llm_provider_model_id = serializers.PrimaryKeyRelatedField(
        queryset=LLMProvider.objects.all(),
        source='llm_provider_model',
        write_only=True,
        required=False,
        allow_null=True,
    )
    embedding_model = EmbeddingModelNestedSerializer(read_only=True)
    embedding_model_id = serializers.PrimaryKeyRelatedField(
        queryset=EmbeddingModel.objects.all(),
        source='embedding_model',
        write_only=True,
        required=False,
        allow_null=True,
    )

    # SMTP password — write-only field + masked read helpers
    email_smtp_password = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        allow_null=True,
    )
    smtp_password_masked = serializers.SerializerMethodField()
    smtp_password_set = serializers.SerializerMethodField()

    # API key — masked read-only
    api_key_masked = serializers.SerializerMethodField()

    class Meta:
        model = Client
        fields = [
            # Basic Info
            'id',
            'company_name',
            'user',
            'tag',
            'description',
            'client_type',
            'is_active',
            'branch',
            'branch_id',
            'specialization',
            'specialization_id',
            'greeting_message',

            # AI Config
            'llm_provider_model',
            'llm_provider_model_id',
            'embedding_model',
            'embedding_model_id',

            # Channels
            'telegram_enabled',
            'whatsapp_meta_enabled',
            'whatsapp_bridge_enabled',
            'whatsapp_bridge_status',
            'email_smtp_enabled',
            'widget_enabled',

            # SMTP Config
            'email_smtp_host',
            'email_smtp_port',
            'email_smtp_use_tls',
            'email_smtp_username',
            'email_smtp_password',
            'smtp_password_masked',
            'smtp_password_set',
            'email_from_address',
            'email_from_name',

            # Email Reports
            'email_report_enabled',
            'email_report_recipients',
            'notification_language',

            # Features
            'leads_enabled',
            'extension_enabled',
            'pixel_dashboard_enabled',

            # Metadata
            'api_key_masked',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'whatsapp_bridge_status',
            'smtp_password_masked',
            'smtp_password_set',
            'api_key_masked',
            'created_at',
            'updated_at',
        ]

    # --- Method fields ---

    def get_smtp_password_masked(self, obj):
        return _mask(obj.email_smtp_password)

    def get_smtp_password_set(self, obj):
        return bool(obj.email_smtp_password)

    def get_api_key_masked(self, obj):
        return _mask(obj.api_key)

    # --- Write semantics for SMTP password ---

    def update(self, instance, validated_data):
        smtp_password = validated_data.pop('email_smtp_password', serializers.empty)
        if smtp_password is serializers.empty or smtp_password is None:
            pass  # keep existing
        else:
            instance.email_smtp_password = smtp_password  # '' clears, non-empty replaces
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance
