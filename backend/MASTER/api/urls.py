from django.urls import path
from . import views
from . import views_bootstrap


urlpatterns = [
    path('query/', views.RAGQueryView.as_view(), name='rag-query'),
    path('upload/', views.DocumentUploadView.as_view(), name='rag-upload'),
    path('docs/', views.APIDocsView.as_view(), name='rag-docs'),
    path('chat/', views.PublicRAGChatView.as_view(), name='rag-chat'),
    path('auth/token-by-client-token/', views.TokenByClientTokenView.as_view(), name='token-by-client-token'),
    path('bootstrap/<slug:branch_slug>/<slug:specialization_slug>/<slug:client_token>/', views_bootstrap.BootstrapProvisionView.as_view(), name='bootstrap-provision'),
    path('provision-link/', views.ProvisionLinkView.as_view(), name='provision-link'),
    path('client/features/overview/', views.ClientFeaturesOverviewView.as_view(), name='client-features-overview'),
    # AI Models endpoint (from mg.nexelin.com)
    path('ai-models/', views.AIModelsListView.as_view(), name='ai-models-list'),
    # Sync our embedding models to MG
    path('embedding-models/sync-to-mg/', views.EmbeddingModelsSyncToMGView.as_view(), name='embedding-models-sync-to-mg'),
    # Embedding models endpoints
    path('embedding-models/', views.EmbeddingModelsListView.as_view(), name='embedding-models-list'),
    path('client/embedding-model/', views.ClientEmbeddingModelSetView.as_view(), name='client-embedding-model-set'),
    path('client/index-new/', views.ClientIndexNewDocumentsView.as_view(), name='client-index-new-documents'),
    path('client/reindex/', views.ClientReindexDocumentsView.as_view(), name='client-reindex-documents'),
    path('client/llm/', views.ClientLLMSetView.as_view(), name='client-llm-set'),
    path('embedding-models/<int:model_id>/reindex/', views.EmbeddingModelReindexView.as_view(), name='embedding-model-reindex'),
    # Client AI usage statistics
    path('client/ai-usage/', views.ClientAIUsageView.as_view(), name='client-ai-usage'),
    # LLM Providers endpoints
    path('llm-providers/', views.LLMProvidersListView.as_view(), name='llm-providers-list'),
    path('client/llm-provider/', views.ClientLLMProviderSetView.as_view(), name='client-llm-provider-set'),
    # Model Pairs endpoint
    path('model-pairs/', views.ModelPairsView.as_view(), name='model-pairs'),
    # Save Q&A from sandbox
    path('sandbox/save-qa/', views.SaveSandboxQAView.as_view(), name='sandbox-save-qa'),
    # Save photo from sandbox
    path('sandbox/save-photo/', views.SaveSandboxPhotoView.as_view(), name='sandbox-save-photo'),
    # Email service endpoints
    path('email/send/', views.EmailSendView.as_view(), name='email-send'),
    path('email/recent/', views.EmailRecentView.as_view(), name='email-recent'),
    path('email/search/', views.EmailSearchView.as_view(), name='email-search'),
    path('email/analyze/', views.EmailAnalyzeView.as_view(), name='email-analyze'),
    # Dynamic manifest for webchat PWA
    path('webchat/manifest.json', views.WebChatManifestView.as_view(), name='webchat-manifest'),
    # Package API endpoint (from mg.nexelin)
    path('package/', views.PackageReceiveView.as_view(), name='package-receive'),
    # Integration Service endpoints (for Matrix HITL)
    path('v1/integration/update-room', views.integration_update_room, name='integration-update-room'),
    path('v1/integration/forward-message', views.integration_forward_message, name='integration-forward-message'),
]
