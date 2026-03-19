from django.urls import path
from . import views

urlpatterns = [
    path('config/', views.AgentConfigView.as_view(), name='agent-config'),
    path('logs/', views.AgentLogListView.as_view(), name='agent-logs'),
    path('sessions/', views.AgentSessionListView.as_view(), name='agent-sessions'),
]
