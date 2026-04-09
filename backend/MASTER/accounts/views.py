from django.shortcuts import render
from django.http import JsonResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from MASTER.clients.models import Client
from MASTER.clients.views import get_client_from_request
from MASTER.accounts.models import User


# Create your views here.


def health(_request):
    return JsonResponse({"module": "accounts", "status": "ok"})


class RegisterView(APIView):
    """
    API endpoint для реєстрації нового користувача.
    POST /api/auth/register/

    Request body:
    {
        "email": "string",
        "password": "string",
        "salon_name": "string" (optional)
    }

    Response:
    {
        "access": "string",
        "refresh": "string",
        "user": {...}
    }
    """
    permission_classes = []

    def post(self, request):
        email = request.data.get('email')
        password = request.data.get('password')
        salon_name = request.data.get('salon_name', '')

        # Валідація
        if not email or not password:
            return Response(
                {'error': 'Email and password are required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Перевірка чи користувач вже існує
        if User.objects.filter(email=email).exists():
            return Response(
                {'error': 'User with this email already exists'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Створюємо username з email
        username = email.split('@')[0]
        # Якщо username вже існує, додаємо числовий суфікс
        base_username = username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1

        # Створюємо користувача
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=salon_name or username,
            last_name='',
            role='client'
        )

        # Генеруємо JWT токени
        refresh = RefreshToken.for_user(user)

        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': {
                'id': user.id,
                'email': user.email,
                'salon_name': user.first_name,
                'username': user.username,
                'role': user.role,
                'is_trial': True,
                'trial_end_date': None
            }
        }, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    """
    API endpoint для входу користувача.
    POST /api/auth/login/

    Request body:
    {
        "email": "string",
        "password": "string"
    }

    Response:
    {
        "access": "string",
        "refresh": "string",
        "user": {...}
    }
    """
    permission_classes = []

    def post(self, request):
        email = request.data.get('email')
        password = request.data.get('password')

        # Валідація
        if not email or not password:
            return Response(
                {'error': 'Email and password are required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Знаходимо користувача за email
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response(
                {'error': 'Invalid email or password'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # Перевіряємо пароль
        if not user.check_password(password):
            return Response(
                {'error': 'Invalid email or password'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # Перевіряємо чи користувач активний
        if not user.is_active:
            return Response(
                {'error': 'User account is disabled'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # Генеруємо JWT токени
        refresh = RefreshToken.for_user(user)

        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': {
                'id': user.id,
                'email': user.email,
                'salon_name': user.first_name,
                'username': user.username,
                'role': user.role,
                'is_trial': True,
                'trial_end_date': None
            }
        })


class LogoutView(APIView):
    """
    API endpoint для виходу користувача.
    POST /api/auth/logout/

    Опціонально можна передати refresh token для blacklist:
    Request body:
    {
        "refresh": "string" (optional)
    }

    Response: 200 OK
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get('refresh')
            if refresh_token:
                # Додаємо токен до blacklist (якщо використовується)
                try:
                    token = RefreshToken(refresh_token)
                    token.blacklist()
                except Exception:
                    pass  # Ігноруємо помилки blacklist

            return Response(
                {'message': 'Successfully logged out'},
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class AuthMeView(APIView):
    """
    API endpoint для отримання профілю поточного користувача або клієнта.
    GET /api/auth/me/

    Працює для:
    - Звичайних користувачів (повертає дані User)
    - Клієнтів через JWT токен (username=client_{id}, повертає дані Client)
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Перевіряємо чи це клієнт (через helper функцію)
        client = get_client_from_request(request)

        if client:
            # Якщо це клієнт, повертаємо дані клієнта
            from MASTER.clients.serializers import ClientSerializer
            serializer = ClientSerializer(client, context={'request': request})
            return Response(serializer.data)
        else:
            # Якщо це звичайний користувач, повертаємо дані користувача
            user = request.user
            return Response({
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'role': user.role,
                'is_staff': user.is_staff,
            })
