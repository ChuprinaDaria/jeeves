from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from Jeeves.branches.models import Branch, BranchDocument
from Jeeves.clients.models import Client
from Jeeves.concierge_platform.models import PlatformLicense
from Jeeves.concierge_platform.permissions import IsOwner
from Jeeves.EmbeddingModel.models import EmbeddingModel, LLMProvider
from Jeeves.specializations.models import Specialization, SpecializationDocument


class DashboardStatsView(APIView):
    """Counters + config-health checklist + license card for /owner/dashboard."""

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsOwner]

    def get(self, request):
        lic = PlatformLicense.get()

        counters = {
            "branches": Branch.objects.count(),
            "specializations": Specialization.objects.count(),
            "clients": Client.objects.count(),
            "documents": (
                BranchDocument.objects.count()
                + SpecializationDocument.objects.count()
            ),
        }

        config_health = {
            "license_valid": lic.status == PlatformLicense.LicenseStatus.VALID,
            "llm_providers_configured": LLMProvider.objects.filter(is_active=True).exists(),
            "embedding_models_configured": EmbeddingModel.objects.filter(is_active=True).exists(),
            "branches_exist": Branch.objects.exists(),
        }

        return Response({
            "counters": counters,
            "config_health": config_health,
            "license": {
                "status": lic.status,
                "last_verified_at": (
                    lic.last_verified_at.isoformat() if lic.last_verified_at else None
                ),
                "grace_days_remaining": lic.grace_days_remaining,
            },
        })


from django.utils import timezone
from rest_framework import status as drf_status

from Jeeves.concierge_platform import gumroad_client


class ReverifyLicenseView(APIView):
    """Manual 'Re-verify now' button in Settings. Works even when expired."""

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsOwner]

    def post(self, request):
        lic = PlatformLicense.get()
        if not lic.license_key:
            return Response(
                {"error": "no_license_key"},
                status=drf_status.HTTP_400_BAD_REQUEST,
            )

        result = gumroad_client.verify_license(lic.license_key)
        now = timezone.now()
        lic.last_attempt_at = now

        if result.outcome == "valid":
            lic.status = PlatformLicense.LicenseStatus.VALID
            lic.last_verified_at = now
            lic.last_error = ""
            purchase = result.data.get("purchase", {}) or {}
            lic.gumroad_purchase_email = purchase.get("email", "") or ""
            lic.gumroad_product_id = purchase.get("product_id", "") or ""
            lic.gumroad_uses = int(result.data.get("uses", 0) or 0)
        elif result.outcome == "invalid":
            lic.last_error = result.error
            # leave status as-is: if it was expired it stays expired
        else:
            # network_error: do not change status on reverify, just record attempt
            lic.last_error = result.error

        lic.save()
        return Response({
            "status": lic.status,
            "last_verified_at": (
                lic.last_verified_at.isoformat() if lic.last_verified_at else None
            ),
            "grace_days_remaining": lic.grace_days_remaining,
        })


from Jeeves.concierge_platform.models import PlatformDefaults
from Jeeves.concierge_platform.serializers import PlatformDefaultsSerializer


class PlatformDefaultsView(APIView):
    """Singleton get/put for /owner/settings/defaults."""

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsOwner]

    def get(self, request):
        obj = PlatformDefaults.get()
        return Response(PlatformDefaultsSerializer(obj).data)

    def put(self, request):
        obj = PlatformDefaults.get()
        serializer = PlatformDefaultsSerializer(
            obj, data=request.data, partial=False,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
