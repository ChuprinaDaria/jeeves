import logging
import re

from django.db import IntegrityError, transaction
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import serializers
from rest_framework.permissions import IsAdminUser

from .models import Client, ClientTelephonyConfig
from .views import get_client_from_request

logger = logging.getLogger(__name__)

VALID_VOICE_MODELS = {'alloy', 'echo', 'fable', 'onyx', 'nova', 'shimmer'}
VALID_MODES = {'prompt_only', 'prompt_with_rag'}
VALID_STATUSES = {ClientTelephonyConfig.STATUS_ACTIVE, ClientTelephonyConfig.STATUS_INACTIVE}
PHONE_RE = re.compile(r'^\+\d{7,15}$')

VOICE_MODELS_LIST = [
    {'id': 'alloy',   'name': 'Alloy',   'gender': 'neutral', 'description': 'Neutral, balanced voice'},
    {'id': 'echo',    'name': 'Echo',    'gender': 'male',    'description': 'Male, warm tone'},
    {'id': 'fable',   'name': 'Fable',   'gender': 'male',    'description': 'Male, expressive'},
    {'id': 'onyx',    'name': 'Onyx',    'gender': 'male',    'description': 'Male, deep and authoritative'},
    {'id': 'nova',    'name': 'Nova',    'gender': 'female',  'description': 'Female, friendly'},
    {'id': 'shimmer', 'name': 'Shimmer', 'gender': 'female',  'description': 'Female, calm and clear'},
]


class TelephonyConfigSerializer(serializers.ModelSerializer):
    tag = serializers.CharField(source='client.tag', read_only=True)
    client_id = serializers.IntegerField(source='client.id', read_only=True)

    class Meta:
        model = ClientTelephonyConfig
        fields = [
            'id', 'tag', 'client_id', 'phone_number', 'status',
            'voice_config', 'response_config', 'webhook_url', 'created_at',
        ]
        read_only_fields = ['id', 'tag', 'client_id', 'created_at']
        # webhook_secret intentionally excluded from serializer output


def _get_client_by_tag(tag: str):
    """Return active Client by tag or None."""
    try:
        return Client.objects.get(tag=tag, is_active=True)
    except Client.DoesNotExist:
        return None


def _validate_voice_config(voice_config: dict) -> str | None:
    model = voice_config.get('model')
    if model and model not in VALID_VOICE_MODELS:
        return f"Unknown voice model '{model}'. Valid: {sorted(VALID_VOICE_MODELS)}"
    return None


def _validate_response_config(response_config: dict) -> str | None:
    mode = response_config.get('mode')
    if mode and mode not in VALID_MODES:
        return f"Unknown mode '{mode}'. Valid: {sorted(VALID_MODES)}"
    return None


class TelephonyConnectView(APIView):
    """POST /api/telephony/connect/ — assign client to telephony.

    Client identifies itself via tag in the request body (consistent with
    the project-wide get_client_from_request pattern). The tag doubles as
    the authentication credential — admin must enable telephony_enabled
    on the client record first.
    """
    permission_classes = []

    def post(self, request):
        data = request.data or {}
        tag = data.get('tag')
        phone_number = data.get('phone_number', '')
        voice_config = data.get('voice_config') or {}
        response_config = data.get('response_config') or {}
        webhook_url = data.get('webhook_url', '')
        webhook_secret = data.get('webhook_secret', '')

        if not tag:
            return Response({'error': 'tag is required'}, status=400)

        client = _get_client_by_tag(tag)
        if not client:
            return Response({'error': 'Client with given tag not found'}, status=404)

        if not client.telephony_enabled:
            return Response({'error': 'Telephony is not enabled for this client'}, status=403)

        # Validate before any DB writes
        if not PHONE_RE.match(phone_number):
            return Response({'error': 'Invalid phone number format. Use E.164 (e.g. +48123456789)'}, status=400)

        err = _validate_voice_config(voice_config)
        if err:
            return Response({'error': err}, status=400)

        err = _validate_response_config(response_config)
        if err:
            return Response({'error': err}, status=400)

        try:
            with transaction.atomic():
                # Re-check uniqueness inside the transaction to avoid race condition
                if ClientTelephonyConfig.objects.filter(phone_number=phone_number).exclude(client=client).exists():
                    return Response({'error': 'Phone number already assigned to another client'}, status=409)

                config, created = ClientTelephonyConfig.objects.update_or_create(
                    client=client,
                    defaults={
                        'phone_number': phone_number,
                        'voice_config': voice_config,
                        'response_config': response_config,
                        'webhook_url': webhook_url,
                        'webhook_secret': webhook_secret,
                        'status': ClientTelephonyConfig.STATUS_ACTIVE,
                    },
                )
        except IntegrityError:
            return Response({'error': 'Phone number already assigned to another client'}, status=409)

        return Response(TelephonyConfigSerializer(config).data, status=201 if created else 200)


