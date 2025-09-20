from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Q
from django.http import JsonResponse
from django.core.exceptions import PermissionDenied
from functools import wraps
from .forms import CustomUserCreationForm, TeamInviteForm
from rest_framework import viewsets, status
from rest_framework.decorators import api_view, action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import (Project, Task, PullRequest, BuildLog, ChangelogEntry, 
                    Notification, Team, Membership, User, Comment, TeamInvitation)
from .serializers import (ProjectSerializer, TaskSerializer, PullRequestSerializer, 
                         BuildLogSerializer, ChangelogEntrySerializer, NotificationSerializer,
                         TeamSerializer, TeamInvitationSerializer, MembershipSerializer)
from . import hooks
from .services import InvitationService, TeamPermissions, require_team_permission, require_team_membership
import google.generativeai as genai
import os

# Configure Gemini API
from django.conf import settings
genai.configure(api_key=settings.GEMINI_API_KEY)

# Home and Landing Views
def home_view(request):
    """
    Landing page for non-authenticated users.
    Redirects authenticated users to dashboard.
    """
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    return render(request, 'home.html')

# Authorization decorators for team-specific operations
def require_project_access(view_func):
    """
    Decorator to ensure user has access to project through team membership.
    """
    @wraps(view_func)
    def wrapper(request, project_id, *args, **kwargs):
        project = get_object_or_404(Project, id=project_id)
        
        # Check if user has access to this project through team membership
        if not TeamPermissions.is_team_member(request.user, project.team):
            messages.error(request, 'You do not have access to this project.')
            return redirect('dashboard')
        
        # Add project to kwargs for convenience
        kwargs['project'] = project
        return view_func(request, project_id, *args, **kwargs)
    return wrapper

def require_pr_access(view_func):
    """
    Decorator to ensure user has access to pull request through team membership.
    """
    @wraps(view_func)
    def wrapper(request, pr_id, *args, **kwargs):
        pr = get_object_or_404(PullRequest, id=pr_id)
        
        # Check if user has access to this PR through team membership
        if not TeamPermissions.is_team_member(request.user, pr.project.team):
            messages.error(request, 'You do not have access to this pull request.')
            return redirect('dashboard')
        
        # Add pr to kwargs for convenience
        kwargs['pr'] = pr
        return view_func(request, pr_id, *args, **kwargs)
    return wrapper

