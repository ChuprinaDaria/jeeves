"""
Middleware для дозволу вбудовування фронтенду в iframe.

Дозволяє app.nexelin.com відображатися в iframe на mg.nexelin.com
для інтеграції клієнтської панелі.
"""


class AllowIframeMiddleware:
    """
    Middleware що дозволяє вбудовування в iframe з дозволених доменів.

    Замінює стандартний X-Frame-Options на ALLOW-FROM для конкретних доменів.
    """

    ALLOWED_IFRAME_HOSTS = [
        'https://mg.nexelin.com',
        'http://mg.nexelin.com',
        'https://app.nexelin.com',
        'http://localhost:3000',
        'http://localhost:5173',
    ]

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Видаляємо стандартний X-Frame-Options якщо він є
        if 'X-Frame-Options' in response:
            del response['X-Frame-Options']

        # Перевіряємо Referer або Origin для безпеки
        referer = request.META.get('HTTP_REFERER', '')
        origin = request.META.get('HTTP_ORIGIN', '')

        # Якщо запит походить з дозволеного домену, дозволяємо iframe
        allowed = any(
            host in referer or host in origin
            for host in self.ALLOWED_IFRAME_HOSTS
        )

        if allowed or origin in self.ALLOWED_IFRAME_HOSTS:
            # Дозволяємо вбудовування з конкретного origin
            response['X-Frame-Options'] = f'ALLOW-FROM {origin}' if origin else 'SAMEORIGIN'
            # Сучасний стандарт - Content-Security-Policy
            if origin:
                response['Content-Security-Policy'] = f"frame-ancestors {origin} 'self'"
            else:
                response['Content-Security-Policy'] = "frame-ancestors https://mg.nexelin.com http://mg.nexelin.com 'self'"
        else:
            # Для інших запитів використовуємо стандартну безпеку
            response['X-Frame-Options'] = 'SAMEORIGIN'

        return response
