from django.urls import path

from MASTER.concierge_platform import views_platform, views_setup

urlpatterns = [
    path('platform/bootstrap/', views_platform.BootstrapView.as_view(), name='platform-bootstrap'),
    path('setup/owner/', views_setup.CreateOwnerView.as_view(), name='setup-owner'),
    path('setup/license/', views_setup.SetupLicenseView.as_view(), name='setup-license'),
    path('setup/complete/', views_setup.SetupCompleteView.as_view(), name='setup-complete'),
]
