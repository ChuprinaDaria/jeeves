"""
Web Widget Integration Views

Handles:
- Widget code generation for white label clients
- Iframe chat page
- Widget configuration
"""

import logging
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.views import View
from django.conf import settings
from django.utils.decorators import method_decorator
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .models import Client
from .views import get_client_from_request

logger = logging.getLogger(__name__)


class WebWidgetConfigView(APIView):
    """Get/Update web widget configuration for white label clients."""
    permission_classes = []  # Публічний, ідентифікація через middleware/api_key/tag

    def get(self, request):
        client = get_client_from_request(request)
        if not client:
            return Response({'error': 'Client not found'}, status=401)
        
        # Перевіряємо чи це white label клієнт
        if client.client_type != Client.TYPE_WHITE_LABEL:
            return Response({'error': 'Web widget is only available for white label clients'}, status=403)
        
        # Формуємо URL для віджета та iframe
        # Скрипт віджета завжди з frontend
        default_frontend = getattr(settings, 'CLIENT_PORTAL_BASE_URL', 'http://localhost:3000')
        widget_url = f"{default_frontend}/static/widget/chat.js"
        
        # Для white label з власним доменом - використовуємо їхній домен для чату
        custom_domain = getattr(client, 'webchat_domain', '') or ''
        if custom_domain:
            # Прибираємо протокол якщо є
            custom_domain = custom_domain.replace('https://', '').replace('http://', '').strip('/')
            chat_base_url = f"https://{custom_domain}"
        else:
            chat_base_url = default_frontend
        
        iframe_url = f"{chat_base_url}/client?tag={client.tag}"
        
        data = {
            'widget_enabled': getattr(client, 'widget_enabled', False),
            'widget_url': widget_url,
            'iframe_url': iframe_url,
            'custom_domain': custom_domain if custom_domain else None,
            'widget_code_html': self._generate_widget_code(client.tag, widget_url, custom_domain) if getattr(client, 'widget_enabled', False) else None,
            'iframe_code_html': self._generate_iframe_code(iframe_url) if getattr(client, 'widget_enabled', False) else None,
        }
        return Response(data)

    def post(self, request):
        return self._update(request)

    def patch(self, request):
        return self._update(request)

    def _update(self, request):
        client = get_client_from_request(request)
        if not client:
            return Response({'error': 'Client not found'}, status=401)
        
        # Перевіряємо чи це white label клієнт
        if client.client_type != Client.TYPE_WHITE_LABEL:
            return Response({'error': 'Web widget is only available for white label clients'}, status=403)
        
        data = request.data or {}
        old_widget_enabled = getattr(client, 'widget_enabled', False)
        
        if 'widget_enabled' in data:
            client.widget_enabled = bool(data['widget_enabled'])
            client.save(update_fields=['widget_enabled'])
            
            # Новіни про інтеграції створюються тільки через адмін-панель, не автоматично
        
        # Повертаємо оновлені дані
        # Скрипт віджета завжди з frontend
        default_frontend = getattr(settings, 'CLIENT_PORTAL_BASE_URL', 'http://localhost:3000')
        widget_url = f"{default_frontend}/static/widget/chat.js"
        
        # Для white label з власним доменом - використовуємо їхній домен для чату
        custom_domain = getattr(client, 'webchat_domain', '') or ''
        if custom_domain:
            custom_domain = custom_domain.replace('https://', '').replace('http://', '').strip('/')
            chat_base_url = f"https://{custom_domain}"
        else:
            chat_base_url = default_frontend
        
        iframe_url = f"{chat_base_url}/client?tag={client.tag}"
        
        return Response({
            'success': True,
            'widget_enabled': client.widget_enabled,
            'widget_url': widget_url,
            'iframe_url': iframe_url,
            'custom_domain': custom_domain if custom_domain else None,
            'widget_code_html': self._generate_widget_code(client.tag, widget_url, custom_domain) if client.widget_enabled else None,
            'iframe_code_html': self._generate_iframe_code(iframe_url) if client.widget_enabled else None,
        })

    def _generate_widget_code(self, tag: str, widget_url: str, custom_domain: str = None) -> str:
        """Генерує HTML код для вставки віджета"""
        # Якщо є власний домен - додаємо його як параметр
        if custom_domain:
            src = f"{widget_url}?tag={tag}&domain={custom_domain}"
        else:
            src = f"{widget_url}?tag={tag}"
        
        return f'''<!-- AI Chat Widget -->
<script>
  (function() {{
    var script = document.createElement('script');
    script.src = '{src}';
    script.async = true;
    document.head.appendChild(script);
  }})();
</script>'''

    def _generate_iframe_code(self, iframe_url: str) -> str:
        """Генерує HTML код для вставки iframe"""
        return f'''<!-- AI Chat Iframe -->
<iframe 
  src="{iframe_url}" 
  width="100%" 
  height="600px" 
  frameborder="0"
  style="border: none; border-radius: 8px;"
  allow="microphone; camera">
</iframe>'''


