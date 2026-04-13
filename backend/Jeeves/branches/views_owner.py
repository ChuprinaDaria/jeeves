from django.db.models import Count
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication

from Jeeves.concierge_platform.permissions import IsOwner
from Jeeves.EmbeddingModel.models import EmbeddingModel
from .models import Branch
from .serializers_owner import BranchOwnerSerializer


class BranchOwnerViewSet(viewsets.ModelViewSet):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsOwner]
    serializer_class = BranchOwnerSerializer

    def get_queryset(self):
        return Branch.objects.select_related('embedding_model').annotate(
            documents_count=Count('documents', distinct=True),
            clients_count=Count('clients', distinct=True),
        ).order_by('name')

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=False, methods=['get'])
    def choices(self, request):
        return Response({
            'embedding_models': list(
                EmbeddingModel.objects.filter(is_active=True).values('id', 'name').order_by('name')
            ),
        })
