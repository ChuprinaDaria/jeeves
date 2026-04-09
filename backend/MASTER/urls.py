from django.contrib import admin
from django.http import JsonResponse
from django.views.generic import RedirectView
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, re_path, include

from MASTER.clients.views_meta_whatsapp import MetaWhatsAppWebhookView
from MASTER.clients.views_whatsapp import TwilioWhatsAppWebhookView
from MASTER.clients.views_webwidget import WebWidgetChatIframeView, WebWidgetScriptView
from MASTER.quick_admin import urlpatterns as quick_admin_urlpatterns


def health_view(_request):
    return JsonResponse({
        "status": "ok",
        "app": "ai_nexelin",
        "version": "dev",
    })


urlpatterns = [
    # Healthcheck
    path('', health_view, name='health'),

    # Django admin & accounts
    path('accounts/login/', RedirectView.as_view(url='/admin/login/', permanent=False)),
    path('admin/', admin.site.urls),

    # API endpoints
    path('api/embedding-model/', include('MASTER.EmbeddingModel.urls')),
    path('api/accounts/', include('MASTER.accounts.urls')),
    path('api/auth/', include('MASTER.accounts.urls')),  # Alias для /api/auth/ для сумісності з фронтендом
    path('api/branches/', include('MASTER.branches.urls')),
    path('api/specializations/', include('MASTER.specializations.urls')),
    path('api/clients/', include('MASTER.clients.urls')),
    path('api/rag/', include('MASTER.api.urls')),
    # Twilio webhook
    path('api/whatsapp/status/', TwilioWhatsAppWebhookView.as_view(), name='twilio_whatsapp_status_direct'),

    # Meta WhatsApp API (офіційна інтеграція)
    path('api/whatsapp/meta/webhook/', MetaWhatsAppWebhookView.as_view(), name='meta_whatsapp_webhook'),

    # Web Widget routes (for white label clients)
    path('widget/chat.js', WebWidgetScriptView.as_view(), name='web_widget_script'),
    path('widget/chat', WebWidgetChatIframeView.as_view(), name='web_widget_iframe'),

    # Client portal тепер обробляється React додатком (frontend), не Django

    # SP1: MCP Core Engine
    path('api/tools/', include('MASTER.tools.urls')),
    path('api/agents/', include('MASTER.agents.urls')),
    path('api/mcp/', include('MASTER.mcp_hub.urls')),
]

# Serve media & static files
from django.views.static import serve
from django.urls import re_path as url_re_path

urlpatterns += [
    url_re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
    url_re_path(r'^static/(?P<path>.*)$', serve, {'document_root': settings.STATIC_ROOT}),
]

# Quick admin URLs
urlpatterns += quick_admin_urlpatterns
