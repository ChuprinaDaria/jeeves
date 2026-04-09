from django.urls import path
from . import views


urlpatterns = [
    path('health/', views.health, name='branches-health'),
    path('list/', views.list_branches, name='branches-list'),
    path('create/', views.create_branch, name='branches-create'),
    path('<int:branch_id>/', views.get_branch, name='branches-get'),
    path('<int:branch_id>/update/', views.update_branch, name='branches-update'),
    path('<int:branch_id>/delete/', views.delete_branch, name='branches-delete'),
]