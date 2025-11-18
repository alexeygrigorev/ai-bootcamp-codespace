from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('tasks/new/', views.task_create, name='task_create'),
    path('tasks/<int:pk>/edit/', views.task_edit, name='task_edit'),
    path('tasks/<int:pk>/delete/', views.task_delete, name='task_delete'),
    path('tasks/<int:pk>/toggle-complete/', views.task_toggle_complete, name='task_toggle_complete'),
    path('tasks/<int:pk>/', views.task_detail, name='task_detail'),
    path('tasks/<int:pk>/comments/add/', views.task_comment_add, name='task_comment_add'),

    path('teams/', views.team_list, name='teams'),
    path('teams/new/', views.team_create, name='team_create'),
    path('teams/<int:team_id>/', views.team_manage, name='team_manage'),
    path('teams/<int:team_id>/members/add/', views.team_member_add, name='team_member_add'),
    path('teams/<int:team_id>/members/<int:user_id>/remove/', views.team_member_remove, name='team_member_remove'),

    path('accounts/signup/', views.signup, name='signup'),
]
