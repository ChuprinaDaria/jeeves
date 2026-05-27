from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from Jeeves.accounts.models import User, Roles


class BootstrapView(APIView):
    """Public endpoint that tells the frontend whether setup is needed.
    Called on every React boot.
    """

    permission_classes = [AllowAny]

    def get(self, request):
        setup_required = not User.objects.filter(role=Roles.OWNER).exists()
        return Response({
            "setup_required": setup_required,
        })