class WebWidgetChatIframeView(View):
    """Iframe версія чату для вставки на сторонні сайти"""
    
    def get(self, request):
        tag = request.GET.get('tag')
        if not tag:
            return HttpResponse("Missing tag parameter", status=400)
        
        try:
            client = Client.objects.get(tag=tag, is_active=True)
        except Client.DoesNotExist:
            return HttpResponse("Client not found", status=404)
        
        # Перевіряємо чи це white label клієнт
        if client.client_type != Client.TYPE_WHITE_LABEL:
            return HttpResponse("Web widget is only available for white label clients", status=403)
        
        # Перевіряємо чи увімкнено віджет
        if not getattr(client, 'widget_enabled', False):
            return HttpResponse("Widget is not enabled for this client", status=403)
        
        # Рендеримо HTML сторінку для iframe
        base_url = request.build_absolute_uri('/').rstrip('/')
        chat_url = f"{base_url}/client?tag={tag}"
        
        html = f'''<!DOCTYPE html>
<html lang="uk">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Chat - {client.company_name or 'Assistant'}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        html, body {{
            height: 100%;
            overflow: hidden;
        }}
        iframe {{
            width: 100%;
            height: 100vh;
            border: none;
        }}
    </style>
</head>
<body>
    <iframe src="{chat_url}" frameborder="0" allow="microphone; camera"></iframe>
</body>
</html>'''
        
        return HttpResponse(html, content_type='text/html')


class WebWidgetScriptView(View):
    """JavaScript файл для віджета"""
    
    def get(self, request):
        tag = request.GET.get('tag')
        if not tag:
            return HttpResponse("Missing tag parameter", status=400)
        
        try:
            client = Client.objects.get(tag=tag, is_active=True)
        except Client.DoesNotExist:
            return HttpResponse("Client not found", status=404)
        
        # Перевіряємо чи це white label клієнт
        if client.client_type != Client.TYPE_WHITE_LABEL:
            return HttpResponse("Web widget is only available for white label clients", status=403)
        
        # Перевіряємо чи увімкнено віджет
        if not getattr(client, 'widget_enabled', False):
            return HttpResponse("Widget is not enabled for this client", status=403)
        
        # Читаємо статичний JavaScript файл віджета
        import os
        from django.conf import settings
        
        # Шлях до статичного файлу віджета
        widget_js_path = os.path.join(
            settings.BASE_DIR.parent,  # Виходимо з backend
            'frontend',
            'public',
            'static',
            'widget',
            'chat.js'
        )
        
        try:
            with open(widget_js_path, 'r', encoding='utf-8') as f:
                js_code = f.read()
        except FileNotFoundError:
            # Fallback на динамічну генерацію, якщо файл не знайдено
            logger.error(f"Widget JS file not found at {widget_js_path}")
            base_url = request.build_absolute_uri('/').rstrip('/')
            chat_url = f"{base_url}/webchat?tag={tag}"
            js_code = f'''(function() {{
  'use strict';
  
  // Конфігурація
  const config = {{
    tag: '{tag}',
    chatUrl: '{chat_url}',
    position: 'bottom-right',
    primaryColor: '#3b82f6',
    buttonText: '💬 Chat',
    buttonSize: '56px'
  }};
  
  // Створюємо стилі
  const style = document.createElement('style');
  style.textContent = `
    .concierge-widget-container {{
      position: fixed;
      bottom: 20px;
      right: 20px;
      z-index: 9999;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    }}
    .concierge-widget-button {{
      width: ${{config.buttonSize}};
      height: ${{config.buttonSize}};
      border-radius: 50%;
      background: ${{config.primaryColor}};
      color: white;
      border: none;
      cursor: pointer;
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 24px;
      transition: transform 0.2s, box-shadow 0.2s;
    }}
    .concierge-widget-button:hover {{
      transform: scale(1.1);
      box-shadow: 0 6px 16px rgba(0, 0, 0, 0.2);
    }}
    .concierge-widget-chat {{
      position: fixed;
      bottom: 90px;
      right: 20px;
      width: 380px;
      height: 600px;
      max-width: calc(100vw - 40px);
      max-height: calc(100vh - 100px);
      border-radius: 12px;
      box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
      background: white;
      display: none;
      overflow: hidden;
      z-index: 10000;
    }}
    .concierge-widget-chat.active {{
      display: block;
    }}
    .concierge-widget-chat iframe {{
      width: 100%;
      height: 100%;
      border: none;
    }}
    @media (max-width: 480px) {{
      .concierge-widget-chat {{
        width: 100%;
        height: 100%;
        bottom: 0;
        right: 0;
        border-radius: 0;
      }}
    }}
  `;
  document.head.appendChild(style);
  
  // Створюємо контейнер
  const container = document.createElement('div');
  container.className = 'concierge-widget-container';
  
  // Створюємо кнопку
  const button = document.createElement('button');
  button.className = 'concierge-widget-button';
  button.innerHTML = config.buttonText;
  button.setAttribute('aria-label', 'Open chat');
  
  // Створюємо чат iframe
  const chatContainer = document.createElement('div');
  chatContainer.className = 'concierge-widget-chat';
  const iframe = document.createElement('iframe');
  iframe.src = config.chatUrl;
  iframe.setAttribute('allow', 'microphone; camera');
  chatContainer.appendChild(iframe);
  
  // Обробка кліку
  let isOpen = false;
  button.addEventListener('click', function() {{
    isOpen = !isOpen;
    if (isOpen) {{
      chatContainer.classList.add('active');
      button.innerHTML = '✕';
    }} else {{
      chatContainer.classList.remove('active');
      button.innerHTML = config.buttonText;
    }}
  }});
  
  // Закриваємо при кліку поза чатом
  document.addEventListener('click', function(e) {{
    if (isOpen && !container.contains(e.target)) {{
      isOpen = false;
      chatContainer.classList.remove('active');
      button.innerHTML = config.buttonText;
    }}
  }});
  
  // Додаємо до DOM
  container.appendChild(button);
  container.appendChild(chatContainer);
  document.body.appendChild(container);
  
  // Повідомляємо про завантаження
  console.log('Concierge AI Chat Widget loaded');
}})();'''
        
        return HttpResponse(js_code, content_type='application/javascript')

