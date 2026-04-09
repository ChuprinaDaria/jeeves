from django.urls import path
from django.views.generic import RedirectView
from rest_framework_simplejwt.views import TokenRefreshView
from . import views


urlpatterns = [
    # Auth endpoints
    path('register/', views.RegisterView.as_view(), name='auth-register'),
    path('login/', views.LoginView.as_view(), name='auth-login'),
    path('logout/', views.LogoutView.as_view(), name='auth-logout'),
    path('me/', views.AuthMeView.as_view(), name='auth-me'),
    path('refresh/', TokenRefreshView.as_view(), name='token-refresh'),

    # Legacy redirects
    path('health/', views.health, name='accounts-health'),
]

