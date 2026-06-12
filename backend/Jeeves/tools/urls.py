from django.urls import path
from . import views
from . import bridge_views

urlpatterns = [
    path('matrix/bridges/<str:network>/login/start/',
         bridge_views.BridgeLoginStartView.as_view(), name='matrix-bridge-login-start'),
    path('matrix/bridges/<str:network>/login/status/',
         bridge_views.BridgeLoginStatusView.as_view(), name='matrix-bridge-login-status'),
    path('matrix/bridges/<str:network>/login/cookies/',
         bridge_views.BridgeLoginCookiesView.as_view(), name='matrix-bridge-login-cookies'),
    path('matrix/bridges/<str:network>/state/',
         bridge_views.BridgeStateView.as_view(), name='matrix-bridge-state'),

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

    path('flow/activity/', views.FlowActivityView.as_view(), name='flow-activity'),
    path('flow/channels/', views.FlowChannelsView.as_view(), name='flow-channels'),

    path('skills/', views.SkillsView.as_view(), name='skills-list'),
    path('skills/<slug:slug>/<str:action>/', views.SkillActionView.as_view(), name='skill-action'),

    path('word-cloud/', views.WordCloudView.as_view(), name='tool-word-cloud'),
]
