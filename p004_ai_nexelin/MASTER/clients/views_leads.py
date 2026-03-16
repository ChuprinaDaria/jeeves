import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, serializers
from django.db.models import Q

from MASTER.clients.models import Lead
from MASTER.clients.views import get_client_from_request

logger = logging.getLogger(__name__)


class LeadSerializer(serializers.ModelSerializer):
    conversation_id = serializers.IntegerField(source='conversation.id', read_only=True, default=None)

    class Meta:
        model = Lead
        fields = [
            'id', 'name', 'email', 'phone', 'request_summary',
            'interest_score', 'status', 'source',
            'conversation_id', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'conversation_id', 'source']


class LeadListView(APIView):
    """List leads for client. Supports filtering by status, source, interest_score."""
    permission_classes = []

    def get(self, request):
        client = get_client_from_request(request)
        if not client:
            return Response({'error': 'Client not found'}, status=401)

        if not getattr(client, 'leads_enabled', False):
            return Response({'error': 'Leads module is not enabled'}, status=403)

        leads = Lead.objects.filter(client=client)

        # Filters
        status_filter = request.GET.get('status')
        if status_filter:
            leads = leads.filter(status=status_filter)

        source_filter = request.GET.get('source')
        if source_filter:
            leads = leads.filter(source=source_filter)

        min_interest = request.GET.get('min_interest')
        if min_interest:
            leads = leads.filter(interest_score__gte=int(min_interest))

        search = request.GET.get('search')
        if search:
            leads = leads.filter(
                Q(name__icontains=search) |
                Q(email__icontains=search) |
                Q(phone__icontains=search) |
                Q(request_summary__icontains=search)
            )

        # Pagination
        page = int(request.GET.get('page', 1))
        per_page = min(int(request.GET.get('per_page', 25)), 100)
        total = leads.count()
        offset = (page - 1) * per_page

        leads_page = leads[offset:offset + per_page]
        serializer = LeadSerializer(leads_page, many=True)

        return Response({
            'results': serializer.data,
            'total': total,
            'page': page,
            'per_page': per_page,
        })


class LeadDetailView(APIView):
    """Get/Update/Delete a specific lead."""
    permission_classes = []

    def get(self, request, lead_id):
        client = get_client_from_request(request)
        if not client:
            return Response({'error': 'Client not found'}, status=401)

        try:
            lead = Lead.objects.get(id=lead_id, client=client)
        except Lead.DoesNotExist:
            return Response({'error': 'Lead not found'}, status=404)

        return Response(LeadSerializer(lead).data)

    def patch(self, request, lead_id):
        client = get_client_from_request(request)
        if not client:
            return Response({'error': 'Client not found'}, status=401)

        try:
            lead = Lead.objects.get(id=lead_id, client=client)
        except Lead.DoesNotExist:
            return Response({'error': 'Lead not found'}, status=404)

        updatable = {'name', 'email', 'phone', 'request_summary', 'interest_score', 'status'}
        data = request.data or {}

        for key, val in data.items():
            if key in updatable:
                if key == 'interest_score':
                    val = max(1, min(5, int(val)))
                setattr(lead, key, val)

        lead.save()
        return Response(LeadSerializer(lead).data)

    def delete(self, request, lead_id):
        client = get_client_from_request(request)
        if not client:
            return Response({'error': 'Client not found'}, status=401)

        try:
            lead = Lead.objects.get(id=lead_id, client=client)
        except Lead.DoesNotExist:
            return Response({'error': 'Lead not found'}, status=404)

        lead.delete()
        return Response({'success': True}, status=204)
