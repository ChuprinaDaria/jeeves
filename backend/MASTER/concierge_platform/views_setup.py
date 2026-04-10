from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from MASTER.accounts.models import User, Roles
from MASTER.concierge_platform.serializers import OwnerCreateSerializer


class CreateOwnerView(APIView):
    """Create the first (and only) OWNER user during the setup wizard.

    Rejects with 409 if an owner already exists. The owner also gets
    is_superuser/is_staff flags as a fallback path into Django admin.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        if User.objects.filter(role=Roles.OWNER).exists():
            return Response(
                {"error": "owner_exists"},
                status=status.HTTP_409_CONFLICT,
            )

        serializer = OwnerCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        user = User.objects.create_user(
            username=data["email"],
            email=data["email"],
            password=data["password"],
            first_name=data["first_name"],
            last_name=data["last_name"],
            role=Roles.OWNER,
            is_staff=True,
            is_superuser=True,
        )

        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "role": user.role,
                },
            },
            status=status.HTTP_201_CREATED,
        )


from django.utils import timezone
from rest_framework_simplejwt.authentication import JWTAuthentication

from MASTER.concierge_platform import gumroad_client
from MASTER.concierge_platform.models import PlatformLicense
from MASTER.concierge_platform.permissions import IsOwner
from MASTER.concierge_platform.serializers import LicenseKeySerializer


class SetupLicenseView(APIView):
    """Save + verify the Gumroad license key during wizard Step 2.

    - valid:         persist key, status=valid, return 200 valid
    - invalid:       do NOT persist, return 400 invalid_key
    - network_error: persist key, status=grace, return 200 grace
    """

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsOwner]

    def post(self, request):
        serializer = LicenseKeySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        license_key = serializer.validated_data["license_key"]

        result = gumroad_client.verify_license(license_key)
        lic = PlatformLicense.get()
        now = timezone.now()

        if result.outcome == "valid":
            lic.license_key = license_key
            lic.status = PlatformLicense.LicenseStatus.VALID
            lic.last_verified_at = now
            lic.last_attempt_at = now
            lic.last_error = ""
            purchase = result.data.get("purchase", {}) or {}
            lic.gumroad_purchase_email = purchase.get("email", "") or ""
            lic.gumroad_product_id = purchase.get("product_id", "") or ""
            lic.gumroad_uses = int(result.data.get("uses", 0) or 0)
            lic.save()
            return Response({"status": "valid"})

        if result.outcome == "invalid":
            return Response(
                {"error": "invalid_key", "message": result.error},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # network_error — grace
        lic.license_key = license_key
        lic.status = PlatformLicense.LicenseStatus.GRACE
        lic.last_attempt_at = now
        lic.last_error = result.error
        lic.save()
        return Response({
            "status": "grace",
            "message": (
                "We couldn't reach Gumroad. Your key was saved and we'll retry "
                "automatically. Grace period: 7 days."
            ),
        })