def require_project_management_permission(view_func):
    """
    Decorator to ensure user can manage projects in the team.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        # For project creation, check if user has teams they can manage
        user_teams = TeamPermissions.filter_user_teams(request.user)
        manageable_teams = [
            team_info for team_info in user_teams 
            if TeamPermissions.has_permission(request.user, team_info['team'], 'manage_projects')
        ]
        
        if not manageable_teams:
            messages.error(request, 'You do not have permission to create projects. You need to be an admin of at least one team.')
            return redirect('dashboard')
        
        # Add manageable teams to kwargs
        kwargs['manageable_teams'] = manageable_teams
        return view_func(request, *args, **kwargs)
    return wrapper

class ProjectViewSet(viewsets.ModelViewSet):
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        # Filter projects by user's team memberships using TeamPermissions
        user_teams_info = TeamPermissions.filter_user_teams(self.request.user)
        user_team_ids = [team_info['team'].id for team_info in user_teams_info]
        return Project.objects.filter(team__id__in=user_team_ids).select_related('team')
    
    def perform_create(self, serializer):
        # Ensure user can create projects in the specified team
        team = serializer.validated_data.get('team')
        if team and not TeamPermissions.can_manage_projects(self.request.user, team):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("You do not have permission to create projects in this team.")
        serializer.save()
    
    def perform_update(self, serializer):
        # Ensure user can manage the project
        project = self.get_object()
        if not TeamPermissions.can_manage_projects(self.request.user, project.team):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("You do not have permission to modify this project.")
        serializer.save()
    
    def perform_destroy(self, instance):
        # Ensure user can manage the project
        if not TeamPermissions.can_manage_projects(self.request.user, instance.team):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("You do not have permission to delete this project.")
        instance.delete()

class TaskViewSet(viewsets.ModelViewSet):
    queryset = Task.objects.all()
    serializer_class = TaskSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        # Filter tasks by user's project access using TeamPermissions
        user_teams_info = TeamPermissions.filter_user_teams(self.request.user)
        user_team_ids = [team_info['team'].id for team_info in user_teams_info]
        return Task.objects.filter(project__team__id__in=user_team_ids).select_related('project', 'project__team')
    
    def perform_create(self, serializer):
        # Ensure user can create tasks in the project's team
        project = serializer.validated_data.get('project')
        if project and not TeamPermissions.can_create_tasks(self.request.user, project.team):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("You do not have permission to create tasks in this project.")
        serializer.save()
    
    def perform_update(self, serializer):
        # Check if user can manage tasks or if it's their own task
        task = self.get_object()
        can_manage = TeamPermissions.can_create_tasks(self.request.user, task.project.team)
        is_assignee = task.assignee == self.request.user
        
        if not (can_manage or is_assignee):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("You do not have permission to modify this task.")
        serializer.save()

class PullRequestViewSet(viewsets.ModelViewSet):
    queryset = PullRequest.objects.all()
    serializer_class = PullRequestSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        # Filter PRs by user's team access using TeamPermissions
        user_teams_info = TeamPermissions.filter_user_teams(self.request.user)
        user_team_ids = [team_info['team'].id for team_info in user_teams_info]
        return PullRequest.objects.filter(project__team__id__in=user_team_ids).select_related('project', 'project__team')
    
    def perform_create(self, serializer):
        # Ensure user has access to the project
        project = serializer.validated_data.get('project')
        if project and not TeamPermissions.is_team_member(self.request.user, project.team):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("You do not have access to create pull requests in this project.")
        serializer.save()

class BuildLogViewSet(viewsets.ModelViewSet):
    queryset = BuildLog.objects.all()
    serializer_class = BuildLogSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        # Filter build logs by user's team access using TeamPermissions
        user_teams_info = TeamPermissions.filter_user_teams(self.request.user)
        user_team_ids = [team_info['team'].id for team_info in user_teams_info]
        return BuildLog.objects.filter(project__team__id__in=user_team_ids).select_related('project', 'project__team')

class ChangelogEntryViewSet(viewsets.ModelViewSet):
    queryset = ChangelogEntry.objects.all()
    serializer_class = ChangelogEntrySerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        # Filter changelog entries by user's team access using TeamPermissions
        user_teams_info = TeamPermissions.filter_user_teams(self.request.user)
        user_team_ids = [team_info['team'].id for team_info in user_teams_info]
        return ChangelogEntry.objects.filter(project__team__id__in=user_team_ids).select_related('project', 'project__team')

class NotificationViewSet(viewsets.ModelViewSet):
    queryset = Notification.objects.all()
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)
    
    @action(detail=True, methods=['patch'])
    def mark_read(self, request, pk=None):
        notification = self.get_object()
        from django.utils import timezone
        notification.read_at = timezone.now()
        notification.save()
        return Response({'status': 'marked as read'})
    
    @action(detail=False, methods=['patch'])
    def mark_all_read(self, request):
        """Mark all notifications as read for the current user."""
        from .services import NotificationService
        count = NotificationService.mark_all_notifications_read(request.user)
        return Response({'status': f'{count} notifications marked as read'})

class TeamViewSet(viewsets.ModelViewSet):
    queryset = Team.objects.all()
    serializer_class = TeamSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        # Return teams where user is a member using TeamPermissions
        user_teams_info = TeamPermissions.filter_user_teams(self.request.user)
        user_team_ids = [team_info['team'].id for team_info in user_teams_info]
        return Team.objects.filter(id__in=user_team_ids).select_related('owner')
    
    def perform_create(self, serializer):
        # Set the current user as the owner
        team = serializer.save(owner=self.request.user)
        # Create admin membership for the owner
        Membership.objects.create(
            user=self.request.user,
            team=team,
            role='Admin'
        )
    
    @action(detail=True, methods=['get'])
    def members(self, request, pk=None):
        """Get team members"""
        team = self.get_object()
        memberships = team.membership_set.all()
        serializer = MembershipSerializer(memberships, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def invite(self, request, pk=None):
        """Send team invitation"""
        team = self.get_object()
        
        # Check permissions
        if not TeamPermissions.can_invite_members(request.user, team):
            return Response(
                {'error': 'You do not have permission to invite members to this team'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        email = request.data.get('email')
        role = request.data.get('role', 'Developer')
        
        if not email:
            return Response({'error': 'Email is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            invitation = InvitationService.send_invitation(team, request.user, email, role)
            serializer = TeamInvitationSerializer(invitation)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

class TeamInvitationViewSet(viewsets.ModelViewSet):
    queryset = TeamInvitation.objects.all()
    serializer_class = TeamInvitationSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        # Return invitations for the current user or sent by the current user
        return TeamInvitation.objects.filter(
            Q(invited_user=self.request.user) | 
            Q(email=self.request.user.email) |
            Q(invited_by=self.request.user)
        )
    
    @action(detail=True, methods=['post'])
    def accept(self, request, pk=None):
        """Accept team invitation"""
        invitation = self.get_object()
        
        # Verify the invitation belongs to the current user
        if invitation.invited_user != request.user and invitation.email != request.user.email:
            return Response(
                {'error': 'You can only accept your own invitations'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            membership = InvitationService.accept_invitation(invitation, request.user)
            return Response({
                'status': 'accepted',
                'team': invitation.team.name,
                'role': membership.role
            })
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def decline(self, request, pk=None):
        """Decline team invitation"""
        invitation = self.get_object()
        
        # Verify the invitation belongs to the current user
        if invitation.invited_user != request.user and invitation.email != request.user.email:
            return Response(
                {'error': 'You can only decline your own invitations'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            InvitationService.decline_invitation(invitation)
            return Response({'status': 'declined'})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def pending(self, request):
        """Get pending invitations for current user"""
        pending_invitations = InvitationService.get_pending_invitations(request.user)
        serializer = TeamInvitationSerializer(pending_invitations, many=True)
        return Response(serializer.data)

# AI Helper Views
@api_view(['POST'])
def pr_summary(request):
    """Generate AI summary for Pull Request"""
    try:
        pr_data = request.data
        pr_id = pr_data.get('pr_id')
        
        # If PR ID is provided, verify user has access
        if pr_id:
            try:
                pr = PullRequest.objects.get(id=pr_id)
                if not TeamPermissions.is_team_member(request.user, pr.project.team):
                    return Response(
                        {'error': 'You do not have access to this pull request'}, 
                        status=status.HTTP_403_FORBIDDEN
                    )
            except PullRequest.DoesNotExist:
                return Response({'error': 'Pull request not found'}, status=status.HTTP_404_NOT_FOUND)
        
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        
        prompt = f"""
        Analyze this Pull Request and provide a concise summary:
        
        Title: {pr_data.get('title', '')}
        Description: {pr_data.get('description', '')}
        Files Changed: {pr_data.get('files_changed', [])}
        
        Provide:
        1. Brief summary of changes
        2. Potential impact
        3. Recommendations for review
        """
        
        response = model.generate_content(prompt)
        return Response({'summary': response.text})
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
def build_explain(request):
    """Explain build logs using AI"""
    try:
        build_log = request.data.get('build_log', '')
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        
        prompt = f"""
        Analyze this build log and explain what went wrong:
        
        {build_log}
        
        Provide:
        1. Root cause of the failure
        2. Suggested fixes
        3. Prevention strategies
        """
        
        response = model.generate_content(prompt)
        return Response({'explanation': response.text})
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
def changelog_generate(request):
    """Generate changelog using AI"""
    try:
        commits = request.data.get('commits', [])
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        
        commit_messages = '\n'.join([f"- {commit.get('message', '')}" for commit in commits])
        
        prompt = f"""
        Generate a professional changelog from these commit messages:
        
        {commit_messages}
        
        Format as:
        ## [Version] - Date
        ### Added
        ### Changed
        ### Fixed
        ### Removed
        """
        
        response = model.generate_content(prompt)
        return Response({'changelog': response.text})
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
def task_suggest(request):
    """Suggest tasks based on project context"""
    try:
        project_data = request.data
        project_id = project_data.get('project_id')
        
        # If project ID is provided, verify user has access
        if project_id:
            try:
                project = Project.objects.get(id=project_id)
                if not TeamPermissions.is_team_member(request.user, project.team):
                    return Response(
                        {'error': 'You do not have access to this project'}, 
                        status=status.HTTP_403_FORBIDDEN
                    )
            except Project.DoesNotExist:
                return Response({'error': 'Project not found'}, status=status.HTTP_404_NOT_FOUND)
        
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        
        prompt = f"""
        Based on this project information, suggest relevant tasks:
        
        Project: {project_data.get('name', '')}
        Description: {project_data.get('description', '')}
        Current Tasks: {project_data.get('current_tasks', [])}
        Recent Activity: {project_data.get('recent_activity', [])}
        
        Suggest 5 actionable tasks that would benefit this project.
        """
        
        response = model.generate_content(prompt)
        return Response({'suggestions': response.text})
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
def add_comment(request):
    """Add a comment to a PR or other object"""
    try:
        from django.contrib.contenttypes.models import ContentType
        
        content_type_name = request.data.get('content_type')
        object_id = request.data.get('object_id')
        body = request.data.get('body')
        
        if not all([content_type_name, object_id, body]):
            return Response({'error': 'Missing required fields'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Get the content type and verify access
        if content_type_name.lower() == 'pullrequest':
            content_type = ContentType.objects.get_for_model(PullRequest)
            
            # Check if user has access to this PR through team membership
            try:
                pr = PullRequest.objects.get(id=object_id)
                if not TeamPermissions.is_team_member(request.user, pr.project.team):
                    return Response(
                        {'error': 'You do not have access to comment on this pull request'}, 
                        status=status.HTTP_403_FORBIDDEN
                    )
            except PullRequest.DoesNotExist:
                return Response({'error': 'Pull request not found'}, status=status.HTTP_404_NOT_FOUND)
        else:
            return Response({'error': 'Invalid content type'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Create the comment
        comment = Comment.objects.create(
            content_type=content_type,
            object_id=object_id,
            author=request.user,
            body=body
        )
        
        return Response({
            'id': comment.id,
            'author': comment.author.username,
            'body': comment.body,
            'created_at': comment.created_at.isoformat()
        })
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# Web Views
def register_view(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Account created successfully!')
            return redirect('dashboard')
    else:
        form = CustomUserCreationForm()
    return render(request, 'registration/register.html', {'form': form})

@login_required
def dashboard_view(request):
    # Get user's teams with permissions
    user_teams_info = TeamPermissions.filter_user_teams(request.user)
    user_team_ids = [team_info['team'].id for team_info in user_teams_info]
    
    # Filter projects based on user's team memberships
    projects = Project.objects.filter(team__id__in=user_team_ids).select_related('team')
    
    # Recent PRs from accessible projects
    recent_prs = PullRequest.objects.filter(
        project__team__id__in=user_team_ids
    ).select_related('project', 'project__team').order_by('-created_at')[:5]
    
    # Stats based on accessible projects
    stats = {
        'total_projects': projects.count(),
        'total_teams': len(user_teams_info),
        'total_prs': PullRequest.objects.filter(project__team__id__in=user_team_ids).count(),
        'open_prs': PullRequest.objects.filter(project__team__id__in=user_team_ids, status='open').count(),
        'merged_prs': PullRequest.objects.filter(project__team__id__in=user_team_ids, status='merged').count(),
    }
    
    # User's teams with their roles and permissions
    user_teams = []
    for team_info in user_teams_info:
        team_data = {
            'team': team_info['team'],
            'role': team_info['role'],
            'is_owner': team_info['is_owner'],
            'can_invite': TeamPermissions.can_invite_members(request.user, team_info['team']),
            'can_manage_projects': TeamPermissions.can_manage_projects(request.user, team_info['team']),
        }
        user_teams.append(team_data)
    
    # Recent activity (mock data for now)
    recent_activity = []
    if recent_prs:
        recent_activity.append({
            'icon': 'code-branch', 
            'message': f'New PR created in {recent_prs[0].project.name}', 
            'created_at': recent_prs[0].created_at
        })
    
    return render(request, 'dashboard.html', {
        'projects': projects,
        'recent_prs': recent_prs,
        'stats': stats,
        'recent_activity': recent_activity,
        'user_teams': user_teams,
    })

@login_required
@require_project_management_permission
def project_create_view(request, manageable_teams=None):
    if request.method == 'POST':
        team_id = request.POST.get('team')
        
        if team_id:
            # User selected a specific team
            team = get_object_or_404(Team, id=team_id)
            
            # Verify user can manage projects in this team
            if not TeamPermissions.can_manage_projects(request.user, team):
                messages.error(request, 'You do not have permission to create projects in this team.')
                return redirect('dashboard')
        else:
            # Get or create a team for the user if they don't have one
            team, created = Team.objects.get_or_create(
                owner=request.user,
                defaults={'name': f"{request.user.username}'s Team"}
            )
            
            # Create membership if it doesn't exist
            Membership.objects.get_or_create(
                user=request.user,
                team=team,
                defaults={'role': 'Admin'}
            )
        
        project = Project.objects.create(
            name=request.POST['name'],
            description=request.POST['description'],
            repo_url=request.POST.get('repo_url', ''),
            team=team
        )
        
        messages.success(request, f'Project "{project.name}" created successfully!')
        return redirect('project_detail', project.id)
    
    # Get teams where user can manage projects (provided by decorator)
    teams_with_permissions = [
        team_info['team'] for team_info in manageable_teams
    ]
    
    return render(request, 'project_create.html', {
        'teams': teams_with_permissions,
        'manageable_teams': manageable_teams
    })

@login_required
@require_project_access
def project_detail_view(request, project_id, project=None):
    # project is provided by the decorator
    pull_requests = PullRequest.objects.filter(project=project).order_by('-created_at')
    changelog_entries = ChangelogEntry.objects.filter(project=project).order_by('-created_at')[:10]
    team_members = Membership.objects.filter(team=project.team)
    
    # Project stats
    stats = {
        'total_prs': pull_requests.count(),
        'open_prs': pull_requests.filter(status='open').count(),
        'merged_prs': pull_requests.filter(status='merged').count(),
        'risky_prs': pull_requests.filter(risk_flags__isnull=False).count(),
    }
    
    # User permissions for this project
    user_permissions = {
        'can_manage_project': TeamPermissions.can_manage_projects(request.user, project.team),
        'can_create_tasks': TeamPermissions.can_create_tasks(request.user, project.team),
        'user_role': TeamPermissions.get_user_role(request.user, project.team),
        'is_team_owner': project.team.owner == request.user,
    }
    
    return render(request, 'project_detail.html', {
        'project': project,
        'pull_requests': pull_requests,
        'changelog_entries': changelog_entries,
        'team_members': team_members,
        'stats': stats,
        'user_permissions': user_permissions,
    })

@login_required
@require_project_access
def pr_create_view(request, project_id, project=None):
    # project is provided by the decorator
    
    if request.method == 'POST':
        pr = PullRequest.objects.create(
            project=project,
            number=request.POST['number'],
            title=request.POST['title'],
            description=request.POST['description'],
            author=request.POST['author'],
            diff_url=request.POST['diff_url'],
            status='open'
        )
        
        # Trigger AI summary generation if requested
        if request.POST.get('generate_ai_summary'):
            hooks.handle_new_pr(
                project_id=project.id,
                pr_number=pr.number,
                diff_url=pr.diff_url,
                title=pr.title,
                description=pr.description,
                author=pr.author
            )
        
        messages.success(request, f'Pull Request #{pr.number} created successfully!')
        return redirect('pr_detail', pr.id)
    
    return render(request, 'pr_create.html', {'project': project})

@login_required
@require_pr_access
def pr_detail_view(request, pr_id, pr=None):
    # pr is provided by the decorator
    
    # Get related PRs (same project, recent)
    related_prs = PullRequest.objects.filter(
        project=pr.project
    ).exclude(id=pr.id).order_by('-created_at')[:5]
    
    # Get comments for this PR
    from django.contrib.contenttypes.models import ContentType
    from .models import Comment
    pr_content_type = ContentType.objects.get_for_model(PullRequest)
    comments = Comment.objects.filter(
        content_type=pr_content_type,
        object_id=pr.id
    ).order_by('created_at')
    
    # User permissions for this PR
    user_permissions = {
        'can_manage_project': TeamPermissions.can_manage_projects(request.user, pr.project.team),
        'user_role': TeamPermissions.get_user_role(request.user, pr.project.team),
        'is_team_owner': pr.project.team.owner == request.user,
    }
    
    return render(request, 'pr_detail.html', {
        'pr': pr,
        'related_prs': related_prs,
        'comments': comments,
        'user_permissions': user_permissions,
    })

@login_required
def team_create_view(request):
    if request.method == 'POST':
        team = Team.objects.create(
            name=request.POST['name'],
            owner=request.user
        )
        
        # Create membership for the owner
        Membership.objects.create(
            user=request.user,
            team=team,
            role='Admin'
        )
        
        messages.success(request, f'Team "{team.name}" created successfully!')
        return redirect('dashboard')
    
    return render(request, 'team_create.html')

@login_required
def profile_view(request):
    if request.method == 'POST':
        user = request.user
        user.first_name = request.POST.get('first_name', '')
        user.last_name = request.POST.get('last_name', '')
        user.email = request.POST.get('email', '')
        user.username = request.POST.get('username', '')
        user.save()
        
        messages.success(request, 'Profile updated successfully!')
        return redirect('profile')
    
    # User stats
    user_teams = request.user.membership_set.values_list('team', flat=True)
    user_stats = {
        'projects_count': Project.objects.filter(team__in=user_teams).count(),
        'prs_count': PullRequest.objects.filter(author=request.user.username).count(),
        'teams_count': request.user.membership_set.count(),
        'notifications_count': Notification.objects.filter(user=request.user, read_at__isnull=True).count(),
    }
    
    return render(request, 'profile.html', {'user_stats': user_stats})


# Team Invitation Views

@login_required
@require_team_permission('invite_members')
def team_invite_view(request, team_id, team=None):
    """View for sending team invitations."""
    # team is provided by the decorator
    
    if request.method == 'POST':
        form = TeamInviteForm(request.POST, team=team)
        if form.is_valid():
            try:
                invitation = InvitationService.send_invitation(
                    team=team,
                    inviter=request.user,
                    email=form.cleaned_data['email'],
                    role=form.cleaned_data['role']
                )
                
                messages.success(
                    request, 
                    f"Invitation sent to {form.cleaned_data['email']} successfully!"
                )
                return redirect('team_detail', team_id=team.id)
                
            except (ValueError, PermissionError) as e:
                messages.error(request, str(e))
            except Exception as e:
                messages.error(request, "An error occurred while sending the invitation. Please try again.")
    else:
        form = TeamInviteForm(team=team)
    
    # Get existing invitations for this team
    sent_invitations = InvitationService.get_sent_invitations(request.user, team)
    
    return render(request, 'team_invite.html', {
        'form': form,
        'team': team,
        'sent_invitations': sent_invitations
    })


@login_required
def invitation_accept_view(request, token):
    """View for accepting team invitations."""
    try:
        invitation = get_object_or_404(TeamInvitation, token=token, status='pending')
        
        # Check if invitation is expired
        if invitation.is_expired():
            invitation.status = 'expired'
            invitation.save()
            error_msg = "This invitation has expired."
            if request.headers.get('Content-Type') == 'application/json':
                return JsonResponse({'error': error_msg}, status=400)
            messages.error(request, error_msg)
            return redirect('dashboard')
        
        # Check if the current user's email matches the invitation
        if invitation.email != request.user.email:
            error_msg = "This invitation is not for your email address."
            if request.headers.get('Content-Type') == 'application/json':
                return JsonResponse({'error': error_msg}, status=403)
            messages.error(request, error_msg)
            return redirect('dashboard')
        
        if request.method == 'POST':
            try:
                membership = InvitationService.accept_invitation(token, request.user)
                success_msg = f"You have successfully joined the team '{invitation.team.name}' as a {membership.role}!"
                
                # Handle AJAX requests
                if request.headers.get('Content-Type') == 'application/json':
                    return JsonResponse({
                        'success': True,
                        'message': success_msg,
                        'team_id': invitation.team.id,
                        'team_name': invitation.team.name,
                        'role': membership.role
                    })
                
                messages.success(request, success_msg)
                return redirect('team_detail', team_id=invitation.team.id)
                
            except ValueError as e:
                error_msg = str(e)
                if request.headers.get('Content-Type') == 'application/json':
                    return JsonResponse({'error': error_msg}, status=400)
                messages.error(request, error_msg)
                return redirect('dashboard')
            except Exception as e:
                error_msg = "An error occurred while accepting the invitation. Please try again."
                if request.headers.get('Content-Type') == 'application/json':
                    return JsonResponse({'error': error_msg}, status=500)
                messages.error(request, error_msg)
                return redirect('dashboard')
        
        return render(request, 'invitation_accept.html', {
            'invitation': invitation
        })
        
    except TeamInvitation.DoesNotExist:
        error_msg = "Invalid or expired invitation."
        if request.headers.get('Content-Type') == 'application/json':
            return JsonResponse({'error': error_msg}, status=404)
        messages.error(request, error_msg)
        return redirect('dashboard')


@login_required  
def invitation_decline_view(request, token):
    """View for declining team invitations."""
    try:
        invitation = get_object_or_404(TeamInvitation, token=token, status='pending')
        
        # Check if invitation is expired
        if invitation.is_expired():
            invitation.status = 'expired'
            invitation.save()
            error_msg = "This invitation has expired."
            if request.headers.get('Content-Type') == 'application/json':
                return JsonResponse({'error': error_msg}, status=400)
            messages.error(request, error_msg)
            return redirect('dashboard')
        
        # Check if the current user's email matches the invitation
        if invitation.email != request.user.email:
            error_msg = "This invitation is not for your email address."
            if request.headers.get('Content-Type') == 'application/json':
                return JsonResponse({'error': error_msg}, status=403)
            messages.error(request, error_msg)
            return redirect('dashboard')
        
        if request.method == 'POST':
            try:
                InvitationService.decline_invitation(token, request.user)
                success_msg = f"You have declined the invitation to join '{invitation.team.name}'."
                
                # Handle AJAX requests
                if request.headers.get('Content-Type') == 'application/json':
                    return JsonResponse({
                        'success': True,
                        'message': success_msg,
                        'team_name': invitation.team.name
                    })
                
                messages.info(request, success_msg)
                return redirect('dashboard')
                
            except ValueError as e:
                error_msg = str(e)
                if request.headers.get('Content-Type') == 'application/json':
                    return JsonResponse({'error': error_msg}, status=400)
                messages.error(request, error_msg)
                return redirect('dashboard')
            except Exception as e:
                error_msg = "An error occurred while declining the invitation. Please try again."
                if request.headers.get('Content-Type') == 'application/json':
                    return JsonResponse({'error': error_msg}, status=500)
                messages.error(request, error_msg)
                return redirect('dashboard')
        
        return render(request, 'invitation_decline.html', {
            'invitation': invitation
        })
        
    except TeamInvitation.DoesNotExist:
        messages.error(request, "Invalid or expired invitation.")
        return redirect('dashboard')


@login_required
def invitation_list_view(request):
    """View for listing user's pending invitations."""
    pending_invitations = InvitationService.get_pending_invitations(request.user)
    sent_invitations = InvitationService.get_sent_invitations(request.user)
    
    return render(request, 'invitation_list.html', {
        'pending_invitations': pending_invitations,
        'sent_invitations': sent_invitations
    })

