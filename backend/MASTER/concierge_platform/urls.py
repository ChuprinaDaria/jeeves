from django.urls import path

from MASTER.concierge_platform import views_platform, views_setup

urlpatterns = [
    path('platform/bootstrap/', views_platform.BootstrapView.as_view(), name='platform-bootstrap'),
    path('setup/owner/', views_setup.CreateOwnerView.as_view(), name='setup-owner'),
]
