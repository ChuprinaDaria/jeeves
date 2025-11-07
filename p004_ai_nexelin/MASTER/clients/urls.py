from django.urls import path, include
from . import views
from .views_whatsapp import TwilioWhatsAppWebhookView
from .views_meta_whatsapp import MetaWhatsAppWebhookView


urlpatterns = [
    # Explicit routes ПЕРЕД router - щоб гарантувати пріоритет
    path('health/', views.health, name='clients-health'),
    path('me/', views.ClientMeView.as_view(), name='client-me'),
    path('logo/', views.ClientLogoUploadView.as_view(), name='client-logo-upload'),
    path('conversations/', views.ClientConversationsView.as_view(), name='client-conversations'),
    path('conversations/<int:conversation_id>/', views.ClientConversationDetailView.as_view(), name='client-conversation-detail'),
    path('top-questions/', views.ClientTopQuestionsView.as_view(), name='client-top-questions'),
    path('recent-activity/', views.ClientRecentActivityView.as_view(), name='client-recent-activity'),
    path('stats/', views.ClientStatsView.as_view(), name='client-stats'),
    path('embeddings-stats/', views.ClientEmbeddingsStatsView.as_view(), name='client-embeddings-stats'),
    path('model-status/', views.ClientModelStatusView.as_view(), name='client-model-status'),
    path('list-extended/', views.list_clients_extended, name='clients-list-extended'),
    path('rag-test/', views.rag_test_query, name='rag-test-query'),
    path('whatsapp/webhook/', TwilioWhatsAppWebhookView.as_view(), name='twilio_whatsapp_webhook'),
    path('whatsapp/status/', TwilioWhatsAppWebhookView.as_view(), name='twilio_whatsapp_status'),
    path('whatsapp/meta/webhook/', MetaWhatsAppWebhookView.as_view(), name='meta_whatsapp_webhook'),
    
    # Router URLs (viewsets) - після explicit routes
    path('', include(views.router.urls)),
    
    # Routes з параметрами після router
    # Видалено дублюючий path('create/'), тому що роутер вже обробляє POST на базовий URL
    path('<int:client_id>/stats/', views.client_stats, name='client-stats'),
    path('<int:client_id>/create-api-key/', views.create_api_key_for_client, name='client-create-api-key'),
    path('api-docs/<int:client_id>/', views.generate_api_docs, name='generate_api_docs'),
    path('<int:pk>/regenerate-qrs/', views.ClientRegenerateQRsView.as_view(), name='client-regenerate-qrs'),
    path('knowledge-blocks/<int:block_id>/documents/', views.KnowledgeBlockDocumentsView.as_view(), name='knowledge-block-documents'),
]

# Додаємо URL для Twilio статусу без префіксу clients
from django.urls import path as django_path
urlpatterns += [
    django_path('whatsapp/status/', TwilioWhatsAppWebhookView.as_view(), name='twilio_whatsapp_status_direct'),
]
