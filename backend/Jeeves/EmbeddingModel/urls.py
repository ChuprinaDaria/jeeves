from django.urls import path
from . import views


urlpatterns = [
    path('health/', views.health, name='embeddingmodel-health'),
    path('models/', views.get_models, name='embeddingmodel-list'),
    path('select/', views.select_model, name='embeddingmodel-select'),
    path('reindex/', views.reindex_client_documents, name='embeddingmodel-reindex-client'),
]

