from django.urls import path
from . import views

urlpatterns = [
    path('chat/', views.ChatSSEView.as_view(), name='mcp-chat-sse'),
]
