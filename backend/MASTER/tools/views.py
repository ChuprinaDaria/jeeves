from collections import defaultdict

from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from MASTER.nexelin_platform.models import FeatureFlag
from .models import ToolCard, ToolConnection, EdgeMiddleware
from .serializers import (
    ToolCatalogItemSerializer, ToolConnectionSerializer,
    FlowConnectionSerializer, FlowConnectionUpdateSerializer,
    EdgeMiddlewareSerializer, EdgeMiddlewareCreateSerializer,
)


def _serialize_conn(conn):
    """Serialize a single ToolConnection for catalog response."""
    return {
        'id': conn.pk,
        'status': conn.status,
        'enabled': conn.enabled,
        'target': conn.target,
        'scope': conn.scope,
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
    }


class ToolCatalogView(APIView):
    """GET /api/tools/catalog/ — all available tools with connection status."""

    def get(self, request):
        client = getattr(request, 'client', None)
        lang = request.query_params.get('lang') or request.headers.get(
            'Accept-Language', '')[:2] or 'en'
        tools = ToolCard.objects.filter(is_active=True).order_by('sort_order', 'name')

        connections = defaultdict(list)
        if client:
            conns_qs = ToolConnection.objects.filter(
                client=client
            ).prefetch_related('middlewares__skill_card')
            for tc in conns_qs:
                connections[tc.tool_card_id].append(tc)

        multi_conn = client and FeatureFlag.is_enabled(
            'mcp_tools_multi_connection', client)

        result = []
        for tool in tools:
            tool_conns = connections.get(tool.pk, [])
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
                'is_system': tool.is_system,
                'auth_type': tool.auth_type,
                'auth_config': tool.auth_config,
                'skill_scopes': tool.skill_scopes,
                'scope_schema': tool.scope_schema,
            }

            if multi_conn:
                item['connections'] = [_serialize_conn(c) for c in tool_conns]
                first_conn = next(
                    (c for c in tool_conns
                     if c.status == 'connected' and c.enabled), None)
                item['connection'] = (
                    _serialize_conn(first_conn) if first_conn else None)
            else:
                conn = next(iter(tool_conns), None)
                item['connection'] = (
                    _serialize_conn(conn) if conn else None)

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
                client=client, tool_card=tool_card, target=target,
                defaults={'status': 'pending'})
            # Auto-enable bridge on client so login endpoint doesn't reject
            if tool_card.slug == 'whatsapp-bridge' and not client.whatsapp_bridge_enabled:
                client.whatsapp_bridge_enabled = True
                client.save(update_fields=['whatsapp_bridge_enabled'])
            initiate_url = tool_card.auth_config.get('initiate_url', '')
            return Response({'status': 'pending', 'initiate_url': initiate_url})

        # api_key, credentials, none
        conn, _ = ToolConnection.objects.update_or_create(
            client=client, tool_card=tool_card, target=target,
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

        target = request.data.get('target')
        qs = ToolConnection.objects.filter(client=client, tool_card__slug=slug)
        if target:
            qs = qs.filter(target=target)
        updated = qs.update(status='disconnected', enabled=False)

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

        # For multi-connection: if tool already has an active connection,
        # reuse its credentials for the new target
        existing_conn = ToolConnection.objects.filter(
            client=client, tool_card=tool_card, status='connected', enabled=True
        ).first()

        if tool_card.auth_type != 'none' and not existing_conn:
            return Response(
                {'error': 'This tool requires authentication. Use /api/tools/{slug}/connect/'},
                status=status.HTTP_400_BAD_REQUEST)

        credentials = existing_conn.credentials if existing_conn else {}

        conn, created = ToolConnection.objects.update_or_create(
            client=client, tool_card=tool_card, target=target,
            defaults={
                'credentials': credentials,
                'status': 'connected',
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


from MASTER.tools.word_cloud import compute_word_frequencies


class WordCloudView(APIView):

    def get(self, request):
        client = getattr(request, 'client', None)
        if not client:
            return Response({'error': 'Client not found'}, status=status.HTTP_401_UNAUTHORIZED)
        words = compute_word_frequencies(client.id)
        return Response({'words': words})
