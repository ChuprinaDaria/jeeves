from rest_framework.response import Response
from rest_framework.views import APIView

from .models import AgentConfig, AgentSession, AgentLog
from .serializers import AgentConfigSerializer, AgentSessionSerializer, AgentLogSerializer


class AgentConfigView(APIView):
    """GET/PATCH /api/agents/config/ — agent config for current client."""

    def get(self, request):
        client = getattr(request, 'client', None)
        if not client:
            return Response({'error': 'Client not found'}, status=401)
        config, _ = AgentConfig.objects.get_or_create(client=client)
        return Response(AgentConfigSerializer(config).data)

    def patch(self, request):
        client = getattr(request, 'client', None)
        if not client:
            return Response({'error': 'Client not found'}, status=401)
        config, _ = AgentConfig.objects.get_or_create(client=client)
        serializer = AgentConfigSerializer(config, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class AgentLogListView(APIView):
    """GET /api/agents/logs/ — recent agent logs."""

    def get(self, request):
        client = getattr(request, 'client', None)
        if not client:
            return Response({'error': 'Client not found'}, status=401)
        logs = AgentLog.objects.filter(
            session__agent_config__client=client
        ).order_by('-created_at')[:100]
        return Response(AgentLogSerializer(logs, many=True).data)


class AgentSessionListView(APIView):
    """GET /api/agents/sessions/ — recent sessions."""

    def get(self, request):
        client = getattr(request, 'client', None)
        if not client:
            return Response({'error': 'Client not found'}, status=401)
        sessions = AgentSession.objects.filter(
            agent_config__client=client
        ).order_by('-started_at')[:50]
        return Response(AgentSessionSerializer(sessions, many=True).data)
