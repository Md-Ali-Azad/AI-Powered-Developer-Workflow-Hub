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
router.register(r'teams', views.TeamViewSet)
router.register(r'invitations', views.TeamInvitationViewSet)

urlpatterns = [
    # Web Views
    path('', views.home_view, name='home'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('register/', views.register_view, name='register'),
    path('login/', auth_views.LoginView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    path('profile/', views.profile_view, name='profile'),
    
    # Project Views
    path('projects/create/', views.project_create_view, name='project_create'),
    path('projects/<int:project_id>/', views.project_detail_view, name='project_detail'),
    path('projects/<int:project_id>/github-sync/', views.project_github_sync_view, name='project_github_sync'),
    
    # PR Views
    path('projects/<int:project_id>/prs/create/', views.pr_create_view, name='pr_create'),
    path('prs/<int:pr_id>/', views.pr_detail_view, name='pr_detail'),
    
    # Team Views
    path('teams/create/', views.team_create_view, name='team_create'),
    path('teams/<int:team_id>/', views.team_detail_view, name='team_detail'),
    path('teams/<int:team_id>/invite/', views.team_invite_view, name='team_invite'),
    
    # Invitation Views
    path('invitations/', views.invitation_list_view, name='invitation_list'),
    path('invitations/<uuid:token>/accept/', views.invitation_accept_view, name='invitation_accept'),
    path('invitations/<uuid:token>/decline/', views.invitation_decline_view, name='invitation_decline'),
    
    # Token-based API endpoints for invitations
    path('api/invitations/token/<uuid:token>/', views.invitation_by_token, name='invitation_by_token'),
    path('api/invitations/token/<uuid:token>/accept/', views.invitation_accept_api, name='invitation_accept_api'),
    path('api/invitations/token/<uuid:token>/decline/', views.invitation_decline_api, name='invitation_decline_api'),
    
    # API
    path('api/', include(router.urls)),
    
    # AI Endpoints
    path('ai/pr_summary/', views.pr_summary, name='pr_summary'),
    path('ai/build_explain/', views.build_explain, name='build_explain'),
    path('ai/changelog/', views.changelog_generate, name='changelog_generate'),
    path('ai/task_suggest/', views.task_suggest, name='task_suggest'),
    
    # Comment Endpoints
    path('api/comments/', views.add_comment, name='add_comment'),
    
    # GitHub Integration Endpoints
    path('api/github/validate-repo/', views.github_validate_repo, name='github_validate_repo'),
    path('api/github/fetch-pr/', views.github_fetch_pr, name='github_fetch_pr'),
    path('api/github/import-pr/', views.github_import_pr, name='github_import_pr'),
]