# Token-based API endpoints for invitations
@api_view(['GET'])
def invitation_by_token(request, token):
    """Get invitation details by token (for public access)"""
    try:
        invitation = get_object_or_404(TeamInvitation, token=token)
        
        # Check if invitation is expired
        if invitation.is_expired():
            invitation.status = 'expired'
            invitation.save()
            return Response({'error': 'This invitation has expired'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Return limited invitation details (no sensitive info)
        return Response({
            'team_name': invitation.team.name,
            'invited_by': invitation.invited_by.username,
            'role': invitation.role,
            'email': invitation.email,
            'status': invitation.status,
            'expires_at': invitation.expires_at
        })
        
    except TeamInvitation.DoesNotExist:
        return Response({'error': 'Invalid invitation token'}, status=status.HTTP_404_NOT_FOUND)

@api_view(['POST'])
def invitation_accept_api(request, token):
    """Accept invitation via API (requires authentication)"""
    if not request.user.is_authenticated:
        return Response({'error': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)
    
    try:
        invitation = get_object_or_404(TeamInvitation, token=token, status='pending')
        
        # Check if invitation is expired
        if invitation.is_expired():
            invitation.status = 'expired'
            invitation.save()
            return Response({'error': 'This invitation has expired'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if the current user's email matches the invitation
        if invitation.email != request.user.email:
            return Response(
                {'error': 'This invitation is not for your email address'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        membership = InvitationService.accept_invitation(invitation, request.user)
        return Response({
            'success': True,
            'message': f"You have joined '{invitation.team.name}' as {membership.role}",
            'team_name': invitation.team.name,
            'role': membership.role
        })
        
    except ValueError as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response(
            {'error': 'An error occurred while accepting the invitation'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST'])
def invitation_decline_api(request, token):
    """Decline invitation via API (requires authentication)"""
    if not request.user.is_authenticated:
        return Response({'error': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)
    
    try:
        invitation = get_object_or_404(TeamInvitation, token=token, status='pending')
        
        # Check if invitation is expired
        if invitation.is_expired():
            invitation.status = 'expired'
            invitation.save()
            return Response({'error': 'This invitation has expired'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if the current user's email matches the invitation
        if invitation.email != request.user.email:
            return Response(
                {'error': 'This invitation is not for your email address'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        InvitationService.decline_invitation(invitation)
        return Response({
            'success': True,
            'message': f"You have declined the invitation to join '{invitation.team.name}'",
            'team_name': invitation.team.name
        })
        
    except ValueError as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response(
            {'error': 'An error occurred while declining the invitation'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@login_required
@require_team_membership
def team_detail_view(request, team_id, team=None):
    """View for team dashboard with members, projects, and activities."""
    # team is provided by the decorator
    
    # Get team members
    team_members = Membership.objects.filter(team=team).select_related('user')
    
    # Get team projects (filtered by user permissions)
    team_projects = TeamPermissions.filter_team_projects(request.user, team).order_by('-created_at')
    
    # Get recent pull requests from accessible team projects
    recent_prs = PullRequest.objects.filter(
        project__in=team_projects
    ).order_by('-created_at')[:10]
    
    # Get team invitations (only for users who can invite)
    team_invitations = []
    if TeamPermissions.can_invite_members(request.user, team):
        team_invitations = TeamInvitation.objects.filter(
            team=team
        ).select_related('invited_user', 'invited_by').order_by('-created_at')[:10]
    
    # Team stats
    stats = {
        'total_members': team_members.count(),
        'total_projects': team_projects.count(),
        'total_prs': PullRequest.objects.filter(project__in=team_projects).count(),
        'open_prs': PullRequest.objects.filter(project__in=team_projects, status='open').count(),
        'pending_invitations': len(team_invitations),
    }
    
    # User permissions for this team
    user_permissions = {
        'can_invite_members': TeamPermissions.can_invite_members(request.user, team),
        'can_manage_members': TeamPermissions.can_manage_members(request.user, team),
        'can_manage_projects': TeamPermissions.can_manage_projects(request.user, team),
        'can_create_tasks': TeamPermissions.can_create_tasks(request.user, team),
        'user_role': TeamPermissions.get_user_role(request.user, team),
        'is_owner': team.owner == request.user,
    }
    
    return render(request, 'team_detail.html', {
        'team': team,
        'team_members': team_members,
        'team_projects': team_projects,
        'recent_prs': recent_prs,
        'team_invitations': team_invitations,
        'stats': stats,
        'user_permissions': user_permissions,
    })