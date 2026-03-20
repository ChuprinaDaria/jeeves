from django.urls import path
from . import views

urlpatterns = [
    path('catalog/', views.ToolCatalogView.as_view(), name='tool-catalog'),
    path('<slug:slug>/connect/', views.ToolConnectView.as_view(), name='tool-connect'),
    path('<slug:slug>/disconnect/', views.ToolDisconnectView.as_view(), name='tool-disconnect'),
    path('<slug:slug>/status/', views.ToolStatusView.as_view(), name='tool-status'),
    path('my/', views.MyToolsView.as_view(), name='my-tools'),

    # Flow canvas API
    path('flow/connections/', views.FlowConnectionsView.as_view(), name='flow-connections'),
    path('flow/connections/<int:pk>/', views.FlowConnectionDetailView.as_view(), name='flow-connection-detail'),

    # Edge middleware
    path('flow/edges/<int:connection_id>/middleware/',
         views.EdgeMiddlewareView.as_view(), name='edge-middleware'),
    path('flow/edges/<int:connection_id>/middleware/<int:pk>/',
         views.EdgeMiddlewareDetailView.as_view(), name='edge-middleware-detail'),
]
