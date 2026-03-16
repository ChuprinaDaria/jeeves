"""
API views for WhatsApp Bridge (mautrix-whatsapp) integration.
Handles QR login flow, connection status, and incoming bridge messages.
"""
import logging

from rest_framework.response import Response
from rest_framework.views import APIView

from .views import get_client_from_request
from .models import WhatsAppBridgeConfig
from .services.whatsapp_bridge import (
    WhatsAppBridgeError,
    start_whatsapp_login,
    check_login_status,
    logout_whatsapp,
    get_connection_status,
)

logger = logging.getLogger(__name__)


def _check_bridge_globally_enabled():
    """Return error Response if bridge is globally disabled, else None."""
    try:
        config = WhatsAppBridgeConfig.objects.get(pk=1)
        if not config.is_enabled:
            return Response(
                {'error': 'WhatsApp Bridge is disabled by administrator'},
                status=403,
            )
    except WhatsAppBridgeConfig.DoesNotExist:
        return Response(
            {'error': 'WhatsApp Bridge is not configured'},
            status=503,
        )
    return None


class WhatsAppBridgeConfigView(APIView):
    """GET/PATCH bridge config and status for the authenticated client."""
    permission_classes = []

    def get(self, request):
        client = get_client_from_request(request)
        if not client:
            return Response({'error': 'Client not found'}, status=401)

        # Check global availability
        globally_enabled = False
        try:
            config = WhatsAppBridgeConfig.objects.get(pk=1)
            globally_enabled = config.is_enabled
        except WhatsAppBridgeConfig.DoesNotExist:
            pass

        return Response({
            'globally_enabled': globally_enabled,
            'whatsapp_bridge_enabled': client.whatsapp_bridge_enabled,
            'whatsapp_bridge_status': client.whatsapp_bridge_status,
            'whatsapp_bridge_phone': client.whatsapp_bridge_phone,
            'whatsapp_bridge_connected_at': client.whatsapp_bridge_connected_at,
            'whatsapp_bridge_error': client.whatsapp_bridge_error,
        })

    def patch(self, request):
        client = get_client_from_request(request)
        if not client:
            return Response({'error': 'Client not found'}, status=401)

        err = _check_bridge_globally_enabled()
        if err:
            return err

        enabled = request.data.get('whatsapp_bridge_enabled')
        if enabled is not None:
            client.whatsapp_bridge_enabled = bool(enabled)
            client.save(update_fields=['whatsapp_bridge_enabled'])

        return Response({
            'whatsapp_bridge_enabled': client.whatsapp_bridge_enabled,
            'whatsapp_bridge_status': client.whatsapp_bridge_status,
        })


class WhatsAppBridgeLoginView(APIView):
    """POST — start WhatsApp login, returns QR code."""
    permission_classes = []

    def post(self, request):
        client = get_client_from_request(request)
        if not client:
            return Response({'error': 'Client not found'}, status=401)

        err = _check_bridge_globally_enabled()
        if err:
            return err

        if not client.whatsapp_bridge_enabled:
            return Response({'error': 'WhatsApp Bridge is not enabled for this client'}, status=400)

        try:
            result = start_whatsapp_login(client)
            return Response(result)
        except WhatsAppBridgeError as e:
            return Response({'error': str(e)}, status=400)
        except Exception as e:
            logger.error(f"WhatsApp bridge login error: {e}", exc_info=True)
            return Response({'error': 'Internal error during login'}, status=500)


class WhatsAppBridgeQRPollView(APIView):
    """GET — poll login status (QR pending / connected / error)."""
    permission_classes = []

    def get(self, request):
        client = get_client_from_request(request)
        if not client:
            return Response({'error': 'Client not found'}, status=401)

        login_id = request.query_params.get('login_id', '')
        if not login_id:
            return Response({'error': 'login_id is required'}, status=400)

        try:
            result = check_login_status(client, login_id)
            return Response(result)
        except WhatsAppBridgeError as e:
            return Response({'error': str(e)}, status=400)
        except Exception as e:
            logger.error(f"WhatsApp bridge status poll error: {e}", exc_info=True)
            return Response({'error': 'Internal error checking status'}, status=500)


class WhatsAppBridgeLogoutView(APIView):
    """POST — disconnect WhatsApp."""
    permission_classes = []

    def post(self, request):
        client = get_client_from_request(request)
        if not client:
            return Response({'error': 'Client not found'}, status=401)

        try:
            logout_whatsapp(client)
            return Response({'status': 'disconnected'})
        except WhatsAppBridgeError as e:
            return Response({'error': str(e)}, status=400)
        except Exception as e:
            logger.error(f"WhatsApp bridge logout error: {e}", exc_info=True)
            return Response({'error': 'Internal error during logout'}, status=500)


class WhatsAppBridgeStatusView(APIView):
    """GET — check actual connection health."""
    permission_classes = []

    def get(self, request):
        client = get_client_from_request(request)
        if not client:
            return Response({'error': 'Client not found'}, status=401)

        try:
            result = get_connection_status(client)
            return Response(result)
        except WhatsAppBridgeError as e:
            return Response({'error': str(e)}, status=400)
        except Exception as e:
            logger.error(f"WhatsApp bridge status error: {e}", exc_info=True)
            return Response({'error': 'Internal error checking status'}, status=500)


class WhatsAppBridgeMessageView(APIView):
    """
    POST — receive incoming WhatsApp message from Go integration service.
    Internal endpoint, called by the integration service when a bridged
    WhatsApp message arrives via Matrix.
    """
    permission_classes = []

    def post(self, request):
        from django.conf import settings

        # Simple auth: check internal service token
        service_token = request.headers.get('X-Service-Token', '')
        expected_token = getattr(settings, 'INTEGRATION_SERVICE_TOKEN', '')
        if expected_token and service_token != expected_token:
            return Response({'error': 'Unauthorized'}, status=403)

        client_id = request.data.get('client_id')
        sender_phone = request.data.get('sender_phone', '')
        message_text = request.data.get('message_text', '')
        room_id = request.data.get('room_id', '')

        if not client_id or not message_text:
            return Response({'error': 'client_id and message_text are required'}, status=400)

        from .models import Client, ClientWhatsAppConversation

        try:
            client = Client.objects.get(id=client_id, is_active=True)
        except Client.DoesNotExist:
            return Response({'error': 'Client not found'}, status=404)

        # Find or create conversation
        conversation = ClientWhatsAppConversation.objects.filter(
            client=client,
            customer_phone=sender_phone,
            is_active=True,
        ).order_by('-last_activity_at').first()

        if not conversation:
            conversation = ClientWhatsAppConversation.objects.create(
                client=client,
                customer_phone=sender_phone,
                is_active=True,
                context_metadata={'platform': 'whatsapp_bridge', 'matrix_room_id': room_id},
            )

        # Add user message
        conversation.add_message('user', message_text)

        # Process via RAG (same as other channels)
        try:
            from MASTER.rag.views import process_rag_query
            rag_response = process_rag_query(client, message_text, conversation)
            if rag_response:
                conversation.add_message('assistant', rag_response)
                return Response({
                    'reply': rag_response,
                    'conversation_id': conversation.id,
                })
        except Exception as e:
            logger.error(f"RAG processing failed for bridge message: {e}", exc_info=True)

        return Response({
            'reply': '',
            'conversation_id': conversation.id,
            'error': 'Failed to generate response',
        }, status=200)
