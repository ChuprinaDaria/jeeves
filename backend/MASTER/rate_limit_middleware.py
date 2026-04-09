"""
Rate limiting middleware using Redis.
Protects AI chat endpoints (30 req/min) and bootstrap provisioning (5 req/min).
"""
import time
import logging

from django.http import JsonResponse

logger = logging.getLogger(__name__)

# Paths and their limits: (max_requests, window_seconds)
RATE_LIMITS = {
    '/api/rag/chat/': (30, 60),
    '/api/rag/bootstrap/': (5, 60),
}


def _get_client_ip(request):
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '0.0.0.0')


class RateLimitMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self._redis = None

    def _get_redis(self):
        if self._redis is None:
            try:
                from django_redis import get_redis_connection
                self._redis = get_redis_connection("default")
            except Exception:
                try:
                    import redis
                    self._redis = redis.Redis(host='redis', port=6379, db=1)
                except Exception:
                    self._redis = False
        return self._redis if self._redis else None

    def __call__(self, request):
        path = request.path

        for prefix, (max_requests, window) in RATE_LIMITS.items():
            if path.startswith(prefix):
                if self._is_rate_limited(request, prefix, max_requests, window):
                    return JsonResponse(
                        {'error': 'Rate limit exceeded. Try again later.'},
                        status=429,
                    )
                break

        return self.get_response(request)

    def _is_rate_limited(self, request, prefix, max_requests, window):
        r = self._get_redis()
        if not r:
            return False  # fail open if Redis unavailable

        ip = _get_client_ip(request)
        # Include client tag for per-client limiting on chat
        client_tag = getattr(request, 'client', None)
        if client_tag:
            client_tag = getattr(client_tag, 'tag', str(client_tag))
        key_id = f"{ip}:{client_tag}" if client_tag else ip

        key = f"ratelimit:{prefix}:{key_id}"
        try:
            current = r.get(key)
            if current is None:
                pipe = r.pipeline()
                pipe.set(key, 1, ex=window)
                pipe.execute()
                return False
            count = int(current)
            if count >= max_requests:
                return True
            r.incr(key)
            return False
        except Exception as e:
            logger.warning(f"Rate limit check failed: {e}")
            return False  # fail open
