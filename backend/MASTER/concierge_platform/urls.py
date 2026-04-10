from django.urls import path

from MASTER.concierge_platform import views_platform

urlpatterns = [
    path('platform/bootstrap/', views_platform.BootstrapView.as_view(), name='platform-bootstrap'),
]
