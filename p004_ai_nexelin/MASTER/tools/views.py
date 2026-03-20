from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ToolCard, ToolConnection, EdgeMiddleware
from .serializers import (
    ToolCatalogItemSerializer, ToolConnectionSerializer,
    FlowConnectionSerializer, FlowConnectionUpdateSerializer,
    EdgeMiddlewareSerializer, EdgeMiddlewareCreateSerializer,
)


class ToolCatalogView(APIView):
    """GET /api/tools/catalog/ — all available tools with connection status."""

    def get(self, request):
        client = getattr(request, 'client', None)
        lang = request.query_params.get('lang') or request.headers.get(
            'Accept-Language', '')[:2] or 'en'
        tools = ToolCard.objects.filter(is_active=True).order_by('sort_order', 'name')

        connections = {}
        if client:
            conns_qs = ToolConnection.objects.filter(
                client=client
            ).prefetch_related('middlewares__skill_card')
            connections = {tc.tool_card_id: tc for tc in conns_qs}

        result = []
        for tool in tools:
            conn = connections.get(tool.pk)
            # Resolve tagline: prefer i18n version for requested lang
            tagline = tool.tagline
            if tool.tagline_i18n and lang in tool.tagline_i18n:
                tagline = tool.tagline_i18n[lang]

            item = {
                'slug': tool.slug,
                'name': tool.name,
                'tagline': tagline,
                'tagline_i18n': tool.tagline_i18n,
                'description': tool.description,
                'icon': tool.icon,
                'color': tool.color,
                'category': tool.category,
                'is_featured': tool.is_featured,
                'auth_type': tool.auth_type,
                'auth_config': tool.auth_config if not conn else None,
                'skill_scopes': tool.skill_scopes,
                'connection': {
                    'id': conn.pk,
                    'status': conn.status,
                    'enabled': conn.enabled,
                    'target': conn.target,
                    'connected_at': conn.connected_at.isoformat() if conn.connected_at else None,
                    'last_used_at': conn.last_used_at.isoformat() if conn.last_used_at else None,
                    'middlewares': [
                        {
                            'id': mw.pk,
                            'skill_slug': mw.skill_card.slug,
                            'skill_name': mw.skill_card.name,
                            'skill_icon': mw.skill_card.icon,
                            'skill_color': mw.skill_card.color,
                            'order': mw.order,
                            'enabled': mw.enabled,
                        }
                        for mw in conn.middlewares.all()
                    ],
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
        target = request.data.get('target', 'assistant')

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
                defaults={'status': 'pending', 'target': target})
            initiate_url = tool_card.auth_config.get('initiate_url', '')
            return Response({'status': 'pending', 'initiate_url': initiate_url})

        # api_key, credentials, none
        conn, _ = ToolConnection.objects.update_or_create(
            client=client, tool_card=tool_card,
            defaults={
                'credentials': credentials,
                'status': 'connected',
                'target': target,
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


# ── Flow Canvas API ────────────────────────────────


class FlowConnectionsView(APIView):
    """
    GET  /api/flow/connections/ — all connections for this tenant (with tool info)
    POST /api/flow/connections/ — create a new connection (for drag-to-connect)
    """

    def get(self, request):
        client = getattr(request, 'client', None)
        if not client:
            return Response({'error': 'Client not found'}, status=status.HTTP_401_UNAUTHORIZED)

        conns = ToolConnection.objects.filter(
            client=client
        ).select_related('tool_card').order_by('tool_card__sort_order')

        return Response(FlowConnectionSerializer(conns, many=True).data)

    def post(self, request):
        client = getattr(request, 'client', None)
        if not client:
            return Response({'error': 'Client not found'}, status=status.HTTP_401_UNAUTHORIZED)

        slug = request.data.get('slug')
        target = request.data.get('target', 'assistant')

        if not slug:
            return Response({'error': 'slug is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            tool_card = ToolCard.objects.get(slug=slug, is_active=True)
        except ToolCard.DoesNotExist:
            return Response({'error': 'Tool not found'}, status=status.HTTP_404_NOT_FOUND)

        # Only allow auto-connect for no-auth tools via this endpoint
        if tool_card.auth_type != 'none':
            return Response(
                {'error': 'This tool requires authentication. Use /api/tools/{slug}/connect/'},
                status=status.HTTP_400_BAD_REQUEST)

        conn, created = ToolConnection.objects.update_or_create(
            client=client, tool_card=tool_card,
            defaults={
                'status': 'connected',
                'target': target,
                'enabled': True,
                'connected_at': timezone.now(),
                'last_error': '',
                'error_count': 0,
            })

        return Response(
            FlowConnectionSerializer(conn).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class FlowConnectionDetailView(APIView):
    """
    PATCH  /api/flow/connections/<id>/ — update target, position, enabled
    DELETE /api/flow/connections/<id>/ — remove connection
    """

    def _get_connection(self, request, pk):
        client = getattr(request, 'client', None)
        if not client:
            return None, Response(
                {'error': 'Client not found'}, status=status.HTTP_401_UNAUTHORIZED)
        try:
            conn = ToolConnection.objects.select_related('tool_card').get(
                pk=pk, client=client)
            return conn, None
        except ToolConnection.DoesNotExist:
            return None, Response(
                {'error': 'Connection not found'}, status=status.HTTP_404_NOT_FOUND)

    def patch(self, request, pk):
        conn, err = self._get_connection(request, pk)
        if err:
            return err

        serializer = FlowConnectionUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        for field, value in serializer.validated_data.items():
            setattr(conn, field, value)
        conn.save(update_fields=list(serializer.validated_data.keys()) + ['updated_at'])

        return Response(FlowConnectionSerializer(conn).data)

    def delete(self, request, pk):
        conn, err = self._get_connection(request, pk)
        if err:
            return err

        conn.status = 'disconnected'
        conn.enabled = False
        conn.save(update_fields=['status', 'enabled', 'updated_at'])
        return Response(status=status.HTTP_204_NO_CONTENT)


class EdgeMiddlewareView(APIView):
    """
    GET  /api/tools/flow/edges/<connection_id>/middleware/
    POST /api/tools/flow/edges/<connection_id>/middleware/
    """

    def _get_connection(self, request, connection_id):
        client = getattr(request, 'client', None)
        if not client:
            return None, Response(
                {'error': 'Client not found'}, status=status.HTTP_401_UNAUTHORIZED)
        try:
            conn = ToolConnection.objects.get(pk=connection_id, client=client)
            return conn, None
        except ToolConnection.DoesNotExist:
            return None, Response(
                {'error': 'Connection not found'}, status=status.HTTP_404_NOT_FOUND)

    def get(self, request, connection_id):
        conn, err = self._get_connection(request, connection_id)
        if err:
            return err
        middlewares = conn.middlewares.select_related('skill_card').all()
        return Response(EdgeMiddlewareSerializer(middlewares, many=True).data)

    def post(self, request, connection_id):
        conn, err = self._get_connection(request, connection_id)
        if err:
            return err

        ser = EdgeMiddlewareCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        skill_slug = ser.validated_data['skill_slug']
        try:
            skill_card = ToolCard.objects.get(slug=skill_slug, is_active=True)
        except ToolCard.DoesNotExist:
            return Response(
                {'error': 'Skill not found'}, status=status.HTTP_404_NOT_FOUND)

        # Check if skill supports this edge's target
        scopes = skill_card.skill_scopes.get('scopes', [])
        if scopes and conn.target not in scopes:
            return Response(
                {'error': f'Skill does not support target "{conn.target}"'},
                status=status.HTTP_400_BAD_REQUEST)

        middleware, created = EdgeMiddleware.objects.get_or_create(
            connection=conn,
            skill_card=skill_card,
            client=conn.client,
            defaults={
                'order': ser.validated_data.get('order', 0),
                'config': ser.validated_data.get('config', {}),
            })

        return Response(
            EdgeMiddlewareSerializer(middleware).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class EdgeMiddlewareDetailView(APIView):
    """DELETE /api/tools/flow/edges/<connection_id>/middleware/<pk>/"""

    def delete(self, request, connection_id, pk):
        client = getattr(request, 'client', None)
        if not client:
            return Response(
                {'error': 'Client not found'}, status=status.HTTP_401_UNAUTHORIZED)
        deleted, _ = EdgeMiddleware.objects.filter(
            pk=pk, connection_id=connection_id, client=client
        ).delete()
        if not deleted:
            return Response(
                {'error': 'Middleware not found'}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)
