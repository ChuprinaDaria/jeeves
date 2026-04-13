import logging

from django.db.models import Count
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication

from Jeeves.clients.models import Client
from Jeeves.concierge_platform.permissions import IsOwner
from .models import ToolCard, ToolConnection
from .mcp_discovery import discover_mcp_server, DiscoveryError
from .serializers_owner import (
    ToolCardOwnerSerializer,
    DiscoverRequestSerializer,
    FromUrlRequestSerializer,
)

logger = logging.getLogger(__name__)


class ToolCardOwnerViewSet(viewsets.ModelViewSet):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsOwner]
    serializer_class = ToolCardOwnerSerializer

    def get_queryset(self):
        return ToolCard.objects.annotate(
            connections_count=Count('connections'),
        ).order_by('sort_order', 'name')

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.is_builtin:
            return Response(
                {'error': 'Cannot delete built-in tools.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['post'])
    def discover(self, request):
        """Connect to MCP server URL, return available tools. Does not save."""
        ser = DiscoverRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        url = ser.validated_data['url']

        try:
            result = discover_mcp_server(url)
        except DiscoveryError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response({
            'server_name': result.server_name,
            'tools': result.tools,
        })

    @action(detail=False, methods=['post'], url_path='from-url')
    def from_url(self, request):
        """Discover + create ToolCard + auto-connect to all clients."""
        ser = FromUrlRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        # 1. Discover
        try:
            result = discover_mcp_server(data['url'])
        except DiscoveryError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 2. Create ToolCard
        name = data['name'] or result.server_name or 'Unnamed MCP Server'
        tool_data = {
            'name': name,
            'tagline': f"External MCP server with {len(result.tools)} tools",
            'description': ', '.join(t['name'] for t in result.tools),
            'icon': data['icon'],
            'color': data['color'],
            'category': data['category'],
            'mcp_server_url': data['url'],
            'transport_type': 'sse',
            'is_builtin': False,
            'tools_schema': result.tools,
            'auth_type': 'none',
            'is_active': True,
            'is_system': True,
            'skill_scopes': {'scopes': data['targets']},
        }
        card_ser = ToolCardOwnerSerializer(data=tool_data)
        card_ser.is_valid(raise_exception=True)
        tool_card = card_ser.save()

        # 3. Auto-connect all clients
        now = timezone.now()
        clients = Client.objects.all()
        connections = []
        for client in clients:
            for target in data['targets']:
                connections.append(ToolConnection(
                    client=client,
                    tool_card=tool_card,
                    target=target,
                    status='connected',
                    enabled=True,
                    connected_at=now,
                ))
        ToolConnection.objects.bulk_create(connections, ignore_conflicts=True)

        # Re-fetch with annotation
        tool_card = self.get_queryset().get(pk=tool_card.pk)
        return Response(
            ToolCardOwnerSerializer(tool_card).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['post'])
    def refresh(self, request, pk=None):
        """Re-discover tools from existing MCP server URL."""
        tool_card = self.get_object()
        if not tool_card.mcp_server_url:
            return Response(
                {'error': 'No MCP server URL configured.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            result = discover_mcp_server(tool_card.mcp_server_url)
        except DiscoveryError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        tool_card.tools_schema = result.tools
        tool_card.save(update_fields=['tools_schema', 'updated_at'])

        tool_card = self.get_queryset().get(pk=tool_card.pk)
        return Response(ToolCardOwnerSerializer(tool_card).data)
