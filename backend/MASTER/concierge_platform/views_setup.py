from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from MASTER.accounts.models import User, Roles
from MASTER.concierge_platform.serializers import OwnerCreateSerializer


class CreateOwnerView(APIView):
    """Create the first (and only) OWNER user during the setup wizard.

    Rejects with 409 if an owner already exists. The owner also gets
    is_superuser/is_staff flags as a fallback path into Django admin.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        if User.objects.filter(role=Roles.OWNER).exists():
            return Response(
                {"error": "owner_exists"},
                status=status.HTTP_409_CONFLICT,
            )

        serializer = OwnerCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        user = User.objects.create_user(
            username=data["email"],
            email=data["email"],
            password=data["password"],
            first_name=data["first_name"],
            last_name=data["last_name"],
            role=Roles.OWNER,
            is_staff=True,
            is_superuser=True,
        )

        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "role": user.role,
                },
            },
            status=status.HTTP_201_CREATED,
        )
