from django.urls import path
from . import views

urlpatterns = [
    path('catalog/', views.ToolCatalogView.as_view(), name='tool-catalog'),
    path('<slug:slug>/connect/', views.ToolConnectView.as_view(), name='tool-connect'),
    path('<slug:slug>/disconnect/', views.ToolDisconnectView.as_view(), name='tool-disconnect'),
    path('<slug:slug>/status/', views.ToolStatusView.as_view(), name='tool-status'),
    path('my/', views.MyToolsView.as_view(), name='my-tools'),
]
