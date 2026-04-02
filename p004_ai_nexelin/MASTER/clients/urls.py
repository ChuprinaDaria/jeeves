from django.urls import path, include
from . import views
from .views_meta_whatsapp import MetaWhatsAppWebhookView
from .views_telegram import TelegramWebhookView
from .views_webwidget import WebWidgetConfigView, WebWidgetChatIframeView, WebWidgetScriptView
from .views_telephony import (
    TelephonyConnectView,
    TelephonyListView,
    TelephonyDetailView,
    TelephonyVoicesView,
)
from .views_whatsapp_bridge import (
    WhatsAppBridgeConfigView,
    WhatsAppBridgeLoginView,
    WhatsAppBridgeQRPollView,
    WhatsAppBridgeLogoutView,
    WhatsAppBridgeStatusView,
    WhatsAppBridgeMessageView,
)
from .views_leads import LeadListView, LeadDetailView
from .views_auto_reply import (
    ChannelAutoReplyListView,
    ChannelAutoReplyDetailView,
    ChannelAutoReplyContactsView,
)


urlpatterns = [
    # Universal Bridge API
    path('bridges/', include('MASTER.clients.urls_bridge')),

    # Explicit routes ПЕРЕД router - щоб гарантувати пріоритет
    path('health/', views.health, name='clients-health'),
    path('me/', views.ClientMeView.as_view(), name='client-me'),
    path('logo/', views.ClientLogoUploadView.as_view(), name='client-logo-upload'),
    path('conversations/', views.ClientConversationsView.as_view(), name='client-conversations'),
    path('conversations/<int:conversation_id>/', views.ClientConversationDetailView.as_view(), name='client-conversation-detail'),
    path('conversations/<int:conversation_id>/rate/', views.ConversationRatingView.as_view(), name='conversation-rate'),
    path('conversations/<int:conversation_id>/generate-report/', views.ManualReportView.as_view(), name='conversation-generate-report'),
    path('conversations/<int:conversation_id>/notes/', views.ConversationNotesView.as_view(), name='conversation-notes'),
    path('conversations/statistics/', views.ConversationStatisticsView.as_view(), name='conversation-statistics'),
    path('web-conversations/', views.ClientWebConversationView.as_view(), name='client-web-conversations'),
    path('web-knowledge/', views.ClientWebKnowledgeView.as_view(), name='client-web-knowledge'),
    path('top-questions/', views.ClientTopQuestionsView.as_view(), name='client-top-questions'),
    path('recent-activity/', views.ClientRecentActivityView.as_view(), name='client-recent-activity'),
    path('stats/', views.ClientStatsView.as_view(), name='client-stats'),
    path('embeddings-stats/', views.ClientEmbeddingsStatsView.as_view(), name='client-embeddings-stats'),
    path('model-status/', views.ClientModelStatusView.as_view(), name='client-model-status'),
    path('pixel-status/', views.PixelDashboardStatusView.as_view(), name='client-pixel-status'),
    path('top-prompts/', views.TopPromptsView.as_view(), name='top-prompts'),
    path('whatsapp/meta/config/', views.ClientWhatsAppConfigView.as_view(), name='client-whatsapp-meta-config'),
    # WhatsApp Bridge (mautrix-whatsapp)
    path('whatsapp/bridge/config/', WhatsAppBridgeConfigView.as_view(), name='client-whatsapp-bridge-config'),
    path('whatsapp/bridge/login/', WhatsAppBridgeLoginView.as_view(), name='client-whatsapp-bridge-login'),
    path('whatsapp/bridge/login/status/', WhatsAppBridgeQRPollView.as_view(), name='client-whatsapp-bridge-login-status'),
    path('whatsapp/bridge/logout/', WhatsAppBridgeLogoutView.as_view(), name='client-whatsapp-bridge-logout'),
    path('whatsapp/bridge/status/', WhatsAppBridgeStatusView.as_view(), name='client-whatsapp-bridge-status'),
    path('whatsapp/bridge/message/', WhatsAppBridgeMessageView.as_view(), name='client-whatsapp-bridge-message'),
    path('telegram/config/', views.ClientTelegramConfigView.as_view(), name='client-telegram-config'),
    path('email-smtp/config/', views.ClientEmailSMTPConfigView.as_view(), name='client-email-smtp-config'),
    path('reports/daily-digest/send/', views.SendDailyDigestNowView.as_view(), name='client-send-daily-digest-now'),
    path('hitl/config/', views.ClientHITLConfigView.as_view(), name='client-hitl-config'),
    # Telephony — порядок важливий: конкретні paths перед <str:tag>
    path('telephony/', TelephonyListView.as_view(), name='telephony-list'),
    path('telephony/connect/', TelephonyConnectView.as_view(), name='telephony-connect'),
    path('telephony/voices/', TelephonyVoicesView.as_view(), name='telephony-voices'),
    path('telephony/<str:tag>/', TelephonyDetailView.as_view(), name='telephony-detail'),
    path('extension/page/', views.ClientExtensionPageView.as_view(), name='client-extension-page'),
    path('extension/data/', views.ClientExtensionDataView.as_view(), name='client-extension-data'),
    path('web-widget/config/', WebWidgetConfigView.as_view(), name='client-web-widget-config'),
    path('list-extended/', views.list_clients_extended, name='clients-list-extended'),
    path('rag-test/', views.rag_test_query, name='rag-test-query'),
    path('whatsapp/meta/webhook/', MetaWhatsAppWebhookView.as_view(), name='meta_whatsapp_webhook'),
    path('telegram/webhook/', TelegramWebhookView.as_view(), name='telegram_webhook'),

    # Channel Auto-Reply
    path('channel-auto-reply/', ChannelAutoReplyListView.as_view(), name='channel-auto-reply-list'),
    path('channel-auto-reply/<str:channel>/', ChannelAutoReplyDetailView.as_view(), name='channel-auto-reply-detail'),
    path('channel-auto-reply/<str:channel>/contacts/', ChannelAutoReplyContactsView.as_view(), name='channel-auto-reply-contacts'),

    # Leads
    path('leads/', LeadListView.as_view(), name='lead-list'),
    path('leads/<int:lead_id>/', LeadDetailView.as_view(), name='lead-detail'),

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
