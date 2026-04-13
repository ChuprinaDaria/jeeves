from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication

from Jeeves.clients.models import Client
from Jeeves.concierge_platform.permissions import IsOwner
from .models import FeatureFlag, SystemMessage
from .serializers_ff_sm import FeatureFlagSerializer, SystemMessageSerializer


class FeatureFlagViewSet(viewsets.ModelViewSet):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsOwner]
    serializer_class = FeatureFlagSerializer
    queryset = FeatureFlag.objects.prefetch_related('enabled_clients').order_by('key')

    @action(detail=False, methods=['get'])
    def choices(self, request):
        return Response({
            'clients': list(
                Client.objects.values('id', 'company_name', 'tag').order_by('company_name')
            ),
            'rollout_options': [
                {'value': c[0], 'label': c[1]} for c in FeatureFlag.ROLLOUT_CHOICES
            ],
        })


class SystemMessageViewSet(viewsets.ModelViewSet):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsOwner]
    serializer_class = SystemMessageSerializer
    queryset = SystemMessage.objects.order_by('key')
