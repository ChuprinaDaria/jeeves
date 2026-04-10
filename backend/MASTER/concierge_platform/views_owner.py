from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from MASTER.branches.models import Branch, BranchDocument
from MASTER.clients.models import Client
from MASTER.concierge_platform.models import PlatformLicense
from MASTER.concierge_platform.permissions import IsOwner
from MASTER.EmbeddingModel.models import EmbeddingModel, LLMProvider
from MASTER.specializations.models import Specialization, SpecializationDocument


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
