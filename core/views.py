from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Q
from .forms import CustomUserCreationForm, TeamInviteForm
from rest_framework import viewsets, status
from rest_framework.decorators import api_view, action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import (Project, Task, PullRequest, BuildLog, ChangelogEntry, 
                    Notification, Team, Membership, User, Comment, TeamInvitation)
from .serializers import (ProjectSerializer, TaskSerializer, PullRequestSerializer, 
                         BuildLogSerializer, ChangelogEntrySerializer, NotificationSerializer)
from . import hooks
from .services import InvitationService, TeamPermissions
import google.generativeai as genai
import os

# Configure Gemini API
from django.conf import settings
genai.configure(api_key=settings.GEMINI_API_KEY)

class ProjectViewSet(viewsets.ModelViewSet):
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        # Filter projects by user's team memberships
        user_teams = self.request.user.membership_set.values_list('team', flat=True)
        return Project.objects.filter(team__in=user_teams)

class TaskViewSet(viewsets.ModelViewSet):
    queryset = Task.objects.all()
    serializer_class = TaskSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        # Filter tasks by user's project access
        user_teams = self.request.user.membership_set.values_list('team', flat=True)
        return Task.objects.filter(project__team__in=user_teams)

class PullRequestViewSet(viewsets.ModelViewSet):
    queryset = PullRequest.objects.all()
    serializer_class = PullRequestSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        user_teams = self.request.user.membership_set.values_list('team', flat=True)
        return PullRequest.objects.filter(project__team__in=user_teams)

class BuildLogViewSet(viewsets.ModelViewSet):
    queryset = BuildLog.objects.all()
    serializer_class = BuildLogSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        user_teams = self.request.user.membership_set.values_list('team', flat=True)
        return BuildLog.objects.filter(project__team__in=user_teams)

class ChangelogEntryViewSet(viewsets.ModelViewSet):
    queryset = ChangelogEntry.objects.all()
    serializer_class = ChangelogEntrySerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        user_teams = self.request.user.membership_set.values_list('team', flat=True)
        return ChangelogEntry.objects.filter(project__team__in=user_teams)

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

# AI Helper Views
@api_view(['POST'])
def pr_summary(request):
    """Generate AI summary for Pull Request"""
    try:
        pr_data = request.data
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
        
        # Get the content type
        if content_type_name.lower() == 'pullrequest':
            content_type = ContentType.objects.get_for_model(PullRequest)
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
    # Get user's teams and projects
    user_teams = request.user.membership_set.values_list('team', flat=True)
    projects = Project.objects.filter(team__in=user_teams)
    
    # Recent PRs
    recent_prs = PullRequest.objects.filter(
        project__team__in=user_teams
    ).order_by('-created_at')[:5]
    
    # Stats
    stats = {
        'total_projects': projects.count(),
        'total_prs': PullRequest.objects.filter(project__team__in=user_teams).count(),
        'open_prs': PullRequest.objects.filter(project__team__in=user_teams, status='open').count(),
        'merged_prs': PullRequest.objects.filter(project__team__in=user_teams, status='merged').count(),
    }
    
    # Recent activity (mock data for now)
    recent_activity = [
        {'icon': 'code-branch', 'message': 'New PR created', 'created_at': recent_prs[0].created_at if recent_prs else None},
    ]
    
    return render(request, 'dashboard.html', {
        'projects': projects,
        'recent_prs': recent_prs,
        'stats': stats,
        'recent_activity': recent_activity,
    })

@login_required
def project_create_view(request):
    if request.method == 'POST':
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
    
    # Get user's teams
    user_teams = Team.objects.filter(membership__user=request.user)
    
    return render(request, 'project_create.html', {'teams': user_teams})

@login_required
def project_detail_view(request, project_id):
    project = get_object_or_404(Project, id=project_id)
    
    # Check if user has access to this project
    if not request.user.membership_set.filter(team=project.team).exists():
        messages.error(request, 'You do not have access to this project.')
        return redirect('dashboard')
    
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
    
    return render(request, 'project_detail.html', {
        'project': project,
        'pull_requests': pull_requests,
        'changelog_entries': changelog_entries,
        'team_members': team_members,
        'stats': stats,
    })

@login_required
def pr_create_view(request, project_id):
    project = get_object_or_404(Project, id=project_id)
    
    # Check access
    if not request.user.membership_set.filter(team=project.team).exists():
        messages.error(request, 'You do not have access to this project.')
        return redirect('dashboard')
    
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
def pr_detail_view(request, pr_id):
    pr = get_object_or_404(PullRequest, id=pr_id)
    
    # Check access
    if not request.user.membership_set.filter(team=pr.project.team).exists():
        messages.error(request, 'You do not have access to this pull request.')
        return redirect('dashboard')
    
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
    
    return render(request, 'pr_detail.html', {
        'pr': pr,
        'related_prs': related_prs,
        'comments': comments,
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
def team_invite_view(request, team_id):
    """View for sending team invitations."""
    team = get_object_or_404(Team, id=team_id)
    
    # Check if user has permission to invite members
    if not TeamPermissions.can_invite_members(request.user, team):
        error_msg = TeamPermissions.get_permission_error_message(
            request.user, team, 'invite_members'
        )
        messages.error(request, error_msg)
        return redirect('team_detail', team_id=team.id)
    
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
            messages.error(request, "This invitation has expired.")
            return redirect('dashboard')
        
        # Check if the current user's email matches the invitation
        if invitation.email != request.user.email:
            messages.error(request, "This invitation is not for your email address.")
            return redirect('dashboard')
        
        if request.method == 'POST':
            try:
                InvitationService.decline_invitation(token, request.user)
                messages.info(
                    request, 
                    f"You have declined the invitation to join '{invitation.team.name}'."
                )
                return redirect('dashboard')
                
            except ValueError as e:
                messages.error(request, str(e))
                return redirect('dashboard')
            except Exception as e:
                messages.error(request, "An error occurred while declining the invitation. Please try again.")
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


@login_required
def team_detail_view(request, team_id):
    """View for team dashboard with members, projects, and activities."""
    team = get_object_or_404(Team, id=team_id)
    
    # Check if user has access to this team
    if not TeamPermissions.can_view_team(request.user, team):
        messages.error(request, 'You do not have access to this team.')
        return redirect('dashboard')
    
    # Get team members
    team_members = Membership.objects.filter(team=team).select_related('user')
    
    # Get team projects
    team_projects = team.project_set.all().order_by('-created_at')
    
    # Get recent pull requests from team projects
    recent_prs = PullRequest.objects.filter(
        project__team=team
    ).order_by('-created_at')[:10]
    
    # Get team invitations (only for users who can invite)
    team_invitations = []
    if TeamPermissions.can_invite_members(request.user, team):
        team_invitations = TeamInvitation.objects.filter(
            team=team
        ).order_by('-created_at')[:10]
    
    # Team stats
    stats = {
        'total_members': team_members.count(),
        'total_projects': team_projects.count(),
        'total_prs': recent_prs.count(),
        'pending_invitations': team_invitations.count() if team_invitations else 0,
    }
    
    # User permissions for this team
    user_permissions = {
        'can_invite_members': TeamPermissions.can_invite_members(request.user, team),
        'can_manage_members': TeamPermissions.can_manage_members(request.user, team),
        'can_manage_projects': TeamPermissions.can_manage_projects(request.user, team),
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