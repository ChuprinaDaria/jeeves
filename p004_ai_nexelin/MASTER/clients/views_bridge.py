import logging

from asgiref.sync import async_to_sync
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from MASTER.clients.models_bridge import BridgeConfig
from MASTER.clients.services.bridge_service import bridge_service, BridgeServiceError

logger = logging.getLogger(__name__)


def _get_client(request):
    client = getattr(request, 'client', None)
    if not client:
        return None
    return client


class BridgeListView(APIView):
    """GET /api/bridges/ — list available bridge configs."""

    def get(self, request):
        configs = BridgeConfig.objects.filter(is_enabled=True).values(
            'bridge_type', 'display_name', 'icon', 'auth_flow', 'default_scopes'
        )
        return Response(list(configs))


class BridgeStatusView(APIView):
    """GET /api/bridges/{type}/status/"""

    def get(self, request, bridge_type):
        client = _get_client(request)
        if not client:
            return Response({'error': 'Client not found'}, status=status.HTTP_401_UNAUTHORIZED)
        try:
            result = async_to_sync(bridge_service.check_status)(client, bridge_type)
            return Response(result)
        except BridgeServiceError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class BridgeLoginStartView(APIView):
    """POST /api/bridges/{type}/login/start/"""

    def post(self, request, bridge_type):
        client = _get_client(request)
        if not client:
            return Response({'error': 'Client not found'}, status=status.HTTP_401_UNAUTHORIZED)
        try:
            result = async_to_sync(bridge_service.start_login)(client, bridge_type)
            return Response(result)
        except BridgeServiceError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class BridgeLoginCookiesView(APIView):
    """POST /api/bridges/{type}/login/cookies/"""

    def post(self, request, bridge_type):
        client = _get_client(request)
        if not client:
            return Response({'error': 'Client not found'}, status=status.HTTP_401_UNAUTHORIZED)
        cookies = request.data.get('cookies', {})
        if not cookies:
            return Response({'error': 'cookies field is required'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            result = async_to_sync(bridge_service.submit_cookies)(client, bridge_type, cookies)
            return Response(result)
        except BridgeServiceError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class BridgeLoginStatusView(APIView):
    """GET /api/bridges/{type}/login/status/"""

    def get(self, request, bridge_type):
        client = _get_client(request)
        if not client:
            return Response({'error': 'Client not found'}, status=status.HTTP_401_UNAUTHORIZED)
        try:
            result = async_to_sync(bridge_service.check_status)(client, bridge_type)
            return Response(result)
        except BridgeServiceError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class BridgeLogoutView(APIView):
    """POST /api/bridges/{type}/logout/"""

    def post(self, request, bridge_type):
        client = _get_client(request)
        if not client:
            return Response({'error': 'Client not found'}, status=status.HTTP_401_UNAUTHORIZED)
        try:
            result = async_to_sync(bridge_service.logout)(client, bridge_type)
            return Response(result)
        except BridgeServiceError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class BridgeMessageView(APIView):
    """POST /api/bridges/message/ — universal incoming message from Integration Service."""
    permission_classes = []

    def post(self, request):
        from django.conf import settings
        token = request.headers.get('X-Service-Token', '')
        if token != getattr(settings, 'INTEGRATION_SERVICE_TOKEN', ''):
            return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)

        client_id = request.data.get('client_id')
        bridge_type = request.data.get('bridge_type')
        sender_id = request.data.get('sender_id', '')
        message_text = request.data.get('message_text', '')
        room_id = request.data.get('room_id', '')

        if not client_id or not bridge_type:
            return Response({'error': 'client_id and bridge_type required'}, status=status.HTTP_400_BAD_REQUEST)

        from MASTER.clients.models import Client
        try:
            client = Client.objects.get(pk=client_id)
        except Client.DoesNotExist:
            return Response({'error': 'Client not found'}, status=status.HTTP_404_NOT_FOUND)

        from MASTER.tools.models import ToolConnection, ToolCard
        try:
            tool_card = ToolCard.objects.get(slug=bridge_type)
            conn = ToolConnection.objects.filter(
                client=client, tool_card=tool_card, status='connected'
            ).first()
            scope = conn.target if conn else 'assistant'
        except ToolCard.DoesNotExist:
            scope = 'assistant'

        from MASTER.agents.orchestrator import AgentOrchestrator
        try:
            orchestrator = AgentOrchestrator(client=client, scope=scope)
            response = async_to_sync(orchestrator.process)(message_text)
            return Response({'response': response, 'bridge_type': bridge_type, 'scope': scope})
        except Exception as e:
            logger.error(f'Bridge message processing error: {e}', exc_info=True)
            return Response({'error': 'Processing failed'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
