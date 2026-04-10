from django.db.models import ProtectedError
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication

from Jeeves.concierge_platform.permissions import IsOwner
from Jeeves.concierge_platform import provider_test_client as ptc
from Jeeves.EmbeddingModel.models import EmbeddingModel, LLMProvider, ModelPair
from Jeeves.EmbeddingModel.serializers import (
    EmbeddingModelSerializer,
    LLMProviderSerializer,
    ModelPairSerializer,
)


class _OwnerOnlyMixin:
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsOwner]


def _result_to_response(result):
    return Response({
        'outcome': result.outcome,
        'message': result.message,
        'metadata': result.metadata,
    })


def _protected_delete(instance):
    try:
        instance.delete()
    except ProtectedError as exc:
        refs = getattr(exc, 'protected_objects', []) or []
        count = len(list(refs))
        return Response(
            {
                'error': 'has_protected_references',
                'count': count,
                'references': 'protected',
            },
            status=status.HTTP_409_CONFLICT,
        )
    return None


class LLMProviderViewSet(_OwnerOnlyMixin, viewsets.ModelViewSet):
    queryset = LLMProvider.objects.all().order_by('name')
    serializer_class = LLMProviderSerializer

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        err = _protected_delete(instance)
        if err is not None:
            return err
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'])
    def test(self, request, pk=None):
        obj = self.get_object()
        override = request.data.get('api_key') if isinstance(request.data, dict) else None
        api_key = override or obj.api_key or ''
        result = ptc.test_llm_provider(
            provider_type=obj.provider_type,
            api_key=api_key,
            api_endpoint=obj.api_endpoint,
            model_name=obj.model_name,
        )
        return _result_to_response(result)

    @action(detail=False, methods=['post'], url_path='test-unsaved')
    def test_unsaved(self, request):
        data = request.data or {}
        result = ptc.test_llm_provider(
            provider_type=data.get('provider_type', ''),
            api_key=data.get('api_key', '') or '',
            api_endpoint=data.get('api_endpoint') or None,
            model_name=data.get('model_name') or None,
        )
        return _result_to_response(result)


class EmbeddingModelViewSet(_OwnerOnlyMixin, viewsets.ModelViewSet):
    queryset = EmbeddingModel.objects.all().order_by('name')
    serializer_class = EmbeddingModelSerializer

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        err = _protected_delete(instance)
        if err is not None:
            return err
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'])
    def test(self, request, pk=None):
        obj = self.get_object()
        override = request.data.get('api_key') if isinstance(request.data, dict) else None
        api_key = override or obj.api_key or ''
        result = ptc.test_embedding_model(
            provider=obj.provider,
            api_key=api_key,
            model_name=obj.model_name,
            dimensions=obj.dimensions,
            api_endpoint=obj.api_endpoint,
        )
        return _result_to_response(result)

    @action(detail=False, methods=['post'], url_path='test-unsaved')
    def test_unsaved(self, request):
        data = request.data or {}
        try:
            dims = int(data.get('dimensions') or 0)
        except (TypeError, ValueError):
            dims = 0
        result = ptc.test_embedding_model(
            provider=data.get('provider', ''),
            api_key=data.get('api_key', '') or '',
            model_name=data.get('model_name', '') or '',
            dimensions=dims,
            api_endpoint=data.get('api_endpoint') or None,
        )
        return _result_to_response(result)


class ModelPairViewSet(_OwnerOnlyMixin, viewsets.ModelViewSet):
    queryset = ModelPair.objects.select_related(
        'llm_provider', 'embedding_model',
    ).order_by('-created_at')
    serializer_class = ModelPairSerializer
