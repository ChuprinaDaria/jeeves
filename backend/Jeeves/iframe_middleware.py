"""
Middleware для дозволу вбудовування фронтенду в iframe.

Дозволяє frontend відображатися в iframe для інтеграції клієнтської панелі.
Дозволені домени конфігуруються через env var IFRAME_ALLOWED_HOSTS.
"""

import os
from urllib.parse import urlparse


def _origin_of(url: str) -> str:
    """Нормалізує URL до origin (scheme://host[:port]) для точного порівняння."""
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return ''
    return f"{parsed.scheme}://{parsed.netloc}"


class AllowIframeMiddleware:
    """
    Middleware що дозволяє вбудовування в iframe з дозволених доменів.

    Замінює стандартний X-Frame-Options на ALLOW-FROM для конкретних доменів.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        # Build allowed hosts from env var + defaults
        extra = [h.strip() for h in os.environ.get('IFRAME_ALLOWED_HOSTS', '').split(',') if h.strip()]
        self.allowed_iframe_hosts = [
            'http://localhost:3000',
            'http://localhost:5173',
        ] + extra

    def __call__(self, request):
        response = self.get_response(request)

        # Видаляємо стандартний X-Frame-Options якщо він є
        if 'X-Frame-Options' in response:
            del response['X-Frame-Options']

        # Перевіряємо Referer або Origin для безпеки
        referer = request.META.get('HTTP_REFERER', '')
        origin = request.META.get('HTTP_ORIGIN', '')

        # Точне порівняння origin: substring-перевірка ("host in referer")
        # обходилась URL-ами виду http://evil.com/?x=http://localhost:3000
        referer_origin = _origin_of(referer)
        allowed = (
            (origin and origin in self.allowed_iframe_hosts)
            or (referer_origin and referer_origin in self.allowed_iframe_hosts)
        )

        if allowed:
            # Дозволяємо вбудовування з конкретного origin
            response['X-Frame-Options'] = f'ALLOW-FROM {origin}' if origin else 'SAMEORIGIN'
            # Сучасний стандарт - Content-Security-Policy
            if origin:
                response['Content-Security-Policy'] = f"frame-ancestors {origin} 'self'"
            else:
                ancestors = ' '.join(self.allowed_iframe_hosts)
                response['Content-Security-Policy'] = f"frame-ancestors {ancestors} 'self'"
        else:
            # Для інших запитів використовуємо стандартну безпеку
            response['X-Frame-Options'] = 'SAMEORIGIN'

        return response
