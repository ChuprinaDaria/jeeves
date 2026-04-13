from django.db.models import Count
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication

from Jeeves.branches.models import Branch
from Jeeves.concierge_platform.permissions import IsOwner
from Jeeves.EmbeddingModel.models import EmbeddingModel
from .models import Specialization
from .serializers_owner import SpecializationOwnerSerializer


class SpecializationOwnerViewSet(viewsets.ModelViewSet):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsOwner]
    serializer_class = SpecializationOwnerSerializer

    def get_queryset(self):
        return Specialization.objects.select_related(
            'branch', 'embedding_model',
        ).annotate(
            documents_count=Count('documents', distinct=True),
            clients_count=Count('clients', distinct=True),
        ).order_by('branch__name', 'name')

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=False, methods=['get'])
    def choices(self, request):
        return Response({
            'branches': list(
                Branch.objects.filter(is_active=True).values('id', 'name').order_by('name')
            ),
            'embedding_models': list(
                EmbeddingModel.objects.filter(is_active=True).values('id', 'name').order_by('name')
            ),
        })
