from rest_framework import serializers

from Jeeves.accounts.models import User


class OwnerCreateSerializer(serializers.Serializer):
    """Validates input for POST /api/setup/owner.

    Only used during first-run setup wizard Step 1. The view handles the
    actual user creation (including `is_superuser`/`is_staff` flags) and
    the 'owner already exists' 409 short-circuit — this serializer only
    validates input shape and simple uniqueness.
    """

    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    first_name = serializers.CharField(max_length=30)
    last_name = serializers.CharField(max_length=30)

    def validate_password(self, value):
        if len(value) < 8:
            raise serializers.ValidationError("weak_password")
        return value

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("email_taken")
        return value


class LicenseKeySerializer(serializers.Serializer):
    """Validates input for POST /api/setup/license and /api/owner/license/reverify.

    Thin wrapper — the real validation is done by the Gumroad API call
    inside the view.
    """

    license_key = serializers.CharField(max_length=100, min_length=1)


from Jeeves.concierge_platform.models import PlatformDefaults


class PlatformDefaultsSerializer(serializers.ModelSerializer):
    default_llm = serializers.SerializerMethodField()
    default_embedding = serializers.SerializerMethodField()

    class Meta:
        model = PlatformDefaults
        fields = [
            'default_temperature',
            'default_max_tokens',
            'default_similarity_threshold',
            'default_max_context_chunks',
            'default_top_k',
            'supported_languages',
            'default_language',
            'language_detection_method',
            'default_greeting',
            'default_llm',
            'default_embedding',
        ]

    def get_default_llm(self, obj):
        llm = PlatformDefaults.get_default_llm_provider()
        if not llm:
            return None
        return {'id': llm.pk, 'name': llm.name, 'is_default': llm.is_default}

    def get_default_embedding(self, obj):
        em = PlatformDefaults.get_default_embedding_model()
        if not em:
            return None
        return {'id': em.pk, 'name': em.name, 'is_default': em.is_default}

    def validate_default_temperature(self, value):
        if value is None:
            return value
        if not (0.0 <= float(value) <= 2.0):
            raise serializers.ValidationError('must be between 0.0 and 2.0')
        return value

    def validate_default_max_tokens(self, value):
        if value is not None and int(value) < 1:
            raise serializers.ValidationError('must be >= 1')
        return value

    def validate_default_similarity_threshold(self, value):
        if value is None:
            return value
        if not (0.0 <= float(value) <= 1.0):
            raise serializers.ValidationError('must be between 0.0 and 1.0')
        return value

    def validate_default_max_context_chunks(self, value):
        if value is not None and int(value) < 1:
            raise serializers.ValidationError('must be >= 1')
        return value

    def validate_default_top_k(self, value):
        if value is not None and int(value) < 1:
            raise serializers.ValidationError('must be >= 1')
        return value

    def validate_language_detection_method(self, value):
        if value and value not in ('llm', 'library', 'none'):
            raise serializers.ValidationError(
                "must be one of 'llm', 'library', 'none'",
            )
        return value

    def validate(self, attrs):
        lang = attrs.get('default_language') or getattr(
            self.instance, 'default_language', '',
        )
        supported = attrs.get('supported_languages')
        if supported is None:
            supported = getattr(self.instance, 'supported_languages', []) or []
        if lang and supported and lang not in supported:
            raise serializers.ValidationError({
                'default_language': 'must be in supported_languages',
            })
        return attrs
