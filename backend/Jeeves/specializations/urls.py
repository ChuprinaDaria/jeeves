from django.urls import path
from . import views


urlpatterns = [
    path('health/', views.health, name='specializations-health'),
    path('list/', views.list_specializations, name='specializations-list'),
    path('create/', views.create_specialization, name='specializations-create'),
    path('<int:spec_id>/', views.get_specialization, name='specializations-get'),
    path('<int:spec_id>/update/', views.update_specialization, name='specializations-update'),
    path('<int:spec_id>/delete/', views.delete_specialization, name='specializations-delete'),
]