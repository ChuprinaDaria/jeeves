from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ToolCard, ToolConnection
from .serializers import ToolCatalogItemSerializer, ToolConnectionSerializer


class ToolCatalogView(APIView):
    """GET /api/tools/catalog/ — all available tools with connection status."""

    def get(self, request):
        client = getattr(request, 'client', None)
        tools = ToolCard.objects.filter(is_active=True).order_by('sort_order', 'name')

        connections = {}
        if client:
            connections = {
                tc.tool_card_id: tc
                for tc in ToolConnection.objects.filter(client=client)
            }

        result = []
        for tool in tools:
            conn = connections.get(tool.pk)
            item = {
                'slug': tool.slug,
                'name': tool.name,
                'tagline': tool.tagline,
                'description': tool.description,
                'icon': tool.icon,
                'color': tool.color,
                'category': tool.category,
                'is_featured': tool.is_featured,
                'auth_type': tool.auth_type,
                'auth_config': tool.auth_config if not conn else None,
                'connection': {
                    'status': conn.status,
                    'enabled': conn.enabled,
                    'connected_at': conn.connected_at.isoformat() if conn.connected_at else None,
                    'last_used_at': conn.last_used_at.isoformat() if conn.last_used_at else None,
                } if conn else None,
            }
            result.append(item)

        return Response(result)


class ToolConnectView(APIView):
    """POST /api/tools/{slug}/connect/ — connect a tool with credentials."""

    def post(self, request, slug):
        client = getattr(request, 'client', None)
        if not client:
            return Response({'error': 'Client not found'}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            tool_card = ToolCard.objects.get(slug=slug, is_active=True)
        except ToolCard.DoesNotExist:
            return Response({'error': 'Tool not found'}, status=status.HTTP_404_NOT_FOUND)

        credentials = request.data.get('credentials', {})

        # Validate required fields from auth_config
        if tool_card.auth_type in ('api_key', 'credentials'):
            required_fields = [
                f['name'] for f in tool_card.auth_config.get('fields', [])
                if f.get('required', False)
            ]
            missing = [f for f in required_fields if not credentials.get(f)]
            if missing:
                return Response(
                    {'error': f'Missing required fields: {", ".join(missing)}'},
                    status=status.HTTP_400_BAD_REQUEST)

        if tool_card.auth_type == 'oauth2':
            # Return OAuth URL for frontend redirect
            auth_url = tool_card.auth_config.get('authorize_url', '')
            return Response({'auth_url': auth_url, 'status': 'pending'})

        if tool_card.auth_type == 'qr_code':
            conn, _ = ToolConnection.objects.update_or_create(
                client=client, tool_card=tool_card,
                defaults={'status': 'pending'})
            initiate_url = tool_card.auth_config.get('initiate_url', '')
            return Response({'status': 'pending', 'initiate_url': initiate_url})

        # api_key, credentials, none
        conn, _ = ToolConnection.objects.update_or_create(
            client=client, tool_card=tool_card,
            defaults={
                'credentials': credentials,
                'status': 'connected',
                'enabled': True,
                'connected_at': timezone.now(),
                'last_error': '',
                'error_count': 0,
            })
        return Response({'status': conn.status})


class ToolDisconnectView(APIView):
    """POST /api/tools/{slug}/disconnect/"""

    def post(self, request, slug):
        client = getattr(request, 'client', None)
        if not client:
            return Response({'error': 'Client not found'}, status=status.HTTP_401_UNAUTHORIZED)

        updated = ToolConnection.objects.filter(
            client=client, tool_card__slug=slug
        ).update(status='disconnected', enabled=False)

        if not updated:
            return Response({'error': 'Connection not found'}, status=status.HTTP_404_NOT_FOUND)
        return Response({'status': 'disconnected'})


class ToolStatusView(APIView):
    """GET /api/tools/{slug}/status/"""

    def get(self, request, slug):
        client = getattr(request, 'client', None)
        if not client:
            return Response({'error': 'Client not found'}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            conn = ToolConnection.objects.select_related('tool_card').get(
                client=client, tool_card__slug=slug)
        except ToolConnection.DoesNotExist:
            return Response({'status': 'not_connected'})

        return Response(ToolConnectionSerializer(conn).data)


class MyToolsView(APIView):
    """GET /api/tools/my/ — client's connected tools."""

    def get(self, request):
        client = getattr(request, 'client', None)
        if not client:
            return Response({'error': 'Client not found'}, status=status.HTTP_401_UNAUTHORIZED)

        connections = ToolConnection.objects.filter(
            client=client, enabled=True
        ).select_related('tool_card').order_by('tool_card__sort_order')

        return Response(ToolConnectionSerializer(connections, many=True).data)
