from django.urls import path
from MASTER.clients import views_bridge

urlpatterns = [
    path('', views_bridge.BridgeListView.as_view(), name='bridge-list'),
    path('message/', views_bridge.BridgeMessageView.as_view(), name='bridge-message'),
    path('<str:bridge_type>/status/', views_bridge.BridgeStatusView.as_view(), name='bridge-status'),
    path('<str:bridge_type>/login/start/', views_bridge.BridgeLoginStartView.as_view(), name='bridge-login-start'),
    path('<str:bridge_type>/login/cookies/', views_bridge.BridgeLoginCookiesView.as_view(), name='bridge-login-cookies'),
    path('<str:bridge_type>/login/status/', views_bridge.BridgeStatusView.as_view(), name='bridge-login-status'),
    path('<str:bridge_type>/logout/', views_bridge.BridgeLogoutView.as_view(), name='bridge-logout'),
]
