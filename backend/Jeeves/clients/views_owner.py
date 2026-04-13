import logging

from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication

from Jeeves.branches.models import Branch
from Jeeves.concierge_platform.permissions import IsOwner
from Jeeves.EmbeddingModel.models import EmbeddingModel, LLMProvider
from Jeeves.specializations.models import Specialization
from .models import Client
from .serializers_owner import ClientOwnerSerializer

logger = logging.getLogger(__name__)


class ClientOwnerViewSet(viewsets.ModelViewSet):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsOwner]
    serializer_class = ClientOwnerSerializer

    def get_queryset(self):
        return Client.objects.select_related(
            'branch', 'specialization', 'llm_provider_model', 'embedding_model',
        ).order_by('-created_at')

    @action(detail=False, methods=['get'])
    def choices(self, request):
        """Return options for dropdowns: branches, specializations, LLM providers, embedding models."""
        return Response({
            'branches': list(
                Branch.objects.values('id', 'name').order_by('name')
            ),
            'specializations': list(
                Specialization.objects.values('id', 'name').order_by('name')
            ),
            'llm_providers': list(
                LLMProvider.objects.filter(is_active=True).values('id', 'name').order_by('name')
            ),
            'embedding_models': list(
                EmbeddingModel.objects.filter(is_active=True).values('id', 'name').order_by('name')
            ),
            'client_types': [
                {'value': c[0], 'label': c[1]} for c in Client.CLIENT_TYPE_CHOICES
            ],
            'notification_languages': [
                {'value': 'en', 'label': 'English'},
                {'value': 'de', 'label': 'Deutsch'},
                {'value': 'fr', 'label': 'Français'},
                {'value': 'es', 'label': 'Español'},
                {'value': 'it', 'label': 'Italiano'},
                {'value': 'nl', 'label': 'Nederlands'},
                {'value': 'da', 'label': 'Dansk'},
                {'value': 'uk', 'label': 'Українська'},
                {'value': 'ru', 'label': 'Русский'},
            ],
        })
