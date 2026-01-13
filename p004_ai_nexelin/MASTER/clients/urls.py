from django.urls import path, include
from . import views
from .views_meta_whatsapp import MetaWhatsAppWebhookView
from .views_telegram import TelegramWebhookView
from .views_webwidget import WebWidgetConfigView, WebWidgetChatIframeView, WebWidgetScriptView


urlpatterns = [
    # Explicit routes ПЕРЕД router - щоб гарантувати пріоритет
    path('health/', views.health, name='clients-health'),
    path('me/', views.ClientMeView.as_view(), name='client-me'),
    path('logo/', views.ClientLogoUploadView.as_view(), name='client-logo-upload'),
    path('conversations/', views.ClientConversationsView.as_view(), name='client-conversations'),
    path('conversations/<int:conversation_id>/', views.ClientConversationDetailView.as_view(), name='client-conversation-detail'),
    path('conversations/<int:conversation_id>/rate/', views.ConversationRatingView.as_view(), name='conversation-rate'),
    path('conversations/<int:conversation_id>/generate-report/', views.ManualReportView.as_view(), name='conversation-generate-report'),
    path('conversations/statistics/', views.ConversationStatisticsView.as_view(), name='conversation-statistics'),
    path('web-conversations/', views.ClientWebConversationView.as_view(), name='client-web-conversations'),
    path('web-knowledge/', views.ClientWebKnowledgeView.as_view(), name='client-web-knowledge'),
    path('top-questions/', views.ClientTopQuestionsView.as_view(), name='client-top-questions'),
    path('recent-activity/', views.ClientRecentActivityView.as_view(), name='client-recent-activity'),
    path('stats/', views.ClientStatsView.as_view(), name='client-stats'),
    path('embeddings-stats/', views.ClientEmbeddingsStatsView.as_view(), name='client-embeddings-stats'),
    path('model-status/', views.ClientModelStatusView.as_view(), name='client-model-status'),
    path('top-prompts/', views.TopPromptsView.as_view(), name='top-prompts'),
    path('whatsapp/meta/config/', views.ClientWhatsAppConfigView.as_view(), name='client-whatsapp-meta-config'),
    path('telegram/config/', views.ClientTelegramConfigView.as_view(), name='client-telegram-config'),
    path('email-smtp/config/', views.ClientEmailSMTPConfigView.as_view(), name='client-email-smtp-config'),
    path('extension/page/', views.ClientExtensionPageView.as_view(), name='client-extension-page'),
    path('extension/data/', views.ClientExtensionDataView.as_view(), name='client-extension-data'),
    path('web-widget/config/', WebWidgetConfigView.as_view(), name='client-web-widget-config'),
    path('list-extended/', views.list_clients_extended, name='clients-list-extended'),
    path('rag-test/', views.rag_test_query, name='rag-test-query'),
    path('whatsapp/meta/webhook/', MetaWhatsAppWebhookView.as_view(), name='meta_whatsapp_webhook'),
    path('telegram/webhook/', TelegramWebhookView.as_view(), name='telegram_webhook'),
    
    # Явні маршрути для viewsets з POST підтримкою
    path('documents/', views.ClientDocumentViewSet.as_view({'get': 'list', 'post': 'create'}), name='document-list'),
    path('documents/<int:pk>/', views.ClientDocumentViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='document-detail'),
    path('knowledge-blocks/', views.KnowledgeBlockViewSet.as_view({'get': 'list', 'post': 'create'}), name='knowledge-block-list'),
    path('knowledge-blocks/<int:pk>/', views.KnowledgeBlockViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='knowledge-block-detail'),
    path('qr-codes/', views.ClientQRCodeViewSet.as_view({'get': 'list', 'post': 'create'}), name='qr-code-list'),
    path('qr-codes/<int:pk>/', views.ClientQRCodeViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='qr-code-detail'),
    path('web-parsing-requests/', views.WebParsingRequestViewSet.as_view({'get': 'list', 'post': 'create'}), name='web-parsing-request-list'),
    path('web-parsing-requests/<int:pk>/', views.WebParsingRequestViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='web-parsing-request-detail'),
    path('prompts/', views.PromptViewSet.as_view({'get': 'list', 'post': 'create'}), name='prompt-list'),
    path('prompts/<int:pk>/', views.PromptViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='prompt-detail'),
    path('prompts/<int:pk>/vote/', views.PromptVoteView.as_view(), name='prompt-vote'),
    # Custom prompts management
    path('custom-prompts/', views.ClientCustomPromptViewSet.as_view({'get': 'list', 'post': 'create'}), name='custom-prompt-list'),
    path('custom-prompts/<int:pk>/', views.ClientCustomPromptViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='custom-prompt-detail'),
    path('custom-prompts/<int:pk>/activate/', views.ClientCustomPromptViewSet.as_view({'post': 'activate'}), name='custom-prompt-activate'),
    path('custom-prompts/add-from-library/<int:prompt_id>/', views.ClientCustomPromptViewSet.as_view({'post': 'add_from_library'}), name='custom-prompt-add-from-library'),
    path('news/', views.NewsViewSet.as_view({'get': 'list'}), name='news-list'),
    path('news/<int:pk>/', views.NewsViewSet.as_view({'get': 'retrieve'}), name='news-detail'),
    
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

# Twilio маршрути видалено — використовуємо лише Meta WhatsApp Business API