class TelephonyListView(APIView):
    """GET /api/telephony/ — list all connections. Admin only."""
    permission_classes = [IsAdminUser]

    def get(self, request):
        qs = ClientTelephonyConfig.objects.select_related('client').all()

        status_filter = request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)

        total = qs.count()
        try:
            page = max(1, int(request.query_params.get('page', 1)))
            page_size = min(100, max(1, int(request.query_params.get('page_size', 20))))
        except (ValueError, TypeError):
            page, page_size = 1, 20

        start = (page - 1) * page_size
        results = TelephonyConfigSerializer(qs[start:start + page_size], many=True).data

        base_url = request.build_absolute_uri(request.path)
        # Preserve status filter in pagination links
        status_param = f"&status={status_filter}" if status_filter else ""
        next_url = f"{base_url}?page={page + 1}&page_size={page_size}{status_param}" if start + page_size < total else None
        prev_url = f"{base_url}?page={page - 1}&page_size={page_size}{status_param}" if page > 1 else None

        return Response({
            'count': total,
            'next': next_url,
            'previous': prev_url,
            'results': results,
        })


class TelephonyDetailView(APIView):
    """GET / PATCH / DELETE /api/telephony/{tag}/

    Client authenticates via tag (URL path). Consistent with get_client_from_request
    pattern used across the project.
    """
    permission_classes = []

    def _get_config(self, tag: str):
        client = _get_client_by_tag(tag)
        if not client:
            return None
        try:
            return client.telephony_config
        except ClientTelephonyConfig.DoesNotExist:
            return None

    def get(self, request, tag):
        config = self._get_config(tag)
        if not config:
            return Response(status=404)
        return Response(TelephonyConfigSerializer(config).data)

    def patch(self, request, tag):
        config = self._get_config(tag)
        if not config:
            return Response(status=404)

        data = request.data or {}

        # Validate everything before touching the object
        new_phone = data.get('phone_number')
        if new_phone is not None:
            if not PHONE_RE.match(new_phone):
                return Response({'error': 'Invalid phone number format'}, status=400)

        new_status = data.get('status')
        if new_status is not None and new_status not in VALID_STATUSES:
            return Response({'error': f"Invalid status '{new_status}'. Valid: {sorted(VALID_STATUSES)}"}, status=400)

        for json_field in ('voice_config', 'response_config'):
            if json_field in data:
                err = (_validate_voice_config if json_field == 'voice_config' else _validate_response_config)(data[json_field])
                if err:
                    return Response({'error': err}, status=400)

        # Apply changes
        for json_field in ('voice_config', 'response_config'):
            if json_field in data:
                current = getattr(config, json_field) or {}
                current.update(data[json_field])
                setattr(config, json_field, current)

        for field in ('phone_number', 'webhook_url', 'webhook_secret', 'status'):
            if field in data:
                setattr(config, field, data[field])

        try:
            with transaction.atomic():
                if new_phone is not None:
                    if ClientTelephonyConfig.objects.filter(phone_number=new_phone).exclude(pk=config.pk).exists():
                        return Response({'error': 'Phone number already assigned to another client'}, status=409)
                config.save()
        except IntegrityError:
            return Response({'error': 'Phone number already assigned to another client'}, status=409)

        return Response(TelephonyConfigSerializer(config).data)

    def delete(self, request, tag):
        config = self._get_config(tag)
        if not config:
            return Response(status=404)
        client = config.client
        config.delete()
        client.telephony_enabled = False
        client.save(update_fields=['telephony_enabled'])
        return Response(status=204)


class TelephonyVoicesView(APIView):
    """GET /api/telephony/voices/ — list available voice models."""
    permission_classes = []

    def get(self, request):
        return Response(VOICE_MODELS_LIST)
