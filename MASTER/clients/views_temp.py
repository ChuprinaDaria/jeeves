from django.conf import settings
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.template.loader import render_to_string
from rest_framework import viewsets, permissions, status, serializers
from rest_framework.routers import DefaultRouter
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from MASTER.clients.models import Client, ClientDocument, ClientAPIKey, ClientAPIConfig, KnowledgeBlock, ClientQRCode, ClientWhatsAppConversation
from MASTER.clients.serializers import (
    ClientSerializer,
    ClientDocumentSerializer,
    ClientAPIKeySerializer,
    KnowledgeBlockSerializer,
    ClientQRCodeSerializer,
)
from MASTER.clients.permissions import IsAdminOrReadOnly, IsClientOwner
from django.views.decorators.http import require_POST
from django.contrib.admin.views.decorators import staff_member_required
from MASTER.rag.response_generator import ResponseGenerator
from MASTER.branches.models import Branch
from MASTER.specializations.models import Specialization
import json


# Create your views here.


def get_client_from_request(request):
    """
    Helper function to get client from request.
    Supports:
    - request.user.client_profile (for regular users)
    - request.user.username = Client.user (for JWT tokens from TokenByClientTokenView)
    - request.user.username = 'client_{id}' (fallback)
    """
    # Спочатку пробуємо через client_profile
    client = getattr(request.user, 'client_profile', None)
    if client:
        return client
    
    # Якщо немає client_profile, шукаємо клієнта за username
    username = getattr(request.user, 'username', '')
    if not username:
        return None
    
    # Спочатку шукаємо за Client.user (основний випадок для JWT токенів)
    try:
        client = Client.objects.get(user=username, is_active=True)
        return client
    except Client.DoesNotExist:
        pass
    
    # Fallback: перевіряємо чи username має формат 'client_{id}'
    if username.startswith('client_'):
        try:
            client_id = int(username.replace('client_', ''))
            client = Client.objects.get(id=client_id, is_active=True)
            return client
