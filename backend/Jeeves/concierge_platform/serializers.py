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
