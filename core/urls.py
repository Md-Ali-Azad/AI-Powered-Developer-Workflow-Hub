from django.urls import path, include
from django.contrib.auth import views as auth_views
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'projects', views.ProjectViewSet)
router.register(r'tasks', views.TaskViewSet)
router.register(r'prs', views.PullRequestViewSet)
router.register(r'builds', views.BuildLogViewSet)
router.register(r'changelog', views.ChangelogEntryViewSet)
router.register(r'notifications', views.NotificationViewSet)

urlpatterns = [
    # Web Views
    path('', views.dashboard_view, name='dashboard'),
    path('register/', views.register_view, name='register'),
    path('login/', auth_views.LoginView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    path('profile/', views.profile_view, name='profile'),
    
    # Project Views
    path('projects/create/', views.project_create_view, name='project_create'),
    path('projects/<int:project_id>/', views.project_detail_view, name='project_detail'),
    
    # PR Views
    path('projects/<int:project_id>/prs/create/', views.pr_create_view, name='pr_create'),
    path('prs/<int:pr_id>/', views.pr_detail_view, name='pr_detail'),
    
    # Team Views
    path('teams/create/', views.team_create_view, name='team_create'),
    
    # API
    path('api/', include(router.urls)),
    
    # AI Endpoints
    path('ai/pr_summary/', views.pr_summary, name='pr_summary'),
    path('ai/build_explain/', views.build_explain, name='build_explain'),
    path('ai/changelog/', views.changelog_generate, name='changelog_generate'),
    path('ai/task_suggest/', views.task_suggest, name='task_suggest'),
    
    # Comment Endpoints
    path('api/comments/', views.add_comment, name='add_comment'),
]