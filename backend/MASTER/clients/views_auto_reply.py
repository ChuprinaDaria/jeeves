from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from .models_auto_reply import ChannelAutoReply
from .models import ClientWhatsAppConversation
from .serializers_auto_reply import ChannelAutoReplySerializer


class ChannelAutoReplyListView(APIView):
    """GET /api/clients/channel-auto-reply/ — all configs for current client."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        client = request.user.client
        configs = ChannelAutoReply.objects.filter(client=client)
        serializer = ChannelAutoReplySerializer(configs, many=True)
        return Response({'results': serializer.data})


class ChannelAutoReplyDetailView(APIView):
    """PUT /api/clients/channel-auto-reply/<channel>/ — create or update config."""
    permission_classes = [IsAuthenticated]

    def get(self, request, channel):
        client = request.user.client
        try:
            config = ChannelAutoReply.objects.get(client=client, channel=channel)
        except ChannelAutoReply.DoesNotExist:
            return Response({'detail': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        serializer = ChannelAutoReplySerializer(config)
        return Response(serializer.data)

    def put(self, request, channel):
        client = request.user.client
        valid_channels = dict(ChannelAutoReply.CHANNEL_CHOICES)
        if channel not in valid_channels:
            return Response(
                {'detail': f'Invalid channel: {channel}'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        config, created = ChannelAutoReply.objects.get_or_create(
            client=client,
            channel=channel,
        )
        serializer = ChannelAutoReplySerializer(config, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)


class ChannelAutoReplyContactsView(APIView):
    """GET /api/clients/channel-auto-reply/<channel>/contacts/ — existing contacts for picker."""
    permission_classes = [IsAuthenticated]

    def get(self, request, channel):
        client = request.user.client
        conversations = ClientWhatsAppConversation.objects.filter(
            client=client,
        ).order_by('-last_activity_at')

        if channel == 'whatsapp_bridge':
            conversations = conversations.filter(
                context_metadata__platform='whatsapp_bridge',
            )
        elif channel == 'telegram':
            conversations = conversations.exclude(telegram_chat_id='').exclude(
                telegram_chat_id__isnull=True,
            )
        else:
            return Response({'contacts': []})

        contacts = []
        seen = set()
        for conv in conversations[:50]:
            if channel == 'whatsapp_bridge':
                contact_id = conv.customer_phone
                label = f"+{contact_id}" if contact_id and not contact_id.startswith('+') else contact_id
            elif channel == 'telegram':
                contact_id = conv.telegram_chat_id
                username = (conv.context_metadata or {}).get('username', '')
                first_name = (conv.context_metadata or {}).get('first_name', '')
                label = f"@{username}" if username else first_name or contact_id

            if not contact_id or contact_id in seen:
                continue
            seen.add(contact_id)

            last_msg = ''
            if conv.messages:
                for m in reversed(conv.messages):
                    if m.get('role') == 'user':
                        last_msg = m.get('content', '')[:100]
                        break

            contacts.append({
                'id': contact_id,
                'label': label,
                'last_message': last_msg,
                'last_activity': conv.last_activity_at.isoformat() if conv.last_activity_at else None,
            })

        return Response({'contacts': contacts})
