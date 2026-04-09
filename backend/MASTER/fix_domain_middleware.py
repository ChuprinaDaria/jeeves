class FixDomainMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Виправляємо HTTP_HOST
        if 'HTTP_HOST' in request.META:
            if 'frontend' in request.META['HTTP_HOST']:
                request.META['HTTP_HOST'] = 'api.nexelin.com'
        
        response = self.get_response(request)
        return response
