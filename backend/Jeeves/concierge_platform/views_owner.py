from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from Jeeves.branches.models import Branch, BranchDocument
from Jeeves.clients.models import Client
from Jeeves.concierge_platform.permissions import IsOwner
from Jeeves.EmbeddingModel.models import EmbeddingModel, LLMProvider
from Jeeves.specializations.models import Specialization, SpecializationDocument


class DashboardStatsView(APIView):
    """Counters + config-health checklist for /owner/dashboard."""

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsOwner]

    def get(self, request):
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
            "llm_providers_configured": LLMProvider.objects.filter(is_active=True).exists(),
            "embedding_models_configured": EmbeddingModel.objects.filter(is_active=True).exists(),
            "branches_exist": Branch.objects.exists(),
        }

        return Response({
            "counters": counters,
            "config_health": config_health,
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
