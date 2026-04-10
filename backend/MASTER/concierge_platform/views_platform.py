from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from MASTER.concierge_platform.models import PlatformLicense


class BootstrapView(APIView):
    """Public endpoint that tells the frontend whether setup is needed
    and what the current license status is. Called on every React boot.
    """

    permission_classes = [AllowAny]

    def get(self, request):
        lic = PlatformLicense.get()
        return Response({
            "setup_required": not lic.is_setup_complete,
            "license_status": lic.status,
            "license_last_verified_at": (
                lic.last_verified_at.isoformat() if lic.last_verified_at else None
            ),
            "grace_days_remaining": lic.grace_days_remaining,
        })
